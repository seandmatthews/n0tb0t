import os
import sys
from inspect import getsourcefile
from unittest.mock import Mock

import pytest

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
root_dir = os.path.join(current_dir, os.pardir, os.pardir, os.pardir)
sys.path.append(root_dir)

import PythonCore.src.core_modules.auto_quotes as auto_quotes
from PythonCore.src.models import AutoQuote
from PythonCore.src.message import Message
from PythonCore.src.base_service import MessageTypes


@pytest.fixture
def mock_db_session():
    return Mock()


@pytest.fixture
def auto_quote_mixin_obj():
    auto_quote_mixin_obj = auto_quotes.AutoQuoteMixin()
    yield auto_quote_mixin_obj
    for AQnum in auto_quote_mixin_obj.auto_quotes_timers.keys():
        auto_quote_mixin_obj.auto_quotes_timers[AQnum].cancel()
    del auto_quote_mixin_obj.auto_quotes_timers


def test_add_auto_quote(auto_quote_mixin_obj, mock_db_session):
    auto_quote_mixin_obj.add_auto_quote(Message(content="!add_auto_quote 300 this is a test", message_type=MessageTypes.PUBLIC), mock_db_session)
    mock_db_session.add.assert_called()
    assert auto_quote_mixin_obj.public_message_queue[0].startswith('Auto quote added as auto quote #')
    assert len(auto_quote_mixin_obj.auto_quotes_timers) == 1
    assert len(auto_quote_mixin_obj.command_queue) == 1


def test_edit_auto_quote(auto_quote_mixin_obj, mock_db_session):
    pass


def test_delete_auto_quote(auto_quote_mixin_obj, mock_db_session):
    auto_quote_mixin_obj.add_auto_quote(Message(content="!add_auto_quote 300 this is a test", message_type=MessageTypes.PUBLIC), mock_db_session)
    assert len(auto_quote_mixin_obj.auto_quotes_timers) == 1

    # Cheese strats go here
    for AQnum in auto_quote_mixin_obj.auto_quotes_timers.keys():
        auto_quote_mixin_obj.auto_quotes_timers[AQnum].cancel()
    auto_quote_mixin_obj.auto_quotes_timers = {}

    auto_quote_mixin_obj._create_repeating_timer(1, "this is a test", 300)
    query_val = mock_db_session.query.return_value
    query_val.all.return_value = [AutoQuote(id=1, period=300, quote="this is a test", active=True)]

    auto_quote_mixin_obj.delete_auto_quote(Message(content="!delete_auto_quote 1", message_type=MessageTypes.PUBLIC), mock_db_session)
    assert len(auto_quote_mixin_obj.auto_quotes_timers) == 0
    assert auto_quote_mixin_obj.public_message_queue[0] == 'Auto quote deleted'
