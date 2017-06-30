import logging
import os

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
    formatter = logging.Formatter(u'%(asctime)s %(message)s')
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

error_log_path = os.path.join(config.data_dir, f'{config.bot_info["channel"]}_error-log.txt')
event_log_path = os.path.join(config.data_dir, f'{config.bot_info["channel"]}_event-log.txt')

error_logger = setup_logger('error_logger', error_log_path, level=logging.WARNING)
event_logger = setup_logger('event_logger', event_log_path, level=logging.INFO)
