import functools
import socket
import time
from enum import Enum, auto

import requests

from src.service import Service
from src.message import Message


def reconnect_on_error(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except Exception as e:
            print(f'{str(e)}: Attempting to reconnecting to the socket.')
            args[0].event_logger.info(f'{str(e)}: Attempting to reconnecting to the socket.')
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
        Message.__init__(self, service=Service.TWITCH,
                         message_type=message_type,
                         user=user, content=content,
                         display_name=display_name,
                         is_mod=is_mod)


class TwitchService(object):
    def __init__(self, pw, user, channel, error_logger, event_logger):
        self.host = 'irc.chat.twitch.tv'
        self.port = 6667
        self.pw = pw
        self.user = user.lower()
        self.display_user = user
        self.channel = channel.lower()
        self.display_channel = channel
        self.error_logger = error_logger
        self.event_logger = event_logger
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._join_room()

    @reconnect_on_error
    def send_public_message(self, message_content):
        """
        Sends a message to the twitch public chat
        """
        message_temp = f'PRIVMSG #{self.channel} :{message_content}\r\n'.encode('utf-8')
        print('{} PUBLIC {}: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S'),
            self.display_user,
            message_content))
        self.sock.send(message_temp)
        self.event_logger.info(f'sent: {message_temp}')

    @reconnect_on_error
    def send_private_message(self, recipient, whisper_content):
        """
        Sends a whisper with the specified content to the specified user 
        """
        message_temp = f'PRIVMSG #{self.channel} :/w {recipient} {whisper_content}\r\n'.encode('utf-8')
        print('{} PRIVATE {} to {}: {}'.format(
            time.strftime('%Y-%m-%d %H:%M:%S'),
            self.display_user,
            recipient,
            whisper_content))
        self.sock.send(message_temp)
        self.event_logger.info(f'sent: {message_temp}')

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
                read_buffer = self.sock.recv(2048)
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

    # Getter methods
    @staticmethod
    def get_message_display_name(message):
        return message.display_name

    @staticmethod
    def get_message_content(message):
        return message.content

    @staticmethod
    def get_mod_status(message):
        return message.is_mod

    @staticmethod
    def get_message_type(message):
        return message.message_type.name

    def _get_all_users(self):
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
            raise RuntimeError('Error talking to the twitch API')

    def get_mods(self):
        return self._get_all_users()['moderators']
        
    def get_viewers(self):
        return self._get_all_users()['viewers']

    def get_all_chatters(self):
        chatters = []
        for k, v in self._get_all_users().items():
            [chatters.append(user) for user in v]
        return chatters

    @staticmethod
    def _get_username_from_line(line):
        exclam_index = None
        at_index = None
        for i, char in enumerate(line):
            if char == '!':
                exclam_index = i
            if char == '@' and exclam_index is not None:
                at_index = i
                break
        return line[exclam_index+1:at_index]

    @staticmethod
    def _get_data_from_line(line, data_type):
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
        if "PRIVMSG" in line:
            return ('user-type=mod' in line) or (self._get_display_name_from_line(line).lower() == self.channel.lower())
        elif "WHISPER" in line:
            return (self._get_username_from_line(line) in self.get_mods()) or (self._get_username_from_line(line) == self.channel.lower())

    def _line_to_message(self, line):
        """
        Takes a twitch IRC line and converts it to a Message
        
        @params:
            line is a twitch IRC line
        """
        kwargs = {}
        try:
            if line == 'PING :tmi.twitch.tv':
                kwargs['message_type'] = MessageTypes.PING
            elif 'PRIVMSG' in line:
                kwargs['user'] = self._get_user_id_from_line(line)
                kwargs['display_name'] = self._get_display_name_from_line(line)
                kwargs['message_type'] = MessageTypes.PUBLIC
                kwargs['content'] = line.split(f'#{self.channel} :')[1]
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
        except Exception as e:
            print(str(e))
            print(line)
        return TwitchMessage(**kwargs)

    def get_time_out_message(self, username, seconds):
        message = f'/timeout {username} {seconds}'
        return message

    def run(self, bot):
        while True:
            messages = []
            lines = ''
            try:
                read_buffer = self.sock.recv(2048)
            except Exception as e:
                print('{}: Attempting to reconnecting to the socket.'.format(str(e)))
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._join_room()
                read_buffer = self.sock.recv(2048)

            if len(read_buffer) == 0:
                print('Disconnected: Attempting to reconnecting to the socket.')
                self.event_logger.info(r'Disconnected: Attempting to reconnecting to the socket.'.encode('utf-8'))
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._join_room()
                read_buffer = self.sock.recv(2048)
            try:
                lines = lines + read_buffer.decode(encoding='utf-8', errors='strict')
                line_list = lines.split('\r\n')
                self.event_logger.info(f'received: {line_list[-2]}'.encode('utf-8'))
            except Exception as e:
                print(e)
                self.error_logger.exception("Error Decoding the buffer")
                continue
            for line in line_list:
                messages.append(self._line_to_message(line))

            last_message = messages[-2]
            if last_message.message_type == MessageTypes.NOTICE:
                print(last_message.content)
            elif last_message.message_type == MessageTypes.PING:
                resp = 'PONG :tmi.twitch.tv\r\n'.encode('utf-8')
                self.sock.send(resp)
                self.event_logger.info(f'sent: {resp}')
            # elif last_message.message_type == MessageTypes.SYSTEM_MESSAGE:
            #     print(last_message.content)
            elif last_message.message_type in [MessageTypes.PUBLIC, MessageTypes.PRIVATE]:
                try:
                    bot._act_on(last_message)
                    print('{} {} {}: {}'.format(
                        time.strftime('%Y-%m-%d %H:%M:%S'),
                        last_message.message_type.name,
                        last_message.display_name,
                        last_message.content))
                except Exception as e:
                    print(e)
                    self.error_logger.exception(
                        f"""Message type: {last_message.message_type} 
                        Message content: {last_message.content} 
                        User: {last_message.display_name}"""
                    )
                    self.send_public_message('Something went wrong. The error has been logged.')

            time.sleep(.02)
