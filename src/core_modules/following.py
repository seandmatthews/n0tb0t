import src.utils as utils

class FollowingMixin:
    def following(self, message):
        """
        Returns how long a user has been following the channel.

        !following
        """
        userid = message.user
        utils.add_to_appropriate_chat_queue(self, message, self.service.follow_time(userid))
