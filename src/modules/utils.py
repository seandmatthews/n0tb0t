import functools
import datetime
import gspread
import requests
from config import BOT_INFO


class UtilsMixin(object):
    def __init__(self):
        super(UtilsMixin, self).__init__()



    def _get_live_time(self):
        """
        Uses the kraken API to fetch the start time of the current stream.
        Computes how long the stream has been running, returns that value in a dictionary.
        """
        channel = BOT_INFO['channel']
        url = 'https://api.twitch.tv/kraken/streams/{}'.format(channel.lower())
        for attempt in range(5):
            try:
                r = requests.get(url)
                r.raise_for_status()
                start_time_str = r.json()['stream']['created_at']
                start_time_dt = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%SZ')
                now_dt = datetime.datetime.utcnow()
                time_delta = now_dt - start_time_dt
                time_dict = {'hour': None,
                             'minute': None,
                             'second': None}

                time_dict['hour'], remainder = divmod(time_delta.seconds, 3600)
                time_dict['minute'], time_dict['second'] = divmod(remainder, 60)
                for time_var in time_dict:
                    if time_dict[time_var] == 1:
                        time_dict[time_var] = "{} {}".format(time_dict[time_var], time_var)
                    else:
                        time_dict[time_var] = "{} {}s".format(time_dict[time_var], time_var)
                time_dict['stream_start'] = start_time_dt
                time_dict['now'] = now_dt
            except requests.exceptions.HTTPError:
                continue
            except TypeError:
                self._add_to_chat_queue('Sorry, the channel doesn\'t seem to be live at the moment.')
                break
            except ValueError:
                continue
            else:
                return time_dict
        else:
            self._add_to_chat_queue(
                "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")