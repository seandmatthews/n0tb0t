class OgodMixin:
    def ogod(self, message):
        """
        The bot responds with "X's delicate sensibilities have been offended!"

        !ogod
        !ogod an offensive thing
        """
        user = self.service.get_display_name(message)
        msg_list = self.service.get_message_content(message).split(' ')

        if len(msg_list) > 1:
            offender_str = ' '.join(msg_list[1:])
            # TODO: Use NLP magic to figure out whether offender_str is plural or not
            plural = False  # We are lazy right now
            if plural:
                ogod_str = "{} have offended {}'s delicate sensibilities!".format(offender_str, user)
            else:
                ogod_str = "{} has offended {}'s delicate sensibilities!".format(offender_str, user)
        else:
            ogod_str = "{}'s delicate sensibilities have been offended!".format(user)
        self._add_to_chat_queue(ogod_str)