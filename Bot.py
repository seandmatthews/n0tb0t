import os
import time
import random
import threading
import datetime
import collections
import inspect
import functools
import pytz
import requests
import gspread
import showerThoughtFetcher
import google_auth
import PlayerQueue
import db
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from pyshorteners import Shortener
from config import SOCKET_ARGS, bitly_access_token


# noinspection PyArgumentList,PyIncorrectDocstring
class Bot(object):
    def __init__(self, twitch_socket):

        self.ts = twitch_socket

        self.sorted_methods = self._sort_methods()

        self.chat_message_queue = collections.deque()
        self.whisper_message_queue = collections.deque()
        self.player_queue = PlayerQueue.PlayerQueue()
        self.shortener = Shortener('Bitly', bitly_token=bitly_access_token)

        self.cur_dir = os.path.dirname(os.path.realpath(__file__))
        self.Session = self._initialize_db(self.cur_dir)
        session = self.Session()

        self.credentials = google_auth.get_credentials()
        starting_spreadsheets_list = ['quotes', 'auto_quotes', 'commands', 'highlights', 'player_guesses']
        self.spreadsheets = {}
        for sheet in starting_spreadsheets_list:
            sheet_name = '{}-{}-{}'.format(SOCKET_ARGS['channel'], SOCKET_ARGS['user'], sheet)
            already_existed, spreadsheet_id = google_auth.ensure_file_exists(self.credentials, sheet_name)
            web_view_link = 'https://docs.google.com/spreadsheets/d/{}'.format(spreadsheet_id)
            sheet_tuple = (sheet_name, web_view_link)
            self.spreadsheets[sheet] = sheet_tuple
            init_command = '_initialize_{}_spreadsheet'.format(sheet)
            getattr(self, init_command)(sheet_name)

        self.guessing_enabled = session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'guessing-enabled') == 'True'

        self.allowed_to_chat = True

        self.chat_thread = threading.Thread(target=self._process_chat_queue,
                                            kwargs={'chat_queue': self.chat_message_queue})
        self.chat_thread.daemon = True
        self.chat_thread.start()

        self.whisper_thread = threading.Thread(target=self._process_whisper_queue,
                                               kwargs={'whisper_queue': self.whisper_message_queue})
        self.whisper_thread.daemon = True
        self.whisper_thread.start()

        self._add_to_chat_queue('{} is online'.format(SOCKET_ARGS['user']))

        self.auto_quotes_timers = {}
        for auto_quote in session.query(db.AutoQuote).all():
            self._auto_quote(index=auto_quote.id, quote=auto_quote.quote, period=auto_quote.period)

        session.close()

# DECORATORS #
    def _retry_gspread_func(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            while True:
                try:
                    f(*args, **kwargs)
                except gspread.exceptions.HTTPError:
                    continue
                break
        return wrapper

    def _mod_only(func):
        """
        Set's the method's _mods_only property to True
        """
        func._mods_only = True
        return func
# END DECORATORS #


    def _sort_methods(self):
        """
        Looks through the object's methods,
        sorts them into lists by evaluating who can use them
        puts those lists into a dictionary and returns it.
        """
        # Collect all methods and properties of the object.
        # Add them to self.my_dir if they don't start with an _
        my_dir = [item for item in self.__dir__() if item[0] != '_']

        my_methods = []
        methods_dict = {'for_mods': [],
                        'for_all': []}

        # Look at all the items in self.my_dir
        # Check to see if they're callable.
        # If they are add them to self.my_methods
        for item in my_dir:
            if callable(getattr(self, item)):
                my_methods.append(item)

        # Sort all methods in self.my_methods into either the for_mods list
        # or the for_all list based on the function's _mods_only property
        for method in my_methods:
            if hasattr(getattr(self, method), '_mods_only'): 
                methods_dict['for_mods'].append(method)
            else:
                methods_dict['for_all'].append(method)

        methods_dict['for_all'].sort(key=lambda item: item.lower())
        methods_dict['for_mods'].sort(key=lambda item: item.lower())

        return methods_dict

    def _initialize_db(self, db_location):
        """
        Creates the database and domain model and Session Class
        """
        channel = SOCKET_ARGS['channel']
        self.db_path = os.path.join(db_location, '{}.db'.format(channel))
        engine = sqlalchemy.create_engine('sqlite:///{}'.format(self.db_path), connect_args={'check_same_thread':False})
        # noinspection PyPep8Naming
        session_factory = sessionmaker(bind=engine)
        db.Base.metadata.create_all(engine)
        db_session = session_factory()
        misc_values = db_session.query(db.MiscValue).all()
        if len(misc_values) == 0:
            db_session.add_all([
                db.MiscValue(mv_key='guess-total-enabled', mv_value='False'),
                db.MiscValue(mv_key='current-deaths', mv_value='0'),
                db.MiscValue(mv_key='total-deaths', mv_value='0'),
                db.MiscValue(mv_key='guessing-enabled', mv_value='False')])
        db_session.commit()
        db_session.close()
        return session_factory

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

    @_retry_gspread_func
    def _initialize_commands_spreadsheet(self, spreadsheet_name):
        """
        Populate the commands google sheet with its initial data.
        """
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            cs = sheet.worksheet('Commands')
        except gspread.exceptions.WorksheetNotFound:
            cs = sheet.add_worksheet('Commands', 1000, 20)
            sheet1 = sheet.worksheet('Sheet1')
            sheet.del_worksheet(sheet1)

        cs.update_acell('A1', 'Commands\nfor\nEveryone')
        cs.update_acell('B1', 'Command\nDescription')
        cs.update_acell('D1', 'Commands\nfor\nMods')
        cs.update_acell('E1', 'Command\nDescription')
        cs.update_acell('G1', 'User\nCreated\nCommands')
        cs.update_acell('H1', 'Bot Response')
        cs.update_acell('J1', 'User\nSpecific\nCommands')
        cs.update_acell('K1', 'Bot Response')
        cs.update_acell('L1', 'User List')

        for index in range(len(self.sorted_methods['for_all'])+10):
            cs.update_cell(index+2, 1, '')
            cs.update_cell(index+2, 2, '')

        for index, method in enumerate(self.sorted_methods['for_all']):
            cs.update_cell(index+2, 1, '!{}'.format(method))
            cs.update_cell(index+2, 2, getattr(self, method).__doc__)

        for index in range(len(self.sorted_methods['for_mods'])+10):
            cs.update_cell(index+2, 4, '')
            cs.update_cell(index+2, 5, '')

        for index, method in enumerate(self.sorted_methods['for_mods']):
            cs.update_cell(index+2, 4, '!{}'.format(method))
            cs.update_cell(index+2, 5, getattr(self, method).__doc__)

        # self.update_command_spreadsheet()

    @_retry_gspread_func
    def _initialize_highlights_spreadsheet(self, spreadsheet_name):
        """
        Populate the highlights google sheet with its initial data.
        """
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            hls = sheet.worksheet('Highlight List')
        except gspread.exceptions.WorksheetNotFound:
            hls = sheet.add_worksheet('Highlight List', 1000, 4)
            sheet1 = sheet.worksheet('Sheet1')
            sheet.del_worksheet(sheet1)

        hls.update_acell('A1', 'User')
        hls.update_acell('B1', 'Stream Start Time EST')
        hls.update_acell('C1', 'Highlight Time')
        hls.update_acell('D1', 'User Note')

    @_retry_gspread_func
    def _initialize_player_guesses_spreadsheet(self, spreadsheet_name):
        """
        Populate the player_guesses google sheet with its initial data.
        """
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            pgs = sheet.worksheet('Player Guesses')
        except gspread.exceptions.WorksheetNotFound:
            pgs = sheet.add_worksheet('Player Guesses', 1000, 3)
            sheet1 = sheet.worksheet('Sheet1')
            sheet.del_worksheet(sheet1)

        pgs.update_acell('A1', 'User')
        pgs.update_acell('B1', 'Current Guess')
        pgs.update_acell('C1', 'Total Guess')

    def _add_to_chat_queue(self, message):
        """
        Adds the message to the left side of the chat queue.
        """
        self.chat_message_queue.appendleft(message)

    def _add_to_whisper_queue(self, user, message):
        """
        Creates a tuple of the user and message.
        Appends that to the left side of the whisper queue.
        """
        whisper_tuple = (user, message)
        self.whisper_message_queue.appendleft(whisper_tuple)

    def _process_chat_queue(self, chat_queue):
        """
        If there are messages in the chat queue that need
        to be sent, pop off the oldest one and pass it
        to the ts.send_message function. Then sleep for
        two seconds to stay below the twitch rate limit.
        """
        while self.allowed_to_chat:
            if len(chat_queue) > 0:
                self.ts.send_message(chat_queue.pop())
            time.sleep(.5)

    def _process_whisper_queue(self, whisper_queue):
        """
        If there are whispers in the queue that need
        to be sent, pop off the oldest one and pass it
        to the ts.send_whisper function. Then sleep for
        one second to stay below the twitch rate limit.
        """
        while True:
            if len(whisper_queue) > 0:
                whisper_tuple = (whisper_queue.pop())
                self.ts.send_whisper(whisper_tuple[0], whisper_tuple[1])
            time.sleep(.5)

    def _act_on(self, message):
        """
        Takes a message from a user.
        Looks at the message.
        Tries to extract a command from the message.
        Checks permissions for that command.
        Runs the command if the permissions check out.
        """
        if 'PING' in self.ts.get_human_readable_message(message):  # PING/PONG silliness
            self._add_to_chat_queue(self.ts.get_human_readable_message(message.replace('PING', 'PONG')))

        db_session = self.Session()
        command = self._get_command(message, db_session)
        if command is not None:
            user = self.ts.get_user(message)
            user_is_mod = self.ts.check_mod(message)
            if self._has_permission(user, user_is_mod, command, db_session):
                self._run_command(command, message, db_session)
            else:
                self._add_to_whisper_queue(user,
                                           'Sorry {} you\'re not authorized to use the command: !{}'
                                           .format(user, command[0]))
        db_session.commit()
        db_session.close()

    def _get_command(self, message, db_session):
        """
        Takes a message from the user and a database session.
        Returns a list which contains the command and the place where it can be found.
        If it's a method, that place will be the key in the sorted_methods dictionary which
        has the corresponding list containing the command. Otherwise it will be the word 'Database'.
        """
        first_word = self.ts.get_human_readable_message(message).split(' ')[0]
        if len(first_word) > 1 and first_word[0] == '!':
            potential_command = first_word[1:].lower()
        else:
            return None
        if potential_command in self.sorted_methods['for_all']:
            return [potential_command, 'for_all']
        if potential_command in self.sorted_methods['for_mods']:
            return [potential_command, 'for_mods']
        db_result = db_session.query(db.Command).filter(db.Command.call == potential_command).all()
        if db_result:
            return [potential_command, db_result[0]]
        return None

    def _has_permission(self, user, user_is_mod, command, db_session):
        """
        Takes a message from the user, and a list which contains the
        command and where it's found, and a database session.
        Returns True or False depending on whether the user that
        sent the command has the authority to use that command
        """

        if command[1] == 'for_all':
            return True
        if command[1] == 'for_mods' and user_is_mod:
            return True
        if type(command[1]) == db.Command:
            db_command = command[1]
            if bool(db_command.permissions) is False:
                return True
            elif user in [permission.user_entity for permission in db_command.permissions]:
                return True
        return False

    def _run_command(self, command, message, db_session):
        if type(command[1]) == db.Command:
            db_command = command[1]
            self._add_to_chat_queue(db_command.response)
        else:
            method_command = command[0]
            kwargs = {}
            if 'message' in inspect.signature(getattr(self, method_command)).parameters:
                kwargs['message'] = message
            if 'db_session' in inspect.signature(getattr(self, method_command)).parameters:
                kwargs['db_session'] = db_session
            getattr(self, method_command)(**kwargs)

    @_mod_only
    def stop_speaking(self):
        """
        Stops the bot from putting stuff in chat to cut down on bot spam.
        In long run, this should be replaced with rate limits.

        !stop_speaking
        """
        self.ts.send_message("Okay, I'll shut up for a bit. !start_speaking when you want me to speak again.")
        self.allowed_to_chat = False

    @_mod_only
    def start_speaking(self):
        """
        Allows the bot to start speaking again.

        !start_speaking
        """
        self.allowed_to_chat = True
        self.chat_message_queue.clear()
        self.chat_thread = threading.Thread(target=self._process_chat_queue,
                                            kwargs={'chat_queue': self.chat_message_queue})
        self.chat_thread.daemon = True
        self.chat_thread.start()

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

    @_mod_only
    @_retry_gspread_func
    def update_command_spreadsheet(self, db_session):
        """
        Updates the commands google sheet with all available user commands.
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.
        """
        spreadsheet_name, web_view_link = self.spreadsheets['commands']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        cs = sheet.worksheet('Commands')

        db_commands = db_session.query(db.Command).all()
        everyone_commands = []
        user_specific_commands = []
        for command in db_commands:
            if bool(command.permissions) is False:
                everyone_commands.append(command)
            else:
                user_specific_commands.append(command)

        for index in range(len(everyone_commands)+10):
            cs.update_cell(index+2, 7, '')
            cs.update_cell(index+2, 8, '')

        for index, command in enumerate(everyone_commands):
            cs.update_cell(index+2, 7, '!{}'.format(command.call))
            cs.update_cell(index+2, 8, command.response)

        for index in range(len(everyone_commands)+10):
            cs.update_cell(index+2, 10, '')
            cs.update_cell(index+2, 11, '')
            cs.update_cell(index+2, 12, '')

        for index, command in enumerate(user_specific_commands):
            users = [permission.user_entity for permission in command.permissions]
            users_str = ', '.join(users)
            cs.update_cell(index+2, 10, '!{}'.format(command.call))
            cs.update_cell(index+2, 11, command.response)
            cs.update_cell(index+2, 12, users_str)

    @_mod_only
    def add_command(self, message, db_session):
        """
        Adds a new command.
        The first word after !add_command with an exclamation mark is the command.
        The rest of the sentence is the reply.
        Optionally takes the names of twitch users before the command.
        This would make the command only available to those users.

        !add_command !test_command This is a test.
        !add_command TestUser1 TestUser2 !test_command This is a test
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        for index, word in enumerate(msg_list[1:]):  # exclude !add_user_command
            if word[0] == '!':
                command = word
                users = msg_list[1:index + 1]
                response = ' '.join(msg_list[index + 2:])
                break
        else:
            self._add_to_whisper_queue(user, 'Sorry, the command needs to have an ! in it.')
            return
        db_commands = db_session.query(db.Command).all()
        if command[1:] in [db_command.call for db_command in db_commands]:
            self._add_to_whisper_queue(user, 'Sorry, that command already exists. Please delete it first.')
        else:
            db_command = db.Command(call=command[1:], response=response)
            if len(users) != 0:
                users = [user.lower() for user in users]
                permissions = []
                for user in users:
                    permissions.append(db.Permission(user_entity=user))
                db_command.permissions = permissions
            db_session.add(db_command)
            self._add_to_whisper_queue(user, 'Command added.')
            my_thread = threading.Thread(target=self.update_command_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()

    @_mod_only
    def delete_command(self, message, db_session):
        """
        Removes a user created command.
        Takes the name of the command.

        !delete_command !test
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        command_str = msg_list[1][1:]
        db_commands = db_session.query(db.Command).all()
        for db_command in db_commands:
            if command_str == db_command.call:
                db_session.delete(db_command)
                self._add_to_whisper_queue(user, 'Command deleted.')
                my_thread = threading.Thread(target=self.update_command_spreadsheet,
                                             kwargs={'db_session': db_session})
                my_thread.daemon = True
                my_thread.start()
                break
        else:
            self._add_to_whisper_queue(user, 'Sorry, that command doesn\'t seem to exist.')

    def show_commands(self, message):
        """
        Links the google spreadsheet containing all commands in chat

        !show_commands
        """
        user = self.ts.get_user(message)
        web_view_link = self.spreadsheets['commands'][1]
        short_url = self.shortener.short(web_view_link)
        self._add_to_whisper_queue(user, 'View the commands at: {}'.format(short_url))

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

    @_mod_only
    def so(self, message):
        """
        Shouts out a twitch caster in chat. Uses the twitch API to confirm
        that the caster is real and to fetch their last played game.

        !SO $caster
        """
        # TODO: Add a command to be able to set the shout_out_str from within twitch chat, or at least somewhere
        user = self.ts.get_user(message)
        me = SOCKET_ARGS['channel']
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1:
            channel = msg_list[1]
            url = 'https://api.twitch.tv/kraken/channels/{channel}'.format(channel=channel.lower())
            for attempt in range(5):
                try:
                    r = requests.get(url)
                    r.raise_for_status()
                    game = r.json()['game']
                    channel_url = r.json()['url']
                    shout_out_str = 'Friends, {channel} is worth a follow. They last played {game}. If that sounds appealing to you, check out {channel} at {url}! Tell \'em {I} sent you!'.format(
                        channel=channel, game=game, url=channel_url, I=me)
                    self._add_to_chat_queue(shout_out_str)
                except requests.exceptions.HTTPError:
                    self._add_to_chat_queue('Hey {}, that\'s not a real streamer!'.format(user))
                    break
                except ValueError:
                    continue
                else:
                    break
            else:
                self._add_to_chat_queue(
                    "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")
        else:
            self._add_to_chat_queue('Sorry {}, you need to specify a caster to shout out.'.format(user))

    def shower_thought(self):
        """
        Fetches the top shower thought from reddit in the last 24 hours and sends it to chat.

        !shower_thought
        """
        self._add_to_chat_queue(showerThoughtFetcher.get_shower_thought())

    def _get_live_time(self):
        """
        Uses the kraken API to fetch the start time of the current stream.
        Computes how long the stream has been running, returns that value in a dictionary.
        """
        channel = SOCKET_ARGS['channel']
        url = 'https://api.twitch.tv/kraken/streams/{}'.format(channel.lower())
        for attempt in range(5):
            try:
                r = requests.get(url)
                r.raise_for_status()
                start_time_str = r.json()['stream']['created_at']
                start_time_dt = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%SZ')
                now_dt = datetime.datetime.utcnow()
                time_delta = now_dt - start_time_dt
                time_dict = {'hour': None,
                             'minute': None,
                             'second': None,
                             }

                time_dict['hour'], remainder = divmod(time_delta.seconds, 3600)
                time_dict['minute'], time_dict['second'] = divmod(remainder, 60)
                for time_var in time_dict:
                    if time_dict[time_var] == 1:
                        time_dict[time_var] = "{} {}".format(time_dict[time_var], time_var)
                    else:
                        time_dict[time_var] = "{} {}s".format(time_dict[time_var], time_var)
                time_dict['stream_start'] = start_time_dt
                time_dict['now'] = now_dt
            except requests.exceptions.HTTPError:
                continue
            except TypeError:
                self._add_to_chat_queue('Sorry, the channel doesn\'t seem to be live at the moment.')
                break
            except ValueError:
                continue
            else:
                return time_dict
        else:
            self._add_to_chat_queue(
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

    def uptime(self):
        """
        Sends a message to stream saying how long the caster has been streaming for.

        !uptime
        """
        time_dict = self._get_live_time()
        if time_dict is not None:
            uptime_str = 'The channel has been live for {hours}, {minutes} and {seconds}.'.format(
                    hours=time_dict['hour'], minutes=time_dict['minute'], seconds=time_dict['second'])
            self._add_to_chat_queue(uptime_str)

    def highlight(self, message):
        """
        Logs the time in the video when something amusing happened.
        Takes an optional short sentence describing the event.
        Writes that data to a google spreadsheet.

        !highlight
        !highlight The caster screamed like a little girl!
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1:
            user_note = ' '.join(msg_list[1:])
        else:
            user_note = ''
        time_dict = self._get_live_time()
        if time_dict is not None:
            est_tz = pytz.timezone('US/Eastern')
            start_time_utc = time_dict['stream_start']
            start_time_est = est_tz.normalize(start_time_utc.replace(tzinfo=pytz.utc).astimezone(est_tz))
            time_str = 'Approximately {hours}, {minutes} and {seconds} into the stream.'.format(
                    hours=time_dict['hour'], minutes=time_dict['minute'], seconds=time_dict['second'])

            spreadsheet_name, _ = self.spreadsheets['highlights']
            gc = gspread.authorize(self.credentials)
            sheet = gc.open(spreadsheet_name)
            ws = sheet.worksheet('Highlight List')
            records = ws.get_all_records()  # Doesn't include the first row
            next_row = len(records) + 2
            ws.update_cell(next_row, 1, user)
            ws.update_cell(next_row, 2, str(start_time_est)[:-6])
            ws.update_cell(next_row, 3, time_str)
            ws.update_cell(next_row, 4, user_note)
            self._add_to_whisper_queue(user, 'The highlight has been added to the spreadsheet for review.')

    def join(self, message, db_session):
        """
        Adds the user to the game queue.
        The players who've played the fewest
        times with the caster get priority.

        !join_queue
        """
        username = self.ts.get_user(message)
        user = db_session.query(db.User).filter(db.User.name == username).one_or_none()
        if not user:
            user = db.User(name=username)
            db_session.add(user)
        try:
            self.player_queue.push(username, user.times_played)
            self._add_to_whisper_queue(username, "You've joined the queue.")
        except RuntimeError:
            self._add_to_whisper_queue(username, "You're already in the queue and can't join again.")
        user.times_played += 1

    @_mod_only
    def cycle(self, message):
        """
        Sends out a message to the next set of players.

        !cycle
        !cycle Password!1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        players = self.player_queue.pop_all()
        players_str = ' '.join(players)
        channel = SOCKET_ARGS['channel']
        if len(msg_list) > 1:
            credential_str = ' '.join(msg_list[1:])
            whisper_str = 'You may now join {} to play. The credentials you need are: {}'.format(
                    channel, credential_str)
        else:
            whisper_str = 'You may now join {} to play.'.format(channel)
        for player in players:
            self._add_to_whisper_queue(player, whisper_str)
        self._add_to_chat_queue("Invites sent to: {} and there are {} people left in the queue".format(
            players_str, len(self.player_queue.queue)
        ))

    @_mod_only
    def cycle_one(self, message):
        """
        Sends out a message to the next player.

        !cycle_one
        !cycle_one Password!1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        channel = SOCKET_ARGS['channel']
        try:
            player = self.player_queue.pop()
        except IndexError:
            self._add_to_chat_queue('Sorry, there are no more players in the queue')
        if len(msg_list) > 1:
            credential_str = ' '.join(msg_list[1:])
            whisper_str = 'You may now join {} to play. The credentials you need are: {}'.format(
                    channel, credential_str)
        else:
            whisper_str = 'You may now join {} to play.'.format(channel)
        self._add_to_whisper_queue(player, whisper_str)
        self._add_to_chat_queue("Invite sent to: {} and there are {} people left in the queue".format(
            player, len(self.player_queue.queue)
        ))


    @_mod_only
    def reset_queue(self, db_session):
        """
        Creates a new queue with the default room size
        and resets all players stats for how many
        times they've played with the caster.

        !reset_queue
        """
        self.player_queue = PlayerQueue.PlayerQueue()
        db_session.execute(sqlalchemy.update(db.User.__table__, values={db.User.__table__.c.times_played: 0}))
        self._add_to_chat_queue('The queue has been emptied and all players start fresh.')

    @_mod_only
    def set_cycle_number(self, message):
        """
        Sets the number of players to cycle
        in when it's time to play with new people.
        By default this value is 7.

        !set_cycle_number 5
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        user = self.ts.get_user(message)
        if len(msg_list) > 1 and msg_list[1].isdigit() and int(msg_list[1]) > 0:
            cycle_num = int(msg_list[1])
            self.player_queue.cycle_num = cycle_num
            self._add_to_whisper_queue(user, "The new room size is {}.".format(cycle_num))
        else:
            self._add_to_whisper_queue(user, "Make sure the command is followed by an integer greater than 0.")

    def enter_contest(self, message, db_session):
        """
        Adds the user to the contest entrants
        or informs them that they're already entered if they've already
        entered since the last time the entrants were cleared.

        !enter_contest
        """
        username = self.ts.get_user(message)
        user = db_session.query(db.User).filter(db.User.name == username).one_or_none()
        if user:
            if user.entered_in_contest:
                self._add_to_whisper_queue(user, 'You\'re already entered into the contest, you can\'t enter again.')
            else:
                user.entered_in_contest = True
                self._add_to_whisper_queue(user, 'You\'re entered into the contest!')
        else:
            user = db.User(name=username, entered_in_contest=True)
            db_session.add(user)
            self._add_to_whisper_queue(user, 'You\'re entered into the contest!')

    @_mod_only
    def show_contest_winner(self, db_session):
        """
        Selects a contest entrant at random.
        Sends their name to the chat.

        !show_contest_winner
        """
        users_contest_list = db_session.query(db.User).filter(db.User.entered_in_contest.isnot(False)).all()
        if len(users_contest_list) > 0:
            winner = random.choice(users_contest_list)
            self._add_to_chat_queue('The winner is {}!'.format(winner))
        else:
            self._add_to_chat_queue('There are currently no entrants for the contest.')

    @_mod_only
    def clear_contest_entrants(self, db_session):
        """
        Sets the entrants list to be an empty list and then writes
        that to the entrants file.

        !clear_contest_entrants
        """
        db_session.execute(sqlalchemy.update(db.User.__table__, values={db.User.__table__.c.entered_in_contest: False}))
        self._add_to_chat_queue("Contest entrants cleared.")

    @_mod_only
    def enable_guessing(self, db_session):
        """
        Allows users to guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !enable_guessing
        """
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'guessing-enabled').one()
        mv_obj.mv_value = "True"
        self._add_to_chat_queue("Guessing is now enabled.")

    @_mod_only
    def disable_guessing(self, db_session):
        """
        Stops users from guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !disable_guessing
        """
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'guessing-enabled').one()
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
        user = self.ts.get_user(message)
        if db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'guessing-enabled').one().mv_value == 'True':
            msg_list = self.ts.get_human_readable_message(message).split(' ')
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

    @_mod_only
    def enable_guesstotal(self, db_session):
        """
        Enables guessing for the total number of deaths for the run.
        Modifies the value associated with the guess-total-enabled key
        in the miscellaneous values dictionary and writes it to the json file.

        !enable_guesstotal
        """
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'guess-total-enabled').one()
        mv_obj.mv_value = "True"
        self._add_to_chat_queue("Guessing for the total amount of deaths is now enabled.")

    @_mod_only
    def disable_guesstotal(self, db_session):
        """
        Disables guessing for the total number of deaths for the run.

        !disable_guesstotal
        """
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'guess-total-enabled').one()
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
        user = self.ts.get_user(message)
        if db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'guess-total-enabled').one().mv_value == "True":
            msg_list = self.ts.get_human_readable_message(message).split(' ')
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

    @_mod_only
    def clear_guesses(self, db_session):
        """
        Clear all guesses so that users
        can guess again for the next segment
        of the run.

        !clear_guesses
        """
        db_session.execute(sqlalchemy.update(db.User.__table__, values={db.User.__table__.c.current_guess: None}))
        self._add_to_chat_queue("Guesses have been cleared.")

    @_mod_only
    def clear_total_guesses(self, db_session):
        """
        Clear all total guesses so that users
        can guess again for the next game
        where they guess about the total number of deaths

        !clear_total_guesses
        """
        db_session.execute(sqlalchemy.update(db.User.__table__, values={db.User.__table__.c.total_guess: None}))
        self._add_to_chat_queue("Guesses for the total number of deaths have been cleared.")

    @_retry_gspread_func
    def _update_player_guesses_spreadsheet(self):
        """
        Updates the player guesses spreadsheet from the database.
        """
        db_session = self.Session()
        spreadsheet_name, web_view_link = self.spreadsheets['player_guesses']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        ws = sheet.worksheet('Player Guesses')
        all_users = db_session.query(db.User).all()
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

    @_mod_only
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

    @_mod_only
    def set_deaths(self, message, db_session):
        """
        Sets the number of deaths for the current
        leg of the run. Needs a non-negative integer.

        !set_deaths 5
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
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

    @_mod_only
    def set_total_deaths(self, message, db_session):
        """
        Sets the total number of deaths for the run.
        Needs a non-negative integer.

        !set_total_deaths 5
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
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

    @_mod_only
    def add_death(self, message, db_session):
        """
        Adds one to both the current sequence
        and total death counters.

        !add_death
        """
        user = self.ts.get_user(message)
        deaths = int(self._get_current_deaths(db_session))
        total_deaths = int(self._get_total_deaths(db_session))
        deaths += 1
        total_deaths += 1
        self._set_deaths(str(deaths), db_session)
        self._set_total_deaths(str(total_deaths), db_session)
        whisper_msg = 'Current Deaths: {}, Total Deaths: {}'.format(deaths, total_deaths)
        self._add_to_whisper_queue(user, whisper_msg)

    @_mod_only
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
        users = db_session.query(db.User).filter(db.User.current_guess.isnot(None)).all()
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
            me = SOCKET_ARGS['channel']
            winners_str = 'You all guessed too high. You should have had more faith in {}. {} wins!'.format(me, me)
        self._add_to_chat_queue(winners_str)

    def _set_current_guess(self, user, guess, db_session):
        """
        Takes a user and a guess.
        Adds the user (if they don't already exist)
        and their guess to the users table.
        """
        db_user = db_session.query(db.User).filter(db.User.name == user).first()
        if not db_user:
            db_user = db.User(name=user)
            db_session.add(db_user)
        db_user.current_guess = guess

    def _set_total_guess(self, user, guess, db_session):
        """
        Takes a user and a guess
        for the total number of deaths.
        Adds the user and their guess
        to the users table.
        """
        db_user = db_session.query(db.User).filter(db.User.name == user).first()
        if not db_user:
            db_user = db.User(name=user)
            db_session.add(db_user)
        db_user.total_guess = guess

    def _get_current_deaths(self, db_session):
        """
        Returns the current number of deaths
        for the current leg of the run.
        """
        deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'current-deaths').one()
        return deaths_obj.mv_value

    def _get_total_deaths(self, db_session):
        """
        Returns the total deaths that
        have occurred in the run so far.
        """
        total_deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'total-deaths').one()
        return total_deaths_obj.mv_value

    def _set_deaths(self, deaths_num, db_session):
        """
        Takes a string for the number of deaths.
        Updates the miscellaneous values table.
        """
        deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'current-deaths').one()
        deaths_obj.mv_value = deaths_num

    def _set_total_deaths(self, total_deaths_num, db_session):
        """
        Takes a string for the total number of deaths.
        Updates the miscellaneous values table.
        """
        total_deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.mv_key == 'total-deaths').one()
        total_deaths_obj.mv_value = total_deaths_num