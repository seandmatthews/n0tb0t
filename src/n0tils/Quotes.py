import threading
import gspread
import models
from .Utils import _mod_only, _retry_gspread_func


@_retry_gspread_func
def _initialize_quotes_spreadsheet(self, spreadsheet_name):
    """
    Populate the quotes google sheet with its initial data.
    """
    gc = gspread.authorize(self.credentials)
    sheet = gc.open(spreadsheet_name)
    sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

    try:
        qs = sheet.worksheet('Quotes')
    except gspread.exceptions.WorksheetNotFound:
        qs = sheet.add_worksheet('Quotes', 1000, 2)
        sheet1 = sheet.worksheet('Sheet1')
        sheet.del_worksheet(sheet1)

    qs.update_acell('A1', 'Quote Index')
    qs.update_acell('B1', 'Quote')

    # self.update_quote_spreadsheet()

@_mod_only
@_retry_gspread_func
def update_quote_spreadsheet(self, db_session):
    """
    Updates the quote spreadsheet from the database.
    Only call directly if you really need to as the bot
    won't be able to do anything else while updating.
    """
    spreadsheet_name, web_view_link = self.spreadsheets['quotes']
    gc = gspread.authorize(self.credentials)
    sheet = gc.open(spreadsheet_name)
    qs = sheet.worksheet('Quotes')

    quotes = db_session.query(db.Quote).all()

    for index in range(len(quotes)+10):
        qs.update_cell(index+2, 1, '')
        qs.update_cell(index+2, 2, '')

    for index, quote_obj in enumerate(quotes):
        qs.update_cell(index+2, 1, index+1)
        qs.update_cell(index+2, 2, quote_obj.quote)

@_mod_only
def update_quote_db_from_spreadsheet(self, db_session):
    """
    Updates the database from the quote spreadsheet.
    Only call directly if you really need to as the bot
    won't be able to do anything else while updating.
    This function will stop looking for quotes when it
    finds an empty row in the spreadsheet.
    """
    spreadsheet_name, web_view_link = self.spreadsheets['quotes']
    gc = gspread.authorize(self.credentials)
    sheet = gc.open(spreadsheet_name)
    qs = sheet.worksheet('Quotes')
    cell_location = [2, 2]
    quotes_list = []
    while True:
        if bool(qs.cell(*cell_location).value) is not False:
            quotes_list.append(db.Quote(quote=qs.cell(*cell_location).value))
            cell_location[0] += 1
        else:
            break

    db_session.execute(
        "DELETE FROM QUOTES;"
    )
    db_session.add_all(quotes_list)

def add_quote(self, message, db_session):
    """
    Adds a quote to the database.

    !add_quote Oh look, the caster has uttered an innuendo!
    """
    user = self.ts.get_user(message)
    msg_list = self.ts.get_human_readable_message(message).split(' ')
    quote = ' '.join(msg_list[1:])
    quote_obj = db.Quote(quote=quote)
    db_session.add(quote_obj)
    self._add_to_whisper_queue(user, 'Quote added as quote #{}.'.format(db_session.query(db.Quote).count()))
    my_thread = threading.Thread(target=self.update_quote_spreadsheet,
                                 kwargs={'db_session': db_session})
    my_thread.daemon = True
    my_thread.start()

@_mod_only
def delete_quote(self, message, db_session):
    """
    Removes a user created quote.
    Takes a 1 indexed quote index.

    !delete_quote 1
    """
    msg_list = self.ts.get_human_readable_message(message).split(' ')
    user = self.ts.get_user(message)
    if len(msg_list) > 1 and msg_list[1].isdigit() and int(msg_list[1]) > 0:
        quotes = db_session.query(db.Quote).all()
        if int(msg_list[1]) <= len(quotes):
            index = int(msg_list[1]) - 1
            db_session.delete(quotes[index])
            self._add_to_whisper_queue(user, 'Quote deleted.')
            my_thread = threading.Thread(target=self.update_quote_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()
        else:
            self._add_to_whisper_queue(user, 'Sorry, that\'s not a quote that can be deleted.')

def show_quotes(self, message, db_session):
    """
    Links to the google spreadsheet containing all the quotes.

    !show_quotes
    """
    user = self.ts.get_user(message)
    web_view_link = self.spreadsheets['quotes'][1]
    short_url = self.shortener.short(web_view_link)
    self._add_to_whisper_queue(user, 'View the quotes at: {}'.format(short_url))

def quote(self, message, db_session):
    """
    Displays a quote in chat. Takes a 1 indexed quote index.
    If no index is specified, displays a random quote.

    !quote 5
    !quote
    """
    msg_list = self.ts.get_human_readable_message(message).split(' ')
    if len(msg_list) > 1 and msg_list[1].isdigit():
        if int(msg_list[1]) > 0:
            index = int(msg_list[1]) - 1
            quotes = db_session.query(db.Quote).all()
            if index <= len(quotes)-1:
                self._add_to_chat_queue('#{} {}'.format(str(index + 1), quotes[index].quote))
            else:
                self._add_to_chat_queue('Sorry, there are only {} quotes.'.format(len(quotes)))
        else:
            self._add_to_chat_queue('Sorry, a quote index must be greater than or equal to 1.')
    else:
        quotes = db_session.query(db.Quote).all()
        random_quote_index = random.randrange(len(quotes))
        self._add_to_chat_queue('#{} {}'.format(str(random_quote_index + 1), quotes[random_quote_index].quote))
