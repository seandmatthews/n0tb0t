from enum import Enum, auto


class Services(Enum):
    TWITCH = auto()
    MIXER = auto()


class BaseService:
    def send_public_message(self):
        pass

    def send_private_message(self):
        pass

    # Getter methods
    @staticmethod
    def get_message_display_name(message):
        pass

    @staticmethod
    def get_message_content(message):
        pass

    @staticmethod
    def get_mod_status(message):
        pass

    @staticmethod
    def get_message_type(message):
        pass

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