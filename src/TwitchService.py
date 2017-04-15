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
            args[0]._join_room()
            f(*args, **kwargs)
    return wrapper


class MessageTypes(Enum):
    PUBLIC = auto()
    PRIVATE = auto()
    NOTICE = auto()
    PING = auto()
    SYSTEM_MESSAGE = auto()


class TwitchMessage(Message):
    def __init__(self, message_type=None, user=None, content=None, display_name=None, is_mod=False):
        Message.__init__(self, service=Service.TWITCH, message_type=message_type, user=user, content=content)
        self.display_name = display_name
        self.is_mod = is_mod


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

        self._join_room()

    @reconnect_on_error
    def send_public_message(self, message_content):
        message_temp = f'PRIVMSG #{self.channel} :{message_content}'
        print('{} {}: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S'),
            self.display_user,
            message_content))
        bytes_num = self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))
        print(f'Sent {bytes_num} bytes')

    @reconnect_on_error
    def send_private_message(self, user, whisper):
        message_temp = f'PRIVMSG #{self.channel} :/w {user} {whisper}'
        print('{} {}: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S'),
            self.display_user,
            whisper))
        bytes_num = self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))
        print(f'Sent {bytes_num} bytes')

    @reconnect_on_error
    def _join_room(self):
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

        self.sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))
        self.sock.send('CAP REQ :twitch.tv/commands\r\n'.encode('utf-8'))
        # self.sock.send('CAP REQ :twitch.tv/membership\r\n'.encode('utf-8'))

    # Unpythonic Getters
    # TODO: Consider removing and accessing methods directly
    def get_message_display_name(self, message):
        return message.display_name

    def get_message_content(self, message):
        return message.content

    def get_mod_status(self, message):
        return message.is_mod

    def get_message_type(self, message):
        return message.message_type.name

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

    def _get_username_from_line(self, line):
        exclam_index = None
        at_index = None
        for i, char in enumerate(line):
            if char == '!':
                exclam_index = i
            if char == '@' and exclam_index is not None:
                at_index = i
                break
        return line[exclam_index+1:at_index]

    def _get_data_from_line(self, line, data_type):
        if data_type in line:
            _, *rest_of_line = line.split("{}=".format(data_type), 1)
            for i, char in enumerate(rest_of_line[0]):
                if char in [':', ';']:
                    return rest_of_line[0][:i].strip()

    def _get_display_name_from_line(self, line):
        display_name = self._get_data_from_line(line, 'display-name')
        if display_name not in [None, '']:
            return display_name
        else:
            username = self._get_username_from_line(line)
            display_name = f'{username[0].upper()}{username[1:]}'
            return display_name

    def _get_user_id_from_line(self, line):
        return self._get_data_from_line(line, 'user-id')

    def _check_mod_from_line(self, line):
        line_list = line.split(':', 2)
        if "PRIVMSG" in line:
            return ('user-type=mod' in line_list[0]) or (self._get_display_name_from_line(line).lower() == self.channel.lower())
        elif "WHISPER" in line:
            return (self._get_username_from_line(line) in self.get_mods()) or (self._get_username_from_line(line) == self.channel.lower())

    def _line_to_message(self, line):
        """
        Takes a twitch IRC line and converts it to a Message
        
        @params:
            line is a twitch IRC line
        """
        kwargs = {}
        if line == 'PING :tmi.twitch.tv':
            kwargs['message_type'] = MessageTypes.PING
        elif 'PRIVMSG' in line:
            kwargs['user'] = self._get_user_id_from_line(line)
            kwargs['display_name'] = self._get_display_name_from_line(line)
            kwargs['message_type'] = MessageTypes.PUBLIC
            kwargs['content'] = line.split(f'#{self.channel} :')[1]  # TODO: Make sure this works with odd capitalization
            kwargs['is_mod'] = self._check_mod_from_line(line)
        elif 'WHISPER' in line:
            kwargs['user'] = self._get_user_id_from_line(line)
            kwargs['display_name'] = self._get_display_name_from_line(line)
            kwargs['message_type'] = MessageTypes.PRIVATE
            kwargs['content'] = line.split(f'WHISPER {self.user} :')[1]
            kwargs['is_mod'] = self._check_mod_from_line(line)
        elif 'NOTICE' in line:
            kwargs['message_type'] = MessageTypes.NOTICE
            kwargs['content'] = line
        else:
            kwargs['message_type'] = MessageTypes.SYSTEM_MESSAGE
            kwargs['content'] = line

        return TwitchMessage(**kwargs)

    def run(self, bot):
        messages = []
        lines = ''

        while True:
            try:
                read_buffer = self.sock.recv(1024)
            except Exception as e:
                print('{}: Attempting to reconnecting to the socket.'.format(str(e)))
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._join_room()
                read_buffer = self.sock.recv(1024)

            if len(read_buffer) == 0:
                print('Disconnected: Attempting to reconnecting to the socket.')
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._join_room()
                read_buffer = self.sock.recv(1024)

            lines = lines + read_buffer.decode('utf-8')
            line_list = lines.split('\r\n')
            for line in line_list:
                messages.append(self._line_to_message(line))
            lines = ''

            last_message = messages[-2]
            if last_message.message_type == MessageTypes.NOTICE:
                print(last_message.content)
            elif last_message.message_type == MessageTypes.PING:
                resp = 'PONG :tmi.twitch.tv'
                self.sock.send(resp.encode('utf-8'))
            # elif last_message.message_type == MessageTypes.SYSTEM_MESSAGE:
            #     print(last_message.content)
            elif last_message.message_type in [MessageTypes.PUBLIC, MessageTypes.PRIVATE]:
                try:
                    bot._act_on(last_message)
                    print('{} {}: {}'.format(
                        time.strftime('%Y-%m-%d %H:%M:%S'),
                        last_message.display_name,
                        last_message.content))
                except Exception as e:
                    print(e)
                    logging.exception('Error occurred at {}'.format(time.strftime('%Y-%m-%d %H:%M:%S')))
                    self.send_public_message('Something went wrong. The error has been logged.')

            time.sleep(.02)
