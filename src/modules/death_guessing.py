import gspread
import sqlalchemy

import src.models as models
import src.utils as utils


class DeathGuessingDisabled:
    @utils.mod_only
    def enable_guessing(self, db_session):
        """
        Allows users to guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !enable_guessing
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled').one()
        mv_obj.mv_value = "True"
        self._add_to_chat_queue("Guessing is now enabled.")

    @utils.mod_only
    def disable_guessing(self, db_session):
        """
        Stops users from guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !disable_guessing
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled').one()
        mv_obj.mv_value = "False"
        self._add_to_chat_queue("Guessing is now disabled.")

    def guess(self, message, db_session):
        """
        Updates the database with a user's guess
        or informs the user that their guess
        doesn't fit the acceptable parameters
        or that guessing is disabled for everyone.

        !guess 50
        """
        user = self.service.get_message_display_name(message)
        if db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled').one().mv_value == 'True':
            msg_list = self.service.get_message_content(message).split(' ')
            if len(msg_list) > 1:
                guess = msg_list[1]
                if guess.isdigit() and int(guess) >= 0:
                    self._set_current_guess(user, guess, db_session)
                    self._add_to_whisper_queue(user, "{} your guess has been recorded.".format(user))
                else:
                    self._add_to_whisper_queue(user, "Sorry {}, that's not a non-negative integer.".format(user))
            else:
                self._add_to_whisper_queue(user,
                                           "Sorry {}, !guess must be followed by a non-negative integer.".format(user))
        else:
            self._add_to_whisper_queue(user, "Sorry {}, guessing is disabled.".format(user))

    @utils.mod_only
    def enable_guesstotal(self, db_session):
        """
        Enables guessing for the total number of deaths for the run.
        Modifies the value associated with the guess-total-enabled key
        in the miscellaneous values dictionary and writes it to the json file.

        !enable_guesstotal
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guess-total-enabled').one()
        mv_obj.mv_value = "True"
        self._add_to_chat_queue("Guessing for the total amount of deaths is now enabled.")

    @utils.mod_only
    def disable_guesstotal(self, db_session):
        """
        Disables guessing for the total number of deaths for the run.

        !disable_guesstotal
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guess-total-enabled').one()
        mv_obj.mv_value = "False"
        self._add_to_chat_queue("Guessing for the total amount of deaths is now disabled.")

    def guesstotal(self, message, db_session):
        """
        Updates the database with a user's guess
        for the total number of deaths in the run
        or informs the user that their guess
        doesn't fit the acceptable parameters
        or that guessing is disabled for everyone.

        !guesstotal 50
        """
        user = self.service.get_message_display_name(message)
        if db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guess-total-enabled').one().mv_value == "True":
            msg_list = self.service.get_message_content(message).split(' ')
            if len(msg_list) > 1:
                guess = msg_list[1]
                if guess.isdigit() and int(guess) >= 0:
                    self._set_total_guess(user, guess, db_session)
                    self._add_to_whisper_queue(user, "{} your guess has been recorded.".format(user))
                else:
                    self._add_to_whisper_queue(user, "Sorry {}, that's not a non-negative integer.".format(user))
            else:
                self._add_to_whisper_queue(user,
                                           "Sorry {}, you need to include a number after your guess.".format(user))
        else:
            self._add_to_whisper_queue(user,
                                       "Sorry {}, guessing for the total number of deaths is disabled.".format(user))

    @utils.mod_only
    def clear_guesses(self, db_session):
        """
        Clear all guesses so that users
        can guess again for the next segment
        of the run.

        !clear_guesses
        """
        db_session.execute(sqlalchemy.update(models.User.__table__, values={models.User.__table__.c.current_guess: None}))
        self._add_to_chat_queue("Guesses have been cleared.")

    @utils.mod_only
    def clear_total_guesses(self, db_session):
        """
        Clear all total guesses so that users
        can guess again for the next game
        where they guess about the total number of deaths

        !clear_total_guesses
        """
        db_session.execute(sqlalchemy.update(models.User.__table__, values={models.User.__table__.c.total_guess: None}))
        self._add_to_chat_queue("Guesses for the total number of deaths have been cleared.")

    @utils.retry_gspread_func
    def _update_player_guesses_spreadsheet(self):
        """
        Updates the player guesses spreadsheet from the database.
        """
        db_session = self.Session()
        spreadsheet_name, web_view_link = self.spreadsheets['player_guesses']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        ws = sheet.worksheet('Player Guesses')
        all_users = db_session.query(models.User).all()
        users = [user for user in all_users if user.current_guess is not None or user.total_guess is not None]
        for i in range(2, len(users) + 10):
            ws.update_cell(i, 1, '')
            ws.update_cell(i, 2, '')
            ws.update_cell(i, 3, '')
        for index, user in enumerate(users):
            row_num = index + 2
            ws.update_cell(row_num, 1, user.name)
            ws.update_cell(row_num, 2, user.current_guess)
            ws.update_cell(row_num, 3, user.total_guess)
        return web_view_link

    @utils.mod_only
    def show_guesses(self, db_session):
        """
        Clears all guesses out of the google
        spreadsheet, then repopulate it from
        the database.

        !show_guesses
        """
        self._add_to_chat_queue(
            "Formatting the google sheet with the latest information about all the guesses may take a bit." +
            " I'll let you know when it's done.")
        web_view_link = self.spreadsheets['player_guesses'][1]
        short_url = self.shortener.short(web_view_link)
        self._update_player_guesses_spreadsheet()
        self._add_to_chat_queue(
            "Hello again friends. I've updated a google spread sheet with the latest guess information. " +
            "Here's a link. {}".format(short_url))

    @utils.mod_only
    def set_deaths(self, message, db_session):
        """
        Sets the number of deaths for the current
        leg of the run. Needs a non-negative integer.

        !set_deaths 5
        """
        user = self.service.get_message_display_name(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            deaths_num = msg_list[1]
            if deaths_num.isdigit() and int(deaths_num) >= 0:
                self._set_deaths(deaths_num, db_session)
                self._add_to_whisper_queue(user, 'Current deaths: {}'.format(deaths_num))
            else:
                self._add_to_whisper_queue(user,
                                           'Sorry {}, !set_deaths should be followed by a non-negative integer'.format(
                                               user))
        else:
            self._add_to_whisper_queue(user,
                                       'Sorry {}, !set_deaths should be followed by a non-negative integer'.format(
                                           user))

    @utils.mod_only
    def set_total_deaths(self, message, db_session):
        """
        Sets the total number of deaths for the run.
        Needs a non-negative integer.

        !set_total_deaths 5
        """
        user = self.service.get_message_display_name(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            total_deaths_num = msg_list[1]
            if total_deaths_num.isdigit() and int(total_deaths_num) >= 0:
                self._set_total_deaths(total_deaths_num, db_session)
                self._add_to_whisper_queue(user, 'Total deaths: {}'.format(total_deaths_num))
            else:
                self._add_to_whisper_queue(user,
                                           'Sorry {}, !set_total_deaths should be followed by a non-negative integer'.format(
                                               user))
        else:
            self._add_to_whisper_queue(user,
                                       'Sorry {}, !set_total_deaths should be followed by a non-negative integer'.format(
                                           user))

    @utils.mod_only
    def add_death(self, message, db_session):
        """
        Adds one to both the current sequence
        and total death counters.

        !add_death
        """
        user = self.service.get_message_display_name(message)
        deaths = int(self._get_current_deaths(db_session))
        total_deaths = int(self._get_total_deaths(db_session))
        deaths += 1
        total_deaths += 1
        self._set_deaths(str(deaths), db_session)
        self._set_total_deaths(str(total_deaths), db_session)
        whisper_msg = 'Current Deaths: {}, Total Deaths: {}'.format(deaths, total_deaths)
        self._add_to_whisper_queue(user, whisper_msg)

    @utils.mod_only
    def clear_deaths(self, db_session):
        """
        Sets the number of deaths for the current
        stage of the run to 0. Used after progressing
        to the next stage of the run.

        !clear_deaths
        """
        self._set_deaths('0', db_session)
        self.show_deaths()

    def show_deaths(self, db_session):
        """
        Sends the current and total death
        counters to the chat.

        !show_deaths
        """
        deaths = self._get_current_deaths(db_session)
        total_deaths = self._get_total_deaths(db_session)
        self._add_to_chat_queue("Current Boss Deaths: {}, Total Deaths: {}".format(deaths, total_deaths))

    def show_winner(self, db_session):
        """
        Sends the name of the currently winning
        player to the chat. Should be used after
        stage completion to display who won.

        !show_winner
        """
        winners_list = []
        deaths = self._get_current_deaths(db_session)
        last_winning_guess = -1
        users = db_session.query(models.User).filter(models.User.current_guess.isnot(None)).all()
        for user in users:
            # If your guess was over the number of deaths you lose due to the price is right rules.
            if int(user.current_guess) <= int(deaths):
                if user.current_guess > last_winning_guess:
                    winners_list = [user.name]
                    last_winning_guess = user.current_guess
                elif user.current_guess == last_winning_guess:
                    winners_list.append(user.name)
        if len(winners_list) == 1:
            winners_str = "The winner is {}.".format(winners_list[0])
        elif len(winners_list) > 1:
            winners_str = 'The winners are '
            for winner in winners_list[:-1]:
                winners_str += "{}, ".format(winner)
            winners_str = '{} and {}!'.format(winners_str[:-2], winners_list[-1])
        else:
            me = self.info['channel']
            winners_str = 'You all guessed too high. You should have had more faith in {}. {} wins!'.format(me, me)
        self._add_to_chat_queue(winners_str)

    def _set_current_guess(self, user, guess, db_session):
        """
        Takes a user and a guess.
        Adds the user (if they don't already exist)
        and their guess to the users table.
        """
        db_user = db_session.query(models.User).filter(models.User.name == user).first()
        if not db_user:
            db_user = models.User(name=user)
            db_session.add(db_user)
        db_user.current_guess = guess

    def _set_total_guess(self, user, guess, db_session):
        """
        Takes a user and a guess
        for the total number of deaths.
        Adds the user and their guess
        to the users table.
        """
        db_user = db_session.query(models.User).filter(models.User.name == user).first()
        if not db_user:
            db_user = models.User(name=user)
            db_session.add(db_user)
        db_user.total_guess = guess

    def _get_current_deaths(self, db_session):
        """
        Returns the current number of deaths
        for the current leg of the run.
        """
        deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'current-deaths').one()
        return deaths_obj.mv_value

    def _get_total_deaths(self, db_session):
        """
        Returns the total deaths that
        have occurred in the run so far.
        """
        total_deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'total-deaths').one()
        return total_deaths_obj.mv_value

    def _set_deaths(self, deaths_num, db_session):
        """
        Takes a string for the number of deaths.
        Updates the miscellaneous values table.
        """
        deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'current-deaths').one()
        deaths_obj.mv_value = deaths_num

    def _set_total_deaths(self, total_deaths_num, db_session):
        """
        Takes a string for the total number of deaths.
        Updates the miscellaneous values table.
        """
        total_deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'total-deaths').one()
        total_deaths_obj.mv_value = total_deaths_num
