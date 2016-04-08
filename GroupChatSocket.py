import socket


class GroupChatSocket(object):

    def __init__(self, pw, user, channel):
        self.host = '52.223.240.152'
        self.port = 443
        self.pw = pw
        self.user = user
        self.channel = channel
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.join_room()

    def join_room(self):
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

    def send_message(self, message):
        message_temp = "PRIVMSG #" + self.channel + " :" + message
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))

    def send_whisper(self, user, message):
        message_temp = "PRIVMSG #jtv :/w " + user + " " + message
        self.sock.send("{}\r\n".format(message_temp).encode('utf-8'))