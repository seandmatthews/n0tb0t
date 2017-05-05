from inspect import getsourcefile
import os.path

from src.Service import Service


current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
data_dir = os.path.join(current_dir, 'DataAndLogs')

service = Service.TWITCH  # Pick an available option from the Service enum.
service_name = service.name

BOT_INFO = {
    'pw': '',  # Oauth token from twitch - get it here: https://twitchapps.com/tmi/
    'user': '',  # Twitch username of the bot account
    'channel': '',  # Twitch chat channel to join
    'twitch_api_client_id': ''  # Twitch client id - get it here: https://www.twitch.tv/settings/connections
}

bitly_access_token = ''  # Token from bitly for URL shortening

# For now, you have to create your own script to interact with the reddit API
# and put your own credentials here.
# The details of how to do this can be found here: https://github.com/reddit/reddit/wiki/OAuth2
# The client ID is the string of numbers and letters beneath the name and description of the application you create
reddit_client_id = ''  # Found here https://www.reddit.com/prefs/apps
reddit_client_secret = ''  # Found here https://www.reddit.com/prefs/apps
reddit_user_agent = ''  # Should use the form: <platform>:<app ID>:<version string> (by /u/<Reddit username>)

time_zone_choice = "US/Central"  # Pick your timezone. Some examples are listed below.

time_zone_examples = [
    "US/Alaska",
    "US/Aleutian",
    "US/Arizona",
    "US/Central",
    "US/East-Indiana",
    "US/Eastern",
    "US/Hawaii",
    "US/Indiana-Starke",
    "US/Michigan",
    "US/Mountain",
    "US/Pacific",
    "US/Pacific-New",
    "US/Samoa",
    "Etc/GMT+0",
    "Etc/GMT+1",
    "Etc/GMT+10",
    "Etc/GMT+11",
    "Etc/GMT+12",
    "Etc/GMT+2",
    "Etc/GMT+3",
    "Etc/GMT+4",
    "Etc/GMT+5",
    "Etc/GMT+6",
    "Etc/GMT+7",
    "Etc/GMT+8",
    "Etc/GMT+9",
    "Etc/GMT-0",
    "Etc/GMT-1",
    "Etc/GMT-10",
    "Etc/GMT-11",
    "Etc/GMT-12",
    "Etc/GMT-13",
    "Etc/GMT-14",
    "Etc/GMT-2",
    "Etc/GMT-3",
    "Etc/GMT-4",
    "Etc/GMT-5",
    "Etc/GMT-6",
    "Etc/GMT-7",
    "Etc/GMT-8",
    "Etc/GMT-9"
]

