class NordMixin:
    def nord(self, message):
        """
        The bot responds with "X belongs to the Nords!"

        !nord
        !nord something that belongs to the Nords
        """
        msg_list = self.service.get_message_content(message).split(' ')

        if len(msg_list) > 1:
            belongs_str = ' '.join(msg_list[1:])
            # TODO: Use NLP magic to figure out whether offender_str is plural or not
            plural = False  # We are lazy right now
            if plural:
                nord_str = f'{belongs_str} belong to the Nords!'
            else:
                nord_str = f'{belongs_str} belongs to the Nords!'
        else:
            nord_str = f'Skyrim belongs to the Nords!'
        self._add_to_chat_queue(nord_str)
