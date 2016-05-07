import collections
import datetime
import functools
import inspect
import os
import random
import threading
import time

import gspread
import pytz
import requests
import sqlalchemy
from pyshorteners import Shortener
from sqlalchemy.orm import sessionmaker

import db
import google_auth
from config import SOCKET_ARGS, bitly_access_token
from modules import PlayerQueue


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

