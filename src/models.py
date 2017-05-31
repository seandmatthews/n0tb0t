import datetime

import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'USER'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    is_regular = sqlalchemy.Column(sqlalchemy.Boolean)
    current_guess = sqlalchemy.Column(sqlalchemy.Integer)
    total_guess = sqlalchemy.Column(sqlalchemy.Integer)
    entered_in_contest = sqlalchemy.Column(sqlalchemy.Boolean)
    times_played = sqlalchemy.Column(sqlalchemy.Integer)
    current_points = sqlalchemy.Column(sqlalchemy.Integer)
    total_points = sqlalchemy.Column(sqlalchemy.Integer)
    whitelisted = sqlalchemy.Column(sqlalchemy.Boolean)

    def __init__(self, **kwargs):
        self.entered_in_contest = False
        self.times_played = 0
        self.points = 0
        self.total_points = 0
        self.whitelisted = False
        self.is_regular = False
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])


class TwitchUser(Base):
    __tablename__ = 'TWITCH-USER'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(User.id))
    twitch_id = sqlalchemy.Column(sqlalchemy.String)
    display_name = sqlalchemy.Column(sqlalchemy.String)


class Quote(Base):
    __tablename__ = 'QUOTE'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_friendly_id = sqlalchemy.Column(sqlalchemy.Integer, unique=True)
    user = sqlalchemy.column(sqlalchemy.Integer, sqlalchemy.ForeignKey(User.id))
    quote = sqlalchemy.Column(sqlalchemy.String)
    added_on = sqlalchemy.Column(sqlalchemy.DateTime)

    def __init__(self, **kwargs):
        self.date_added = datetime.datetime.now()
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])


class Timer(Base):
    __tablename__ = 'TIMER'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_friendly_id = sqlalchemy.Column(sqlalchemy.Integer, unique=True)
    command = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(Command.id))
    period = sqlalchemy.Column(sqlalchemy.Integer)
    active = sqlalchemy.Column(sqlalchemy.Boolean)


class Command(Base):
    __tablename__ = 'COMMAND'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean)
    public_allowed = sqlalchemy.Column(sqlalchemy.Boolean)
    private_allowed = sqlalchemy.Column(sqlalchemy.Boolean)
    response = sqlalchemy.Column(sqlalchemy.String)
    cool_down = sqlalchemy.Column(sqlalchemy.Integer)
    last_used = sqlalchemy.Column(sqlalchemy.DateTime)
    point_cost = sqlalchemy.Column(sqlalchemy.Integer)
    aliases = relationship('Alias', backref='COMMAND')
    permissions_set = sqlalchemy.Column(sqlalchemy.Boolean)
    everyone_allowed = sqlalchemy.Column(sqlalchemy.Boolean)
    regulars_allowed = sqlalchemy.Column(sqlalchemy.Boolean)
    moderators_allowed = sqlalchemy.Column(sqlalchemy.Boolean)
    caster_allowed = sqlalchemy.Column(sqlalchemy.Boolean)
    individual_user_permissions = relationship('IndividualUserPermission', backref='COMMAND')


class Alias(Base):
    __tablename__ = 'ALIAS'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    call = sqlalchemy.Column(sqlalchemy.String, unique=True)
    command = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(Command.id))


class IndividualUserPermission(Base):
    __tablename__ = 'INDIVIDUAL-USER-PERMISSION'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    command_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(Command.id))
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(User.id))


class CommandGroup(Base):
    __tablename__ = 'COMMAND-GROUP'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_friendly_id = sqlalchemy.Column(sqlalchemy.Integer, unique=True)


class CommandGroup_Command(Base):
    __tablename__ = 'COMMAND-GROUP-COMMAND'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    command_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(Command.id))
    command_group_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(CommandGroup.id))
