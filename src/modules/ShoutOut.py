import requests

import src.modules.Utils as Utils


class ShoutOutMixin:

    @Utils._mod_only
    def so(self, message):
        """
        Shouts out a twitch caster in chat. Uses the twitch API to confirm
        that the caster is real and to fetch their last played game.

        !SO $caster
        """
        user = self.service.get_username(message)
        me = self.info['channel']
        msg_list = self.service.get_human_readable_message(message).split(' ')
        if len(msg_list) > 1:
            channel = msg_list[1]
            url = 'https://api.twitch.tv/kraken/channels/{channel}'.format(channel=channel.lower())
            for attempt in range(5):
                try:
                    r = requests.get(url, headers={"Client-ID": self.info['twitch_api_client_id']})
                    r.raise_for_status()
                    game = r.json()['game']
                    channel_url = r.json()['url']
                    shout_out_str = 'Friends, {channel} is worth a follow. They last played {game}. If that sounds appealing to you, check out {channel} at {url}! Tell \'em {I} sent you!'.format(
                        channel=channel, game=game, url=channel_url, I=me)
                    self._add_to_chat_queue(shout_out_str)
                except requests.exceptions.HTTPError:
                    self._add_to_chat_queue('Hey {}, that\'s not a real streamer!'.format(user))
                    break
                except ValueError:
                    continue
                else:
                    break
            else:
                self._add_to_chat_queue(
                    "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")
        else:
            self._add_to_chat_queue('Sorry {}, you need to specify a caster to shout out.'.format(user))