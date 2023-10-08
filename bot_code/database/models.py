from sqlalchemy import create_engine, Column, Integer, String, DateTime, Interval, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    id = Column(String, primary_key=True, nullable=False, index=True)
    url = Column(String, nullable=True, default=None)
    last_name = Column(String, nullable=True, default=None)

    guilds = relationship('Guild', secondary='guild_binding', back_populates='users')
    channels = relationship('GuildChannel', back_populates='user')
    posting_tasks = relationship('PostingTask', back_populates='user')


class Guild(Base):
    __tablename__ = 'guild'
    id = Column(String(length=20), primary_key=True, nullable=False)
    last_name = Column(String, nullable=True, default=None)

    users = relationship('User', secondary='guild_binding', back_populates='guilds')
    channels = relationship('GuildChannel', back_populates='guild')

    __table_args__ = (
        UniqueConstraint('id', ),
    )

    posting_tasks = relationship('PostingTask', back_populates='guild')


class GuildBinding(Base):
    __tablename__ = 'guild_binding'
    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)

    user_id = Column(String, ForeignKey('user.id'), nullable=False)
    guild_id = Column(String, ForeignKey('guild.id'), nullable=False)

    user = relationship('User', overlaps="guilds,users")
    guild = relationship('Guild', overlaps="guilds,users")


class GuildChannel(Base):
    __tablename__ = 'guild_channel'
    id = Column(String, primary_key=True, nullable=False, index=True)
    guild_id = Column(String, ForeignKey('guild.id'), nullable=False)
    user_id = Column(String, ForeignKey('user.id'), nullable=False)
    channel_purpose_id = Column(Integer, ForeignKey('channel_purpose.id'), nullable=False)
    last_name = Column(String, nullable=True, default=None)

    channel_purpose = relationship('ChannelPurpose', back_populates='channels')
    posting_tasks = relationship('PostingTask', back_populates='channel')
    user = relationship('User', back_populates='channels')
    guild = relationship('Guild', back_populates='channels')


class ChannelPurpose(Base):
    __tablename__ = 'channel_purpose'
    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)
    name = Column(String, nullable=False)

    channels = relationship('GuildChannel', back_populates='channel_purpose')


class Fandom(Base):
    __tablename__ = 'fandom'
    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    tag = Column(String, nullable=False)

    characters = relationship('Character', back_populates='fandom')


class Character(Base):
    __tablename__ = 'character'
    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    tag = Column(String, nullable=False)
    fandom_id = Column(Integer, ForeignKey('fandom.id'), nullable=False)

    fandom = relationship('Fandom', back_populates='characters')


class PostingTask(Base):
    __tablename__ = 'posting_task'

    id = Column(Integer, primary_key=True)
    channel_id = Column(String, ForeignKey('guild_channel.id'), nullable=False)
    guild_id = Column(String, ForeignKey('guild.id'), nullable=False)
    user_id = Column(String, ForeignKey('user.id'), nullable=False)

    interval_weeks = Column(Integer, default=0)
    interval_days = Column(Integer, default=0)
    interval_hours = Column(Integer, default=0)
    interval_minutes = Column(Integer, default=0)

    channel = relationship('GuildChannel', back_populates='posting_tasks')
    guild = relationship('Guild', back_populates='posting_tasks')
    user = relationship('User', back_populates='posting_tasks')

    def get_interval(self):
        return (self.interval_weeks, self.interval_days, self.interval_hours, self.interval_minutes)
