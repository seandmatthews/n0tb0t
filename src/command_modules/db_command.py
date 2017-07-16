from Command import command

class DatabaseCommand(Command):
    def __init__(self, allowed_privileges, disallowed_privileges, chat_command, echo_text):
        super().__init__(allowed_privileges, disallowed_privileges, chat_command)
        self.echo_text = echo_text

    def _execute(self, message, service):
        message.contents = self.echo_text
        service.add_to_message_queue(message)
