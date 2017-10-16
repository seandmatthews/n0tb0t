# This is the base command class. Every command should be a subclass of this one.
#
# When making a new command you should not overload the call_command function.
# Instead overload the _execute function.



# Also, lol wtf even is this?
#you'll see, you'll all see!
# tfw you try defining instance level variables at the class level, because who needs init methods anyway? LUL
#not us
# Also it's spelled privileges
#fixed it
# Also, on line 21, it should be if len(allowed_privilges) == 0:
#ogod lol
# Except I lied, because it should be self.allowed_privilges
#fixed that too
# Also, what's a disallowed privilege? Do we have some sort of caste system now?
#moar functionality
# "Dalits cannot use this function no matter what! Even if they're also a mod, or the streamer! It is verboten!" LUL
#whats a dalit

class Command:
    def __init__(self, name, allowed_privileges=[], disallowed_privileges=[]):
        self.name = name
        self.allowed_privileges = allowed_privileges
        self.disallowed_privileges = disallowed_privileges

    def check_privileges(self, privileges):
        for p in privileges:
            if p in self.disallowed_privilges:
                return False
        if len(self.allowed_privilges) == 0:
            return True
        for p in privileges:
            if p in self.allowed_privileges:
                return True
        return False

    def _execute(self, message, service):
        raise NotImplementedError()

    def call(self, message, service):
        if not self.check_privileges(message.privileges):
            return
        self._execute(message, service)
