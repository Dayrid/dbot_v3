import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import discord
import pandas as pd
from discord import utils
from discord.ext import commands
from sqlalchemy import select, update, func, create_engine, Engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import Session, sessionmaker

import config
from database.models import Base, Guild, GuildChannel, ChannelPurpose, User, GuildBinding

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)

channel_id = 0
message_id = 0


class Listen(commands.Cog):
    async_session: async_sessionmaker
    session: sessionmaker

    async_engine: AsyncEngine
    engine: Engine

    def __init__(self, bot):
        self.async_engine = create_async_engine(
            f'postgresql+asyncpg://{os.environ.get("PGSQL_USER")}:{os.environ.get("PGSQL_PASSWORD")}@{os.environ.get("PGSQL_HOSTNAME")}:5432/{os.environ.get("PGSQL_DB")}')
        # self.async_engine.echo = True
        self.async_session = async_sessionmaker(bind=self.async_engine, expire_on_commit=False)

        self.engine = create_engine(
            f'postgresql://{os.environ.get("PGSQL_USER")}:{os.environ.get("PGSQL_PASSWORD")}@{os.environ.get("PGSQL_HOSTNAME")}:5432/{os.environ.get("PGSQL_DB")}')
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)
        # self.engine.echo = True

        self.bot = bot
        self.song_queue = {}
        self.message = {}

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.async_session.begin() as session:
            guild_member = []
            print('Bot guilds:')
            for guild in self.bot.guilds:
                print(f'{guild.id} {guild.name}')
                new_guild = {
                    "id": str(guild.id),
                    "last_name": str(guild.name)
                }
                new_guild = Guild(**new_guild)
                await session.merge(new_guild)
                for member in guild.members:
                    new_member = {
                        'id': str(member.id),
                        'url': member.name,
                        'last_name': member.global_name
                    }
                    new_member = User(**new_member)
                    await session.merge(new_member)
                    guild_member.append({
                        'guild_id': str(guild.id),
                        'user_id': str(member.id)
                    })

            print('Commit..')
            await session.commit()

        async with self.async_session.begin() as session:
            await session.execute(insert(GuildBinding).values(guild_member).on_conflict_do_nothing())

            await session.commit()
            print('Added members to guilds')

    @commands.command()
    async def start(self, ctx):
        async with self.session.begin() as session:
            channel = await session.scalar(select(GuildChannel.id).where(GuildChannel.guild_id == str(ctx.guild.id)))
            if channel:
                await ctx.send(f'Канал уже создан', delete_after=2.0)
            else:
                ch = await ctx.guild.create_text_channel("dbot-channel", topic="Канал для музыки и различных команд")
                reaction_lst = ["⏯", "⏹", "⏭"]
                emb = discord.Embed(color=0x7b00ff)
                emb.add_field(name='Чат', value='| [Автор](https://steamcommunity.com/id/deydya/) |')
                emb.set_footer(text="Если не знаете, что делать, пишите >help")

                emb.set_image(url='http://ii.yakuji.moe/b/src/1600903499659.png')
                message = await ch.send(embed=emb)
                for reaction in reaction_lst:
                    await message.add_reaction(reaction)
                await ctx.send(f'Канал создан', delete_after=2.0)
                cid = ch.id
            await session.execute(insert(ChannelPurpose).values({'id': 0, 'name': 'command'}).on_conflict_do_nothing())
            await session.execute(insert(GuildChannel).values(
                {'id': str(cid), 'guild_id': str(ctx.guild.id), 'user_id': str(ctx.author.id),
                 'last_name': "dbot-channel", 'channel_purpose_id': 0}))
            await session.commit()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        entry = await channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1).get()
        log = (f"удалил канал {channel.name}", str(entry.user.id), entry.user.name, datetime.now().strftime("%Y-%m-%d "
                                                                                                            "%H:%M:%S"),
               str(channel.guild.id))
        self.sql.execute("INSERT INTO `Logs` (action, user_id, user_name, created_at, guild_id) VALUES (%s, %s, "
                         "%s, %s, %s)", log)
        ids = [str(i.id) for i in channel.guild.text_channels]
        self.sql.execute(f"SELECT cid FROM Servers WHERE guild_id = {channel.guild.id}")
        cid = str(list(self.sql.fetchone())[0])
        if cid is not None:
            if cid not in ids:
                self.sql.execute(f"UPDATE Servers SET cid = NULL WHERE guild_id = {channel.guild.id}")
        self.db.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self,
                                  payload):  # Событие на добавление эмодзи, выбор категорий или стандартной роли сервера
        if payload.guild_id == 452431997139288075:  # Проверка на мой сервер (Melancholy)
            if payload.message_id == config.POST_ID:
                if payload.guild_id is None:
                    return
                channel = self.bot.get_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)
                member = await (await self.bot.fetch_guild(payload.guild_id)).fetch_member(payload.user_id)
                try:
                    emoji = str(payload.emoji)  # эмоджик который выбрал юзер
                    role = utils.get(message.guild.roles, id=config.ROLES[emoji])  # объект выбранной роли (если есть)
                    await member.add_roles(role)  # Добавление роли
                    print('[SUCCESS] User {0.display_name} has been granted with role {1.name}'.format(member,
                                                                                                       role))  # Запись в лог
                except KeyError as e:
                    print('[ERROR] KeyError, no role found for ' + emoji)
                except Exception as e:
                    print(repr(e))

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):  # Событие на удаление эмодзи
        if payload.guild_id == 452431997139288075:  # Проверка на мой сервер (Melancholy)
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            member = await (await self.bot.fetch_guild(payload.guild_id)).fetch_member(payload.user_id)
            try:
                emoji = str(payload.emoji)  # эмоджик который выбрал юзер
                role = utils.get(message.guild.roles, id=config.ROLES[emoji])  # объект выбранной роли (если есть)

                await member.remove_roles(role)
                print('[SUCCESS] Role {1.name} has been removed for user {0.display_name}'.format(member, role))
            except KeyError as e:
                print('[ERROR] KeyError, no role found for ' + emoji)
            except Exception as e:
                print(repr(e))


async def setup(client):
    await client.add_cog(Listen(client))
