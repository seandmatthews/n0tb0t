import random


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
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(self.service.get_user(message), 'Sorry, this command is only one word')
            user = None
        if user is not None:
            if random.randint(1, 6) == 6:
                timeout_time = 30
                self._add_to_chat_queue('/timeout {} {}'.format(user, timeout_time))
                # self._add_to_whisper_queue(user, 'Pow!')
                self._add_to_chat_queue('Bang! {} was timed out.'.format(user))
            else:
                self._add_to_chat_queue('{} is safe for now.'.format(user))
                # self._add_to_whisper_queue(user, 'You\'re safe! For now at least.')