'''
This is the base command class. Every command should be a subclass of this one.

When making a new command you should not overload the call_command function.
Instead overload the _execute function.
'''


class Command:
    self.allowed_privilges = []
    self.disallowed_privilges = []
    self.chat_command = ''

    def check_privilges(self, priviliges):
        for p in priviliges:
            if p in self.disallowed_privilges:
                return False
        if len(allowed_privilges == 0):
            return True
        for p in priviliges:
            if p in self.allowed_privilges:
                return True
        return False

    def _execute(self, message, service):
        raise NotImplementedError()

    def call(self, message, service):
        if not self.check_privilges(message.priviliges):
            return
        self._execute(message, service)
