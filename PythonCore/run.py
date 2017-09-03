import os
import subprocess
from inspect import getsourcefile

from PythonCore.src.bot import Bot
from PythonCore.src.loggers import event_logger, error_logger
from PythonCore.src.twitch_service import TwitchService

from PythonCore import config

# TODO: Ensure the venv exists and activate it.
# If the venv must be created, install dependencies through pip


bot_info = config.bot_info

if config.service == config.Service.TWITCH:
    ts = TwitchService(pw=bot_info['pw'],
                       user=bot_info['user'],
                       channel=bot_info['channel'],
                       twitch_api_client_id=bot_info['twitch_api_client_id'],
                       error_logger=error_logger,
                       event_logger=event_logger)

    bot = Bot(bot_info=bot_info,
              service=ts,
              bitly_access_token=config.bitly_access_token,
              top_level_dir=config.top_level_dir,
              data_dir=config.data_dir)
    ts.run(bot)

else:
    raise NotImplementedError("We don't actually care about anything but Twitch yet. Sorry")

