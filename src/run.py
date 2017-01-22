import logging
import socket
import time
from TwitchSocket import TwitchSocket
from Bot import Bot
from config import SOCKET_ARGS

logging.basicConfig(filename='error-log.txt', level=logging.WARNING)
ts = TwitchSocket(**SOCKET_ARGS)
bot = Bot(ts)

messages = ""

while True:
    try:
        read_buffer = ts.sock.recv(1024)
    except Exception as e:
        print('{}: Attempting to reconnecting to the socket.'.format(str(e)))
        ts.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ts.join_room()
        read_buffer = ts.sock.recv(1024)

    if len(read_buffer) == 0:
        print('Disconnected: Attempting to reconnecting to the socket.')
        ts.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ts.join_room()
        read_buffer = ts.sock.recv(1024)

    messages = messages + read_buffer.decode('utf-8')
    messages_list = messages.split('\r\n')
    # print(messages)
    if len(messages_list) >= 2:
        last_message = messages_list[-2]
        if "NOTICE" in last_message:
            print(messages)
        elif ts.get_user(last_message) in [SOCKET_ARGS['user'], 'system']:
            pass
        else:
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
                logging.exception("Error occurred at {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
                ts.send_message("Something went wrong. The error has been logged.")

    time.sleep(.02)
