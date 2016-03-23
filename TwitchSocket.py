import socket


class TwitchSocket(object):

    def __init__(self, pw, user, channel):
        self.host = 'irc.chat.twitch.tv'
        self.port = 6667
        self.pw = pw
        self.user = user
        self.channel = channel

        self.join_room()

    def send_message(self, message):
        message_temp = "PRIVMSG #" + self.channel + " :" + message
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))


    def join_room(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.send("PASS {PASS}\r\n".format(PASS=self.pw).encode('utf-8'))
        self.sock.send("NICK {USER}\r\n".format(USER=self.user).encode('utf-8'))
        self.sock.send("JOIN #{CHANNEL}\r\n".format(CHANNEL=self.channel).encode('utf-8'))

        messages = ""
        loading = True
        while loading:
            read_buffer = self.sock.recv(1024)
            messages = messages + read_buffer.decode('utf-8')
            last_message = messages.split('\r\n')[-2]
            messages = ""
            if "End of /NAMES list" in last_message:
                loading = False
            else:
                loading = True
        self.send_message("{USER} is now online".format(USER=self.user))
        self.sock.send("CAP REQ :twitch.tv/commands\r\n".encode('utf-8'))
        self.sock.send("CAP REQ :twitch.tv/tags\r\n".encode('utf-8'))


    def get_user(self, line):
        line_list = line.split(':', 2)
        user = line_list[1].split('!')[0]
        return user

    def get_human_readable_message(self, line):
        if 'PRIVMSG' in line:
            emotes = 'emotes=;' not in line
            if emotes:
                num_colons = 3
            else:
                num_colons = 2
            line_list = line.split(':', num_colons)
            hr_message = line_list[num_colons]
            return hr_message
        else:
            return ''

    def check_mod(self, line):
        line_list = line.split(':', 2)
        if ('user-type=mod' in line_list[0]) or (self.get_user(line) == self.channel):
            return True
        else:
            return False
