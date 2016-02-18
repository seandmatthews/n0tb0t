import requests
import sqlalchemy
from sqlalchemy.orm import sessionmaker
import db
import os
import json
import gspread
import time
import random
import threading
import datetime
import pytz
import showerThoughtFetcher
import collections
from oauth2client.client import SignedJwtAssertionCredentials
from functools import wraps
from config import SOCKET_ARGS


# noinspection PyArgumentList,PyIncorrectDocstring
class Bot(object):
    def __init__(self, twitch_socket, group_chat_socket):

        self.ts = twitch_socket
        self.gcs = group_chat_socket

        self.sorted_methods = self._sort_methods()

        self.chat_message_queue = collections.deque()
        self.whisper_message_queue = collections.deque()

        self.cur_dir = os.path.dirname(os.path.realpath(__file__))
        self.Session = self._initialize_db(self.cur_dir)

        self.key_path = os.path.join(self.cur_dir, 'gspread test-279fb617abd8.json')
        with open(self.key_path) as kp:
            self.json_key = json.load(kp)
        self.scope = ['https://spreadsheets.google.com/feeds']
        self.credentials = SignedJwtAssertionCredentials(self.json_key['client_email'],
                                                         bytes(self.json_key['private_key'], 'utf-8'), self.scope)

        session = self.Session()
        self.guessing_enabled = bool(session.query(db.MiscValue).filter(db.MiscValue.name == 'guessing-enabled'))

        self.auto_quotes_timers = {}
        for auto_quote in session.query(db.AutoQuote).all():
            self._auto_quote(index=auto_quote.id, quote=auto_quote.quote, time=auto_quote.period)

        self.allowed_to_chat = True

        self.chat_thread = threading.Thread(target=self._process_chat_queue,
                                            kwargs={'chat_queue': self.chat_message_queue})
        self.chat_thread.daemon = True
        self.chat_thread.start()

        self.whisper_thread = threading.Thread(target=self._process_whisper_queue,
                                               kwargs={'whisper_queue': self.whisper_message_queue})
        self.whisper_thread.daemon = True
        self.whisper_thread.start()

    def _sort_methods(self):
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
            if callable(eval('self.' + item)):
                my_methods.append(item)

        # Sort all methods in self.my_methods into either the for_mods list
        # or the for_all list based on the function's _mods_only property
        for method in my_methods:
            try:
                if eval('self.' + method + '._mods_only'):
                    methods_dict['for_mods'].append(method)
            except AttributeError:
                methods_dict['for_all'].append(method)

        return methods_dict

    def _initialize_db(self, db_location):
        """
        Creates the database and domain model and Session Class
        """
        self.db_path = os.path.join(db_location, 'info.db')
        engine = sqlalchemy.create_engine('sqlite:///' + self.db_path)
        # noinspection PyPep8Naming
        Session = sessionmaker(bind=engine)
        db.Base.metadata.create_all(engine)
        return Session

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
        to the _send_message function. Then sleep for
        two seconds to stay below the twitch rate limit.
        """
        while self.allowed_to_chat:
            if len(chat_queue) > 0:
                self._send_message(chat_queue.pop())
                time.sleep(2)

    def _process_whisper_queue(self, whisper_queue):
        """
        If there are whispers in the queue that need
        to be sent, pop off the oldest one and pass it
        to the _send_whisper function. Then sleep for
        one second to stay below the twitch rate limit.
        """
        while True:
            if len(whisper_queue) > 0:
                whisper_tuple = (whisper_queue.pop())
                self._send_whisper(whisper_tuple[0], whisper_tuple[1])
                time.sleep(1)

    def _send_whisper(self, user, message):
        """
        Tries sending the message to the inteded user.
        Then the bot tries sending the message to itself
        to reveal a broken pipe error that stems from channel
        disconnection. In the event of a disconnection,
        reconnect and resend.
        """
        # TODO: Actually maintain a connection with the group chat server
        try:
            self.gcs.send_whisper(user, message)
            time.sleep(1)
            self.gcs.send_whisper(self.gcs.user, message)
        except BrokenPipeError:
            self.gcs.join_room()
            self.gcs.send_whisper(user, message)

    # useless abstractions are useless, but pretty        
    def _send_message(self, message):
        """
        Calls the socket function which
        sends the message to the irc chat.
        """
        self.ts.send_message(message)

    def _act_on(self, message):
        """
        Takes a message from a user.
        Looks at the message.
        Tries to extract a command from the message.
        Checks permissions for that command.
        Runs the command if the permissions check out.
        """
        if 'PING' in self.ts.get_human_readable_message(message):  # PING/PONG silliness
            print(self.ts.get_human_readable_message(message))
            self._add_to_chat_queue(self.ts.get_human_readable_message(message.replace('PING', 'PONG')))

        command = self._get_command(message)
        if command is not None:
            user = self.ts.get_user(message)
            if self._has_permission(user, command):
                self._run_command(command, message)
            else:
                self._add_to_whisper_queue(user,
                                           'Sorry {}, you\'re not authorized to use the command !{}'
                                           .format(user, command))

    def _get_command(self, message, db_session):
        """
        Takes a message from the user and a database session.
        Returns a list which contains the command and the place where it can be found.
        If it's a method, that place will be the key in the sorted_methods dictionary which
        has the corresponding list containing the command. Otherwise it will be the word 'Database'.
        """
        first_word = self.ts.get_human_readable_message(message).split(' ')[0]
        if len(first_word) > 1 and first_word[0] == '!':
            potential_command = first_word[0]
        else:
            return None
        if potential_command in self.sorted_methods['for_all']:
            return [potential_command, 'for_all']
        if potential_command in self.sorted_methods['for_mods']:
            return [potential_command, 'for_mods']

        db_results = db_session.query.filter(db.Command.call == potential_command).all()
        if db_results:
            return [potential_command, 'Database']
        return None

    def _has_permission(self, message, command, db_session):
        """
        Takes a message from the user, and a list which contains the
        command and where it's found, and a database session.
        Returns True or False depending on whether the user that
        sent the command has the authority to use that command
        """
        if command[1] == 'for_all':
            return True
        if command[1] == 'for_mods' and self.ts.check_mod(message):
            return True
        if command[1] == 'Database':
            commands = db_session.query(db.Command).all()

    def _run_command(self):
        pass

    def _get_mods(self):
        """
        Talks to twitch's API to look at all chatters currently in the channel.
        Returns a list of all moderators currently in the channel.
        """
        url = 'http://tmi.twitch.tv/group/user/{channel}/chatters'.format(channel=self.ts.channel)
        for attempt in range(5):
            try:
                r = requests.get(url)
                mods = r.json()['chatters']['moderators']
            except ValueError:
                continue
            else:
                return mods
        else:
            self._add_to_chat_queue(
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

    def _mod_only(func):
        """
        Redefines the method to work if the person trying to use the function is a moderator.
        Also set's the method's _mods_only property to True
        """

        @wraps(func)
        def new_func(self, message):
            if self.ts.check_mod(message):
                # noinspection PyCallingNonCallable
                func(self, message)
            else:
                self._add_to_chat_queue("Sorry {}, that's a mod only command".format(self.ts.get_user(message)))

        new_func._mods_only = True
        return new_func

    @_mod_only
    def stop_speaking(self):
        """
        Stops the bot from putting stuff in chat to cut down on bot spam.
        In long run, this should be replaced with rate limits.

        !stop_speaking
        """
        self._send_message("Okay, I'll shut up for a bit. !start_speaking when you want me to speak again.")
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

    def _auto_quote(self, index, quote, time):
        """
        Takes an index, quote and time in seconds.
        Starts a thread that waits the specified time, says the quote
        and starts another thread with the same arguments, ensuring
        that the quotes continue to be said forever or until they're stopped by the user.
        """
        key = 'AQ{}'.format(index)
        self.auto_quotes_timers[key] = threading.Timer(time, self._auto_quote,
                                                       kwargs={'index': index, 'quote': quote, 'time': time})
        self.auto_quotes_timers[key].start()
        self._add_to_chat_queue(quote)

    @_mod_only
    def start_auto_quotes(self, message):
        """
        Starts the bot spitting out auto quotes by calling the
        _auto_quote function on all quotes in the auto_quotes_file

        !start_auto_quotes
        """
        with open(self.auto_quotes_file) as aqf:
            self.auto_quotes_list = json.load(aqf)
        self.auto_quotes_timers = {}
        for index, quote_sub_list in enumerate(self.auto_quotes_list):
            quote = quote_sub_list[0]
            time = quote_sub_list[1]
            self._auto_quote(index=index, quote=quote, time=time)

    @_mod_only
    def stop_auto_quotes(self, message):
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
        Sends a series of whispers of all current auto quotes,
        each prefixed with their index.

        !show_auto_quotes
        """
        with open(self.auto_quotes_file) as aqf:
            self.auto_quotes_list = json.load(aqf)
        for index, aq in enumerate(self.auto_quotes_list):
            hr_index = index + 1
            msg = aq[0]
            user = self.ts.get_user(message)
            self._add_to_whisper_queue(user, '#{hr_index} {msg}'.format(hr_index=hr_index, msg=msg))

    @_mod_only
    def add_auto_quote(self, message):
        """
        Makes a new sentence that the bot periodically says.
        The first "word" after !add_auto_quote is the number of seconds
        in the interval for the bot to wait before saying the sentence again.
        Requires stopping and starting the auto quotes to take effect.

        !add_auto_quote 600 This is a rudimentary twitch bot.
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            delay = int(msg_list[1])
            quote = ' '.join(msg_list[2:])
            sub_list = [quote, delay]
            self.auto_quotes_list.append(sub_list)
            with open(self.auto_quotes_file, 'w') as aqf:
                aqf.write(json.dumps(self.auto_quotes_list))

    @_mod_only
    def delete_auto_quote(self, message):
        """
        Deletes a sentence that the bot periodically says.
        Takes a 1 indexed auto quote index.
        Requires stopping and starting the auto quotes to take effect.

        !delete_auto_quote 1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            if int(msg_list[1]) <= len(self.auto_quotes_list):
                index = int(msg_list[1]) - 1
                del self.auto_quotes_list[index]
                with open(self.auto_quotes_file, 'w') as aqf:
                    aqf.write(json.dumps(self.auto_quotes_list))

    @_mod_only
    def add_command(self, message):
        """
        Adds a new command.
        The first word after !add_command with an exclamation mark is the command.
        The rest of the sentence is the reply.
        Optionally takes the names of twitch users before the command.
        This would make the command only available to those users.

        !add_command !test This is a test.
        !add_user_command TestUser1 TestUser2 !test_command This is a test
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        command_found = False
        for index, word in enumerate(msg_list[1:]):  # exclude !add_user_command
            if word[0] == '!':
                command = word
                users = msg_list[1:index + 1]
                response = ' '.join(msg_list[index + 2:])
                command_found = True
        if command_found and (command[1:] in self.user_commands_dict or command in self.commands_dict):
            self._add_to_whisper_queue(user, 'Sorry, that command already exists. Please delete it first.')
        else:
            if command_found and len(users) != 0:
                users = [user.lower() for user in users]
                key = command[1:]  # exclude the exclamation mark
                value = [users, response]
                self.user_commands_dict[key] = value
                with open(self.user_commands_file, 'w') as cf:
                    cf.write(json.dumps(self.user_commands_dict))
                self._add_to_whisper_queue(user, 'Command added.')
            elif command_found and len(users) == 0:
                command = msg_list[1]
                response = ' '.join(msg_list[2:])
                key = command[1:]  # exclude the exclamation mark
                value = response
                self.commands_dict[key] = value
                with open(self.commands_file, 'w') as cf:
                    cf.write(json.dumps(self.commands_dict))
                self._add_to_whisper_queue(user, 'Command added.')
            else:
                self._add_to_whisper_queue(user, 'Sorry, the command needs to have an ! in it.')

    @_mod_only
    def delete_command(self, message):
        """
        Removes a user created command.
        Takes the name of the command.

        !delete_command !test
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        command = msg_list[1][1:]
        if command in self.commands_dict:
            del self.commands_dict[command]
            with open(self.commands_file, 'w') as cf:
                cf.write(json.dumps(self.commands_dict))
            self._add_to_whisper_queue(user, 'Command deleted.')
        elif command in self.user_commands_dict:
            del self.user_commands_dict[command]
            with open(self.user_commands_file, 'w') as cf:
                cf.write(json.dumps(self.user_commands_dict))
            self._add_to_whisper_queue(user, 'Command deleted.')
        else:
            self._add_to_whisper_queue(user, 'Sorry, that command doesn\'t seem to exist.')

    @_mod_only
    def show_deletable_commands(self, message):
        """
        Sends a whisper containing all user
        created commands, including specific
        user commands.

        !show_deletable_commands
        """
        user = self.ts.get_user(message)
        commands_str = "Command List: "
        for command in self.commands_dict:
            commands_str += "!{} ".format(command)
        for command in self.user_commands_dict:
            commands_str += "!{} ".format(command)
        self._add_to_whisper_queue(user, commands_str)

    def show_commands(self, message):
        """
        Sends a whisper containing all commands
        that are available to all users

        !show_commands
        """
        user = self.ts.get_user(message)
        commands_str = "Regular Command List: "
        regular_commands_str = "Dynamic/User Command List: "
        mod_commands_str = "Mod Command List: "
        for func in self.sorted_methods['for_all']:
            commands_str += "!{} ".format(func)
        self._add_to_whisper_queue(user, commands_str)
        for command in self.commands_dict:
            regular_commands_str += "!{} ".format(command)
        for command in self.user_commands_dict:
            if user in self.user_commands_dict[command][0]:
                regular_commands_str += "!{} ".format(command)
        self._add_to_whisper_queue(user, regular_commands_str)
        if self.ts.check_mod(message):
            for func in self.for_mods:
                mod_commands_str += "!{} ".format(func)
            self._add_to_whisper_queue(user, mod_commands_str)

    # def show_mod_commands(self, message):
    #     """
    #     Sends a whisper containing all commands
    #     that are available to mods
    #
    #     !show_mod_commands
    #     """
    #     user = self.ts.get_user(message)
    #     commands_str = "Command List: "
    #     for func in self.for_mods:
    #         commands_str += "!{} ".format(func)
    #     self._add_to_whisper_queue(user, commands_str)

    def add_quote(self, message, db_session):
        """
        Adds a quote to the quotes file.

        !add_quote This bot is very suspicious.
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        quote = ' '.join(msg_list[1:])
        quote_obj = db.Quote(quote=quote)
        db_session.add(quote_obj)
        self._add_to_whisper_queue(user, 'Quote added as quote #{}.'.format(db_session.query(db.User).count()))

    @_mod_only
    def delete_quote(self, message, db_session):
        """
        Removes a user created quote.
        Takes a 1 indexed quote index.

        !delete_quote 1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        user = self.ts.get_user(message)
        if len(msg_list) > 1 and msg_list[1].isdigit() and int(msg_list[1] > 0):
            quotes = db_session.query(db.Quote).all()
            if int(msg_list[1]) <= len(quotes):
                index = int(msg_list[1]) - 1
                db_session.delete(quotes[index])
                self._add_to_whisper_queue(user, 'Quote deleted.')
            else:
                self._add_to_chat_queue('Sorry, that\'s not a quote that can be deleted.')

    def show_quotes(self, message, db_session):
        """
        Sends a series of whispers to the user invoking a command.
        Each one contains a quote from the quote file, prefixed by the index of the quote.

        !show_quotes
        """
        # TODO: Stick the quotes in a google spreadsheet or something
        user = self.ts.get_user(message)
        quotes = db_session.query(db.Quote).all()
        for index, quote in enumerate(quotes):
            self._add_to_whisper_queue(user, '#{}, {}'.format(index + 1, quote))

    def quote(self, message, db_session):
        """
        Displays a quote in chat. Takes a 1 indexed quote index.
        If no index is specified, displays a random quote.

        !quote 5
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            if int(msg_list[1]) > 0:
                index = int(msg_list[1]) - 1
                quotes = db_session.query(db.Quote).all()
                if index < len(quotes)-1:
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
    def SO(self, message):
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

    def shower_thought(self, message):
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

    def uptime(self, message):
        """
        Sends a message to stream saying how long the caster has been streaming for.
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
            gc = gspread.authorize(self.credentials)
            sh = gc.open("Highlight list")
            ws = sh.worksheet('Sheet1')
            records = ws.get_all_records()  # Doesn't include the first row
            next_row = len(records) + 2
            ws.update_cell(next_row, 1, user)
            ws.update_cell(next_row, 2, str(start_time_est)[:-6])
            ws.update_cell(next_row, 3, time_str)
            ws.update_cell(next_row, 4, user_note)
            self._add_to_chat_queue('The highlight has been added to the spreadsheet for review.')

    def enter_contest(self, message, db_session):
        """
        Adds the user to the file of contest entrants
        or informs them that they're already entered if they've already
        entered since the last time the entrants were cleared.

        !enter_contest
        """
        username = self.ts.get_user(message)
        user = db_session.query(db.User).filter(db.User.name == username)
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
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'guess-total-enabled')
        mv_obj.value = True
        self._add_to_chat_queue("Guessing is now enabled.")

    @_mod_only
    def disable_guessing(self, db_session):
        """
        Stops users from guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !disable_guessing
        """
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'guess-total-enabled')
        mv_obj.value = True
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
        if bool(db_session.query(db.MiscValue).filter(db.MiscValue.name == 'guessing-enabled').one().value):
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
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'guess-total-enabled')
        mv_obj.value = True
        self._add_to_chat_queue("Guessing for the total amount of deaths is now enabled.")

    @_mod_only
    def disable_guesstotal(self, db_session):
        """
        Disables guessing for the total number of deaths for the run.

        !disable_guesstotal
        """
        mv_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'guess-total-enabled')
        mv_obj.value = False
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
        if bool(db_session.query(db.MiscValue).filter(db.MiscValue.name == 'guess-total-enabled').one().value):
            msg_list = self.ts.get_human_readable_message(message).split(' ')
            if len(msg_list) > 1:
                guess = msg_list[1]
                if guess.isdigit() and int(guess) > 0:
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

    @_mod_only
    def show_guesses(self, db_session):
        """
        Clears all guesses out of the google
        spreadsheet, then repopulate it from
        the database.

        !show_guesses
        """
        self._add_to_chat_queue(
            "Hello friends, formatting the google sheet with the latest information about all the guesses might take a little bit. I'll let you know when it's done.")
        gc = gspread.authorize(self.credentials)
        sh = gc.open("Dark Souls Guesses")
        ws = sh.worksheet('Dark Souls Guesses')
        all_users = db_session.query(db.User).all()
        users = [user for user in all_users if user.current_guess is not None or user.total_guess is not None]
        for i in range(1, len(users) + 10):
            ws.update_acell('A{}'.format(i), '')
            ws.update_acell('B{}'.format(i), '')
            ws.update_acell('C{}'.format(i), '')
        ws.update_acell('A1', 'User')
        ws.update_acell('B1', 'Current Guess')
        ws.update_acell('B1', 'Total Guess')
        for index, user in enumerate(users):
            row_num = index + 3
            ws.update_acell('A{}'.format(row_num), user.name)
            ws.update_acell('B{}'.format(row_num), user.current_guess)
            ws.update_acell('C{}'.format(row_num), user.total_guess)
        self._add_to_chat_queue(
            "Hello again friends. I've updated a google spread sheet with the latest guess information. Here's a link. https://docs.google.com/spreadsheets/d/1T6mKxdnyHAFU6QdcUYYE0hVrzJw8MTCgFYZu8K4MBzk/")

    @_mod_only
    def set_deaths(self, message):
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
                self._set_deaths(deaths_num)
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
    def set_total_deaths(self, message):
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
                self._set_total_deaths(total_deaths_num)
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
    def add_death(self, message):
        """
        Adds one to both the current sequence
        and total death counters.

        !add_death
        """
        user = self.ts.get_user(message)
        deaths = int(self._get_current_deaths())
        total_deaths = int(self._get_total_deaths())
        deaths += 1
        total_deaths += 1
        self._set_deaths(str(deaths))
        self._set_total_deaths(str(total_deaths))
        whisper_msg = 'Current Deaths: {}, Total Deaths: {}'.format(deaths, total_deaths)
        self._add_to_whisper_queue(user, whisper_msg)

    @_mod_only
    def clear_deaths(self):
        """
        Sets the number of deaths for the current
        stage of the run to 0. Used after progressing
        to the next stage of the run.

        !clear_deaths
        """
        self._set_deaths(0)
        self.show_deaths()

    def show_deaths(self):
        """
        Sends the current and total death
        counters to the chat.

        !show_deaths
        """
        deaths = self._get_current_deaths()
        total_deaths = self._get_total_deaths()
        self._add_to_chat_queue("Current Boss Deaths: {}, Total Deaths: {}".format(deaths, total_deaths))

    def show_winner(self, db_session):
        """
        Sends the name of the currently winning
        player to the chat. Should be used after
        stage completion to display who won.

        !show_winner
        """
        winners_list = []
        deaths = self._get_current_deaths()
        last_winning_guess = -1
        users = db_session.query(db.User).filter(db.User.current_guess.isnot(None)).all()
        for user in users:
            if int(user.current_guess) <= int(
                    deaths):  # If your guess was over the number of deaths you lose due to the price is right rules.
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

    def _set_current_guess(user, guess, db_session):
        """
        Takes a user and a guess.
        Adds the user and their guess
        to the users table.
        """
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
        db_user = db.User(name=user)
        db_session.add(db_user)
        db_user.total_guess = guess

    def _get_current_deaths(self, db_session):
        """
        Returns the current number of deaths
        for the current leg of the run.
        """
        deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'current-deaths')
        return deaths_obj.value

    def _get_total_deaths(self, db_session):
        """
        Returns the total deaths that
        have occurred in the run so far.
        """
        total_deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'total-deaths')
        return total_deaths_obj.value

    def _set_deaths(self, deaths_num, db_session):
        """
        Takes a string for the number of deaths.
        Updates the miscellaneous values table.
        """
        deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'current-deaths')
        deaths_obj.value = deaths_num

    def _set_total_deaths(self, total_deaths_num, db_session):
        """
        Takes a string for the total number of deaths.
        Updates the miscellaneous values table.
        """
        total_deaths_obj = db_session.query(db.MiscValue).filter(db.MiscValue.name == 'total-deaths')
        total_deaths_obj.value = total_deaths_num
