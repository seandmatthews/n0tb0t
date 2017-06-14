from enum import Enum, auto
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

import src.core_modules.quotes as quotes
from src.message import Message
from src.models import Quote


class Service:
    @staticmethod
    def get_message_content(message):
        return message.content

    @staticmethod
    def get_mod_status(message):
        return message.is_mod


class MessageTypes(Enum):
    PUBLIC = auto()
    PRIVATE = auto()


@pytest.fixture
def mock_db_session():
    return Mock()


@pytest.fixture
def quote_mixin_obj():
    quote_mixin_obj = quotes.QuotesMixin()
    quote_mixin_obj.public_message_queue = deque()
    quote_mixin_obj.command_queue = deque()
    quote_mixin_obj.service = Service()
    return quote_mixin_obj


def test_add_quote(quote_mixin_obj, mock_db_session):
    quote_mixin_obj.add_quote(Message(content="!add_quote test", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    mock_db_session.add.assert_called()
    assert quote_mixin_obj.public_message_queue[0].startswith('Quote added as quote #')
    assert len(quote_mixin_obj.command_queue) == 1


def test_edit_quote(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.edit_quote(Message(content="!edit_quote 1 I'm different now", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    assert len(quote_mixin_obj.public_message_queue) == 1
    assert quote_mixin_obj.public_message_queue[0] == 'Quote has been edited.'
    assert len(quote_mixin_obj.command_queue) == 1


def test_edit_quote_invalid_index(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.edit_quote(Message(content="!edit_quote banana I'm different now", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    assert len(quote_mixin_obj.public_message_queue) == 1
    assert quote_mixin_obj.public_message_queue[0] == 'You must use a digit to specify a quote.'
    assert len(quote_mixin_obj.command_queue) == 0


def test_delete_quote_success(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.delete_quote(Message(content="!delete_quote 1", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    mock_db_session.delete.assert_called()
    assert quote_mixin_obj.public_message_queue[0].startswith('Quote deleted')
    assert len(quote_mixin_obj.command_queue) == 1


def test_delete_quote_index_too_high(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.delete_quote(Message(content="!delete_quote 2", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    assert quote_mixin_obj.public_message_queue[0].startswith('That quote does not exist')


def test_delete_quote_not_a_number(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.delete_quote(Message(content="!delete_quote banana", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    assert len(quote_mixin_obj.public_message_queue) == 0


def test_quote(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.quote(Message(content="!quote", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    assert quote_mixin_obj.public_message_queue[0] == '#1 this is a single quote'


def test_quote_specific(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a quote'), Quote(quote='this is a second quote')]
    quote_mixin_obj.quote(Message(content="!quote 2", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    assert quote_mixin_obj.public_message_queue[0] == '#2 this is a second quote'


def test_quote_add(quote_mixin_obj, mock_db_session):
    quote_mixin_obj.quote(Message(content="!quote add test", message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    mock_db_session.add.assert_called()
    assert quote_mixin_obj.public_message_queue[0].startswith('Quote added as quote #')
    assert len(quote_mixin_obj.command_queue) == 1


def test_quote_edit_non_mod(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.quote(Message(content="!quote edit 1 Different now", is_mod=False, message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    assert len(quote_mixin_obj.command_queue) == 0


def test_quote_delete_success(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.quote(Message(content="!quote delete 1", is_mod=True, message_type=MessageTypes.PUBLIC), db_session=mock_db_session)
    mock_db_session.delete.assert_called()
    assert quote_mixin_obj.public_message_queue[0].startswith('Quote deleted')
    assert len(quote_mixin_obj.command_queue) == 1
