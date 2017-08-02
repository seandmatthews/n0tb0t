import config
from src.bot import Bot
from src.twitch_service import TwitchService
from src.loggers import event_logger, error_logger


bot_info = config.bot_info

if config.service == config.Service.TWITCH:
    ts = TwitchService(pw=bot_info['pw'],
                       user=bot_info['user'],
                       channel=bot_info['channel'],
                       client_id=bot_info['twitch_api_client_id'],
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

