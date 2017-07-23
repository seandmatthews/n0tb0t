from enum import Enum
import collections

'''
missing features:

a list of commands the service class will be listening for
a prefix for commands (!ogod vs .ogod or $ogod)
an implementation of _act_on()
'''
class Service:
    def __init__(self):
            self.message_queue = collections.deque()
            self.allowed_to_chat = True
            self.keep_running = True
            self.ready_to_run = False
            self.commands = dict()
            self.prefix = None

    def _send_message(self, message):
        raise NotImplementedError()

    def add_to_message_queue(self, message):
        self.message_queue.appendleft(whisper_tuple)

    def _process_message_queue(self):
        while self.allowed_to_chat:
            if len(chat_queue) > 0:
                self._send_message(chat_queue.pop())

    def _read_from_service(self):
        raise NotImplementedError()

    def _package_messages(self, raw_data):
        raise NotImplementedError()

    def _act_on(self, message):
        pass #this is going to replace bot's act_on

    def configure(self, json_dict):
        '''
        json_dict is a dictionary containing data loaded from json
        '''
        commands_to_load = json_dict["commands"]

    def run(self):
        while self.keep_running:
            raw_data = self._read_from_service()
            new_messages = self._package_messages(raw_data)
            for new_message in new_messages:
                self._act_on(new_message)
