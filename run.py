import logging
import time
from TwitchSocket import TwitchSocket
from Bot import Bot
from config import SOCKET_ARGS

logging.basicConfig(filename='error-log.txt',level=logging.DEBUG)
TS = TwitchSocket(**SOCKET_ARGS)
bot = Bot(TS)

messages = ""

while True:
    read_buffer = TS.sock.recv(1024)

    messages = messages + read_buffer.decode('utf-8')
    last_message = messages.split('\r\n')[-2]
    print(last_message.encode('utf-8'))
    messages = ""
    if last_message == 'PING :tmi.twitch.tv':
        resp = last_message.replace("PING", "PONG") + "\r\n"
        TS.sock.send(resp.encode('utf-8'))
    else:
        try:
            bot._act_on(last_message)
        except Exception as e:
            logging.exception("Something went wrong")
            TS.send_message("Something went wrong. The error has been logged.")

    time.sleep(.02)
