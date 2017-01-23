import random
import sqlalchemy
import db
from .Utils import _mod_only


def enter_raffle(self, message, db_session):
    """
    Adds the user to the raffle entrants
    or informs them that they're already entered if they've already
    entered since the last time the entrants were cleared.

    !enter_raffle
    """
    username = self.ts.get_user(message)
    user = db_session.query(db.User).filter(db.User.name == username).one_or_none()
    if user:
        print('user found')
        if user.entered_in_raffle:
            self._add_to_whisper_queue(user.name, 'You\'re already entered into the raffle, you can\'t enter again.')
        else:
            user.entered_in_raffle = True
            self._add_to_whisper_queue(user.name, 'You\'re entered into the raffle!')
    else:
        print('user created')
        user = db.User(entered_in_raffle=True, name=username)
        db_session.add(user)
        self._add_to_whisper_queue(username, 'You\'re entered into the raffle!')

@_mod_only
def show_raffle_winner(self, db_session):
    """
    Selects a raffle entrant at random.
    Sends their name to the chat.

    !show_raffle_winner
    """
    users_raffle_list = db_session.query(db.User).filter(db.User.entered_in_raffle.isnot(False)).all()
    if len(users_raffle_list) > 0:
        winner = random.choice(users_raffle_list)
        self._add_to_chat_queue('The winner is {}!'.format(winner.name))
    else:
        self._add_to_chat_queue('There are currently no entrants for the raffle.')

@_mod_only
def clear_raffle_entrants(self, db_session):
    """
    Sets every user in the database to not be entered into the raffle.

    !clear_raffle_entrants
    """
    db_session.execute(sqlalchemy.update(db.User.__table__, values={db.User.__table__.c.entered_in_raffle: False}))
    self._add_to_chat_queue("Raffle entrants cleared.")
