from collections import deque
from inspect import getsourcefile
import os
import sys
from unittest.mock import Mock

import pytest

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
root_dir = os.path.join(current_dir, os.pardir, os.pardir)
sys.path.append(root_dir)

from src.modules.player_queue import PlayerQueue as PlayerQueue
from src.modules.player_queue import PlayerQueueMixin as PlayerQueueMixin


class Service:
    @staticmethod
    def get_message_content(message):
        return message.content

    @staticmethod
    def get_mod_status(message):
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
def player_queue_mixin_obj():
    player_queue_mixin_obj = PlayerQueueMixin()
    player_queue_mixin_obj.chat_queue = deque()
    player_queue_mixin_obj.command_queue = deque()
    player_queue_mixin_obj._add_to_chat_queue = _add_to_chat_queue.__get__(player_queue_mixin_obj, PlayerQueueMixin)
    player_queue_mixin_obj._add_to_command_queue = _add_to_command_queue.__get__(player_queue_mixin_obj, PlayerQueueMixin)
    # Something about _write_player_queue here probably
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


