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

import src.modules.quotes as quotes
from src.message import Message
from src.models import Quote


class Service:
    def get_message_content(self, message):
        return message.content

    def get_mod_status(self, message):
        return message.is_mod


def _add_to_chat_queue(self, chat_str):
    self.chat_queue.appendleft(chat_str)


def _add_to_command_queue(self, function, kwargs=None):
    if kwargs is not None:
        command_tuple = (function, kwargs)
    else:
        command_tuple = (function, {})
    self.command_queue.appendleft(command_tuple)


@pytest.fixture
def quote_mixin_obj():
    quote_mixin_obj = quotes.QuotesMixin()
    quote_mixin_obj.chat_queue = deque()
    quote_mixin_obj.command_queue = deque()
    quote_mixin_obj._add_to_chat_queue = _add_to_chat_queue.__get__(quote_mixin_obj, quotes.QuotesMixin)
    quote_mixin_obj._add_to_command_queue = _add_to_command_queue.__get__(quote_mixin_obj, quotes.QuotesMixin)
    quote_mixin_obj.service = Service()
    return quote_mixin_obj

@pytest.fixture
def mock_db_session():
    return Mock()


def test_add_quote(quote_mixin_obj, mock_db_session):
    quote_mixin_obj.add_quote(Message(content="!add_quote test"), db_session=mock_db_session)
    mock_db_session.add.assert_called()
    assert quote_mixin_obj.chat_queue[0].startswith('Quote added as quote #')
    assert len(quote_mixin_obj.command_queue) == 1


def test_edit_quote(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.edit_quote(Message(content="!edit_quote 1 I'm different now"), db_session=mock_db_session)
    assert len(quote_mixin_obj.chat_queue) == 1
    assert quote_mixin_obj.chat_queue[0] == 'Quote has been edited.'
    assert len(quote_mixin_obj.command_queue) == 1


def test_edit_quote_invalid_index(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.edit_quote(Message(content="!edit_quote banana I'm different now"), db_session=mock_db_session)
    assert len(quote_mixin_obj.chat_queue) == 1
    assert quote_mixin_obj.chat_queue[0] == 'You must use a digit to specify a quote.'
    assert len(quote_mixin_obj.command_queue) == 0


def test_delete_quote_success(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.delete_quote(Message(content="!delete_quote 1"), db_session=mock_db_session)
    mock_db_session.delete.assert_called()
    assert quote_mixin_obj.chat_queue[0].startswith('Quote deleted')
    assert len(quote_mixin_obj.command_queue) == 1


def test_delete_quote_index_too_high(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.delete_quote(Message(content="!delete_quote 2"), db_session=mock_db_session)
    assert quote_mixin_obj.chat_queue[0].startswith('That quote does not exist')


def test_delete_quote_not_a_number(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.delete_quote(Message(content="!delete_quote banana"), db_session=mock_db_session)
    assert len(quote_mixin_obj.chat_queue) == 0


def test_quote(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.quote(Message(content="!quote"), db_session=mock_db_session)
    assert quote_mixin_obj.chat_queue[0] == '#1 this is a single quote'


def test_quote_specific(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a quote'), Quote(quote='this is a second quote')]
    quote_mixin_obj.quote(Message(content="!quote 2"), db_session=mock_db_session)
    assert quote_mixin_obj.chat_queue[0] == '#2 this is a second quote'


def test_quote_add(quote_mixin_obj, mock_db_session):
    quote_mixin_obj.quote(Message(content="!quote add test"), db_session=mock_db_session)
    mock_db_session.add.assert_called()
    assert quote_mixin_obj.chat_queue[0].startswith('Quote added as quote #')
    assert len(quote_mixin_obj.command_queue) == 1


def test_quote_edit_non_mod(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.quote(Message(content="!quote edit 1 Different now", is_mod=False), db_session=mock_db_session)
    assert len(quote_mixin_obj.command_queue) == 0


def test_quote_delete_success(quote_mixin_obj, mock_db_session):
    query = mock_db_session.query.return_value
    query.all.return_value = [Quote(quote='this is a single quote')]
    quote_mixin_obj.quote(Message(content="!quote delete 1", is_mod=True), db_session=mock_db_session)
    mock_db_session.delete.assert_called()
    assert quote_mixin_obj.chat_queue[0].startswith('Quote deleted')
    assert len(quote_mixin_obj.command_queue) == 1
