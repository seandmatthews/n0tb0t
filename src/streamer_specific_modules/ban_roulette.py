import random
import src.utils as utils


class BanRouletteMixin:
    def ban_roulette(self, message):
        """
        Roulette which has a 1/6 change of timing out the user for 30 seconds.

        !ban_roulette
        !ban_roulette testuser
        """
        if self.service.get_mod_status(message):
            if len(self.service.get_message_content(message).split(' ')) > 1:
                user = self.service.get_message_content(message).split(' ')[1]
            else:
                user = None
        elif len(self.service.get_message_content(message).split(' ')) == 1:
            user = self.service.get_message_display_name(message)
        else:
            user = None
        if user is not None:
            if random.randint(1, 6) == 6:
                timeout_time = 30
                timeout_message_content = self.service.get_time_out_message(user, timeout_time)
                utils.add_to_approptiate_chat_queue(self, message, timeout_message_content)
                utils.add_to_approptiate_chat_queue(self, message, f'Bang! {user} was timed out.')
            else:
                utils.add_to_approptiate_chat_queue(self, message, f'{user} is safe for now.')
