class Message:
    """
    So what does a message have?
    a service (twitch, beam, whatever)
    a message type (whisper, public message, direct message, etc?)
    a user (who sent the message)
    message content = "!ogod buzzer baby"
    
    The goal is for the bot to act_on(Message)
    This should just hold data...
    """
    def __init__(self, service=None, message_type=None, user=None, content=None):
        self.service = service
        self.message_type = message_type
        self.user = user
        self.content = content