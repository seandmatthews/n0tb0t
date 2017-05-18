from inspect import getsourcefile
import os
import sys
from unittest.mock import Mock

import pytest
from collections import deque

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
root_dir = os.path.join(current_dir, os.pardir, os.pardir)
sys.path.append(root_dir)

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
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = None
    command_mixin_obj.add_command(Message(content="!add_command !test this is a test"), mock_db_session)
    mock_db_session.add.assert_called()
    assert command_mixin_obj.chat_queue[0] == 'Command added.'
    assert len(command_mixin_obj.command_queue) == 1


def test_add_command_no_bang(command_mixin_obj, mock_db_session):
    command_mixin_obj.add_command(Message(content="!add_command test this is a test"), mock_db_session)
    mock_db_session.add.assert_not_called()
    assert command_mixin_obj.chat_queue[0] == 'Sorry, the command needs to have an ! in it.'
    assert len(command_mixin_obj.command_queue) == 0


def test_add_command_collision(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = Command(call='test', response="This is a test")
    command_mixin_obj.add_command(Message(content="!add_command !test this is a test"), mock_db_session)
    assert command_mixin_obj.chat_queue[0] == 'Sorry, that command already exists. Please delete it first.'
    assert len(command_mixin_obj.command_queue) == 0


def test_edit_command(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = Command(call='test', response="This is a test")
    command_mixin_obj.edit_command(Message(content="!edit_command !test this is now different"), mock_db_session)
    assert command_mixin_obj.chat_queue[0] == 'Command edited.'
    assert len(command_mixin_obj.command_queue) == 1


def test_edit_nonexistent_command(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = None
    command_mixin_obj.edit_command(Message(content="!edit_command !test this is now different"), mock_db_session)
    assert command_mixin_obj.chat_queue[0] == 'Sorry, that command does not exist.'
    assert len(command_mixin_obj.command_queue) == 0


def test_delete_command(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = Command(call='test', response="This is a test")
    command_mixin_obj.delete_command(Message(content="!delete_command !test"), mock_db_session)
    mock_db_session.delete.assert_called()
    assert command_mixin_obj.chat_queue[0] == 'Command deleted.'
    assert len(command_mixin_obj.command_queue) == 1


def test_delete_nonexistent_command(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = None
    command_mixin_obj.delete_command(Message(content="!delete_command !test"), mock_db_session)
    assert command_mixin_obj.chat_queue[0] == "Sorry, that command doesn't exist."
    assert len(command_mixin_obj.command_queue) == 0


def test_command_add(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = None
    command_mixin_obj.command(Message(content="!command add !test this is a test"), mock_db_session)
    mock_db_session.add.assert_called()
    assert command_mixin_obj.chat_queue[0] == 'Command added.'
    assert len(command_mixin_obj.command_queue) == 1


def test_command_edit(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = Command(call='test', response="This is a test")
    command_mixin_obj.command(Message(content="!command edit !test this is a new test"), mock_db_session)
    assert command_mixin_obj.chat_queue[0] == 'Command edited.'
    assert len(command_mixin_obj.command_queue) == 1


def test_command_delete(command_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = Command(call='test', response="This is a test")
    command_mixin_obj.command(Message(content="!command delete !test"), mock_db_session)
    mock_db_session.delete.assert_called()
    assert command_mixin_obj.chat_queue[0] == 'Command deleted.'
    assert len(command_mixin_obj.command_queue) == 1

