import config
from src.bot import Bot
from src.twitch_service import TwitchService
from src.loggers import event_logger, error_logger


bot_info = config.bot_info

#now THIS is some stuff that conflicts with project servicemodular
if config.service == config.Service.TWITCH:
    ts = TwitchService(pw=bot_info['pw'],
                       user=bot_info['user'],
                       channel=bot_info['channel'],
                       error_logger=error_logger,
                       event_logger=event_logger)

    bot = Bot(bot_info=bot_info,
              services=[ts],
              bitly_access_token=config.bitly_access_token,
              current_dir=config.current_dir,
              data_dir=config.data_dir)
    ts.run(bot)

else:
    raise NotImplementedError("We don't actually care about anything but Twitch yet. Sorry")
