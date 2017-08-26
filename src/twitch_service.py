import datetime
import functools
import socket
import time
from enum import Enum, auto
from dateutil.relativedelta import relativedelta

import requests

from src.service import Service
from src.message import Message


def reconnect_on_error(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        while True:
            try:
                f(*args, **kwargs)
            except Exception as e:
                print(f'{str(e)}: Attempting to reconnect to the socket.')
                args[0].event_logger.info(f'{str(e)}: Attempting to reconnect to the socket.')
                time.sleep(5)
                try:
                    args[0].sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    args[0]._join_room()
                except Exception as e:
                    continue
                continue
            break
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
    def __init__(self, pw, user, channel, twitch_api_client_id, error_logger, event_logger):
        self.host = 'irc.chat.twitch.tv'
        self.port = 6667
        self.pw = pw
        self.user = user.lower()
        self.display_user = user
        self.channel = channel.lower()
        self.twitch_api_client_id = twitch_api_client_id
        self.display_channel = channel
        self.channel_id = self._get_channel_id_from_channel_name(channel.lower())
        self.error_logger = error_logger
        self.event_logger = event_logger
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._join_room()

    def _get_channel_id_from_channel_name(self, channel_name):
        """
        In twitch your channel id is your user id
        and your channel name is your user name
        """
        return self._get_user_id_from_user_name(channel_name)

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

    def _get_user_id_from_user_name(self, username):
        """
        Talks to the twitch kraken api to fetch the user's id when given their name.
        """
        # TODO: Cache the user IDs in the database, pull from there first.
        url = f'https://api.twitch.tv/kraken/users?login={username}'
        for attempt in range(5):
            try:
                r = requests.get(url, headers={
                    "Client-ID": self.twitch_api_client_id,
                    "Accept": "application/vnd.twitchtv.v5+json"})
                user_id = r.json()['users'][0]['_id']
            except IndexError:
                raise RuntimeError("That's not a twitch user")
            except KeyError:
                raise RuntimeError("That's not a twitch user")
            except ValueError:
                continue
            except TypeError:
                continue
            else:
                return user_id
        else:
            raise RuntimeError('Error talking to the twitch API')

    def get_user_creation_date(self, username):
        """
        Returns the creation date of a given twitch user.
        """
        user_id = self._get_user_id_from_user_name(username)
        url = 'https://api.twitch.tv/kraken/users/{}'.format(user_id)
        for attempt in range(5):
            try:
                r = requests.get(url, headers={"Client-ID": self.twitch_api_client_id,
                                               "Accept": "application/vnd.twitchtv.v5+json"})
                creation_date = r.json()['created_at']
                cut_creation_date = creation_date[:10]
            except ValueError:
                continue
            except TypeError:
                continue
            else:
                return cut_creation_date
        else:
            raise RuntimeError(
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

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

    def get_live_time(self):
        """
        Uses the kraken API to fetch the start time of the current stream.
        Computes how long the stream has been running, returns that value in a dictionary.
        """
        channel_id = self._get_channel_id_from_channel_name(self.channel)

        url = 'https://api.twitch.tv/kraken/streams/{}'.format(channel_id)
        for attempt in range(5):
            try:
                r = requests.get(url, headers={"Client-ID": self.twitch_api_client_id,
                                               "Accept": "application/vnd.twitchtv.v5+json"})
                r.raise_for_status()
                start_time_str = r.json()['stream']['created_at']
                start_time_dt = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%SZ')
                now_dt = datetime.datetime.utcnow()
                time_delta = now_dt - start_time_dt
                time_dict = {'hour': None,
                             'minute': None,
                             'second': None}

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
                raise RuntimeError("Sorry, the channel doesn't seem to be live at the moment.")
            except ValueError:
                continue
            else:
                return time_dict
        else:
            raise RuntimeError(
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

    def follow_time(self, userid, username):
        channel_id = self.channel_id
        url = f'https://api.twitch.tv/kraken/users/{userid}/follows/channels/{channel_id}'
        for attempt in range(5):
            try:
                r = requests.get(url, headers={
                    "Client-ID": self.twitch_api_client_id,
                    "Accept": "application/vnd.twitchtv.v5+json"})
                if "created_at" in r.json():
                    follow_date = r.json()['created_at']
                    follow_time_dt = datetime.datetime.strptime(follow_date, '%Y-%m-%dT%H:%M:%SZ')
                    now_dt = datetime.datetime.utcnow()
                    myrelativedelta = relativedelta(now_dt, follow_time_dt)
                    response_str = f'{username}, you have been following {self.display_channel} for {myrelativedelta.years} year{"s" * int(myrelativedelta.years != 1)}, {myrelativedelta.months} month{"s" * int(myrelativedelta.months != 1)} and {myrelativedelta.days} day{"s" * int(myrelativedelta.days != 1)}.'
                else:
                    response_str = f'{username}, you aren\'t following this channel.'
            except ValueError:
                continue
            except TypeError:
                continue
            else:
                return response_str
        else:
            raise RuntimeError('Error talking to the twitch API')

    def get_channel_url_and_last_played_game(self, username):
        channel_id = self._get_channel_id_from_channel_name(username)
        url = f'https://api.twitch.tv/kraken/channels/{channel_id}'
        for attempt in range(5):
            try:
                r = requests.get(url, headers={"Client-ID": self.twitch_api_client_id,
                                               "Accept": "application/vnd.twitchtv.v5+json"})
                r.raise_for_status()
                game = r.json()['game']
                channel_url = r.json()['url']

                return channel_url, game
            except IndexError:
                raise RuntimeError("That's not a real streamer!")
            except ValueError:
                continue
        else:
            raise RuntimeError("Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

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
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._join_room()
                except Exception as e:
                    time.sleep(5)
                    continue
                read_buffer = self.sock.recv(2048)

            if len(read_buffer) == 0:
                print('Disconnected: Attempting to reconnecting to the socket.')
                self.event_logger.info(r'Disconnected: Attempting to reconnecting to the socket.'.encode('utf-8'))
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._join_room()
                except Exception as e:
                    time.sleep(5)
                    continue
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
