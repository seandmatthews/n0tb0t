import src.utils as utils


class MotherMixin:
    def mama(self, message):
        """
        Checks to see if RizMomma is in chat.
        Mostly so Riz knows how lewd to be when playing Quiplash
        
        !mama
        """
        chatters = self.service.get_all_chatters()
        if 'rizmomma' in chatters:
            utils.add_to_appropriate_chat_queue(self, message, 'Mother is here! Everybody be cool!')
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'Mother is gone! Go crazy!')
