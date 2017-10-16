class Message:
    """
    So what does a message have?
    a service (twitch, beam, whatever)
    a message type (whisper, public message, direct message, etc?)
    a user (who sent the message, using the given unique identifier for a given service)
    message content = "!ogod buzzer baby"
    privilege (the privilegs of the user who sent the message)
    service uuid (the uuid of the service that sent the message)

    if more fields are required for a given service, this class should be subclassed
    the service class that uses those messages should provide helper functions
    """
    def __init__(self, service=None, message_type=None, user=None, display_name=None, content=None, privileges=[]):
        self.service = service
        self.message_type = message_type
        self.user = user
        self.display_name = display_name
        self.content = content
        self.privileges = privileges
