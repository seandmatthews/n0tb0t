import functools
import logging
import socket
import time
from enum import Enum, auto

import requests

from src.Service import Service
from src.Message import Message


def reconnect_on_error(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except Exception as e:
            print('{}: Attempting to reconnecting to the socket.'.format(str(e)))
            args[0].sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            args[0].join_room()
            f(*args, **kwargs)
    return wrapper


class MessageTypes(Enum):
    PUBLIC = auto()
    PRIVATE = auto()
    NOTICE = auto()
    PING = auto()


class TwitchMessage(Message):
    pass


class TwitchService(object):
    def __init__(self, pw, user, channel):
        self.host = 'irc.chat.twitch.tv'
        self.port = 6667
        self.pw = pw
        self.user = user
        self.channel = channel
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.join_room()

    @reconnect_on_error
    def send_message(self, message):
        message_temp = 'PRIVMSG #' + self.channel + " :" + message
        self.sock.send('{}\r\n'.format(message_temp).encode('utf-8'))

    @reconnect_on_error
    def send_whisper(self, user, message):
        message_temp = 'PRIVMSG #jtv :/w ' + user + ' ' + message
        print('{}\r\n'.format(message_temp).encode('utf-8'))
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))

    @reconnect_on_error
    def join_room(self):
        self.sock.connect((self.host, self.port))
        self.sock.send('PASS {PASS}\r\n'.format(PASS=self.pw).encode('utf-8'))
        self.sock.send('NICK {USER}\r\n'.format(USER=self.user).encode('utf-8'))
        self.sock.send('JOIN #{CHANNEL}\r\n'.format(CHANNEL=self.channel).encode('utf-8'))

        messages = ''
        loading = True
        while loading:
            try:
                read_buffer = self.sock.recv(1024)
                messages = messages + read_buffer.decode('utf-8')
                last_message = messages.split('\r\n')[-2]
                messages = ""
                if 'End of /NAMES list' in last_message:
                    loading = False
                else:
                    loading = True
            except:
                continue
        self.sock.send('CAP REQ :twitch.tv/commands\r\n'.encode('utf-8'))

    def get_username(self, line):
        print(line)
        username = None
        return username

    def get_data_from_line(self, line, thing):
        if thing in line:
            _, *rest_of_line = line.split("{}=".format(thing), 1)
            return rest_of_line[0].split(';')[0]

    def get_display_name(self, line):
        display_name = self.get_data_from_line('display-name')
        if display_name is not None:
            return display_name
        else:
            username = self.get_username(line)
            display_name = f'{username[0].upper()}{username[1:]}'
            return display_name

    def get_user_id(self, line):  # Replace all instances of this with get_generic
        if 'user-id=' in line:
            _, *rest_of_line = line.split('user-id=')
            user_id = rest_of_line[0].split(';')[0]
            return user_id

    def get_message_content(self, message):
        return message.content

    def check_mod(self, line):
        line_list = line.split(':', 2)
        if "PRIVMSG" in line:
            if ('user-type=mod' in line_list[0]) or (self.get_username(line).lower() == self.channel.lower()):
                return True
            else:
                return False
        elif "WHISPER" in line:
            if (self.get_username(line) in self.get_mods()) or (self.get_username(line).lower() == self.channel.lower()):
                return True
            else:
                return False

    def fetch_chatters_from_API(self):
        """
        Talks to twitch's unsupported TMI API to look at all chatters currently in the channel.
        Returns that json dictionary. It has 'moderators', 'global_mods',
        'viewers', 'admins', and 'staff' as keys.
        """
        url = 'http://tmi.twitch.tv/group/user/{channel}/chatters'.format(channel=self.channel)
        for attempt in range(5):
            try:
                r = requests.get(url)
                chatters = r.json()['chatters']
            except ValueError:
                continue
            except TypeError:
                continue
            else:
                return chatters
        else:
            self._add_to_chat_queue(
                'Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?')

    def get_mods(self):
        print(self.fetch_chatters_from_API()['moderators'])
        return self.fetch_chatters_from_API()['moderators']
        
    def get_viewers(self):
        return self.fetch_chatters_from_API()['viewers']

    def get_all_chatters(self):
        chatters = []
        for k, v in self.fetch_chatters_from_API().items():
            [chatters.append(user) for user in v]
        return chatters

    def line_to_message(self, line):
        """
        Takes a twitch IRC line and converts it to a Message
        
        @params:
            line is a twitch IRC line
        """
        service = Service.TWITCH
        user = self.get_data_from_line(line, 'display-name')
        if 'PRIVMSG' in line or 'WHISPER' in line:
            msg_info = self.get_data_from_line(line, 'user-type')
            msg_info = msg_info.split(':{0}!{0}@{0}.tmi.twitch.tv'.format(user.lower()), 1)[1]
            msg_info = msg_info.strip()
            msg_info, content = msg_info.split(":", 1)
            msg_info = msg_info.split(' ', 1)[0]

            if msg_info == 'PRIVMSG':
                message_type = MessageTypes.PUBLIC
            elif msg_info == 'WHISPER':
                message_type = MessageTypes.PRIVATE
            else: message_type = None
        else:
            message_type = None
            content = None
        
        return Message(service=service, message_type=message_type, user=user, content=content)

    def run(self, bot):
        messages = []
        lines = ""

        while True:
            try:
                read_buffer = self.sock.recv(1024)
            except Exception as e:
                print('{}: Attempting to reconnecting to the socket.'.format(str(e)))
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.join_room()
                read_buffer = self.sock.recv(1024)

            if len(read_buffer) == 0:
                print('Disconnected: Attempting to reconnecting to the socket.')
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.join_room()
                read_buffer = self.sock.recv(1024)

            lines = lines + read_buffer.decode('utf-8')
            line_list = lines.split('\r\n')
            for line in line_list:
                print(line)
                messages.append(self.line_to_message(line))
            lines = ''

            if len(messages) >= 2:
                last_message = messages[0]
                if last_message.message_type == MessageTypes.NOTICE:
                    print(last_message)
                # elif self.get_username(last_message) in [bot.info['user'], 'system']:
                #     pass
                else:
                    print("{} {}: {}".format(
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        self.get_username(last_message),
                        self.get_human_readable_message(last_message)))
                if last_message.message_type == MessageTypes.PING:
                    resp = 'PONG :tmi.twitch.tv'
                    self.sock.send(resp.encode('utf-8'))
                else:
                    try:
                        bot._act_on(last_message)
                    except Exception as e:
                        print(e)
                        logging.exception('Error occurred at {}'.format(time.strftime('%Y-%m-%d %H:%M:%S')))
                        self.send_message('Something went wrong. The error has been logged.')

            time.sleep(.02)