import src.models as models
import src.utils as utils


class AntiBotMixin:
    @utils.mod_only
    def anti_bot(self, message, db_session):
        """
        Ban that user all other users who have the same creation date.
        Works under the assumption that bots are created programatically on the same day.
    
        !anti_bot testuser1
        """
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            self._add_to_chat_queue('You need to type out a username.')
            return
        try:
            bot_creation_date = self._get_creation_date(msg_list[1])
        except RuntimeError as e:
            self._add_to_chat_queue(str(e))
            return
        viewers = self.service.get_viewers()
        mod_list = self.service.get_mods()
        whitelist = db_session.query(models.User.name).filter(models.User.whitelisted == True).all()
        mod_str = ', '.join(mod_list)
        for viewer in viewers:
            try:
                viewer_creation_date = self._get_creation_date(viewer)
            except RuntimeError:
                continue
            if viewer_creation_date == bot_creation_date and viewer not in whitelist:
                self.service.send_public_message('/ban {}'.format(viewer))
        self._add_to_chat_queue(f"We're currently experiencing a bot attack. If you're a human and were accidentally banned, please whisper a mod: {mod_str}")

    @utils.mod_only
    def whitelist(self, message, db_session):
        """
        Puts username on whitelist so they will NOT be banned by !anti_bot
    
        !whitelist
        """
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            self._add_to_chat_queue('You need to type out a username.')
            return

        user_db_obj = db_session.query(models.User).filter(models.User.name == msg_list[1]).one_or_none()
        if not user_db_obj:
            user_db_obj = models.User(name=msg_list[1])
            db_session.add(user_db_obj)
        if bool(user_db_obj.whitelisted) is True:
            self._add_to_chat_queue(f'{msg_list[1]} is already in the whitelist!')
        else:
            user_db_obj.whitelisted = True
            self._add_to_chat_queue(f'{msg_list[1]} has been added to the whitelist.')

    @utils.mod_only
    def unwhitelist(self, message, db_session):
        """
        Removes user from whitelist designation so they can be banned by anti_bot.
    
        !unwhitelist testuser1
        """
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            self._add_to_chat_queue('You need to type out a username.')
            return
        user_db_obj = db_session.query(models.User).filter(models.User.name == msg_list[1]).one_or_none()
        if bool(user_db_obj.whitelisted) is False:
            self._add_to_chat_queue('{} is already off the whitelist.'.format(msg_list[1]))
        if bool(user_db_obj.whitelisted) is True:
            user_db_obj.whitelisted = False
            self._add_to_chat_queue('{} has been removed from the whitelist.'.format(msg_list[1]))
