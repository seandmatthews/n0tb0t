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

import src.core_modules.auto_quotes as auto_quotes
from src.message import Message
from src.models import AutoQuote


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
def autoquote_mixin_obj():
    autoquote_mixin_obj = auto_quotes.AutoQuoteMixin()
    autoquote_mixin_obj.public_message_queue = deque()
    autoquote_mixin_obj.command_queue = deque()
    autoquote_mixin_obj.service = Service()
    return autoquote_mixin_obj


def test_add_autoquote(autoquote_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = None
    autoquote_mixin_obj.add_auto_quote(Message(content="!add_auto_quote 300 this is a test", message_type=MessageTypes.PUBLIC), mock_db_session)
    mock_db_session.add.assert_called()
    assert autoquote_mixin_obj.public_message_queue[0].startswith('Auto quote added as auto quote #')
    assert len(autoquote_mixin_obj.command_queue) == 1