import threading
import time
import gspread
import models
from .Utils import _retry_gspread_func, _mod_only


@_retry_gspread_func
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
        aqs = sheet.add_worksheet('Auto Quotes', 1000, 3)
        sheet1 = sheet.worksheet('Sheet1')
        sheet.del_worksheet(sheet1)

    aqs.update_acell('A1', 'Auto Quote Index')
    aqs.update_acell('B1', 'Quote')
    aqs.update_acell('C1', 'Period\n(In seconds)')

    # self.update_auto_quote_spreadsheet()

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

@_mod_only
@_retry_gspread_func
def update_auto_quote_spreadsheet(self, db_session):
    """
    Updates the auto_quote spreadsheet with all current auto quotes
    Only call directly if you really need to as the bot
    won't be able to do anything else while updating.
    """
    spreadsheet_name, web_view_link = self.spreadsheets['auto_quotes']
    gc = gspread.authorize(self.credentials)
    sheet = gc.open(spreadsheet_name)
    aqs = sheet.worksheet('Auto Quotes')

    auto_quotes = db_session.query(db.AutoQuote).all()

    for index in range(len(auto_quotes)+10):
        aqs.update_cell(index+2, 1, '')
        aqs.update_cell(index+2, 2, '')
        aqs.update_cell(index+2, 3, '')

    for index, aq in enumerate(auto_quotes):
        aqs.update_cell(index+2, 1, index+1)
        aqs.update_cell(index+2, 2, aq.quote)
        aqs.update_cell(index+2, 3, aq.period)

@_mod_only
def start_auto_quotes(self, db_session):
    """
    Starts the bot spitting out auto quotes by calling the
    _auto_quote function on all quotes in the AUTOQUOTES table

    !start_auto_quotes
    """
    auto_quotes = db_session.query(db.AutoQuote).all()
    self.auto_quotes_timers = {}
    for index, auto_quote in enumerate(auto_quotes):
        quote = auto_quote.quote
        period = auto_quote.period
        self._auto_quote(index=index, quote=quote, period=period)

@_mod_only
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
    user = self.ts.get_user(message)
    web_view_link = self.spreadsheets['auto_quotes'][1]
    short_url = self.shortener.short(web_view_link)
    self._add_to_whisper_queue(user, 'View the auto quotes at: {}'.format(short_url))

@_mod_only
def add_auto_quote(self, message, db_session):
    """
    Makes a new sentence that the bot periodically says.
    The first "word" after !add_auto_quote is the number of seconds
    in the interval for the bot to wait before saying the sentence again.
    Requires stopping and starting the auto quotes to take effect.

    !add_auto_quote 600 This is a rudimentary twitch bot.
    """
    user = self.ts.get_user(message)
    msg_list = self.ts.get_human_readable_message(message).split(' ')
    if len(msg_list) > 1 and msg_list[1].isdigit():
        delay = int(msg_list[1])
        quote = ' '.join(msg_list[2:])
        db_session.add(db.AutoQuote(quote=quote, period=delay))
        my_thread = threading.Thread(target=self.update_auto_quote_spreadsheet,
                                     kwargs={'db_session': db_session})
        my_thread.daemon = True
        my_thread.start()
        self._add_to_whisper_queue(user, 'Auto quote added.')
    else:
        self._add_to_whisper_queue(user, 'Sorry, the command isn\'t formatted properly.')

@_mod_only
def delete_auto_quote(self, message, db_session):
    """
    Deletes a sentence that the bot periodically says.
    Takes a 1 indexed auto quote index.
    Requires stopping and starting the auto quotes to take effect.

    !delete_auto_quote 1
    """
    user = self.ts.get_user(message)
    msg_list = self.ts.get_human_readable_message(message).split(' ')
    if len(msg_list) > 1 and msg_list[1].isdigit():
        auto_quotes = db_session.query(db.AutoQuote).all()
        if int(msg_list[1]) <= len(auto_quotes):
            index = int(msg_list[1]) - 1
            db_session.delete(auto_quotes[index])
            my_thread = threading.Thread(target=self.update_auto_quote_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()
            self._add_to_whisper_queue(user, 'Auto quote deleted.')
        else:
            self._add_to_whisper_queue(user, 'Sorry, there aren\'t that many auto quotes.')
    else:
        self._add_to_whisper_queue(user, 'Sorry, your command isn\'t formatted properly.')