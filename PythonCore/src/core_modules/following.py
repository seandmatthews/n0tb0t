from PythonCore.src.base_module import BaseMixin


class FollowingMixin(BaseMixin):
    def following(self, message):
        """
        Returns how long a user has been following the channel.

        !following
        """
        userid = message.user
        username = self.service.get_message_display_name(message)
        self.add_to_appropriate_chat_queue(message, self.service.follow_time(userid, username))
