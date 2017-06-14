import src.utils as utils


class ShowerThoughtFetcherMixin:
    def shower_thought(self, message):
        """
        Fetches a top shower thought from reddit in the last week and sends it to chat.

        !shower_thought
        """
        shower_thought = utils.fetch_random_reddit_post_title('showerthoughts', time_filter='day', limit=25)
        utils.add_to_appropriate_chat_queue(self, message, shower_thought)
