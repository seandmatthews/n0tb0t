import src.utils as utils


class ShowerThoughtFetcherMixin:
    def shower_thought(self):
        """
        Fetches a top shower thought from reddit in the last week and sends it to chat.

        !shower_thought
        """
        self._add_to_chat_queue(utils.fetch_random_reddit_post_title('showerthoughts', time_filter='day', limit=25))