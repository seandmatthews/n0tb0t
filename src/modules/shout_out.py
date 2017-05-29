import requests

import src.utils as utils


class ShoutOutMixin:
    @utils.mod_only
    def so(self, message):
        """
        Shouts out a twitch caster in chat. Uses the twitch API to confirm
        that the caster is real and to fetch their last played game.

        !SO $caster
        """
        user = self.service.get_message_display_name(message)
        me = self.info['channel']
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            channel = msg_list[1]
            url = f'https://api.twitch.tv/kraken/channels/{channel.lower()}'
            for attempt in range(5):
                try:
                    r = requests.get(url, headers={"Client-ID": self.info['twitch_api_client_id']})
                    r.raise_for_status()
                    game = r.json()['game']
                    channel_url = r.json()['url']
                    shout_out_str = f'Friends, {channel} is worth a follow. They last played {game}. If that sounds appealing to you, check out {channel} at {channel_url}! Tell \'em {me} sent you!'
                    utils.add_to_public_chat_queue(self, shout_out_str)
                except requests.exceptions.HTTPError:
                    utils.add_to_public_chat_queue(self, f"Hey {user}, that's not a real streamer!")
                    break
                except ValueError:
                    continue
                else:
                    break
            else:
                utils.add_to_appropriate_chat_queue(self, message, "Sorry, there was a problem talking to the twitch api. Maybe wait a bit and retry your command?")
        else:
            utils.add_to_appropriate_chat_queue(self, message, f'Sorry {user}, you need to specify a caster to shout out.')
