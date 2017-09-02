import os
import sys
from collections import deque
from enum import Enum, auto
from inspect import getsourcefile
from unittest.mock import Mock

import pytest

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
root_dir = os.path.join(current_dir, os.pardir, os.pardir)
sys.path.append(root_dir)

from src.message import Message
from src.streamer_specific_modules.player_queue import PlayerQueue as PlayerQueue
from src.streamer_specific_modules.player_queue import PlayerQueueMixin as PlayerQueueMixin


class Service:
    @staticmethod
    def get_message_content(message):
        return message.content

    @staticmethod
    def get_mod_status(message):
        return message.is_mod

    @staticmethod
    def get_message_display_name(message):
        return message.display_name


class MessageTypes(Enum):
    PUBLIC = auto()
    PRIVATE = auto()


def _write_player_queue(self):
    # This should maybe be a mock
    pass


@pytest.fixture
def mock_db_session():
    return Mock()


@pytest.fixture
def player_queue_mixin_obj():
    player_queue_mixin_obj = PlayerQueueMixin()
    player_queue_mixin_obj.player_queue = PlayerQueue()
    player_queue_mixin_obj.public_message_queue = deque()
    player_queue_mixin_obj.command_queue = deque()
    player_queue_mixin_obj.player_queue_credentials = None
    player_queue_mixin_obj._write_player_queue = _write_player_queue.__get__(player_queue_mixin_obj, PlayerQueueMixin)
    player_queue_mixin_obj.service = Service()
    return player_queue_mixin_obj


def test_pq_push():
    pq = PlayerQueue()
    pq.push('Alice', 0)
    pq.push('Bob', 1)
    pq.push('Jim', 0)
    assert pq.queue == deque([('Bob', 1,), ('Jim', 0,), ('Alice', 0)])


def test_pq_pop():
    pq = PlayerQueue()
    pq.push('Alice', 0)
    pq.push('Bob', 1)
    pq.push('Jim', 0)
    rightmost = pq.pop()
    assert rightmost == 'Alice'


def test_pq_pop_all():
    pq = PlayerQueue(cycle_num=2)
    pq.push('Alice', 0)
    pq.push('Bob', 1)
    pq.push('Jim', 0)
    players = pq.pop_all()
    assert players == ['Alice', 'Jim']


def test_join(player_queue_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = None
    player_queue_mixin_obj.join(Message(content="!join", display_name='Alice', message_type=MessageTypes.PUBLIC), mock_db_session)
    mock_db_session.add.assert_called()
    assert len(player_queue_mixin_obj.player_queue.queue) == 1
    assert player_queue_mixin_obj.public_message_queue[0] == "Alice, you've joined the queue."


def test_leave(player_queue_mixin_obj, mock_db_session):
    query_val = mock_db_session.query.return_value
    filter_val = query_val.filter.return_value
    filter_val.one_or_none.return_value = None
    player_queue_mixin_obj.join(Message(content="!join", display_name='Alice', message_type=MessageTypes.PUBLIC), mock_db_session)
    player_queue_mixin_obj.leave(Message(content="!leave", display_name='Alice', message_type=MessageTypes.PUBLIC))
    assert player_queue_mixin_obj.public_message_queue[0] == "Alice, you've left the queue."
    assert len(player_queue_mixin_obj.player_queue.queue) == 0
