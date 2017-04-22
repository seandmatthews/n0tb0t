import random


class ShowerThoughtFetcherMixin:
    def __init__(self):
        super(ShowerThoughtFetcherMixin, self).__init__()

    def shower_thought(self):
        """
        Fetches a top shower thought from reddit in the last week and sends it to chat.

        !shower_thought
        """
        self._add_to_chat_queue(self._fetch_random_reddit_post_title('showerthoughts', time_filter='day', limit=25))