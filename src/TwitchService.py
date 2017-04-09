import functools
import logging
import socket
import time
from enum import Enum, auto

import requests
import sqlalchemy

import src.models as models
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
    SYSTEM_MESSAGE = auto()


class TwitchMessage(Message):
    def __init__(self, service=None, message_type=None, user=None, content=None, display_name=None):
        Message.__init__(self, service=service, message_type=message_type, user=user, content=content)
        self.display_name = display_name


class TwitchService(object):
    def __init__(self, pw, user, channel):
        self.host = 'irc.chat.twitch.tv'
        self.port = 6667
        self.pw = pw
        self.user = user.lower()
        self.display_user = user
        self.channel = channel.lower()
        self.display_channel = channel
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.join_room()

    @reconnect_on_error
    def send_message(self, message_content):
        message_temp = 'PRIVMSG #' + self.channel + " :" + message_content
        print('{} {}: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S'),
            self.display_user,
            message_content))
        self.sock.send('{}\r\n'.format(message_temp).encode('utf-8'))

    @reconnect_on_error
    def send_whisper(self, user, whisper):
        message_temp = 'PRIVMSG #jtv :/w ' + user + ' ' + whisper
        print('{} {}: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S'),
            self.display_user,
            whisper))
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))

    @reconnect_on_error
    def join_room(self):
        self.sock.connect((self.host, self.port))
        self.sock.send('PASS {PASS}\r\n'.format(PASS=self.pw).encode('utf-8'))
        self.sock.send('NICK {USER}\r\n'.format(USER=self.user).encode('utf-8'))
        self.sock.send('CAP REQ: twitch.tv/membership\r\n'.encode('utf-8'))
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
        self.sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))

    def _get_username(self, line):
        for i, char in enumerate(line):
            if char == '!':
                exclam_index = i
            if char == '@':
                at_index = i
                break
        return line[exclam_index+1:at_index]

    def _get_data_from_line(self, line, data_type):
        if data_type in line:
            _, *rest_of_line = line.split("{}=".format(data_type), 1)
            for i, char in enumerate(rest_of_line[0]):
                if char in [' ', ';']:
                    return rest_of_line[0][:i]

    def get_display_name(self, line):
        display_name = self._get_data_from_line(line, 'display-name')
        if display_name is not None:
            return display_name
        else:
            username = self._get_username(line)
            display_name = f'{username[0].upper()}{username[1:]}'
            return display_name

    def get_user_id(self, line):
        return self._get_data_from_line(line, 'user-id')

    def get_message_content(self, message):
        return message.content

    def check_mod(self, line):
        line_list = line.split(':', 2)
        if "PRIVMSG" in line:
            if ('user-type=mod' in line_list[0]) or (self._get_username(line) == self.channel.lower()):
                return True
            else:
                return False
        elif "WHISPER" in line:
            if (self._get_username(line) in self.get_mods()) or (self._get_username(line) == self.channel.lower()):
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
        user = None
        display_name = None
        content = None
        message_type = None
        if line == 'PING :tmi.twitch.tv':
            message_type = MessageTypes.PING
        elif 'PRIVMSG' in line:
            user = self.get_user_id(line)
            display_name = self.get_display_name(line)
            message_type = MessageTypes.PUBLIC
            content = line.split(f'#{self.channel} :')[1]
        elif 'WHISPER' in line:
            user = self.get_user_id(line)
            display_name = self.get_display_name(line)
            message_type = MessageTypes.PRIVATE
            content = line.split(f'#{self.channel} :')[1]
        elif 'NOTICE' in line:
            message_type = MessageTypes.NOTICE
            content = line
        else:
            message_type = MessageTypes.SYSTEM_MESSAGE
            content = line

        return TwitchMessage(service=service,
                             message_type=message_type,
                             user=user,
                             content=content,
                             display_name=display_name)

    def run(self, bot):
        messages = []
        lines = ''

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
                messages.append(self.line_to_message(line))
            lines = ''

            last_message = messages[-2]
            if last_message.message_type == MessageTypes.NOTICE:
                print(last_message.content)
            elif last_message.message_type == MessageTypes.PING:
                resp = 'PONG :tmi.twitch.tv'
                self.sock.send(resp.encode('utf-8'))
            elif last_message.message_type in [MessageTypes.PUBLIC, MessageTypes.PRIVATE]:
                try:
                    # bot._act_on(last_message)
                    print('{} {}: {}'.format(
                        time.strftime('%Y-%m-%d %H:%M:%S'),
                        last_message.display_name,
                        last_message.content))
                except Exception as e:
                    print(e)
                    logging.exception('Error occurred at {}'.format(time.strftime('%Y-%m-%d %H:%M:%S')))
                    self.send_message('Something went wrong. The error has been logged.')

            time.sleep(.02)
