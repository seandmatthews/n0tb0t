from src.command_modules.command import Command

class AliasCommmand(Command):
    def __init__(self, chat_command, command):
        super().__init__(command.allowed_privileges, command.disallowed_privileges, chat_command)
        self._execute = command._execute


class Alias(Command):
    def __init__(self, allowed_privileges=["moderator"], disallowed_privileges, chat_command="alias"):
        super().__init__(allowed_privileges, disallowed_privileges, chat_command)

    def _execute(self, message, service):
        '''
        preconditions:
            receives a message like so:
                *   !alias <existing chat command> as <new chat command>
                *   the service class has no existing commands with
                    <new chat command> as their current chat command

        postconditions:
            if the preconditions are met it adds an AliasCommand to the
            service's command dict and adds the AliasCommand to the service's
            config so that the command is preserved over reboots then it sends
            a success message
                e.g. !alias ogod as offended

            if the preconditions are not met it gives a yet to be determined
            reasonal response message
            *   Error adding alias: <new chat command> is already a chat command.
            *   Error adding alias <mesage.contents> is invalid syntax.
        '''
        pass
