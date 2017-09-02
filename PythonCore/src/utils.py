import functools
import random
import time

import gspread
import praw
from PythonCore.src.loggers import error_logger

from PythonCore.config import reddit_client_id
from PythonCore.config import reddit_client_secret
from PythonCore.config import reddit_user_agent


# DECORATORS #

def retry_gspread_func(f):
    """
    Retries the function that uses gspread until it completes without throwing an HTTPError
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        while True:
            try:
                f(*args, **kwargs)
            # Gspread doesn't handle errors very well
            # Sometimes it tries to index an error object, which it can't, which causes a type error.
            # I'd submit a patch, but the last time I tried to do that I had to harangue the author for literally
            # months to get my well tested and documented PR accepted. So I'm not doing that again.
            except (gspread.exceptions.GSpreadException, TypeError) as e:
                print('Gspread failure; retrying')
                error_logger.exception('Gspread failure')
                time.sleep(5)
                continue
            break

    return wrapper


def mod_only(f):
    f._mod_only = True
    return f


def private_message_allowed(f):
    f._private_message_allowed = True
    return f


def public_message_disallowed(f):
    f._public_message_disallowed = True
    return f

# END DECORATORS #


def add_to_public_chat_queue(bot, content):
    """
    Adds the message to the left side of the chat queue.
    """
    bot.public_message_queue.appendleft(content)


def add_to_private_chat_queue(bot, user_display_name, content):
    """
    Creates a tuple of the user and message.
    Appends that to the left side of the whisper queue.
    """
    whisper_tuple = (user_display_name, content)
    bot.private_message_queue.appendleft(whisper_tuple)


def add_to_appropriate_chat_queue(bot, message, content):
    if message.message_type.name == 'PUBLIC':
        bot.public_message_queue.appendleft(content)
    elif message.message_type.name == 'PRIVATE':
        user_display_name = message.display_name
        whisper_tuple = (user_display_name, content)
        bot.private_message_queue.appendleft(whisper_tuple)
    else:
        raise RuntimeError("Message class should have message_type enum with at least PRIVATE and PUBLIC fields")


def add_to_command_queue(bot, function_name, kwargs=None):
    """
    Creates a tuple of the function and key word arguments.
    Appends that to the left side of the command queue.
    """
    if kwargs is not None:
        command_tuple = (function_name, kwargs)
    else:
        command_tuple = (function_name, {})
    bot.command_queue.appendleft(command_tuple)


def fetch_random_reddit_post_title(subreddit, time_filter='day', limit=10):
    """
    Fetches a random title from the specified subreddit
    """
    reddit_specific_words = ['reddit', 'karma', 'repost', 'vote', '/r/']
    valid_thoughts = []
    r = praw.Reddit(client_id=reddit_client_id,
                    client_secret=reddit_client_secret,
                    user_agent=reddit_user_agent)

    submissions = r.subreddit(subreddit).top(time_filter=time_filter, limit=limit)
    for entry in submissions:
        if len([word for word in reddit_specific_words if word in entry.title.lower()]) == 0:
            valid_thoughts.append(entry.title)
    return random.choice(valid_thoughts)
