import random

import praw

from config import reddit_client_id
from config import reddit_client_secret
from config import reddit_user_agent


class ShowerThoughtFetcherMixin:
    """docstring for ShowerThoughtFetcher"""
    def __init__(self):
        super(ShowerThoughtFetcherMixin, self).__init__()

    def _get_shower_thought(self):
        """
        Fetches the top shower thought from reddit.
        """
        shitty_reddit_words = ['Reddit', 'reddit', 'Karma', 'karma', 'Repost', 'repost', 'Vote', 'vote']
        valid_thoughts = []
        default_thought = "Waterboarding at Guantanamo Bay sounds super" \
                          "rad if you don't know what either of those things are."
        r = praw.Reddit(client_id=reddit_client_id,
                        client_secret=reddit_client_secret,
                        user_agent=reddit_user_agent)

        submissions = r.subreddit('showerthoughts').top(time_filter='day', limit=10)
        for entry in submissions:
            if len([word for word in shitty_reddit_words if word in entry.title]) == 0:
                valid_thoughts.append(entry.title)
        if len(valid_thoughts) > 0:
            return random.choice(valid_thoughts)
        else:
            return default_thought

    def shower_thought(self):
        """
        Fetches the top shower thought from reddit in the last 24 hours and sends it to chat.

        !shower_thought
        """
        self._add_to_chat_queue(self._get_shower_thought())