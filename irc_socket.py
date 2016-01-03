import socket


class TwitchSocket(object):

    def __init__(self, pw, user, channel):
        self.host = 'irc.twitch.tv'
        self.port = 6667
        self.pw = pw
        self.user = user
        self.channel = channel

        self.join_room()

    def send_message(self, message):
        message_temp = "PRIVMSG #" + self.channel + " :" + message
        self.s.send("{}\r\n".format(message_temp).encode('utf-8'))


    def join_room(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, self.port))
        self.s.send("PASS {PASS}\r\n".format(PASS=self.pw).encode('utf-8'))
        self.s.send("NICK {USER}\r\n".format(USER=self.user).encode('utf-8'))
        self.s.send("JOIN #{CHANNEL}\r\n".format(CHANNEL=self.channel).encode('utf-8'))

        messages = ""
        loading = True
        while loading:
            read_buffer = self.s.recv(1024)
            messages = messages + read_buffer.decode('utf-8')
            last_message = messages.split('\r\n')[-2]
            messages = ""
            if "End of /NAMES list" in last_message:
                loading = False
            else:
                loading = True
        self.send_message("{USER} is now online".format(USER=self.user))
        self.s.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))
        self.s.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))


    def get_user(self, line):
        line_list = line.split(':', 2)
        user = line_list[1].split('!')[0]
        return user

    def get_hr_message(self, line):
        if 'PRIVMSG' in line:
            line_list = line.split(':', 2)
            hr_message = line_list[2]
            return hr_message
        else:
            return ''

    def check_mod(self, line):
        line_list = line.split(':', 2)
        if ('user-type=mod' in line_list[0]) or (self.get_user(line) == self.channel):
            return True
        else:
            return False


class GroupChatSocket(object):

    def __init__(self, pw, user, channel):
        self.host = '199.9.253.119'
        self.port = 6667
        self.pw = pw
        self.user = user
        self.channel = channel

        self.join_room()
        

    def join_room(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, self.port))
        self.s.send("PASS {PASS}\r\n".format(PASS=self.pw).encode('utf-8'))
        self.s.send("NICK {USER}\r\n".format(USER=self.user).encode('utf-8'))
        self.s.send("JOIN #{CHANNEL}\r\n".format(CHANNEL=self.channel).encode('utf-8'))

        messages = ""
        loading = True
        while loading:
            read_buffer = self.s.recv(1024)
            messages = messages + read_buffer.decode('utf-8')
            last_message = messages.split('\r\n')[-2]
            messages = ""
            if "End of /NAMES list" in last_message:
                loading = False
            else:
                loading = True
        self.send_message("{USER} is now online".format(USER=self.user))
        self.s.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))
        self.s.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))

    def send_message(self, message):
        message_temp = "PRIVMSG #" + self.channel + " :" + message
        self.s.send("{}\r\n".format(message_temp).encode('utf-8'))

    def send_whisper(self, user, message):
        message_temp = "PRIVMSG #jtv :/w " + user + " " + message
        self.s.send("{}\r\n".format(message_temp).encode('utf-8'))
