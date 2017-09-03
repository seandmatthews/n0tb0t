import collections
import importlib
import inspect
import os
import threading
import time
from enum import Enum, auto

import sqlalchemy
from pyshorteners import Shortener
from sqlalchemy.orm import sessionmaker

import PythonCore.src.google_auth as google_auth
import PythonCore.src.models as models
import PythonCore.src.utils as utils
from PythonCore.src.message import Message


def collect_mixin_classes(directory_name):
    """
    Collect all the Mixin classes from all the modules in the specified directory
    Store these class objects in a mixin_classes list
    Return that list so that the bot can inherit from them
    """
    print(F'Loading Modules from {directory_name}')
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    modules_dir = os.path.join(cur_dir, directory_name)
    module_files = [f for f in os.listdir(modules_dir) if os.path.isfile(os.path.join(modules_dir, f))]
    mixin_classes = []

    for file in module_files:
        if file != '__init__.py' and file[-3:] == '.py':
            # Take these .py files and import them, turning them into module objects
            imported = importlib.import_module(f'src.{directory_name}.{file[:-3]}')
            for item in dir(imported):
                if item[0] != '_':
                    if isinstance(getattr(imported, item), type) and 'Mixin' in item:
                        mixin_classes.append(getattr(imported, item))
                        print(item)
    return mixin_classes


all_mixin_classes = []
all_mixin_classes += collect_mixin_classes('core_modules')
all_mixin_classes += collect_mixin_classes('streamer_specific_modules')


class CommandTypes(Enum):
    HARDCODED = auto()
    DYNAMIC = auto()


class Bot(*all_mixin_classes):
    def __init__(self, service, bot_info, bitly_access_token, top_level_dir, data_dir):
        self.service = service
        self.info = bot_info

        self.sorted_methods = self._sort_methods()

        # Most functions run in the main thread, but we can put slow ones here
        self.command_queue = collections.deque()

        self.public_message_queue = collections.deque()
        self.private_message_queue = collections.deque()

        self.shortener = Shortener('Bitly', bitly_token=bitly_access_token)

        self.Session = self._initialize_db(data_dir)
        db_session = self.Session()

        self.credentials = google_auth.get_credentials(credentials_parent_dir=top_level_dir, client_secret_dir=top_level_dir)

        self.starting_spreadsheets_list = []
        self.spreadsheets = {}

        self.guessing_enabled = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled') == 'True'

        self.allowed_to_chat = True

        self.chat_thread = threading.Thread(target=self._process_chat_queue,
                                            kwargs={'chat_queue': self.public_message_queue})
        self.chat_thread.daemon = True
        self.chat_thread.start()

        self.whisper_thread = threading.Thread(target=self._process_whisper_queue,
                                               kwargs={'whisper_queue': self.private_message_queue})
        self.whisper_thread.daemon = True
        self.whisper_thread.start()

        self.command_thread = threading.Thread(target=self._process_command_queue,
                                               kwargs={'command_queue': self.command_queue})
        self.command_thread.daemon = True
        self.command_thread.start()

        # Run all the init methods of all the mixins that have them.
        # This currently doesn't use super because not all mixins have an init method that calls super
        # That would almost certainly break the method resolution order and cause things to fail.
        for mixin_class in all_mixin_classes:
            if getattr(mixin_class, '__init__', None):
                if callable(getattr(mixin_class, '__init__')):
                    mixin_class.__init__(self)

        print('Finding Google Sheets')
        for sheet in self.starting_spreadsheets_list:
            sheet_name = '{}-{}-{}'.format(bot_info['channel'], bot_info['user'], sheet)
            already_existed, spreadsheet_id = google_auth.ensure_file_exists(self.credentials, sheet_name)
            web_view_link = 'https://docs.google.com/spreadsheets/d/{}'.format(spreadsheet_id)
            sheet_tuple = (sheet_name, web_view_link)
            self.spreadsheets[sheet] = sheet_tuple
            if not already_existed:
                init_command = '_initialize_{}_spreadsheet'.format(sheet)
                getattr(self, init_command)(sheet_name)

        utils.add_to_public_chat_queue(self, f"{bot_info['user']} is online")

        active_auto_quotes = db_session.query(models.AutoQuote).filter(models.AutoQuote.active == True).all()
        for aaq in active_auto_quotes:
            self._create_timer_for_auto_quote_object(aaq)
        self.player_queue_credentials = None
        db_session.close()

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
        self.db_path = os.path.join(db_location, f'{channel}.db')
        engine = sqlalchemy.create_engine(f'sqlite:///{self.db_path}', connect_args={'check_same_thread': False})
        session_factory = sessionmaker(bind=engine)
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
            if self.service.get_message_content(message)[0] in ['/', '!']:
                user = self.service.get_message_display_name(message)
                utils.add_to_appropriate_chat_queue(self, message, "You see? This is why we can't have nice things.")
                utils.add_to_appropriate_chat_queue(self, message, f'!ban_roulette {user}')
                cheaty_message_object = Message(content=f'!ban_roulette {user}', is_mod=True)
                self.ban_roulette(cheaty_message_object)
            else:
                utils.add_to_appropriate_chat_queue(self, message, self.service.get_message_content(message).replace('PING', 'PONG'))

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
        if self.service.get_mod_status(message):
            return True
        if command[0] == CommandTypes.HARDCODED:
            if self.service.get_message_type(message) == 'PUBLIC':
                return command[1] not in self.sorted_methods['public_message_disallowed']
            elif self.service.get_message_type(message) == 'PRIVATE':
                return command[1] in self.sorted_methods['private_message_allowed']
        else:
            return self.service.get_message_type(message) == 'PUBLIC'

    def _run_command(self, command, message, db_session):
        """
        If the command is a database command, send the response to the chat queue.
        Otherwise call the relevant function, supplying the message and db_session arguments as needed.
        """
        if command[0] == CommandTypes.DYNAMIC:
            db_command = command[1]
            utils.add_to_appropriate_chat_queue(self, message, db_command.response)
        else:
            method_command = command[1]
            kwargs = {}
            if 'message' in inspect.signature(getattr(self, method_command)).parameters:
                kwargs['message'] = message
            if 'db_session' in inspect.signature(getattr(self, method_command)).parameters:
                kwargs['db_session'] = db_session
            getattr(self, method_command)(**kwargs)
