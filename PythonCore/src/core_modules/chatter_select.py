import random

import sqlalchemy

import PythonCore.src.models as models
import PythonCore.src.utils as utils


class ChatterSelectionMixin:
    def giveaway(self, message, db_session):
        """
        Adds the user to the contest entrants
        or informs them that they're already entered if they've already
        entered since the last time the entrants were cleared.

        !enter_contest
        """

        username = self.service.get_message_display_name(message)
        user = db_session.query(models.User).filter(models.User.name == username).one_or_none()
        if user:
            if user.entered_in_contest:
                pass
            else:
                user.entered_in_contest = True
        else:
            user = models.User(entered_in_contest=True, name=username)
            db_session.add(user)

    @utils.mod_only
    def choose_giveaway(self, message, db_session):
        """
        Selects a contest entrant at random.
        Sends their name to the chat.

        !show_contest_winner
        """
        users_contest_list = db_session.query(models.User).filter(models.User.entered_in_contest == True).all()
        if len(users_contest_list) > 0:
            winner = random.choice(users_contest_list)
            utils.add_to_public_chat_queue(self, f'The winner is {winner.name}!')
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'There are currently no entrants for the giveaway.')

    @utils.mod_only
    def reset_giveaway(self, message, db_session):
        """
        Resets the giveaway so that no one is entered

        !clear_contest_entrants
        """
        db_session.execute(sqlalchemy.update(models.User.__table__, values={
            models.User.__table__.c.entered_in_contest: False}))
        utils.add_to_appropriate_chat_queue(self, message, 'Giveaway entrants cleared.')
