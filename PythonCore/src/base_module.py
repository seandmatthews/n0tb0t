import collections
import concurrent.futures as futures
import os

import grpc
import sqlalchemy
from sqlalchemy.orm import sessionmaker

import PythonCore.config as config
from PythonCore.src.base_service import BaseService


class BaseMixin:
    def __init__(self):
        if self.__class__.__name__ != "Bot":
            self.public_message_queue = collections.deque()
            self.private_message_queue = collections.deque()
            self.command_queue = collections.deque()
            self.starting_spreadsheets_list = []
            self.credentials = None
            self.spreadsheets = []
            self.Session = self._get_dummy_Session()
            self.service = BaseService()
            self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    def _get_dummy_Session(self):
        if self.__class__.__name__ == "Bot":
            raise RuntimeError('This function should not be used in this context. use self.Session instead')
        self.db_path = os.path.join(config.data_dir, 'test.db')
        engine = sqlalchemy.create_engine(f'sqlite:///{self.db_path}', connect_args={'check_same_thread': False})
        session_factory = sessionmaker(bind=engine)
        return session_factory

    def add_to_public_chat_queue(self, content):
        """
        Adds the message to the left side of the chat queue.
        """
        self.public_message_queue.appendleft(content)

    def add_to_appropriate_chat_queue(self, message, content):
        if message.message_type.name == 'PUBLIC':
            self.public_message_queue.appendleft(content)
        elif message.message_type.name == 'PRIVATE':
            user_display_name = message.display_name
            whisper_tuple = (user_display_name, content)
            self.private_message_queue.appendleft(whisper_tuple)
        else:
            raise RuntimeError("Message class should have message_type enum with at least PRIVATE and PUBLIC fields")

    def add_to_command_queue(self, function_name, kwargs=None):
        """
        Creates a tuple of the function and key word arguments.
        Appends that to the left side of the command queue.
        """
        if kwargs is not None:
            command_tuple = (function_name, kwargs)
        else:
            command_tuple = (function_name, {})
        self.command_queue.appendleft(command_tuple)
