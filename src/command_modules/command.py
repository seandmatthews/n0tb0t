# This is the base command class. Every command should be a subclass of this one.
#
# When making a new command you should not overload the call_command function.
# Instead overload the _execute function.



# Also, lol wtf even is this?
# tfw you try defining instance level variables at the class level, because who needs init methods anyway? LUL
# Also it's spelled privileges
# Also, on line 21, it should be if len(allowed_privilges) == 0:
# Except I lied, because it should be self.allowed_privilges
# Also, what's a disallowed privilege? Do we have some sort of caste system now?
# "Dalits cannot use this function no matter what! Even if they're also a mod, or the streamer! It is verboten!" LUL


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
