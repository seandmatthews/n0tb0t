import threading
import time

import gspread
import sqlalchemy

import src.models as models
import src.modules.Utils as Utils


class AutoQuoteMixin:

    def _auto_quote(self, index, quote, period):
        """
        Takes an index, quote and time in seconds.
        Starts a thread that waits the specified time, says the quote
        and starts another thread with the same arguments, ensuring
        that the quotes continue to be said forever or until they're stopped by the user.
        """
        key = 'AQ{}'.format(index)
        self.auto_quotes_timers[key] = threading.Timer(period, self._auto_quote,
                                                       kwargs={'index': index, 'quote': quote, 'period': period})
        self.auto_quotes_timers[key].start()
        self._add_to_chat_queue(quote)

    @Utils._mod_only
    @Utils._retry_gspread_func
    def update_auto_quote_spreadsheet(self, db_session):
        """
        Updates the auto_quote spreadsheet with all current auto quotes
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.

        !update_auto_quote_spreadsheet
        """
        spreadsheet_name, web_view_link = self.spreadsheets['auto_quotes']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        aqs = sheet.worksheet('Auto Quotes')

        auto_quotes = db_session.query(models.AutoQuote).all()

        for index in range(len(auto_quotes)+10):
            aqs.update_cell(index+2, 1, '')
            aqs.update_cell(index+2, 2, '')
            aqs.update_cell(index+2, 3, '')
            aqs.update_cell(index+2, 4, '')

        for index, aq in enumerate(auto_quotes):
            aqs.update_cell(index+2, 1, index+1)
            aqs.update_cell(index+2, 2, aq.quote)
            aqs.update_cell(index+2, 3, aq.period)
            aqs.update_cell(index+2, 4, aq.active)

    @Utils._mod_only
    def start_auto_quotes(self, db_session):
        """
        Starts the bot spitting out auto quotes by calling the
        _auto_quote function on all quotes in the AUTOQUOTES table

        !start_auto_quotes
        """
        auto_quotes = db_session.query(models.AutoQuote).filter(models.AutoQuote.active == True).all()
        self.auto_quotes_timers = {}
        for index, auto_quote in enumerate(auto_quotes):
            quote = auto_quote.quote
            period = auto_quote.period
            self._auto_quote(index=index, quote=quote, period=period)

    @Utils._mod_only
    def _start_auto_quote(self, auto_quote_id, db_session):
        """
        Starts the bot spitting out a specific auto quote again, depending from its index.
        """
        auto_quote = db_session.query(models.AutoQuote).filter(models.AutoQuote.active == True).filter(
            models.AutoQuote.id == auto_quote_id).one()
        index = 'AQ{}'.format(auto_quote_id)
        quote = auto_quote.quote
        period = auto_quote.period
        self._auto_quote(index=index, quote=quote, period=period)

    @Utils._mod_only
    def stop_auto_quotes(self):
        """
        Stops the bot from spitting out quotes by cancelling all auto quote threads.

        !stop_auto_quotes
        """
        for AQ in self.auto_quotes_timers:
            self.auto_quotes_timers[AQ].cancel()
            time.sleep(1)
            self.auto_quotes_timers[AQ].cancel()

    @Utils._mod_only
    def _stop_auto_quote(self, auto_quote_id):
        """
        Stops the bot from spitting out a specific quote by cancelling the quote thread, depending from its index.
        """
        fullid = 'AQ{}'.format(auto_quote_id)
        self.auto_quotes_timers[fullid].cancel()
        time.sleep(1)
        self.auto_quotes_timers[fullid].cancel()

    def show_auto_quotes(self, message):
        """
        Links to a google spreadsheet containing all auto quotes

        !show_auto_quotes
        """
        user = self.service.get_username(message)
        web_view_link = self.spreadsheets['auto_quotes'][1]
        short_url = self.shortener.short(web_view_link)
        # TODO: Fix Whisper Stuff
        self._add_to_chat_queue('View the auto quotes at: {}'.format(short_url))
        # self._add_to_whisper_queue(user, 'View the auto quotes at: {}'.format(short_url))

    @Utils._mod_only
    def add_auto_quote(self, message, db_session):
        """
        Makes a new sentence that the bot periodically says.
        The first "word" after !add_auto_quote is the number of seconds
        in the interval for the bot to wait before saying the sentence again.

        !add_auto_quote 600 This is a rudimentary twitch bot.
        """
        user = self.service.get_username(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            delay = int(msg_list[1])
            quote = ' '.join(msg_list[2:])
            autoquote = models.AutoQuote(quote=quote, period=delay, active=True)
            db_session.add(autoquote)
            db_session.flush()
            last_autoquote_id = autoquote.id
            my_thread = threading.Thread(target=self.update_auto_quote_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()

            # # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, 'Auto quote added.')
            displayed_feedback_message = "Auto quote added (ID #{}).".format(last_autoquote_id)
            self._add_to_chat_queue(displayed_feedback_message)
            self.stop_auto_quotes()
            self.start_auto_quotes(db_session)
        else:
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, 'Sorry, the command isn\'t formatted properly.')
            self._add_to_chat_queue('Sorry, the command isn\'t formatted properly.')

    @Utils._mod_only
    def delete_auto_quote(self, message, db_session):
        """
        Deletes a sentence that the bot periodically says.
        Takes a 1 indexed auto quote index.

        !delete_auto_quote 1
        """
        user = self.service.get_username(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            auto_quote_id = int(msg_list[1])
            auto_quote = db_session.query(models.AutoQuote).filter(models.AutoQuote.id == auto_quote_id).one()
            try:
                index = int(msg_list[1]) - 1
                db_session.delete(auto_quote)
                db_session.flush()
                my_thread = threading.Thread(target=self.update_auto_quote_spreadsheet,
                                             kwargs={'db_session': db_session})
                my_thread.daemon = True
                my_thread.start()
                # TODO: Fix Whisper Stuff
                # self._add_to_whisper_queue(user, 'Auto quote deleted.')
                self._add_to_chat_queue('Auto quote deleted')
                self.stop_auto_quotes()
                self.start_auto_quotes(db_session)
            except sqlalchemy.orm.exc.NoResultFound:
                self._add_to_chat_queue("Sorry, there aren't that many auto quotes.")
                # self._add_to_whisper_queue(user, 'Sorry, there aren\'t that many auto quotes.')
        else:
            pass
            # self._add_to_whisper_queue(user, 'Sorry, your command isn\'t formatted properly.')

    @Utils._mod_only
    def activate_auto_quote(self, message, db_session):
        """
        Starts an auto_quote after it has been deactivated
        Takes the id of an auto_quote

        !deactivate_auto_quote 1
        """
        user = self.service.get_username(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 2 and msg_list[1].isdigit():
            auto_quote_id = int(msg_list[1])

            autoquote = db_session.query(models.AutoQuote).filter(models.AutoQuote.id == auto_quote_id).one()

            autoquote.active = True
            db_session.flush()

            self._start_auto_quote(autoquote.id, db_session)
            my_thread = threading.Thread(target=self.update_auto_quote_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()

    @Utils._mod_only
    def deactivate_auto_quote(self, message, db_session):
        """
        Stops an auto_quote from being posted to chat, but leaves it intact to be easily activated later
        Takes the id of an auto_quote
        
        !deactivate_auto_quote 1
        """
        user = self.service.get_username(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 2 and msg_list[1].isdigit():
            auto_auote_id = int(msg_list[1])

            autoquote = db_session.query(models.AutoQuote).filter(models.AutoQuote.id == auto_auote_id).one()

            autoquote.active = False
            db_session.flush()

            self._stop_auto_quote(auto_auote_id)
            my_thread = threading.Thread(target=self.update_auto_quote_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()
