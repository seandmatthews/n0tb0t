import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'USERS'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    current_guess = sqlalchemy.Column(sqlalchemy.Integer)
    total_guess = sqlalchemy.Column(sqlalchemy.Integer)
    entered_in_contest = sqlalchemy.Column(sqlalchemy.Boolean)
    times_played = sqlalchemy.Column(sqlalchemy.Integer)
    total_points = sqlalchemy.Column(sqlalchemy.Integer)
    current_points = sqlalchemy.Column(sqlalchemy.Integer)
    whitelisted = sqlalchemy.Column(sqlalchemy.Boolean)

    def __init__(self, **kwargs):
        self.entered_in_contest = False
        self.times_played = 0
        self.total_points = 0
        self.current_points = 0
        self.whitelisted = False
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])


class TwitchUser(Base):
    __tablename__ = 'TWITCHUSERS'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(User.id))
    twitch_id = sqlalchemy.Column(sqlalchemy.String)
    display_name = sqlalchemy.Column(sqlalchemy.String)


class Quote(Base):
    __tablename__ = 'QUOTES'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(User.id))
    quote = sqlalchemy.Column(sqlalchemy.String)


class AutoQuote(Base):
    __tablename__ = 'AUTO-QUOTES'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    quote = sqlalchemy.Column(sqlalchemy.String)
    period = sqlalchemy.Column(sqlalchemy.Integer)
    active = sqlalchemy.Column(sqlalchemy.Boolean)


class Command(Base):
    __tablename__ = 'COMMANDS'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    type = sqlalchemy.Column(sqlalchemy.String)
    response = sqlalchemy.Column(sqlalchemy.String)
    cooldown = sqlalchemy.Column(sqlalchemy.Integer)
    last_used = sqlalchemy.Column(sqlalchemy.DateTime)
    permissions = relationship('Permission', backref='COMMANDS')
    aliases = relationship('CommandAlias', backref='COMMANDS')


class CommandAlias(Base):
    __tablename__ = 'COMMAND-ALIASES'
    command_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(Command.id))
    call = sqlalchemy.Column(sqlalchemy.String)


class Permission(Base):
    __tablename__ = 'PERMISSIONS'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    command_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(Command.id))
    user_entity = sqlalchemy.Column(sqlalchemy.String)
