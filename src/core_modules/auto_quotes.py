import threading
import time

import gspread
import sqlalchemy

import src.models as models
import src.utils as utils


class AutoQuoteMixin:
    def __init__(self):
        self.starting_spreadsheets_list.append('auto_quotes')
        self.auto_quotes_timers = {}

    @utils.retry_gspread_func
    def _initialize_auto_quotes_spreadsheet(self, spreadsheet_name):
        """
        Populate the auto_quotes google sheet with its initial data.
        """
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            aqs = sheet.worksheet('Auto Quotes')
        except gspread.exceptions.WorksheetNotFound:
            aqs = sheet.add_worksheet('Auto Quotes', 1000, 4)
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        aqs.update_acell('A1', 'Auto Quote Index')
        aqs.update_acell('B1', 'Quote')
        aqs.update_acell('C1', 'Period\n(In seconds)')
        aqs.update_acell('D1', 'Active')

        self.update_auto_quote_spreadsheet()

    @utils.mod_only
    @utils.retry_gspread_func
    def update_auto_quote_spreadsheet(self):
        """
        Updates the auto_quote spreadsheet with all current auto quotes
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.

        !update_auto_quote_spreadsheet
        """
        # If this is called in a separate thread, it's conceivable that if the main thread doesn't flush changes to the
        # DB first, that this might read in old data from the DB. If this function is displaying incorrect data that
        # don't reflect the last change made to the auto_quotes table, please ensure all DB Changes are flushed first
        # http://docs.sqlalchemy.org/en/latest/orm/session_api.html#sqlalchemy.orm.session.Session.flush
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

    def show_auto_quotes(self, message):
        """
        Links to a google spreadsheet containing all auto quotes

        !show_auto_quotes
        """
        web_view_link = self.spreadsheets['auto_quotes'][1]
        short_url = self.shortener.short(web_view_link)
        utils.add_to_appropriate_chat_queue(self, message, 'View the auto quotes at: {}'.format(short_url))

    @utils.mod_only
    def start_auto_quote(self, message, db_session):
        """
        Starts an auto_quote after it has been deactivated
        Takes the id of an auto quote

        !star_auto_quote 1
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 2 and msg_list[1].isdigit():
            human_readable_auto_quote_index = int(msg_list[1])
            response = self._start_auto_quote(db_session, human_readable_auto_quote_index)
            if response is not None:
                utils.add_to_appropriate_chat_queue(self, message, response)
        else:
            utils.add_to_appropriate_chat_queue(self, message, "Sorry, the command isn't formatted properly.")

    @utils.mod_only
    def stop_auto_quote(self, message, db_session):
        """
        Stops an auto_quote from being posted to chat, but leaves it intact to be easily activated later
        Takes the id of an auto quote

        !stop_auto_quote 1
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 2 and msg_list[1].isdigit():
            human_readable_auto_quote_index = int(msg_list[1])
            response = self._stop_auto_quote(db_session, human_readable_auto_quote_index)
            if response is not None:
                utils.add_to_appropriate_chat_queue(self, message, response)
        else:
            utils.add_to_appropriate_chat_queue(self, message, "Sorry, the command isn't formatted properly.")

    @utils.mod_only
    def start_all_auto_quotes(self, db_session):
        """
        Starts all currently inactive auto quotes

        !start_all_auto_quotes
        """
        inactive_auto_quotes = db_session.query(models.AutoQuote).filter(models.AutoQuote.active == False).all()
        for iaq in inactive_auto_quotes:
            iaq.active = True
            self._create_timer_for_auto_quote_object(iaq)
        utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')

    @utils.mod_only
    def stop_all_auto_quotes(self, message, db_session):
        """
        Stops all currently active auto quotes

        !stop_all_auto_quotes
        """
        active_auto_quotes = db_session.query(models.AutoQuote).filter(models.AutoQuote.active == True).all()
        for aaq in active_auto_quotes:
            aaq.active = False
            self._delete_timer_for_auto_quote_object(aaq)
        utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
        utils.add_to_appropriate_chat_queue(self, message, 'All auto quotes have been stopped')

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
        else:
            utils.add_to_appropriate_chat_queue(self, message, "Sorry, the command isn't formatted correctly.")

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
        !auto_quote start 1
        !auto_quote stop 1
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            if msg_list[1].lower() == 'add' and len(msg_list) > 3 and msg_list[2].isdigit():
                auto_quote_period = int(msg_list[2])
                auto_quote_str = ' '.join(msg_list[3:])
                response = self._add_auto_quote(db_session, auto_quote_period, auto_quote_str)
                utils.add_to_appropriate_chat_queue(self, message, response)

            elif msg_list[1].lower() == 'edit' and len(msg_list) > 4 and msg_list[2].isdigit() and msg_list[3].isdigit():
                auto_quote_index = int(msg_list[2])
                auto_quote_str = ' '.join(msg_list[4:])
                auto_quote_period = int(msg_list[3])
                response = self._edit_auto_quote(db_session, auto_quote_index, auto_quote_str, auto_quote_period)
                utils.add_to_appropriate_chat_queue(self, message, response)

            elif msg_list[1].lower() == 'delete' and len(msg_list) > 2 and msg_list[2].isdigit():
                auto_quote_index = int(msg_list[2])
                response = self._delete_auto_quote(db_session, auto_quote_index)
                utils.add_to_appropriate_chat_queue(self, message, response)

            elif msg_list[1].lower() == 'start' and len(msg_list) > 2 and msg_list[2].isdigit():
                human_readable_auto_quote_index = int(msg_list[2])
                response = self._start_auto_quote(db_session, human_readable_auto_quote_index)
                if response is not None:
                    utils.add_to_appropriate_chat_queue(self, message, response)

            elif msg_list[1].lower() == 'stop' and len(msg_list) > 2 and msg_list[2].isdigit():
                human_readable_auto_quote_index = int(msg_list[2])
                response = self._stop_auto_quote(db_session, human_readable_auto_quote_index)
                if response is not None:
                    utils.add_to_appropriate_chat_queue(self, message, response)

            else:
                utils.add_to_appropriate_chat_queue(self, message, "Sorry, that command wasn't properly formatted.")

        else:
            utils.add_to_appropriate_chat_queue(self, message, "Sorry, auto_quote must be followed by add, edit, delete, start, or stop.")

    def _create_repeating_timer(self, index, quote, period):
        """
        Takes an index, quote and time in seconds.
        Starts a thread that waits the specified time, says the quote
        and starts another thread with the same arguments, ensuring
        that the quotes continue to be said forever or until they're stopped by the user.
        """
        key = 'AQ{}'.format(index)
        self.auto_quotes_timers[key] = threading.Timer(period, self._create_repeating_timer,
                                                       kwargs={'index': index, 'quote': quote, 'period': period})
        self.auto_quotes_timers[key].start()
        utils.add_to_public_chat_queue(self, quote)

    def _create_timer_for_auto_quote_object(self, auto_quote_object):
        """
        Takes a auto_quote object from sqlalchemy and creates a timer for it
        """
        aq_id = auto_quote_object.id
        quote = auto_quote_object.quote
        period = auto_quote_object.period
        self._create_repeating_timer(index=aq_id, quote=quote, period=period)

    def _delete_timer_for_auto_quote_object(self, auto_quote_object):
        """
        Takes a auto_quote object from sqlalchemy and deletes the timer for it
        """
        fullid = 'AQ{}'.format(auto_quote_object.id)
        self.auto_quotes_timers[fullid].cancel()
        del self.auto_quotes_timers[fullid]

    def _start_auto_quote(self, db_session, human_readable_auto_quote_index):
        """
        Gets a list of all auto_quote objects in the database, subtracts one from the HRAQI
        to get a 0 based index, sets that auto_quote object's active attribute to True and
        creates a timer for it
        """
        auto_quote_objs = db_session.query(models.AutoQuote).all()
        auto_quote_obj = auto_quote_objs[human_readable_auto_quote_index - 1]

        if not auto_quote_obj.active:
            auto_quote_obj.active = True
            self._create_timer_for_auto_quote_object(auto_quote_obj)
            db_session.flush()
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
        else:
            return 'The auto_quote was already active'

    def _stop_auto_quote(self, db_session, human_readable_auto_quote_index):
        """
        Gets a list of all auto_quote objects in the database, subtracts one from the HRAQI
        to get a 0 based index, sets that auto_quote object's active attribute to False and
        deletes the timer for it
        """
        auto_quote_objs = db_session.query(models.AutoQuote).all()
        auto_quote_obj = auto_quote_objs[human_readable_auto_quote_index - 1]

        if auto_quote_obj.active:
            auto_quote_obj.active = False
            self._delete_timer_for_auto_quote_object(auto_quote_obj)
            db_session.flush()
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
            return 'The auto_quote has been stopped'
        else:
            return 'The auto_quote was already inactive'

    def _add_auto_quote(self, db_session, delay, quote_str):
        """
        Creates an auto quote in the database
        Sets it to active and creates a repeating timer for it
        """
        auto_quote_obj = models.AutoQuote(quote=quote_str, period=delay, active=True)
        db_session.add(auto_quote_obj)
        db_session.flush()
        self._create_timer_for_auto_quote_object(auto_quote_obj)
        response_str = f'Auto quote added as auto quote #{db_session.query(models.AutoQuote).count()}.'
        utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
        return response_str

    def _edit_auto_quote(self, db_session, human_readable_auto_quote_index, auto_quote_str, auto_quote_period):
        """
        Edits an auto_quote in the database.
        If it's active, deletes the timer for the quote and creates a new one
        """
        # We grab all the auto quotes because we can't just use the auto quote ID
        # Auto quotes may get deleted, and so we need to set all auto quotes after that one back by one
        auto_quote_objs = db_session.query(models.AutoQuote).all()
        if human_readable_auto_quote_index <= len(auto_quote_objs):
            auto_quote_obj = auto_quote_objs[human_readable_auto_quote_index - 1]
            auto_quote_obj.quote = auto_quote_str
            auto_quote_obj.period = auto_quote_period
            if auto_quote_obj.active:
                self._delete_timer_for_auto_quote_object(auto_quote_obj)
                self._create_timer_for_auto_quote_object(auto_quote_obj)
            response_str = 'Auto quote has been edited.'
            db_session.flush()
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
        else:
            response_str = 'That auto quote does not exist'
        return response_str

    def _delete_auto_quote(self, db_session, human_readable_auto_quote_index):
        """
        Deletes an auto_quote from the database.
        If it's currently active, delete the timer for it.
        """
        # We grab all the auto quotes because we can't just use the auto quote ID
        # Auto quotes may get deleted, and so we need to set all auto quotes after that one back by one
        auto_quote_objs = db_session.query(models.AutoQuote).all()
        if human_readable_auto_quote_index <= len(auto_quote_objs):
            auto_quote_obj = auto_quote_objs[human_readable_auto_quote_index - 1]
            db_session.delete(auto_quote_obj)
            response_str = 'Auto quote deleted'
            db_session.flush()
            utils.add_to_command_queue(self, 'update_auto_quote_spreadsheet')
            if auto_quote_obj.active:
                self._delete_timer_for_auto_quote_object(auto_quote_obj)
        else:
            response_str = 'That auto quote does not exist'
        return response_str
