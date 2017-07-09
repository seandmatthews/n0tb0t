from enum import Enum, auto
from uuid import uuid4
import collections


class Service:
    def __init__(self):
            self.uuid = uuid4().int
            self.message_queue = collections.deque()
            self.allowed_to_chat = True #potentally move this to twitch_service
    def _send_message(self, message):
        raise NotImplementedError()

    def add_to_message_queue(self, message):
        self.message_queue.appendleft(whisper_tuple)

    def _process_message_queue(self):
        while self.allowed_to_chat:
            if len(chat_queue) > 0:
                self._send_message(chat_queue.pop())

'''
These should be turned into a command or something, probably. So that we have a shutup message type or something.
    @utils.mod_only
    def stop_speaking(self):
        """
        Stops the bot from putting stuff in chat to cut down on bot spam.
        In long run, this should be replaced with rate limits.

        !stop_speaking
        """
        self.services.send_public_message("Okay, I'll shut up for a bit. !start_speaking when you want me to speak again.")
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
'''
