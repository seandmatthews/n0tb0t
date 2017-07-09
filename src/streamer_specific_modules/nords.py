import src.utils as utils
from src.message import Message


class NordMixin:
    def nord(self, message):
        """
        The bot responds with "X belongs to the Nords!"

        !nord
        !nord something that belongs to the Nords
        """
        msg_list = self.service.get_message_content(message).split(' ')
        user = self.service.get_message_display_name(message)

        if len(msg_list) > 1:
            belongs_str = ' '.join(msg_list[1:])
            if belongs_str[0] in ["!", "/"]:
                nord_str = 'Dirty cheaters belong to the Nords!'
                utils.add_to_appropriate_chat_queue(self, message, nord_str)
                utils.add_to_appropriate_chat_queue(self, message, f'!ban_roulette {user}')
                cheaty_message_object = Message(content=f'!ban_roulette {user}', is_mod=True)
                self.ban_roulette(cheaty_message_object)
            else:
                plural = False  # We are lazy right now
                if plural:
                    nord_str = f'{belongs_str} belong to the Nords!'
                else:
                    nord_str = f'{belongs_str} belongs to the Nords!'
                utils.add_to_appropriate_chat_queue(self, message, nord_str)
        else:
            nord_str = 'Skyrim belongs to the Nords!'
            utils.add_to_appropriate_chat_queue(self, message, nord_str)