import threading

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
            utils.add_to_appropriate_chat_queue(self, message, 'You need to type out a username.')
            return
        try:
            bot_creation_date = utils.get_creation_date(msg_list[1])
        except RuntimeError as e:
            utils.add_to_appropriate_chat_queue(self, message, str(e))
            return
        viewers = self.service.get_viewers()
        mod_list = self.service.get_mods()
        whitelist = db_session.query(models.User.name).filter(models.User.whitelisted == True).all()
        mod_str = ', '.join(mod_list)
        for viewer in viewers:
            try:
                viewer_creation_date = utils.get_creation_date(viewer)
            except RuntimeError:
                continue
            if viewer_creation_date == bot_creation_date and viewer not in whitelist:
                self.service.send_public_message('/ban {}'.format(viewer))
        utils.add_to_public_chat_queue(self, f"We're currently experiencing a bot attack. If you're a human and were accidentally banned, please whisper a mod: {mod_str}")

    @utils.mod_only
    def whitelist(self, message, db_session):
        """
        Puts username on whitelist so they will NOT be banned by !anti_bot
    
        !whitelist
        """
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            utils.add_to_appropriate_chat_queue(self, message, 'You need to type out a username.')
            return

        user_db_obj = db_session.query(models.User).filter(models.User.name == msg_list[1]).one_or_none()
        if not user_db_obj:
            user_db_obj = models.User(name=msg_list[1])
            db_session.add(user_db_obj)
        if bool(user_db_obj.whitelisted):
            utils.add_to_appropriate_chat_queue(self, message, f'{msg_list[1]} is already in the whitelist!')
        else:
            user_db_obj.whitelisted = True
            utils.add_to_appropriate_chat_queue(self, message, f'{msg_list[1]} has been added to the whitelist.')

    @utils.mod_only
    def unwhitelist(self, message, db_session):
        """
        Removes user from whitelist designation so they can be banned by anti_bot.
    
        !unwhitelist testuser1
        """
        msg_list = self.service.get_message_content(message).lower().split(' ')
        if len(msg_list) == 1:
            utils.add_to_appropriate_chat_queue(self, message, 'You need to type out a username.')
            return
        user_db_obj = db_session.query(models.User).filter(models.User.name == msg_list[1]).one_or_none()
        if bool(user_db_obj.whitelisted) is False:
            utils.add_to_appropriate_chat_queue(self, message, f'{msg_list[1]} is already off the whitelist.')
        if bool(user_db_obj.whitelisted) is True:
            user_db_obj.whitelisted = False
            utils.add_to_appropriate_chat_queue(self, message, f'{msg_list[1]} has been removed from the whitelist.')

    @utils.mod_only
    def stop_speaking(self):
        """
        Stops the bot from putting stuff in chat to cut down on bot spam.
        In long run, this should be replaced with rate limits.

        !stop_speaking
        """
        self.service.send_public_message("Okay, I'll shut up for a bit. !start_speaking when you want me to speak again.")
        self.allowed_to_chat = False

    @utils.mod_only
    def start_speaking(self):
        """
        Allows the bot to start speaking again.

        !start_speaking
        """
        self.allowed_to_chat = True
        self.public_message_queue.clear()
        self.chat_thread = threading.Thread(target=self._process_chat_queue,
                                            kwargs={'chat_queue': self.public_message_queue})
        self.chat_thread.daemon = True
        self.chat_thread.start()
