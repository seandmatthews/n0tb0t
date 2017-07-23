import pytest

from src.command_modules.simple_command import *
from src.message import Message

#@todo(someone): do proper mocking if necessary
class FakeService:
    def __init__():
        pass#@todo(aaron) add command dict mocking

    def add_to_message_queue(self, message):
        return message.contents


def test_SimpleCommand():
    echo_string = "this is a test"
    simple = SimpleCommand(None, echo_string)

    fservice = FakeService()

    assert simple.call(Message(), fservice) == echo_string


def test_SimpleCommandAdder():
    new_command_name = "test" #has no spaces
    echo_string = "this is a test"
    adder_command_name = "addcom"

    fservice = FakeService()
    adder = SimpleCommandAdder(adder_command_name)
    valid_message = Message(contents="!{} {} {}".format(adder_command_name, new_command_name, echo_string))

    assert adder.call(valid_message, fservice) == "Successfully added command {}.".format(command_name_valid)
    assert True == False #@todo(aaron): create service's ability to store commands
