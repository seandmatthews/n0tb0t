class OgodMixin:
    def ogod(self, message):
        """
        The bot responds with "X's delicate sensibilities have been offended!"

        !ogod
        !ogod an offensive thing
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1:
            offender_str = ' '.join(msg_list[1:])
            # TODO: Use NLP magic to figure out whether offender_str is plural or not
            ogod_str = "{} has offended {}'s delicate sensibilities!".format(offender_str, user)
        else:
            ogod_str = "{}'s delicate sensibilities have been offended!".format(user)
        self._add_to_chat_queue(ogod_str)