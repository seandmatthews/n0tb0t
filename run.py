import logging
import os

from src.Bot import Bot
from src.TwitchService import TwitchService
import config


def setup_logger(logger_name, log_file, level=logging.INFO):
    """
    Factory method for creating loggers
    :param logger_name: 
    :param log_file: 
    :param level: 
    :return: 
    """
    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(asctime)s %(message)s')
    fileHandler = logging.FileHandler(log_file, mode='a')
    fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(fileHandler)
    # logger.addHandler(streamHandler)

    return logger

if not os.path.exists(config.data_dir):
    os.makedirs(config.data_dir)

error_log_path = os.path.join(config.data_dir, 'error-log.txt')
event_log_path = os.path.join(config.data_dir, 'event-log.txt')

error_logger = setup_logger('error_logger', error_log_path, level=logging.WARNING)
event_logger = setup_logger('event_logger', event_log_path, level=logging.INFO)


bi = config.BOT_INFO

if config.service == config.Service.TWITCH:
    ts = TwitchService(pw=bi['pw'],
                       user=bi['user'],
                       channel=bi['channel'],
                       error_logger=error_logger,
                       event_logger=event_logger)

    bot = Bot(BOT_INFO=bi,
              service=ts,
              bitly_access_token=config.bitly_access_token,
              current_dir=config.current_dir,
              data_dir=config.data_dir)
    ts.run(bot)

else:
    raise NotImplementedError("We don't actually care about anything but Twitch yet. Sorry")

