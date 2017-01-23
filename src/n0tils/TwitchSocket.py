import socket
import requests


class TwitchSocket(object):
    def __init__(self, pw, user, channel):
        self.host = 'irc.chat.twitch.tv'
        self.port = 80
        self.pw = pw
        self.user = user
        self.channel = channel
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.join_room()

    def send_message(self, message):
        message_temp = "PRIVMSG #" + self.channel + " :" + message
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))

    def send_whisper(self, user, message):
        message_temp = "PRIVMSG #jtv :/w " + user + " " + message
        print("{}\r\n".format(message_temp).encode('utf-8'))
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))

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
        self.sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))

    def get_user(self, line):
        if 'emotes=;' in line:
            num_colons = 2
        else:
            num_colons = 3
        line_list = line.split(':', num_colons)
        user = line_list[-2].split('!')[0]
        return user

    def get_human_readable_message(self, line):
        if 'emotes=;' in line:
            num_colons = 2
        else:
            num_colons = 3
        if "PRIVMSG" in line or ("WHISPER" in line and self.get_user(line) in self.get_mods()):
            line_list = line.split(':', num_colons)
            hr_message = line_list[-1]
            return hr_message
        else:
            return ''

    def check_mod(self, line):
        line_list = line.split(':', 2)
        if "PRIVMSG" in line:
            if ('user-type=mod' in line_list[0]) or (self.get_user(line) == self.channel):
                return True
            else:
                return False
        elif "WHISPER" in line:
            if (self.get_user(line) in self.get_mods()) or (self.get_user(line) == self.channel):
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

    def get_all_chatters(self):
        chatters = []
        for k, v in self.fetch_chatters_from_API().items():
            [chatters.append(user) for user in v]
        return chatters
