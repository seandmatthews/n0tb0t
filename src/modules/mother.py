class MotherMixin:
    def mama(self):
        """
        Checks to see if RizMomma is in chat.
        Mostly so Riz knows how lewd to be when playing Quiplash
        
        !mama
        """
        chatters = self.service.get_all_chatters()
        if 'rizmomma' in chatters:
            self._add_to_chat_queue('Mother is here! Everybody be cool!')
        else:
            self._add_to_chat_queue('Mother is gone! Go crazy!')
