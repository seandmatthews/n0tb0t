from config import bot_info
from src.message import Message
import src.utils as utils


class OgodMixin:
    def ogod(self, message):
        """
        The bot responds with "X's delicate sensibilities have been offended!"
        !ogod
        !ogod an offensive thing
        """
        user = self.service.get_message_display_name(message)
        msg_list = self.service.get_message_content(message).split(' ')

        if len(msg_list) > 1:
            offender_str = ' '.join(msg_list[1:])
            if offender_str[0] in ["!", "/"]:
                ogod_str = f'Your poor attempts at hax have offended {bot_info["user"]}\'s delicate sensibilities!'
                utils.add_to_appropriate_chat_queue(self, message, ogod_str)
                utils.add_to_appropriate_chat_queue(self, message, f'!ban_roulette {user}')
                cheaty_message_object = Message(content=f'!ban_roulette {user}', is_mod=True)
                self.ban_roulette(cheaty_message_object)
            else:
                plural = False  # We are lazy right now
                if plural:
                    ogod_str = f"{offender_str} have offended {user}'s delicate sensibilities!"
                else:
                    ogod_str = f"{offender_str} has offended {user}'s delicate sensibilities!"
                utils.add_to_appropriate_chat_queue(self, message, ogod_str)
        else:
            ogod_str = f"{user}'s delicate sensibilities have been offended!"
            utils.add_to_appropriate_chat_queue(self, message, ogod_str)
