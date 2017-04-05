import random

import sqlalchemy

import src.models as models
import src.modules.Utils as Utils


class ChatterSelectionMixin:
    def enter_contest(self, message, db_session):
        """
        Adds the user to the contest entrants
        or informs them that they're already entered if they've already
        entered since the last time the entrants were cleared.

        !enter_contest
        """

        username = self.service.get_username(message)
        user = db_session.query(models.User).filter(models.User.name == username).one_or_none()
        if user:
            print('user found')
            if user.entered_in_contest:
                # TODO: Fix Whisper Stuff
                # self._add_to_whisper_queue(user.name, 'You\'re already entered into the contest, you can\'t enter again.')
                pass
            else:
                user.entered_in_contest = True
                # self._add_to_whisper_queue(user.name, 'You\'re entered into the contest!')
        else:
            user = models.User(entered_in_contest=True, name=username)
            db_session.add(user)
            # self._add_to_whisper_queue(username, 'You\'re entered into the contest!')

    @Utils._mod_only
    def show_contest_winner(self, db_session):
        """
        Selects a contest entrant at random.
        Sends their name to the chat.

        !show_contest_winner
        """
        users_contest_list = db_session.query(models.User).filter(models.User.entered_in_contest.isnot(False)).all()
        if len(users_contest_list) > 0:
            winner = random.choice(users_contest_list)
            self._add_to_chat_queue('The winner is {}!'.format(winner.name))
        else:
            self._add_to_chat_queue('There are currently no entrants for the contest.')

    @Utils._mod_only
    def clear_contest_entrants(self, db_session):
        """
        Sets the entrants list to be an empty list and then writes
        that to the entrants file.

        !clear_contest_entrants
        """
        db_session.execute(sqlalchemy.update(models.User.__table__, values={models.User.__table__.c.entered_in_contest: False}))
        self._add_to_chat_queue("Contest entrants cleared.")