import functools
import logging
import socket
import time
from enum import Enum, auto

from src.Service import Service


import requests

import src.message as message


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


class TwitchMessage(message.Message):
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
        message_temp = "PRIVMSG #" + self.channel + " :" + message
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))

    @reconnect_on_error
    def send_whisper(self, user, message):
        message_temp = "PRIVMSG #jtv :/w " + user + " " + message
        print("{}\r\n".format(message_temp).encode('utf-8'))
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))

    @reconnect_on_error
    def join_room(self):
        self.sock.connect((self.host, self.port))
        self.sock.send("PASS {PASS}\r\n".format(PASS=self.pw).encode('utf-8'))
        self.sock.send("NICK {USER}\r\n".format(USER=self.user).encode('utf-8'))
        self.sock.send("JOIN #{CHANNEL}\r\n".format(CHANNEL=self.channel).encode('utf-8'))

        messages = ""
        loading = True
        while loading:
            try:
                read_buffer = self.sock.recv(1024)
                messages = messages + read_buffer.decode('utf-8')
                last_message = messages.split('\r\n')[-2]
                messages = ""
                if "End of /NAMES list" in last_message:
                    loading = False
                else:
                    loading = True
            except:
                continue
        self.sock.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))

    def get_username(self, line): #replace all instances of this with get_generic
        if 'display-name=' in line:
            _, *rest_of_line = line.split('display-name=')
            username = rest_of_line[0].split(';')[0]
            # Occasionally, no usernames are found; debug this if we see it happen.
            if bool(username) is False:
                print('No username found')
                print(line)
            return username
        else:
            return 'system'

    def get_generic(self, line, thing):  # Give this a better name
        if thing in line:
            junk, *rest_of_line = line.split("{}=".format(thing),1)
            generic = rest_of_line[0].split(';')[0]
            return generic

    def get_user_id(self, line):  # Replace all instances of this with get_generic
        if 'user-id=' in line:
            _, *rest_of_line = line.split('user-id=')
            user_id = rest_of_line[0].split(';')[0]
            return user_id

    def get_human_readable_message(self, line):  # TODO @Sean replace this with MessageObjectThing.contents
        line = self.get_generic(line, 'user-type=')
        # if 'emotes=;' in line:
        #     num_colons = 2
        # else:
        #     num_colons = 3
        num_colons = 2
        if "PRIVMSG" in line or ("WHISPER" in line and self.get_username(line) in self.get_mods()):
            line_list = line.split(':', num_colons)
            hr_message = line_list[-1]
            return hr_message
        else:
            return ''

    def check_mod(self, line):
        line_list = line.split(':', 2)
        if "PRIVMSG" in line:
            if ('user-type=mod' in line_list[0]) or (self.get_username(line) == self.channel):
                return True
            else:
                return False
        elif "WHISPER" in line:
            if (self.get_username(line) in self.get_mods()) or (self.get_username(line) == self.channel):
                return True
            else:
                return False

    def fetch_chatters_from_API(self):
        """
        Talks to twitch's API to look at all chatters currently in the channel.
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
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

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
        Takes a twitch api protocol line and converts it to a Message
        
        @params:
            line is a twitch api protocol line
        """
        service = Service.TWITCH
        user = self.get_generic(line, "display-name")
        msg_info = self.get_generic(line, "user-type")
        msg_info = msg_info.split(":{0}!{0}@{0}.tmi.twitch.tv".format(user.lower()), 1)[1]
        msg_info = msg_info.strip()
        msg_info, content = msg_info.split(":", 1)
        msg_info = msg_info.split(" ", 1)[0]

        if msg_info == "PRIVMSG":
            message_type = MessageTypes.PUBLIC
        elif msg_info == "WHISPER":
            message_type = MessageTypes.PRIVATE
        
        return message.Message(service=service, message_type=message_type, user=user, content=content)

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
            lines = messages.split('\r\n')
            for line in lines:
                messages.append(self.line_to_message(line))
            lines =  ""

            if len(messages) >= 2:
                last_message = messages[0]
                if last_message.message_type == NOTICE:#@tood(someone) sort out message type enums
                    print(message)
                # elif self.get_username(last_message) in [bot.info['user'], 'system']:
                #     pass
                # else: not sure what this is for, commenting out incase we need it
                #     print("{} {}: {}".format(
                #         time.strftime("%Y-%m-%d %H:%M:%S"),
                #         self.get_username(last_message),
                #         self.get_human_readable_message(last_message)))
                # messages = ""
                elif last_message.message_type == PING: #todo sort out mesage type
                    #resp = last_message.replace("PING", "PONG") + "\r\n"
                    #what does a pong response look like?
                    resp = "pong resonse make one please sean"
                    self.sock.send(resp.encode('utf-8'))
                else:
                    try:
                        bot._act_on(last_message)
                    except Exception as e:
                        print(e)
                        logging.exception("Error occurred at {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
                        self.send_message("Something went wrong. The error has been logged.")

            time.sleep(.02)