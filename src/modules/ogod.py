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
            # TODO: Use NLP magic to figure out whether offender_str is plural or not
            plural = False  # We are lazy right now
            if plural:
                ogod_str = f"{offender_str} have offended {user}'s delicate sensibilities!"
            else:
                ogod_str = f"{offender_str} has offended {user}'s delicate sensibilities!"
        else:
            ogod_str = f"{user}'s delicate sensibilities have been offended!"
            utils.add_to_appropriate_chat_queue(self, message, ogod_str)
