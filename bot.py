import irc_socket
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
import showerThoughtFetcher
import collections
from config import SOCKET_ARGS

class Bot(object):
    def __init__(self, ts, gcs):
        self.guessing_enabled = False
        self.ts = ts
        self.gcs = gcs
        self.my_dir = [item for item in self.__dir__() if item[0] != '_']
        self.my_funcs = []
        self.for_mods = []
        self.for_all = []
        for item in self.my_dir:
            if callable(eval('self.' + item)):
                self.my_funcs.append(item)
        
        for func in self.my_funcs:
            try:
                if eval('self.' + func + '._mods_only'):
                    self.for_mods.append(func)
            except AttributeError:
                self.for_all.append(func)
                
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
        
        chat_thread = threading.Thread(target=self._process_chat_queue, kwargs={'chat_queue': self.chat_message_queue})
        chat_thread.daemon = True
        chat_thread.start()

        whisper_thread = threading.Thread(target=self._process_whisper_queue, kwargs={'whisper_queue': self.whisper_message_queue})
        whisper_thread.daemon = True
        whisper_thread.start()

    def _add_to_chat_queue(self, message):
        self.chat_message_queue.appendleft(message)

    def _add_to_whisper_queue(self, user, message):
        whisper_tuple = (user, message)
        self.whisper_message_queue.appendleft(whisper_tuple)

    def _process_chat_queue(self, chat_queue):
        while True:
            if len(chat_queue) > 0:
                self._send_message(chat_queue.pop())
                time.sleep(2)

    def _process_whisper_queue(self, whisper_queue):
        while True:
            if len(whisper_queue) > 0:
                whisper_tuple = (whisper_queue.pop())
                self._send_whisper(whisper_tuple[0], whisper_tuple[1])
                time.sleep(1)

    def _send_whisper(self, user, message):
        try:
            self.gcs.send_whisper(user, message)
            time.sleep(1)
            self.gcs.send_whisper(self.gcs.user, message)
        except BrokenPipeError:
            self.gcs.join_room()
            self.gcs.send_whisper(user, message)

    # useless abstractions are useless, but pretty        
    def _send_message(self, message):
        self.ts.send_message(message)

    def _act_on(self, message):
        fword = self.ts.get_hr_message(message).split(' ')[0]
        if len(fword) > 1 and fword[0] == '!':
            if fword[1:] in self.my_funcs:
                eval('self.' + fword[1:] + '(message)')
            elif fword[1:] in self.commands_dict:
                self._add_to_chat_queue(self.commands_dict[fword[1:]])

    def _get_mods(self):
        url = 'http://tmi.twitch.tv/group/user/{channel}/chatters'.format(channel=self.ts.channel)
        r = requests.get(url)
        mods = r.json()['chatters']['moderators']
        return mods

    def _mod_only(func):
        def new_func(self, message):
            if self.ts.get_user(message) in self._get_mods():
                func(self, message)
            else:
                self._add_to_chat_queue("Sorry {}, that's a mod only command".format(self.ts.get_user(message)))
        new_func.__name__ = func.__name__
        new_func._mods_only = True
        return new_func

    def _auto_quote(self, index, quote, time):
        key = 'AQ{}'.format(index)
        self.auto_quotes_timers[key] = threading.Timer(time, self._auto_quote, kwargs={'index': index,'quote': quote, 'time': time})
        self.auto_quotes_timers[key].start()
        self._add_to_chat_queue(quote)

    @_mod_only
    def start_auto_quotes(self, message):
        with open(self.auto_quotes_file) as aqf:
            self.auto_quotes_list = json.load(aqf)
        self.auto_quotes_timers = {}
        for index, quote_sub_list in enumerate(self.auto_quotes_list):
            quote = quote_sub_list[0]
            time = quote_sub_list[1]
            self._auto_quote(index=index, quote=quote, time=time)

    @_mod_only
    def stop_auto_quotes(self, message):
        for AQ in self.auto_quotes_timers:
            self.auto_quotes_timers[AQ].cancel()
            time.sleep(1)
            self.auto_quotes_timers[AQ].cancel()
            
    def show_auto_quotes(self, message):
        with open(self.auto_quotes_file) as aqf:
            self.auto_quotes_list = json.load(aqf)
        for index, aq in enumerate(self.auto_quotes_list):
            hr_index = index + 1
            msg = aq[0]
            user = self.ts.get_user(message)
            self._add_to_whisper_queue(user, '#{hr_index} {msg}'.format(hr_index=hr_index, msg=msg))
            
    @_mod_only
    def add_auto_quote(self, message):
        msg_list = self.ts.get_hr_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            delay = int(msg_list[1])
            quote = ' '.join(msg_list[2:])
            sub_list = [quote, delay]
            self.auto_quotes_list.append(sub_list)
            with open(self.auto_quotes_file, 'w') as aqf:
                aqf.write(json.dumps(self.auto_quotes_list))

    @_mod_only
    def delete_auto_quote(self, message):
        msg_list = self.ts.get_hr_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            if int(msg_list[1]) <= len(self.auto_quotes_list):
                index = int(msg_list[1]) - 1
                del self.auto_quotes_list[index]
                with open(self.auto_quotes_file, 'w') as aqf:
                    aqf.write(json.dumps(self.auto_quotes_list))

    @_mod_only
    def newcommand(self, message):
        msg_list = self.ts.get_hr_message(message).split(' ')
        command = msg_list[1]
        new_list = self.ts.get_hr_message(message).split('{} '.format(command))
        key = command
        value = new_list[1]
        self.commands_dict[key] = value
        with open(self.commands_file, 'w') as cf:
            cf.write(json.dumps(self.commands_dict))

    @_mod_only
    def delete_command(self, message):
        user = self.ts.get_user(message)
        msg_list = self.ts.get_hr_message(message).split(' ')
        command = msg_list[1]
        try:
            del self.commands_dict[command]
            with open(self.commands_file, 'w') as cf:
                cf.write(json.dumps(self.commands_dict))
        except KeyError:
            self._add_to_whisper_queue(user, 'Sorry, that command can\'t be deleted.')

    def show_commands(self, message):
        user = self.ts.get_user(message)
        commands_str = "Command List: "
        for func in self.for_all:
            commands_str += "!{} ".format(func)
        for func in self.commands_dict:
            commands_str += "!{} ".format(func)
        self._add_to_whisper_queue(user, commands_str)

    def show_mod_commands(self, message):
        user = self.ts.get_user(message)
        commands_str = "Command List: "
        for func in self.for_mods:
            commands_str += "!{} ".format(func)
        self._add_to_whisper_queue(user, commands_str)

    @_mod_only
    def show_deletable_commands(self, message):
        user = self.ts.get_user(message)
        commands_str = "Command List: "
        for func in self.commands_dict:
            commands_str += "!{} ".format(func)
        self._add_to_whisper_queue(user, commands_str)

    def add_quote(self, message):
        msg_list = self.ts.get_hr_message(message).split(' ')
        quote = ' '.join(msg_list[1:])
        self.quotes_list.append(quote)
        with open(self.quotes_file, 'w') as qf:
            qf.write(json.dumps(self.quotes_list))

    @_mod_only
    def delete_quote(self, message):
        msg_list = self.ts.get_hr_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            if int(msg_list[1]) <= len(self.quotes_list):
                index = int(msg_list[1]) - 1
                del self.quotes_list[index]
                with open(self.quotes_file, 'w') as cf:
                    cf.write(json.dumps(self.quotes_list))
            else:
                self._add_to_chat_queue('Sorry, there aren\'t that many quotes. Use a lower number')

    def show_quotes(self, message):
        user = self.ts.get_user(message)
        for index, quote in enumerate(self.quotes_list):
            self._add_to_whisper_queue(user, '#{}, {}'.format(index+1, quote))

    def quote(self, message):
        msg_list = self.ts.get_hr_message(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit():
            if int(msg_list[1]) <= len(self.quotes_list):
                index = int(msg_list[1]) - 1
                self._add_to_chat_queue('#{} {}'.format(str(index+1), self.quotes_list[index]))
            else:
                 self._add_to_chat_queue('Sorry, there aren\'t that many quotes. Use a lower number')
        else:
            random_quote_index = random.randrange(len(self.quotes_list))
            self._add_to_chat_queue('#{} {}'.format(str(random_quote_index+1), self.quotes_list[random_quote_index]))

    @_mod_only
    def SO(self, message):
        user = self.ts.get_user(message)
        msg_list = self.ts.get_hr_message(message).split(' ')
        channel = msg_list[1]
        url = 'https://api.twitch.tv/kraken/channels/{channel}'.format(channel=channel.lower())
        r = requests.get(url)
        try:
            r.raise_for_status()
            game = r.json()['game']
            channel_url = r.json()['url']
            shout_out_str = 'Friends, {channel} is worth a follow. They last played {game}. If that sounds appealing to you, check out {channel} at {url} Tell \'em Riz sent you!'.format(channel=channel, game=game, url=channel_url)
            self._add_to_chat_queue(shout_out_str)
        except requests.exceptions.HTTPError:
            self._add_to_chat_queue('Hey {}, that\'s not a real streamer!'.format(user))
            
    def shower_thought(self, message):
        self._add_to_chat_queue(showerThoughtFetcher.main())

    def uptime(self, message):
        user = self.ts.get_user(message)
        channel = SOCKET_ARGS['channel']
        url = 'https://api.twitch.tv/kraken/streams/{}'.format(channel.lower())
        r = requests.get(url)
        try:
            r.raise_for_status()
            start_time_str = r.json()['stream']['created_at']
            start_time_dt = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%SZ')
            now_dt = datetime.datetime.utcnow()
            td = now_dt - start_time_dt
            hours, remainder = divmod(td.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours == 1:
                hours_end = 's'
            else:
                hours_end = ''
            if minutes == 1:
                minutes_end = 's'
            else:
                minutes_end = ''
            if seconds == 1:
                seconds_end = 's'
            else:
                seconds_end = ''
            uptime_str = 'The channel has been live for {hours} hour{he}, {minutes} minute{me} and {seconds} second{se}.'.format(
                hours=hours, he=hours_end, minutes=minutes, me=minutes_end, seconds=seconds, se=seconds_end)

            self._add_to_chat_queue(uptime_str)
        except requests.exceptions.HTTPError:
            self._add_to_chat_queue('Sorry {}, something seems to have gone wrong. I\'m having trouble querying the twitch api.'.format(user))
        except TypeError:
            self._add_to_chat_queue('Sorry, the channel doesn\'t seem to be live at the moment. Thus, no uptime can be produced')
            
    def enter_contest(self, message):
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
        if len(self.users_contest_list) > 0:
            winner = random.choice(self.users_contest_list)
            self._add_to_chat_queue('The winner is {}!'.format(winner))
        else:
            self._add_to_chat_queue('There are currently no entrants for the contest.')
    @_mod_only
    def clear_contest_entrants(self, message):
        self.users_contest_list = []
        with open(self.users_contest_list_file, 'w') as uclf:
            uclf.write(json.dumps(self.users_contest_list))        
        
    @_mod_only
    def enable_guessing(self, message):
        self.guessing_enabled = True
        self._add_to_chat_queue("Guessing is now enabled.")

    @_mod_only
    def disable_guessing(self, message):
        self.guessing_enabled = False
        self._add_to_chat_queue("Guessing is now disabled.")

    def guess(self, message):
        user = self.ts.get_user(message)
        if self.guessing_enabled:
            msg_list = self.ts.get_hr_message(message).split(' ')
            guess = msg_list[1]
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
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['guess-total-enabled'] = True
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))
        self._add_to_chat_queue("Guessing for the total amount of deaths is now enabled.")

    @_mod_only
    def disable_guesstotal(self, message):
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['guess-total-enabled'] = False
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))
        self._add_to_chat_queue("Guessing for the total amount of deaths is now disabled.")

    def guesstotal(self, message):
        user = self.ts.get_user(message)
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        if misc_values_dict['guess-total-enabled'] is True:
            msg_list = self.ts.get_hr_message(message).split(' ')
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
            self._add_to_whisper_queue(user, "Sorry {}, guessing for the total number of deaths is disabled.".format(user))
            
    @_mod_only
    def clear_guesses(self, message):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        UPDATE USERS SET GUESS=''
        ''')
        self.conn.commit()
        self.conn.close()
        self._add_to_chat_queue("Guesses have been cleared.")

    @_mod_only
    def show_guesses(self, message):
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
        user = self.ts.get_user(message)
        msg_list = self.ts.get_hr_message(message).split(' ')
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
        user = self.ts.get_user(message)
        msg_list = self.ts.get_hr_message(message).split(' ')
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
        self._set_deaths(0)
        self.show_deaths(message)

    def show_deaths(self, message):
        deaths = self._get_deaths()
        total_deaths = self._get_total_deaths()
        self._add_to_chat_queue("Current Boss Deaths: {}, Total Deaths: {}".format(deaths, total_deaths))

    def show_winner(self, message):
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
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        INSERT INTO USERS (USER, GUESS)
        VALUES (?, ?)
        ''', (user, guess))
        self.conn.commit()
        self.conn.close()

    def _insert_guesstotal(self, user, guess):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        INSERT INTO USERS (USER, GUESSTOTAL)
        VALUES (?, ?)
        ''', (user, guess))
        self.conn.commit()
        self.conn.close()

    def _update_guess(self, user, guess):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        UPDATE USERS SET GUESS=? WHERE USER=?
        ''', (guess, user))
        self.conn.commit()
        self.conn.close()

    def _update_guesstotal(self, user, guess):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
        UPDATE USERS SET GUESSTOTAL=? WHERE USER=?
        ''', (guess, user))
        self.conn.commit()
        self.conn.close()

    def _get_deaths(self):
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        return misc_values_dict['deaths']

    def _get_total_deaths(self):
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        return misc_values_dict['total-deaths']

    def _set_deaths(self, deaths_num):
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['deaths'] = deaths_num
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))

    def _set_total_deaths(self, total_deaths_num):
        with open(self.misc_values_file) as mvf:
             misc_values_dict = json.load(mvf)
        misc_values_dict['total-deaths'] = total_deaths_num
        with open(self.misc_values_file, 'w') as mvf:
            mvf.write(json.dumps(misc_values_dict))




TS = irc_socket.TwitchSocket(**SOCKET_ARGS)
GCS = irc_socket.GroupChatSocket(**SOCKET_ARGS)
bot = Bot(TS, GCS)

messages = ""

while True:
    read_buffer = TS.s.recv(1024)
    messages = messages + read_buffer.decode('utf-8')
    last_message = messages.split('\r\n')[-2]
    print(last_message.encode('utf-8'))
    messages = ""
    if "PING" in last_message:
        resp = last_message.replace("PING", "PONG") + "\r\n"
        TS.s.send(resp.encode('utf-8'))
    else:
        bot._act_on(last_message)

