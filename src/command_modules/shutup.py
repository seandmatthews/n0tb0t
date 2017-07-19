from src.command_modules.command import Command


class StopSpeaking(Command):
    """
    This is the generic shutup command. For use when the bot bugs out and talks too much.

    Example use:
        n0tb0t: bla bla bla
        n0tb0t: bla bla bla
        n0tb0t: bla bla bla
        luser: OMG THE BOT'S SO ANNOYING!!1
        Metruption: !stop_speaking
        <the bot no longer speaks>
    """
    def __init__(self, allowed_privileges=["moderator"], disallowed_privileges, chat_command="stop_speaking"):
        super().__init__(allowed_privileges, disallowed_privileges, chat_command)

    def _execute(self, message, service):
        service.allowed_to_chat = False


class StartSpeaking(Command):
    """
    This undoes the stop_speaking command. For use when the bot needs to talk again.

    Example use:
        luser: Teh bot is borked! plz can has working bot?
        Metruption: !start_speaking
        n0tb0t: Hello, I can talk again!
    """
    def __init__(self, allowed_privileges=["moderator"], disallowed_privileges, chat_command="start_speaking"):
        super().__init__(allowed_privileges, disallowed_privileges, chat_command)

    def _execute(self, message, service):
        service.allowed_to_chat = True
        message.contents = "Hello, I can talk again!"
        service.add_to_message_queue(message)
