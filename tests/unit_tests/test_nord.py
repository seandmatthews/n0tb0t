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

import src.modules.nords as nords
from src.message import Message


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

def ban_roulette():
    pass

@pytest.fixture
def nord_mixin_obj():
    nord_mixin_obj = nords.NordMixin()
    nord_mixin_obj.public_message_queue = deque()
    nord_mixin_obj.command_queue = deque()
    nord_mixin_obj.service = Service()
    nord_mixin_obj.ban_roulette
    return nord_mixin_obj
