import src.utils as utils


class FollowingMixin:
    def following(self, message):
        """
        Returns how long a user has been following the channel.

        !following
        """
        userid = message.user
        username = self.service.get_message_display_name(message)
        utils.add_to_appropriate_chat_queue(self, message, self.service.follow_time(userid, username))
