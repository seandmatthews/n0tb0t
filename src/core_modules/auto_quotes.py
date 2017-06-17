import threading
import time

import gspread
import sqlalchemy

import src.models as models
import src.utils as utils


class AutoQuoteMixin:
    @utils.mod_only
    @utils.retry_gspread_func
    def update_auto_quote_spreadsheet(self):
        """
        Updates the auto_quote spreadsheet with all current auto quotes
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.

        !update_auto_quote_spreadsheet
        """
        db_session = self.Session()
        spreadsheet_name, web_view_link = self.spreadsheets['auto_quotes']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        aqs = sheet.worksheet('Auto Quotes')
        worksheet_width = 4

        auto_quotes = db_session.query(models.AutoQuote).all()

        cells = aqs.range(f'A2:D{len(auto_quotes)+11}')
        for cell in cells:
            cell.value = ''
        aqs.update_cells(cells)

        cells = aqs.range(f'A2:D{len(auto_quotes)+1}')
        for index, auto_quote_obj in enumerate(auto_quotes):
            human_readable_index_cell_index = index * worksheet_width
            auto_quote_cell_index = human_readable_index_cell_index + 1
            period_cell_index = auto_quote_cell_index + 1
            active_cell_index = period_cell_index + 1

            cells[human_readable_index_cell_index].value = index + 1
            cells[auto_quote_cell_index].value = auto_quote_obj.quote
            cells[period_cell_index].value = auto_quote_obj.period
            cells[active_cell_index].value = auto_quote_obj.active
        aqs.update_cells(cells)

        db_session.commit()
        db_session.close()

    @utils.mod_only
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
            AQ_ID = index
            self._auto_quote(index=AQ_ID, quote=quote, period=period)

    @utils.mod_only
    def stop_auto_quotes(self):
        """
        Stops the bot from spitting out quotes by cancelling all auto quote threads.

        !stop_auto_quotes
        """
        for AQ in self.auto_quotes_timers:
            self.auto_quotes_timers[AQ].cancel()
            time.sleep(1)
            self.auto_quotes_timers[AQ].cancel()

    def show_auto_quotes(self, message):
        """
        Links to a google spreadsheet containing all auto quotes

        !show_auto_quotes
        """
        web_view_link = self.spreadsheets['auto_quotes'][1]
        short_url = self.shortener.short(web_view_link)
        utils.add_to_appropriate_chat_queue(self, message, 'View the auto quotes at: {}'.format(short_url))

    @utils.mod_only
    def add_auto_quote(self, message, db_session):
        """
        Makes a new sentence that the bot periodically says.
        The first "word" after !add_auto_quote is the number of seconds
        in the interval for the bot to wait before saying the sentence again.

        !add_auto_quote 600 This is a rudimentary twitch bot.
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            delay = int(msg_list[1])
            quote_str = ' '.join(msg_list[2:])

            displayed_feedback_message = self._add_auto_quote(db_session, delay, quote_str)
            utils.add_to_appropriate_chat_queue(self, message, displayed_feedback_message)
            self.stop_auto_quotes()
            self.start_auto_quotes(db_session)
        else:
            utils.add_to_appropriate_chat_queue(self, message, "Sorry, the command isn't formatted properly.")

    @utils.mod_only
    def edit_auto_quote(self, message, db_session):
        """
        Edits auto quotes. Can also edit the time interval.

        !edit_auto_quote 1 600 This is a somewhat less rudimentary twitch bot.
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 3 and msg_list[1].isdigit() and msg_list[2].isdigit():
            auto_quote_id = int(msg_list[1])
            auto_quote_period = int(msg_list[2])
            auto_quote = ' '.join(msg_list[3:])

            displayed_feedback_message = self._edit_auto_quote(db_session, auto_quote_id, auto_quote, auto_quote_period)
            utils.add_to_appropriate_chat_queue(self, message, displayed_feedback_message)
            db_session.flush()
            self.stop_auto_quotes()
            self.start_auto_quotes(db_session)
        else:
            utils.add_to_appropriate_chat_queue(self, message, "Sorry, the command isn't formatted correctly.")

    @utils.mod_only
    def delete_auto_quote(self, message, db_session):
        """
        Deletes a sentence that the bot periodically says.
        Takes a 1 indexed auto quote index.

        !delete_auto_quote 1
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            auto_quote_id = int(msg_list[1])
            displayed_feedback_message = self._delete_auto_quote(db_session, auto_quote_id)
            utils.add_to_appropriate_chat_queue(self, message, displayed_feedback_message)
            db_session.flush()
            self.stop_auto_quotes()
            self.start_auto_quotes(db_session)
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'Sorry, you must provide the number of the auto quote to delete.')

    @utils.mod_only
    def start_auto_quote(self, message, db_session):
        """
        Starts an auto_quote after it has been deactivated
        Takes the id of an auto_quote

        !deactivate_auto_quote 1
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 2 and msg_list[1].isdigit():
            auto_quote_id = int(msg_list[1] - 1)

            auto_quote_objs = db_session.query(models.AutoQuote).all()
            autoquote = auto_quote_objs[auto_quote_id]

            autoquote.active = True
            db_session.flush()

            self._start_auto_quote(autoquote.id, db_session)
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')

    @utils.mod_only
    def stop_auto_quote(self, message, db_session):
        """
        Stops an auto_quote from being posted to chat, but leaves it intact to be easily activated later
        Takes the id of an auto_quote
        
        !deactivate_auto_quote 1
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 2 and msg_list[1].isdigit():
            auto_quote_id = int(msg_list[1] - 1)

            auto_quote_objs = db_session.query(models.AutoQuote).all()
            autoquote = auto_quote_objs[auto_quote_id]

            autoquote.active = False
            db_session.flush()

            self._stop_auto_quote(auto_quote_id)
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')

    @utils.mod_only
    def auto_quote(self, message, db_session):
        """
        Handles adding, editing, and deleting auto quotes.
        Add takes a time interval and message.
        Edit takes an index, time interval, and message.
        Delete takes an index.

        !auto_quote add 300 This is something the bot will repeat every 300 seconds
        !auto_quote edit 1 350 Auto quote 1 now says this every 350 seconds
        !auto_quote delete 1
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            if msg_list[1].lower() == 'add' and len(msg_list) > 3 and msg_list[2].isdigit():
                auto_quote_period = int(msg_list[2])
                auto_quote_str = ' '.join(msg_list[3:])

                displayed_feedback_message = self._add_auto_quote(db_session, auto_quote_period, auto_quote_str)
                utils.add_to_appropriate_chat_queue(self, message, displayed_feedback_message)
                db_session.flush()
                self._start_auto_quote(db_session.query(models.AutoQuote).count(), db_session)

            elif msg_list[1].lower() == 'edit' and len(msg_list) > 4 and msg_list[2].isdigit() and msg_list[3].isdigit():
                auto_quote_index = int(msg_list[2])
                auto_quote_str = ' '.join(msg_list[4:])
                auto_quote_period = int(msg_list[3])

                self._stop_auto_quote(auto_quote_index)
                displayed_feedback_message = self._edit_auto_quote(db_session, auto_quote_index, auto_quote_str, auto_quote_period)
                utils.add_to_appropriate_chat_queue(self, message, displayed_feedback_message)
                db_session.flush()
                self._start_auto_quote(auto_quote_index, db_session)

            elif msg_list[1].lower() == 'delete' and len(msg_list) > 2 and msg_list[2].isdigit():
                auto_quote_index = int(msg_list[2]) - 1

                self._stop_auto_quote(auto_quote_index)
                displayed_feedback_message = self._delete_auto_quote(db_session, auto_quote_index)
                utils.add_to_appropriate_chat_queue(self, message, displayed_feedback_message)

            else:
                utils.add_to_appropriate_chat_queue(self, message, "Sorry, that command wasn't properly formatted.")
        else:
            utils.add_to_appropriate_chat_queue(self, message, "Sorry, auto_quote must be followed by add, edit, or delete.")

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
        utils.add_to_public_chat_queue(self, quote)

    def _add_auto_quote(self, db_session, delay, quote_str):
        """
        Does the heavy lifting of interacting with the db_session.
        """
        auto_quote_obj = models.AutoQuote(quote=quote_str, period=delay, active=True)
        db_session.add(auto_quote_obj)
        response_str = f'Auto quote added as auto quote #{db_session.query(models.AutoQuote).count()}.'
        utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
        return response_str

    def _edit_auto_quote(self, db_session, auto_quote_index, auto_quote_str, auto_quote_period):
        # We grab all the auto quotes because we can't just use the auto quote ID
        # Auto quotes may get deleted, and so we need to set all auto quotes after that one back by one
        auto_quote_objs = db_session.query(models.AutoQuote).all()
        if auto_quote_index <= len(auto_quote_objs):
            auto_quote_obj = auto_quote_objs[auto_quote_index - 1]
            auto_quote_obj.quote = auto_quote_str
            auto_quote_obj.period = auto_quote_period
            response_str = 'Auto quote has been edited.'
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
        else:
            response_str = 'That auto quote does not exist'
        return response_str

    def _delete_auto_quote(self, db_session, auto_quote_index):
        # We grab all the auto quotes because we can't just use the auto quote ID
        # Auto quotes may get deleted, and so we need to set all auto quotes after that one back by one
        auto_quote_objs = db_session.query(models.AutoQuote).all()
        if auto_quote_index <= len(auto_quote_objs):
            auto_quote_obj = auto_quote_objs[auto_quote_index - 1]
            db_session.delete(auto_quote_obj)
            response_str = 'Auto quote deleted'
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
        else:
            response_str = 'That auto quote does not exist'
        return response_str

    def _start_auto_quote(self, auto_quote_id, db_session):
        """
        Starts the bot spitting out a specific auto quote again, depending from its index.
        """
        auto_quote = db_session.query(models.AutoQuote).filter(models.AutoQuote.active == True).filter(
            models.AutoQuote.id == auto_quote_id).one()
        quote = auto_quote.quote
        period = auto_quote.period
        self._auto_quote(index=auto_quote_id, quote=quote, period=period)

    def _stop_auto_quote(self, auto_quote_id):
        """
        Stops the bot from spitting out a specific quote by cancelling the quote thread, depending from its index.
        """
        fullid = 'AQ{}'.format(auto_quote_id)
        self.auto_quotes_timers[fullid].cancel()
        time.sleep(1)
        self.auto_quotes_timers[fullid].cancel()

