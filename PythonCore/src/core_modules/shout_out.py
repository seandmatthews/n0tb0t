import PythonCore.src.utils as utils
from PythonCore.src.base_module import BaseMixin


class ShoutOutMixin(BaseMixin):
    @utils.mod_only
    def so(self, message):
        """
        Shouts out a fellow caster in chat. Uses the platform API to confirm
        that the caster is real and to fetch their last played game.

        !SO FellowStreamerPerson
        """
        user = self.service.get_message_display_name(message)
        i = self.info['channel']
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            channel = msg_list[1]
            try:
                channel_url, game = self.service.get_channel_url_and_last_played_game(channel)
                shout_out_str = f"Friends, {channel} is worth a follow. They last played {game}. If that sounds appealing to you, check out {channel} at {channel_url}! Tell 'em {i} sent you!"
            except RuntimeError as e:
                shout_out_str = str(e)
            self.add_to_public_chat_queue(shout_out_str)
        else:
            self.add_to_appropriate_chat_queue(message, f'Sorry {user}, you need to specify a caster to shout out.')
