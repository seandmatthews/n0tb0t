import random

import gspread

import src.models as models
import src.utils as utils


class QuotesMixin:
    def __init__(self):
        self.starting_spreadsheets_list.append('quotes')

    @utils.retry_gspread_func
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
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        qs.update_acell('A1', 'Quote Index')
        qs.update_acell('B1', 'Quote')

        self.update_quote_spreadsheet()

    @utils.retry_gspread_func
    @utils.mod_only
    def update_quote_spreadsheet(self):
        """
        Updates the quote spreadsheet from the database.
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.

        !update_quote_spreadsheet
        """
        db_session = self.Session()
        spreadsheet_name, web_view_link = self.spreadsheets['quotes']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        qs = sheet.worksheet('Quotes')
        worksheet_width = 2

        quotes = db_session.query(models.Quote).all()

        cells = qs.range(f'A2:B{len(quotes)+11}')
        for cell in cells:
            cell.value = ''
        qs.update_cells(cells)

        cells = qs.range(f'A2:B{len(quotes)+1}')
        for index, quote_obj in enumerate(quotes):
            human_readable_index_cell_index = index * worksheet_width
            quote_cell_index = human_readable_index_cell_index + 1

            cells[human_readable_index_cell_index].value = index + 1
            cells[quote_cell_index].value = quote_obj.quote
        qs.update_cells(cells)

        db_session.commit()
        db_session.close()

    @utils.mod_only
    def update_quote_db_from_spreadsheet(self, db_session):
        """
        Updates the database from the quote spreadsheet.
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.
        This function will stop looking for quotes when it
        finds an empty row in the spreadsheet.

        !update_quote_db_from_spreadsheet
        """
        spreadsheet_name, web_view_link = self.spreadsheets['quotes']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        qs = sheet.worksheet('Quotes')
        cell_location = [2, 2]
        quotes_list = []
        while True:
            if bool(qs.cell(*cell_location).value) is not False:
                quotes_list.append(models.Quote(quote=qs.cell(*cell_location).value))
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
        msg_list = self.service.get_message_content(message).split(' ')
        quote_str = ' '.join(msg_list[1:])
        response_str = self._add_quote(db_session, quote_str)
        utils.add_to_appropriate_chat_queue(self, message, response_str)

    @utils.mod_only
    def edit_quote(self, message, db_session):
        """
        Edits a user created quote. 
        Takes a 1 indexed quote index. 
        
        !edit_quote 5 This quote is now different
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit() and int(msg_list[1]) > 0:
            quote_id = int(msg_list[1])
            quote_str = ' '.join(msg_list[2:])
            response_str = self._edit_quote(db_session, quote_id, quote_str)
            utils.add_to_appropriate_chat_queue(self, message, response_str)
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'You must use a digit to specify a quote.')

    @utils.mod_only
    def delete_quote(self, message, db_session):
        """
        Removes a user created quote.
        Takes a 1 indexed quote index.

        !delete_quote 5
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit() and int(msg_list[1]) > 0:
            quote_id = int(msg_list[1])
            response_str = self._delete_quote(db_session, quote_id)
            utils.add_to_appropriate_chat_queue(self, message, response_str)

    def show_quotes(self, message):
        """
        Links to the google spreadsheet containing all the quotes.

        !show_quotes
        """
        web_view_link = self.spreadsheets['quotes'][1]
        short_url = self.shortener.short(web_view_link)
        utils.add_to_appropriate_chat_queue(self, message, 'View the quotes at: {}'.format(short_url))

    def quote(self, message, db_session):
        """
        Displays a quote in chat. Takes a 1 indexed quote index.
        If no index is specified, displays a random quote.
        
        !quote
        !quote 5
        !quote add Oh look, the caster has uttered an innuendo!
        !quote edit 5 This quote is now different
        !quote delete 5
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 1:  # !quote
            quote_str = self._get_random_quote(db_session)
            utils.add_to_appropriate_chat_queue(self, message, quote_str)
        elif msg_list[1].isdigit():  # !quote 50
            quote_id = int(msg_list[1])
            quote_str = self._get_quote(db_session, quote_id)
            utils.add_to_appropriate_chat_queue(self, message, quote_str)
        else:  # !quote add/edit/delete
            action = msg_list[1].lower()
            if action == 'add':  # !quote add Oh look, the caster has uttered an innuendo!
                quote_str = ' '.join(msg_list[2:])
                response_str = self._add_quote(db_session, quote_str)
                utils.add_to_appropriate_chat_queue(self, message, response_str)
            elif action == 'edit':  # !quote edit 5 This quote is now different
                if self.service.get_mod_status(message):
                    if msg_list[2].isdigit():
                        quote_id = int(msg_list[2])
                        quote_str = ' '.join(msg_list[3:])
                        response_str = self._edit_quote(db_session, quote_id, quote_str)
                        utils.add_to_appropriate_chat_queue(self, message, response_str)
            elif action == 'delete':  # !quote delete 5
                if self.service.get_mod_status(message):
                    if msg_list[2].isdigit():
                        quote_id = int(msg_list[2])
                        response_str = self._delete_quote(db_session, quote_id)
                        utils.add_to_appropriate_chat_queue(self, message, response_str)

    # These methods interact with the database
    @staticmethod
    def _get_quote(db_session, quote_id):
        # We grab all the quotes because we can't just use the quote ID
        # Quotes may get deleted, and so we need to set all quotes after that one back by one
        quote_objs = db_session.query(models.Quote).all()
        if quote_id <= len(quote_objs):
            quote_obj = quote_objs[quote_id-1]
            response_str = f'#{quote_id} {quote_obj.quote}'
        else:
            response_str = f'Invalid quote id - there are only {len(quote_objs)} quotes'
        return response_str

    @staticmethod
    def _get_random_quote(db_session):
        quote_obj_list = db_session.query(models.Quote).all()
        if len(quote_obj_list) > 0:
            index = random.randrange(len(quote_obj_list))
            quote_obj = quote_obj_list[index]
            response_str = f'#{index+1} {quote_obj.quote}'
        else:
            response_str = 'No quotes currently exist'
        return response_str

    def _add_quote(self, db_session, quote_str):
        quote_obj = models.Quote(quote=quote_str)
        db_session.add(quote_obj)
        response_str = f'Quote added as quote #{db_session.query(models.Quote).count()}.'
        utils.add_to_command_queue(self, 'update_quote_spreadsheet')
        return response_str

    def _edit_quote(self, db_session, quote_index, quote_str):
        # We grab all the quotes because we can't just use the quote ID
        # Quotes may get deleted, and so we need to set all quotes after that one back by one
        quote_objs = db_session.query(models.Quote).all()
        if quote_index <= len(quote_objs):
            quote_obj = quote_objs[quote_index - 1]
            quote_obj.quote = quote_str
            response_str = 'Quote has been edited.'
            utils.add_to_command_queue(self, 'update_quote_spreadsheet')
        else:
            response_str = 'That quote does not exist'
        return response_str

    def _delete_quote(self, db_session, quote_id):
        # We grab all the quotes because we can't just use the quote ID
        # Quotes may get deleted, and so we need to set all quotes after that one back by one
        quote_objs = db_session.query(models.Quote).all()
        if quote_id <= len(quote_objs):
            quote_obj = quote_objs[quote_id - 1]
            db_session.delete(quote_obj)
            response_str = 'Quote deleted'
            utils.add_to_command_queue(self, 'update_quote_spreadsheet')
        else:
            response_str = 'That quote does not exist'
        return response_str
