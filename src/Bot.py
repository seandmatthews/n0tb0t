import collections
import importlib
import inspect
import json
import os
import threading
import time
from enum import Enum, auto

import gspread
import sqlalchemy
from pyshorteners import Shortener
from sqlalchemy.orm import sessionmaker

import src.models as models
import src.google_auth as google_auth
import src.modules.Utils as Utils
from config import time_zone_choice
from src.modules.PlayerQueue import PlayerQueue


# Collect all the Mixin classes from all the modules in the src/modules directory
# Store these class objects in a mixin_classes list so that Bot can inherit from them
print('Loading Modules')
cur_dir = os.path.dirname(os.path.realpath(__file__))
modules_dir = os.path.join(cur_dir, 'modules')
module_files = [f for f in os.listdir(modules_dir) if os.path.isfile(os.path.join(modules_dir, f))]
mixin_classes = []

for file in module_files:
    if file != '__init__.py' and file[-3:] == '.py':
        # Take these .py files and import them, turning them into module objects
        imported = importlib.import_module(f'src.modules.{file[:-3]}')
        for item in dir(imported):
            if item[0] != '_':
                if isinstance(getattr(imported, item), type) and 'Mixin' in item:
                    mixin_classes.append(getattr(imported, item))
                    print(item)


class CommandTypes(Enum):
    HARDCODED = auto()
    DYNAMIC = auto()

# noinspection PyArgumentList,PyIncorrectDocstring
class Bot(*mixin_classes):
    def __init__(self, service, BOT_INFO, bitly_access_token, current_dir, data_dir):

        self.service = service
        self.info = BOT_INFO

        self.sorted_methods = self._sort_methods()

        # Most functions run in the main thread, but we can put slow ones here
        self.command_queue = collections.deque()

        self.chat_message_queue = collections.deque()
        self.whisper_message_queue = collections.deque()
        try:
            with open(os.path.join(data_dir, f"{self.info['channel']}_player_queue.json"), 'r', encoding="utf-8") as player_file:
                self.player_queue = PlayerQueue(input_iterable=json.loads(player_file.read()))
        except FileNotFoundError:
            self.player_queue = PlayerQueue()

        self.shortener = Shortener('Bitly', bitly_token=bitly_access_token)

        self.Session = self._initialize_db(data_dir)
        db_session = self.Session()

        self.credentials = google_auth.get_credentials(credentials_parent_dir=current_dir, client_secret_dir=current_dir)

        print('Finding Google Sheets')
        starting_spreadsheets_list = ['quotes', 'auto_quotes', 'commands', 'highlights', 'player_guesses', 'player_queue']
        self.spreadsheets = {}
        for sheet in starting_spreadsheets_list:
            sheet_name = '{}-{}-{}'.format(BOT_INFO['channel'], BOT_INFO['user'], sheet)
            already_existed, spreadsheet_id = google_auth.ensure_file_exists(self.credentials, sheet_name)
            web_view_link = 'https://docs.google.com/spreadsheets/d/{}'.format(spreadsheet_id)
            sheet_tuple = (sheet_name, web_view_link)
            self.spreadsheets[sheet] = sheet_tuple
            init_command = '_initialize_{}_spreadsheet'.format(sheet)
            # getattr(self, init_command)(sheet_name, session)

        self.guessing_enabled = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled') == 'True'

        self.allowed_to_chat = True

        self.chat_thread = threading.Thread(target=self._process_chat_queue,
                                            kwargs={'chat_queue': self.chat_message_queue})
        self.chat_thread.daemon = True
        self.chat_thread.start()

        self.whisper_thread = threading.Thread(target=self._process_whisper_queue,
                                               kwargs={'whisper_queue': self.whisper_message_queue})
        self.whisper_thread.daemon = True
        self.whisper_thread.start()

        self.command_thread = threading.Thread(target=self._process_command_queue,
                                               kwargs={'command_queue': self.command_queue})
        self.command_thread.daemon = True
        self.command_thread.start()

        self._add_to_chat_queue('{} is online'.format(BOT_INFO['user']))

        self.start_auto_quotes(db_session)
        self.player_queue_credentials = None
        db_session.close()
        self.strawpoll_id = ''

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
                        'for_all': [],
                        'private_message_allowed': [],
                        'public_message_disallowed': []}

        # Look at all the items in self.my_dir
        # Check to see if they're callable.
        # If they are add them to self.my_methods
        for item in my_dir:
            if callable(getattr(self, item)):
                my_methods.append(item)

        # Sort all methods in self.my_methods into either the for_mods list
        # or the for_all list based on the function's _mods_only property
        for method in my_methods:
            if hasattr(getattr(self, method), '_mod_only'):
                methods_dict['for_mods'].append(method)
            else:
                methods_dict['for_all'].append(method)
            if hasattr(getattr(self, method), '_private_message_allowed'):
                methods_dict['private_message_allowed'].append(method)
            if hasattr(getattr(self, method), '_public_message_disallowed'):
                methods_dict['public_message_disallowed'].append(method)

        for method_list in methods_dict.values():
            method_list.sort(key=lambda item: item.lower())

        return methods_dict

    def _initialize_db(self, db_location):
        """
        Creates the database and domain model and Session Class
        """
        channel = self.info['channel']
        self.db_path = os.path.join(db_location, '{}.db'.format(channel))
        engine = sqlalchemy.create_engine('sqlite:///{}'.format(self.db_path), connect_args={'check_same_thread': False})
        # noinspection PyPep8Naming
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        models.Base.metadata.create_all(engine)
        db_session = session_factory()
        misc_values = db_session.query(models.MiscValue).all()
        if len(misc_values) == 0:
            db_session.add_all([
                models.MiscValue(mv_key='guess-total-enabled', mv_value='False'),
                models.MiscValue(mv_key='current-deaths', mv_value='0'),
                models.MiscValue(mv_key='total-deaths', mv_value='0'),
                models.MiscValue(mv_key='guessing-enabled', mv_value='False')])
        db_session.commit()
        db_session.close()
        return session_factory

    @Utils._retry_gspread_func
    def _initialize_quotes_spreadsheet(self, spreadsheet_name, db_session):
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

        self.update_quote_spreadsheet(db_session)

    @Utils._retry_gspread_func
    def _initialize_auto_quotes_spreadsheet(self, spreadsheet_name, db_session):
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

        self.update_auto_quote_spreadsheet(db_session)

    @Utils._retry_gspread_func
    def _initialize_commands_spreadsheet(self, spreadsheet_name, db_session):
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
            sheet1 = sheet.get_worksheet(0)
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

        self.update_command_spreadsheet(db_session)

    @Utils._retry_gspread_func
    def _initialize_highlights_spreadsheet(self, spreadsheet_name, db_session):
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
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        hls.update_acell('A1', 'User')
        hls.update_acell('B1', 'Stream Start Time {}'.format(time_zone_choice))
        hls.update_acell('C1', 'Highlight Time')
        hls.update_acell('D1', 'User Note')

    @Utils._retry_gspread_func
    def _initialize_player_guesses_spreadsheet(self, spreadsheet_name, db_session):
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
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        pgs.update_acell('A1', 'User')
        pgs.update_acell('B1', 'Current Guess')
        pgs.update_acell('C1', 'Total Guess')

    @Utils._retry_gspread_func
    def _initialize_player_queue_spreadsheet(self, spreadsheet_name, db_session):
        """
        Populate the player_queue google sheet with its initial data.
        """
        caster = self.info['channel']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            pqs = sheet.worksheet('Player Queue')
        except gspread.exceptions.WorksheetNotFound:
            pqs = sheet.add_worksheet('Player Queue', 500, 3)
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        info = """Priority is given to players with fewest times played.
        The top of this spreadsheet is the back of the queue
        and the bottom is the front. The closer you are to the bottom,
        the closer you are to playing with {}.""".format(caster)

        pqs.update_acell('A1', 'User')
        pqs.update_acell('B1', 'Times played')
        pqs.update_acell('C1', 'Info:')
        pqs.update_acell('C2', info)

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
        half a second to stay below the twitch rate limit.
        """
        while self.allowed_to_chat:
            if len(chat_queue) > 0:
                self.service.send_public_message(chat_queue.pop())
            time.sleep(.5)

    def _process_whisper_queue(self, whisper_queue):
        """
        If there are whispers in the queue that need
        to be sent, pop off the oldest one and pass it
        to the ts.send_whisper function. Then sleep for
        half a second to stay below the twitch rate limit.
        """
        while True:
            if len(whisper_queue) > 0:
                whisper_tuple = (whisper_queue.pop())
                self.service.send_private_message(whisper_tuple[0], whisper_tuple[1])
            time.sleep(1.5)

    def _process_command_queue(self, command_queue):
        """
        If there are commands in the queue, pop off the
        oldest one and run it. Then sleep for half a second
        to avoid busy waiting the CPU into a space heater.
        """
        while True:
            if len(command_queue) > 0:
                command_tuple = command_queue.pop()
                func, kwargs = command_tuple[0], command_tuple[1]
                getattr(self, func)(**kwargs)
            time.sleep(.5)

    def _act_on(self, message):
        """
        Takes a message from a user.
        Looks at the message.
        Tries to extract a command from the message.
        Checks permissions for that command.
        Runs the command if the permissions check out.
        """
        if 'PING' in self.service.get_message_content(message):  # PING/PONG silliness
            self._add_to_chat_queue(self.service.get_message_content(message).replace('PING', 'PONG'))

        db_session = self.Session()
        command = self._get_command(message, db_session)
        if command is not None:
            user = self.service.get_message_display_name(message)
            user_is_mod = self.service.get_mod_status(message)
            if self._has_permission(user, user_is_mod, command) and self._is_valid_message_type(command, message):
                self._run_command(command, message, db_session)
        db_session.commit()
        db_session.close()

    def _get_command(self, message, db_session):
        """
        Takes a message from the user and a database session.
        Returns a list which contains the command and the place where it can be found.
        If it's a method, that place will be the key in the sorted_methods dictionary which
        has the corresponding list containing the command. Otherwise it will be the word 'Database'.
        """
        first_word = self.service.get_message_content(message).split(' ')[0]
        if len(first_word) > 1 and first_word[0] == '!':
            potential_command = first_word[1:].lower()
        else:
            return None
        if potential_command in self.sorted_methods['for_all'] or potential_command in self.sorted_methods['for_mods']:
            return [CommandTypes.HARDCODED, potential_command]
        db_result = db_session.query(models.Command).filter(models.Command.call == potential_command).all()
        if db_result:
            return [CommandTypes.DYNAMIC, db_result[0]]
        return None

    def _has_permission(self, user, user_is_mod, command):
        """
        Takes a message from the user, and a list which contains the
        command and where it's found, and a database session.
        Returns True or False depending on whether the user that
        sent the command has the authority to use that command
        """
        if command[0] == CommandTypes.HARDCODED:
            if command[1] in self.sorted_methods['for_all'] or (command[1] in self.sorted_methods['for_mods'] and user_is_mod):
                return True
        else:
            db_command = command[1]
            if bool(db_command.permissions) is False:
                return True
            elif user in [permission.user_entity for permission in db_command.permissions]:
                return True
        return False

    def _is_valid_message_type(self, command, message):
        if command[0] == CommandTypes.HARDCODED:
            if self.service.get_message_type(message) == 'PUBLIC':
                return command[1] not in self.sorted_methods['public_message_disallowed']
            elif self.service.get_message_type(message) == 'PRIVATE':
                return command[1] in self.sorted_methods['private_message_allowed']

    def _run_command(self, command, message, db_session):
        """
        If the command is a database command, send the response to the chat queue.
        Otherwise call the relevant function, supplying the message and db_session arguments as needed.
        """
        if command[0] == CommandTypes.DYNAMIC:
            db_command = command[1]
            self._add_to_chat_queue(db_command.response)
        else:
            method_command = command[1]
            kwargs = {}
            if 'message' in inspect.signature(getattr(self, method_command)).parameters:
                kwargs['message'] = message
            if 'db_session' in inspect.signature(getattr(self, method_command)).parameters:
                kwargs['db_session'] = db_session
            getattr(self, method_command)(**kwargs)

    @Utils._mod_only
    def stop_speaking(self):
        """
        Stops the bot from putting stuff in chat to cut down on bot spam.
        In long run, this should be replaced with rate limits.

        !stop_speaking
        """
        self.service.send_public_message("Okay, I'll shut up for a bit. !start_speaking when you want me to speak again.")
        self.allowed_to_chat = False

    @Utils._mod_only
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