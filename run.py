import logging
import os

from src.Bot import Bot
from src.TwitchSocket import TwitchSocket
from src import twitch_loop
import config

if not os.path.exists(config.data_dir):
    os.makedirs(config.data_dir)

logging.basicConfig(filename=os.path.join(config.data_dir, 'error-log.txt'), level=logging.WARNING)
bi = config.BOT_INFO

if config.service == config.Service.TWITCH:
    ts = TwitchSocket(pw=bi['pw'], user=bi['user'], channel=bi['channel'])
    bot = Bot(BOT_INFO=bi,
              twitch_socket=ts,
              bitly_access_token=config.bitly_access_token,
              current_dir=config.current_dir,
              data_dir=config.data_dir)
    twitch_loop.run(bi, ts, bot)
