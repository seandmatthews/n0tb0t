import datetime
import functools
import random

import gspread
import praw
import requests

from config import reddit_client_id
from config import reddit_client_secret
from config import reddit_user_agent

from config import bot_info


# DECORATORS #
def _retry_gspread_func(f):
    """
    Retries the function that uses gspread until it completes without throwing an HTTPError
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        while True:
            try:
                f(*args, **kwargs)
            except gspread.exceptions.GSpreadException:
                continue
            break

    return wrapper


def _mod_only(f):
    """
    Set's the method's _mods_only property to True
    """
    f._mod_only = True
    return f


def _private_message_allowed(f):
    """
    Set's the method's _mods_only property to True
    """
    f._private_message_allowed = True
    return f


def _public_message_disallowed(f):
    """
    Set's the method's _mods_only property to True
    """
    f._public_message_disallowed = True
    return f

# END DECORATORS #


class UtilsMixin:

    def _get_live_time(self):
        """
        Uses the kraken API to fetch the start time of the current stream.
        Computes how long the stream has been running, returns that value in a dictionary.
        """
        channel = bot_info['channel']
        url = 'https://api.twitch.tv/kraken/streams/{}'.format(channel.lower())
        for attempt in range(5):
            try:
                r = requests.get(url, headers={"Client-ID": self.info['twitch_api_client_id']})
                r.raise_for_status()
                start_time_str = r.json()['stream']['created_at']
                start_time_dt = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%SZ')
                now_dt = datetime.datetime.utcnow()
                time_delta = now_dt - start_time_dt
                time_dict = {'hour': None,
                             'minute': None,
                             'second': None}

                time_dict['hour'], remainder = divmod(time_delta.seconds, 3600)
                time_dict['minute'], time_dict['second'] = divmod(remainder, 60)
                for time_var in time_dict:
                    if time_dict[time_var] == 1:
                        time_dict[time_var] = "{} {}".format(time_dict[time_var], time_var)
                    else:
                        time_dict[time_var] = "{} {}s".format(time_dict[time_var], time_var)
                time_dict['stream_start'] = start_time_dt
                time_dict['now'] = now_dt
            except requests.exceptions.HTTPError:
                continue
            except TypeError:
                self._add_to_chat_queue("Sorry, the channel doesn't seem to be live at the moment.")
                break
            except ValueError:
                continue
            else:
                return time_dict
        else:
            self._add_to_chat_queue(
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

    def _get_creation_date(self, user):
        """
        Returns the creation date of a given twitch user.
        """
        url = 'https://api.twitch.tv/kraken/users/{}'.format(user)
        for attempt in range(5):
            try:
                r = requests.get(url, headers={"Client-ID": self.info['twitch_api_client_id']})
                creation_date = r.json()['created_at']
                cut_creation_date = creation_date[:10]
            except ValueError:
                continue
            except TypeError:
                continue
            else:
                return cut_creation_date
        else:
            self._add_to_chat_queue(
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")

    def _fetch_random_reddit_post_title(self, subreddit, time_filter='day', limit=10):
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
