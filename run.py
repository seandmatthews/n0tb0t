from inspect import getsourcefile
import os
import subprocess

import config
from src.bot import Bot
from src.twitch_service import TwitchService
from src.loggers import event_logger, error_logger


# TODO: Ensure the venv exists and activate it.
# If the venv must be created, install dependencies through pip


# Fire up subprocess to start the webserver on localhost.
current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
web_file = os.path.join(current_dir, 'src', 'web', 'run_webserver.py')
subprocess.run(["python", web_file])

bot_info = config.bot_info

if config.service == config.Service.TWITCH:
    ts = TwitchService(pw=bot_info['pw'],
                       user=bot_info['user'],
                       channel=bot_info['channel'],
                       error_logger=error_logger,
                       event_logger=event_logger)

    bot = Bot(bot_info=bot_info,
              service=ts,
              bitly_access_token=config.bitly_access_token,
              current_dir=config.current_dir,
              data_dir=config.data_dir)
    ts.run(bot)

else:
    raise NotImplementedError("We don't actually care about anything but Twitch yet. Sorry")

