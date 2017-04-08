import src.models as models
import src.modules.Utils as Utils


class AntiBotMixin:

    @Utils._mod_only
    def anti_bot(self, message, db_session):
        """
        Ban that user all other users who have the same creation date.
        Works under the assumption that bots are created programatically on the same day.
    
        !anti_bot testuser1
        """
        user = self.service.get_username(message)
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            # TODO: Fix Whisper Stuff
            self._add_to_chat_queue('You need to type out a username.')
            # self._add_to_whisper_queue(user, 'You need to type out a username.')
            return
        bot_creation_date = self._get_creation_date(msg_list[1])
        viewers = self.service.fetch_chatters_from_API()['viewers']
        mod_list = self.service.get_mods()
        whitelist = db_session.query(models.User.name).filter(models.User.whitelisted == True).all()
        mod_str = ', '.join(mod_list)
        for viewer in viewers:
            if self._get_creation_date(viewer) == bot_creation_date and viewer not in whitelist:
                self.service.send_message('/ban {}'.format(viewer))
                # TODO: Fix Whisper Stuff
                # self._add_to_whisper_queue(viewer, 'We\'re currently experiencing a bot attack. If you\'re a human and were accidentally banned, please whisper a mod: {}'.format(mod_str))
        self._add_to_chat_queue(
            'We\'re currently experiencing a bot attack. If you\'re a human and were accidentally banned, please whisper a mod: {}'.format(
                mod_str))


    @Utils._mod_only
    def whitelist(self, message, db_session):
        """
        Puts username on whitelist so they will NOT be banned by !anti_bot
    
        !whitelist
        """
        user = self.service.get_username(message)
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, 'You need to type out a username.')
            self._add_to_chat_queue('You need to type out a username.')
            return

        user_db_obj = db_session.query(models.User).filter(models.User.name == msg_list[1]).one_or_none()
        if not user_db_obj:
            user_db_obj = models.User(name=msg_list[1])
            db_session.add(user_db_obj)
        if bool(user_db_obj.whitelisted) is True:
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, '{} is already in the whitelist!'.format(msg_list[1]))
            self._add_to_chat_queue('{} is already in the whitelist!'.format(msg_list[1]))
        else:
            user_db_obj.whitelisted = True
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, '{} has been added to the whitelist.'.format(msg_list[1]))
            self._add_to_chat_queue('{} has been added to the whitelist.'.format(msg_list[1]))


    @Utils._mod_only
    def unwhitelist(self, message, db_session):
        """
        Removes user from whitelist designation so they can be banned by anti_bot.
    
        !unwhitelist testuser1
        """
        user = self.service.get_username(message)
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, 'You need to type out a username.')
            self._add_to_chat_queue('You need to type out a username.')
            return
        user_db_obj = db_session.query(models.User).filter(models.User.name == msg_list[1]).one_or_none()
        if bool(user_db_obj.whitelisted) is False:
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, '{} is already off the whitelist.'.format(msg_list[1]))
            self._add_to_chat_queue('{} is already off the whitelist.'.format(msg_list[1]))
        if bool(user_db_obj.whitelisted) is True:
            user_db_obj.whitelisted = False
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, '{} has been removed from the whitelist.'.format(msg_list[1]))
            self._add_to_chat_queue('{} has been removed from the whitelist.'.format(msg_list[1]))