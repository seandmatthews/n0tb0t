class MotherMixin:
    def mama(self):
        chatters = self.service.get_all_chatters()
        if 'rizmomma' in chatters:
            self._add_to_chat_queue('Mother is here! Everybody be cool!')
        else:
            self._add_to_chat_queue('Mother is gone! Go crazy!')