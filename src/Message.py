class Message:
    """
    So what does a message have?
    a service (twitch, beam, whatever)
    a message type (whisper, public message, direct message, etc?)
    a user (who sent the message, using the given unique identifier for a given service)
    message content = "!ogod buzzer baby"
    
    if more fields are required for a given service, this class should be subclassed
    the service class that uses those messages should provide helper functions
    """
    def __init__(self, service=None, message_type=None, user=None, content=None):
        self.service = service
        self.message_type = message_type
        self.user = user
        self.content = content