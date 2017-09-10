from enum import Enum, auto


class Services(Enum):
    TWITCH = auto()
    MIXER = auto()


class MessageTypes(Enum):
    # When you define your own service it must have its bot instance process messages
    # its message_type attribute must be able to be at least PUBLIC and PRIVATE
    PUBLIC = auto()
    PRIVATE = auto()


class BaseService:
    def send_public_message(self):
        pass

    def send_private_message(self):
        pass

    # Getter methods
    @staticmethod
    def get_message_display_name(message):
        return message.display_name

    @staticmethod
    def get_message_content(message):
        return message.content

    @staticmethod
    def get_mod_status(message):
        return message.is_mod

    @staticmethod
    def get_message_type(message):
        return message.message_type.name

    def get_user_creation_date(self, username):
        pass

    def get_mods(self):
        pass

    def get_viewers(self):
        pass

    def get_all_chatters(self):
        pass

    def get_live_time(self):
        pass

    def follow_time(self):
        pass

    def get_channel_url_and_last_played_game(self):
        pass

    def get_time_out_message(self):
        pass

    def run(self):
        pass