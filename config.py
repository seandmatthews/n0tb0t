from enum import Enum, auto
from inspect import getsourcefile
import os.path


current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
data_dir = os.path.join(current_dir, 'DataAndLogs')


class Service(Enum):
    TWITCH = auto()
    BEAM = auto()  # TODO: Do beam stuff... you know... eventually


service = Service.TWITCH
service_name = service.name

if service == Service.TWITCH:
    BOT_INFO = {
        'pw': '',  # Oauth token from twitch - get it here: https://twitchapps.com/tmi/
        'user': '',  # Twitch username of the bot account
        'channel': '',  # Twitch chat channel to join
        'twitch_api_client_id': ''  # Twitch client id - get it here: https://www.twitch.tv/settings/connections
    }
elif service == Service.BEAM:
    BOT_INFO = {

    }
    raise NotImplementedError("We don't actually care about Beam yet. Sorry")


bitly_access_token = ''  # Token from bitly for URL shortening


# For now, you have to create your own script to interact with the reddit API
# and put your own credentials here.
# The details of how to do this can be found here: https://github.com/reddit/reddit/wiki/OAuth2
# The client ID is the string of numbers and letters beneath the name and description of the application you create
reddit_client_id = ''  # Found here https://www.reddit.com/prefs/apps
reddit_client_secret = ''  # Found here https://www.reddit.com/prefs/apps
reddit_user_agent = ''  # Should use the form: <platform>:<app ID>:<version string> (by /u/<Reddit username>)
