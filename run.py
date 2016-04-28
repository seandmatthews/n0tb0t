import logging
import time
from TwitchSocket import TwitchSocket
from Bot import Bot
from config import SOCKET_ARGS

logging.basicConfig(filename='error-log.txt',level=logging.WARNING)
ts = TwitchSocket(**SOCKET_ARGS)
bot = Bot(ts)

messages = ""

while True:
    read_buffer = ts.sock.recv(1024)

    messages = messages + read_buffer.decode('utf-8')
    messages_list = messages.split('\r\n')
    if len(messages_list) >= 2:
        last_message = messages_list[-2]
        print("{} {}: {}".format(
                time.strftime("%Y-%m-%d %H:%M:%S"),
                ts.get_user(last_message),
                ts.get_human_readable_message(last_message)))
        messages = ""
        if last_message == 'PING :tmi.twitch.tv':
            resp = last_message.replace("PING", "PONG") + "\r\n"
            ts.sock.send(resp.encode('utf-8'))
        else:
            try:
                bot._act_on(last_message)
            except Exception as e:
                logging.exception("Something went wrong")
                ts.send_message("Something went wrong. The error has been logged.")

    time.sleep(.02)
