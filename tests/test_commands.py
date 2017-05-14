from inspect import getsourcefile
import os
import sys
from unittest.mock import Mock

import pytest
from collections import deque

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
parent_dir = os.path.join(current_dir, os.pardir)
sys.path.append(parent_dir)

import src.modules.commands as commands
from src.message import Message
from src.models import Command


class Service:
    def get_message_content(self, message):
        return message.content

    def get_mod_status(self, message):
        return message.is_mod


def _add_to_chat_queue(self, chat_str):
    self.chat_queue.appendleft(chat_str)


def _add_to_command_queue(self, func_name, kwargs=None):
    if kwargs is not None:
        command_tuple = (func_name, kwargs)
    else:
        command_tuple = (func_name, {})
    self.command_queue.appendleft(command_tuple)


@pytest.fixture
def mock_db_session():
    return Mock()


@pytest.fixture
def command_mixin_obj():
    command_mixin_obj = commands.CommandsMixin()
    command_mixin_obj.chat_queue = deque()
    command_mixin_obj.command_queue = deque()
    command_mixin_obj._add_to_chat_queue = _add_to_chat_queue.__get__(command_mixin_obj, commands.CommandsMixin)
    command_mixin_obj._add_to_command_queue = _add_to_command_queue.__get__(command_mixin_obj, commands.CommandsMixin)
    command_mixin_obj.service = Service()
    return command_mixin_obj


def test_add_command(command_mixin_obj, mock_db_session):
    pass


def test_add_no_bang_command(command_mixin_obj, mock_db_session):
    pass


def test_edit_command(command_mixin_obj, mock_db_session):
    pass


def test_edit_nonexistent_command(command_mixin_obj, mock_db_session):
    pass


def test_delete_command(command_mixin_obj, mock_db_session):
    pass


def test_delete_nonexistent_command(command_mixin_obj, mock_db_session):
    pass


def test_command_add(command_mixin_obj, mock_db_session):
    pass


def test_command_edit(command_mixin_obj, mock_db_session):
    pass


def test_command_delete(command_mixin_obj, mock_db_session):
    pass
