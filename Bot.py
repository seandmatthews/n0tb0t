import requests
import sqlite3
import os
import json
import gspread
from oauth2client.client import SignedJwtAssertionCredentials
import time
import random
import threading
import datetime
import pytz
import showerThoughtFetcher
import collections
import logging
from config import SOCKET_ARGS

class Bot(object):
    def __init__(self, ts, gcs):
        self.guessing_enabled = False
        self.ts = ts
        self.gcs = gcs

        # Collect all methods and properties of the object.
        # Add them to self.my_dir if they don't start with an _
        self.my_dir = [item for item in self.__dir__() if item[0] != '_']
        self.my_methods = []
        self.for_mods = []
        self.for_all = []

        # Look at all the items in self.my_dir
        # Check to see if they're callable.
        # If they are add them to self.my_methods
        for item in self.my_dir:
            if callable(eval('self.' + item)):
                self.my_methods.append(item)

        # Sort all methods in self.my_methods into either the for_mods list
        # or the for_all list based on the function's _mods_only property
        for method in self.my_methods:
            try:
                if eval('self.' + method + '._mods_only'):
                    self.for_mods.append(method)
            except AttributeError:
                self.for_all.append(method)
                
        self.chat_message_queue = collections.deque()
        self.whisper_message_queue = collections.deque()

        self.cur_dir = os.path.dirname(os.path.realpath(__file__))

        self.key_path = os.path.join(self.cur_dir, 'gspread test-279fb617abd8.json')
        with open(self.key_path) as kp:
                self.json_key = json.load(kp)
        self.scope = ['https://spreadsheets.google.com/feeds']
        self.credentials = SignedJwtAssertionCredentials(self.json_key['client_email'],
                                                         bytes(self.json_key['private_key'], 'utf-8'), self.scope)
        
        self.misc_values_file = os.path.join(self.cur_dir, 'misc-values.json')
        
        self.commands_file = os.path.join(self.cur_dir, 'commands.json')
        with open(self.commands_file) as cf:
            self.commands_dict = json.load(cf)

        self.user_commands_file = os.path.join(self.cur_dir, 'user-commands.json')
        with open(self.user_commands_file) as ucf:
            self.user_commands_dict = json.load(ucf)

        self.quotes_file = os.path.join(self.cur_dir, 'quotes.json')
        with open(self.quotes_file) as qf:
            self.quotes_list = json.load(qf)
            
        self.users_contest_list_file = os.path.join(self.cur_dir, 'users-contest-list.json')
        with open(self.users_contest_list_file) as uclf:
            self.users_contest_list = json.load(uclf)

        self.auto_quotes_file = os.path.join(self.cur_dir, 'auto-quotes.json')
        with open(self.auto_quotes_file) as aqf:
            self.auto_quotes_list = json.load(aqf)
        self.auto_quotes_timers = {}
        for index, quote_sub_list in enumerate(self.auto_quotes_list):
            quote = quote_sub_list[0]
            time = quote_sub_list[1]
            self._auto_quote(index=index, quote=quote, time=time)

        self.db_path = os.path.join(self.cur_dir, 'DarkSouls.db')
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''CREATE TABLE IF NOT EXISTS USERS
            (ID INTEGER PRIMARY KEY AUTOINCREMENT,
            USER           CHAR(50) NOT NULL,
            GUESS          INTEGER,
            GUESSTOTAL     INTEGER,
            POINTS         INTEGER);''')
        self.conn.commit()
        self.conn.close()

        self.allowed_to_chat = True

        self.chat_thread = threading.Thread(target=self._process_chat_queue, kwargs={'chat_queue': self.chat_message_queue})
        self.chat_thread.daemon = True
        self.chat_thread.start()

        self.whisper_thread = threading.Thread(target=self._process_whisper_queue, kwargs={'whisper_queue': self.whisper_message_queue})
        self.whisper_thread.daemon = True
        self.whisper_thread.start()

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
        Looks at the first word in the message.
        If that word starts with an exclamation point
        and the rest of the word is one of the methods in this
        class, it calls that function. If that word is a key
        in the commands dictionary. Send the corresponding string
        to the chat queue.
        """
        if 'PING' in self.ts.get_human_readable_message(message): # PING/PONG silliness
        	print(self.ts.get_human_readable_message(message))
        	self._add_to_chat_queue(self.ts.get_human_readable_message(message.replace('PING', 'PONG')))

        fword = self.ts.get_human_readable_message(message).split(' ')[0]
        user = self.ts.get_user(message)
        if len(fword) > 1 and fword[0] == '!':
            if fword[1:] in self.my_methods:
                eval('self.' + fword[1:] + '(message)')
            elif fword[1:] in self.commands_dict:
                self._add_to_chat_queue(self.commands_dict[fword[1:]])
            elif fword[1:] in self.user_commands_dict:
                if user in self.user_commands_dict[fword[1:]][0]:
                    self._add_to_chat_queue(self.user_commands_dict[fword[1:]][1])

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
            except ValueError as e:
                continue
            else:
                return mods
        else:
            self._add_to_chat_queue("Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

        

    def _mod_only(func):
        """
        Redefines the method to work if the person trying to use the function is a moderator.
        Also set's the method's _mods_only property to True
        """
        def new_func(self, message):
            if self.ts.check_mod(message):
                func(self, message)
            else:
                self._add_to_chat_queue("Sorry {}, that's a mod only command".format(self.ts.get_user(message)))
        new_func.__name__ = func.__name__
        new_func._mods_only = True
        return new_func

    @_mod_only
    def stop_speaking(self, message):
        """
        Stops the bot from putting stuff in chat to cut down on bot spam.
        In long run, this should be replaced with rate limits.

        !stop_speaking
        """
        self._send_message("Okay, I'll shut up for a bit. !start_speaking when you want me to speak again.")
        self.allowed_to_chat = False

    @_mod_only
    def start_speaking(self, message):
        """
        Allows the bot to start speaking again.

        !start_speaking
        """
        self.allowed_to_chat = True
        self.chat_message_queue.clear()
        self.chat_thread = threading.Thread(target=self._process_chat_queue, kwargs={'chat_queue': self.chat_message_queue})
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
        self.auto_quotes_timers[key] = threading.Timer(time, self._auto_quote, kwargs={'index': index,'quote': quote, 'time': time})
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
        for index, word in enumerate(msg_list[1:]): # exclude !add_user_command
            if word[0] == '!':
                command = word
                users = msg_list[1:index+1]
                response = ' '.join(msg_list[index+2:])
                command_found = True
        if command_found and (command[1:] in self.user_commands_dict or command in self.commands_dict):
            self._add_to_whisper_queue(user, 'Sorry, that command already exists. Please delete it first.')
        else:
            if command_found and len(users) != 0:
                users = [user.lower() for user in users]
                key = command[1:] # exclude the exclamation mark
                value = [users, response]
                self.user_commands_dict[key] = value
                with open(self.user_commands_file, 'w') as cf:
                    cf.write(json.dumps(self.user_commands_dict))
                self._add_to_whisper_queue(user, 'Command added.')
            elif command_found and len(users) == 0:
                command = msg_list[1]
                response = ' '.join(msg_list[2:])
                key = command[1:] # exclude the exclamation mark
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
        for func in self.for_all:
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

    def add_quote(self, message):
        """
        Adds a quote to the quotes file.

        !add_quote This bot is very suspicious.
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        quote = ' '.join(msg_list[1:])
        self.quotes_list.append(quote)
        with open(self.quotes_file, 'w') as qf:
            qf.write(json.dumps(self.quotes_list))
        self._add_to_whisper_queue(user, 'Quote added as quote #{}.'.format(len(self.quotes_list)))

    @_mod_only
    def delete_quote(self, message):
        """
        Removes a user created quote.
        Takes a 1 indexed quote index.

        !delete_quote 1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        user = self.ts.get_user(message)
        if len(msg_list) > 1 and msg_list[1].isdigit():
            if int(msg_list[1]) <= len(self.quotes_list):
                index = int(msg_list[1]) - 1
                del self.quotes_list[index]
                with open(self.quotes_file, 'w') as cf:
                    cf.write(json.dumps(self.quotes_list))
                self._add_to_whisper_queue(user, 'Quote deleted.')
            else:
                self._add_to_chat_queue('Sorry, there aren\'t that many quotes. Use a lower number')

    def show_quotes(self, message):
        """
        Sends a series of whispers to the user invoking a command.
        Each one contains a quote from the quote file, prefixed by the index of the quote.

        !show_quotes
        """
        # TODO: Stick the quotes in a google spreadsheet or something
        user = self.ts.get_user(message)
        for index, quote in enumerate(self.quotes_list):
            self._add_to_whisper_queue(user, '#{}, {}'.format(index+1, quote))

    def quote(self, message):
        """
        Displays a quote in chat. Takes a 1 indexed quote index.
        If no index is specified, displays a random quote.

        !quote 5
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            if int(msg_list[1]) <= len(self.quotes_list):
                index = int(msg_list[1]) - 1
                self._add_to_chat_queue('#{} {}'.format(str(index+1), self.quotes_list[index]))
            else:
                 self._add_to_chat_queue('Sorry, there are only {} quotes.'.format(len(self.quotes_list)))
        else:
            random_quote_index = random.randrange(len(self.quotes_list))
            self._add_to_chat_queue('#{} {}'.format(str(random_quote_index+1), self.quotes_list[random_quote_index]))

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
                    shout_out_str = 'Friends, {channel} is worth a follow. They last played {game}. If that sounds appealing to you, check out {channel} at {url}! Tell \'em {I} sent you!'.format(channel=channel, game=game, url=channel_url, I=me)
                    self._add_to_chat_queue(shout_out_str)
                except requests.exceptions.HTTPError:
                    self._add_to_chat_queue('Hey {}, that\'s not a real streamer!'.format(user))
                    break
                except ValueError:
                    continue
                else:
                    break
            else:
                self._add_to_chat_queue("Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")
        else:
            self._add_to_chat_queue('Sorry {}, you need to specify a caster to shout out.'.format(user))
        
    def shower_thought(self, message):
        """
        Fetches the top shower thought from reddit in the last 24 hours and sends it to chat.

        !shower_thought
        """
        self._add_to_chat_queue(showerThoughtFetcher.main())

    def _get_live_time(self, message):
        """
        Uses the kraken API to fetch the start time of the current stream.
        Computes how long the stream has been running, returns that value in a dictionary.
        """
        user = self.ts.get_user(message)
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
            self._add_to_chat_queue("Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

    def uptime(self, message):
        """
        Sends a message to stream saying how long the caster has been streaming for.
        """
        time_dict = self._get_live_time(message)
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
        time_dict = self._get_live_time(message)
        if time_dict is not None:
            est_tz = pytz.timezone('US/Eastern')
            start_time_utc = time_dict['stream_start']
            start_time_est = est_tz.normalize(start_time_utc.replace(tzinfo=pytz.utc).astimezone(est_tz))
            time_str = 'Approximately {hours}, {minutes} and {seconds} into the stream.'.format(
                    hours=time_dict['hour'], minutes=time_dict['minute'], seconds=time_dict['second'])
            gc = gspread.authorize(self.credentials)
            sh = gc.open("Highlight list")
            ws = sh.worksheet('Sheet1')
            records = ws.get_all_records() # Doesn't include the first row
            next_row = len(records) + 2
            ws.update_cell(next_row, 1, user)
            ws.update_cell(next_row, 2, str(start_time_est)[:-6])
            ws.update_cell(next_row, 3, time_str)
            ws.update_cell(next_row, 4, user_note)
            self._add_to_chat_queue('The highlight has been added to the spreadsheet for review.')

    def enter_contest(self, message):
        """
        Adds the user to the file of contest entrants
        or informs them that they're already entered if they've already
        entered since the last time the entrants were cleared.

        !enter_contest
        """
        user = self.ts.get_user(message)
        if user not in self.users_contest_list:
            self.users_contest_list.append(user)
            with open(self.users_contest_list_file, 'w') as uclf:
                uclf.write(json.dumps(self.users_contest_list))
            self._add_to_whisper_queue(user, 'You\'re entered into the contest!')
        else:
            self._add_to_whisper_queue(user, 'You\'re already entered into the contest, you can\'t enter again.')
        
    @_mod_only
    def show_contest_winner(self, message):
        """
        Selects a contest entrant at random.
        Sends their name to the chat.

        !show_contest_winner
        """
        if len(self.users_contest_list) > 0:
            winner = random.choice(self.users_contest_list)
            self._add_to_chat_queue('The winner is {}!'.format(winner))
        else:
            self._add_to_chat_queue('There are currently no entrants for the contest.')
    @_mod_only
    def clear_contest_entrants(self, message):
        """
        Sets the entrants list to be an empty list and then writes
        that to the entrants file.

        !clear_contest_entrants
        """
        self.users_contest_list = []
        with open(self.users_contest_list_file, 'w') as uclf:
            uclf.write(json.dumps(self.users_contest_list))
        self._add_to_chat_queue("Contest entrants cleared.")        
        
    @_mod_only
    def enable_guessing(self, message):
        """
        Allows users to guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !enable_guessing
        """
        self.guessing_enabled = True
        self._add_to_chat_queue("Guessing is now enabled.")

    @_mod_only
    def disable_guessing(self, message):
        """
        Stops users from guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !disable_guessing
        """
        self.guessing_enabled = False
        self._add_to_chat_queue("Guessing is now disabled.")

    def guess(self, message):
        """
        Updates the database with a user's guess
        or informs the user that their guess
        doesn't fit the acceptable parameters
        or that guessing is disabled for everyone.

        !guess 50
        """
        user = self.ts.get_user(message)
        if self.guessing_enabled:
            msg_list = self.ts.get_human_readable_message(message).split(' ')
            if len(msg_list) > 1:
                guess = msg_list[1]
            else:
                self._add_to_whisper_queue(user, "Sorry {}, !guess must be followed by a non-negative integer.".format(user))
                if guess.isdigit() and int(guess) >= 0:
                    results = self._check_for_user(user)
                    if results:
                        self._update_guess(user, guess)
                        self._add_to_whisper_queue(user, "{} your guess has been recorded.".format(user))
                    else:
                        self._insert_guess(user, guess)
                        self._add_to_whisper_queue(user, "{} your guess has been recorded.".format(user))
                else:
                    self._add_to_whisper_queue(user, "Sorry {}, that's not a non-negative integer.".format(user))
        else:
            self._add_to_whisper_queue(user, "Sorry {}, guessing is disabled.".format(user))

    @_mod_only
    def enable_guesstotal(self, message):
        """
        Enables guessing for the total number of deaths for the run.
        Modifies the value associated with the guess-total-enabled key
        in the miscellaneous values dictionary and writes it to the json file.

        !enable_guesstotal
        """
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['guess-total-enabled'] = True
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))
        self._add_to_chat_queue("Guessing for the total amount of deaths is now enabled.")

    @_mod_only
    def disable_guesstotal(self, message):
        """
        Disables guessing for the total number of deaths for the run.
        Modifies the value associated with the guess-total-enabled key
        in the miscellaneous values dictionary and writes it to the json file.

        !disable_guesstotal
        """
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['guess-total-enabled'] = False
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))
        self._add_to_chat_queue("Guessing for the total amount of deaths is now disabled.")

    def guesstotal(self, message):
        """
        Updates the database with a user's guess
        for the total number of deaths in the run
        or informs the user that their guess
        doesn't fit the acceptable parameters
        or that guessing is disabled for everyone.

        !guesstotal 50
        """
        user = self.ts.get_user(message)
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        if misc_values_dict['guess-total-enabled'] is True:
            msg_list = self.ts.get_human_readable_message(message).split(' ')
            if len(msg_list) > 1:
                guess = msg_list[1]
                if guess.isdigit() and int(guess) > 0:
                    results = self._check_for_user(user)
                    if results:
                        self._update_guesstotal(user, guess)
                        self._add_to_whisper_queue(user, "{} your guess has been recorded.".format(user))
                    else:
                        self._insert_guesstotal(user, guess)
                        self._add_to_whisper_queue(user, "{} your guess has been recorded.".format(user))
                else:
                    self._add_to_whisper_queue(user, "Sorry {}, that's not a non-negative integer.".format(user))
            else:
                self._add_to_whisper_queue(user, "Sorry {}, you need to include a number after your guess.".format(user))
        else:
            self._add_to_whisper_queue(user, "Sorry {}, guessing for the total number of deaths is disabled.".format(user))
            
    @_mod_only
    def clear_guesses(self, message):
        """
        Clear all guesses so that users
        can guess again for the next segment
        of the run.

        !clear_guesses
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        UPDATE USERS SET GUESS=''
        ''')
        self.conn.commit()
        self.conn.close()
        self._add_to_chat_queue("Guesses have been cleared.")

    @_mod_only
    def show_guesses(self, message):
        """
        Clears all guesses out of the google
        spreadsheet, then repopulate it from
        the database.

        !show_guesses
        """
        # TODO: Use a separate thread to handle the spreadsheet so the bot can continue to respond to requests
        # Also perhaps try to rework how the spreadsheet is cleared to do it all at once instead of 1 cell at a time.
        self._add_to_chat_queue("Hello friends, formatting the google sheet with the latest information about all the guesses might take a little bit. I'll let you know when it's done.")
        gc = gspread.authorize(self.credentials)
        sh = gc.open("Dark Souls Guesses")
        ws = sh.worksheet('Dark Souls Guesses')
        for i in range(1, len(self._get_all_users()) + 10):
            ws.update_acell('A{}'.format(i), '')
            ws.update_acell('B{}'.format(i), '')        
        ws.update_acell('A1', 'User')
        ws.update_acell('B1', 'Guess')
        guess_rows = [row for row in self._get_all_users() if bool(row[2]) is not False]
        for index, row in enumerate(guess_rows):
            row_num = index + 3
            ws.update_acell('A{}'.format(row_num), row[1])
            ws.update_acell('B{}'.format(row_num), row[2])
        self._add_to_chat_queue("Hello again friends. I've updated a google spread sheet with the latest guess information. Here's a link. https://docs.google.com/spreadsheets/d/1T6mKxdnyHAFU6QdcUYYE0hVrzJw8MTCgFYZu8K4MBzk/")

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
                self._add_to_whisper_queue(user, 'Sorry {}, !set_deaths should be followed by a non-negative integer'.format(user))
        else:
            self._add_to_whisper_queue(user, 'Sorry {}, !set_deaths should be followed by a non-negative integer'.format(user))


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
                self._add_to_whisper_queue(user, 'Sorry {}, !set_total_deaths should be followed by a non-negative integer'.format(user))
        else:
            self._add_to_whisper_queue(user, 'Sorry {}, !set_total_deaths should be followed by a non-negative integer'.format(user))

    @_mod_only
    def add_death(self, message):
        """
        Adds one to both the current sequence
        and total death counters.

        !add_death
        """
        user = self.ts.get_user(message)
        deaths = int(self._get_deaths())
        total_deaths = int(self._get_total_deaths())
        deaths += 1
        total_deaths += 1
        self._set_deaths(str(deaths))
        self._set_total_deaths(str(total_deaths))
        whisper_msg = 'Current Deaths: {}, Total Deaths: {}'.format(deaths, total_deaths)
        self._add_to_whisper_queue(user, whisper_msg)

    @_mod_only
    def clear_deaths(self, message):
        """
        Sets the number of deaths for the current
        stage of the run to 0. Used after progressing
        to the next stage of the run.

        !clear_deaths
        """
        self._set_deaths(0)
        self.show_deaths(message)

    def show_deaths(self, message):
        """
        Sends the current and total death
        counters to the chat.

        !show_deaths
        """
        deaths = self._get_deaths()
        total_deaths = self._get_total_deaths()
        self._add_to_chat_queue("Current Boss Deaths: {}, Total Deaths: {}".format(deaths, total_deaths))

    def show_winner(self, message):
        """
        Sends the name of the currently winning
        player to the chat. Should be used after
        stage completion to display who won.

        !show_winner
        """
        winners_list = []
        deaths = self._get_deaths()
        last_winning_guess = -1
        guess_rows = [row for row in self._get_all_users() if bool(row[2]) is not False]
        for row in guess_rows:
            if int(row[2]) <= int(deaths): # If your guess was over the number of deaths you lose due to the price is right rules.
                if row[2] > last_winning_guess:
                    winners_list = [row[1]]
                    last_winning_guess = row[2]
                elif row[2] == last_winning_guess:
                    winners_list.append(row[1])
        if len(winners_list) == 1:
            winners_str = "The winner is {}.".format(winners_list[0])
        elif len(winners_list) > 1:
            winners_str = 'The winners are '
            for winner in winners_list[:-1]:
                winners_str += "{}, "
            winners_str = '{} and {}!'.format(winners_str[:-2], winners_list[-1])
        else:
            winners_str = 'You all gussed too high. You should have had more faith in Rizorty. Rizorty wins!'
        self._add_to_chat_queue(winners_str)

    def _check_for_user(self, user):
        """
        Attempts to retrieve a user from the database.
        """
        self.conn = sqlite3.connect(self.db_path)
        c = self.conn.cursor()
        stmt = c.execute('''
            SELECT * FROM USERS WHERE USER=?
            ''', (user,))
        results = stmt.fetchall()
        self.conn.commit()
        self.conn.close()
        return results

    def _get_all_users(self):
        """
        Return all users from the database.
        """
        self.conn = sqlite3.connect(self.db_path)
        c = self.conn.cursor()
        stmt = c.execute('''
            SELECT * FROM USERS
            ''')
        results = stmt.fetchall()
        self.conn.commit()
        self.conn.close()
        return results

    def _insert_guess(self, user, guess):
        """
        Takes a user and a guess.
        Adds the user and their guess
        to the users table.
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        INSERT INTO USERS (USER, GUESS)
        VALUES (?, ?)
        ''', (user, guess))
        self.conn.commit()
        self.conn.close()

    def _insert_guesstotal(self, user, guess):
        """
        Takes a user and a guess
        for the total number of deaths.
        Adds the user and their guess
        to the users table.
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        INSERT INTO USERS (USER, GUESSTOTAL)
        VALUES (?, ?)
        ''', (user, guess))
        self.conn.commit()
        self.conn.close()

    def _update_guess(self, user, guess):
        """
        Takes a user and a guess.
        Updates the users table.
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        UPDATE USERS SET GUESS=? WHERE USER=?
        ''', (guess, user))
        self.conn.commit()
        self.conn.close()

    def _update_guesstotal(self, user, guess):
        """
        Takes a user and a guess
        for the total number of deaths.
        Updates the users table.
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        UPDATE USERS SET GUESSTOTAL=? WHERE USER=?
        ''', (guess, user))
        self.conn.commit()
        self.conn.close()

    def _get_deaths(self):
        """
        Returns the current number of deaths
        for the current leg of the run.
        """
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        return misc_values_dict['deaths']

    def _get_total_deaths(self):
        """
        Returns the total deaths that
         have occurred in the run so far.
        """
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        return misc_values_dict['total-deaths']

    def _set_deaths(self, deaths_num):
        """
        Takes a string for the number of deaths.
        Updates the miscellaneous values file.
        """
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['deaths'] = deaths_num
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))

    def _set_total_deaths(self, total_deaths_num):
        """
        Takes a string for the total number of deaths.
        Updates the miscellaneous values file.
        """
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['total-deaths'] = total_deaths_num
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))