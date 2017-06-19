import collections
import copy
import json
import os
import random
import threading

import gspread
import sqlalchemy

import src.models as models
import src.utils as utils
from config import data_dir
from src.message import Message


class PlayerQueue:
    def __init__(self, cycle_num=7, input_iterable=None):
        self.queue = collections.deque()
        self.cycle_num = cycle_num
        if input_iterable is not None:
            for tup in input_iterable:
                self.push(tup[0], tup[1])

    def push(self, player, priority):
        """
        player is the twitch username of a prospective player
        priority is the number of times they've played with the caster
        """
        index = None
        for i, tup in enumerate(self.queue):
            if player == tup[0]:
                raise RuntimeError('That player already exists in this queue')
            elif index is None and priority >= tup[1]:
                index = i

        if index is not None:
            self.queue.insert(index, (player, priority,))
        else:
            self.queue.append((player, priority,))

    def pop(self):
        """
        Removes one player, priority tuple from the player queue and returns the player's name
        """
        return self.queue.pop()[0]

    def pop_all(self):
        """
        It pops up to cycle_num players, which is 7 by default.
        If there are not enough then it will pop all available players.
        """
        return_list = []
        players = min(self.cycle_num, len(self.queue))
        for player in range(players):
            return_list.append(self.pop())
        return return_list


class PlayerQueueMixin:
    def __init__(self):
        self.ready_user_dict = dict()


    def _update_player_queue_spreadsheet(self, player_queue):
        """
        Used by the join command.
        """
        spreadsheet_name, _ = self.spreadsheets['player_queue']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        pqs = sheet.worksheet('Player Queue')
        worksheet_width = 2

        cells = pqs.range(f'A2:B{len(player_queue)+11}')
        for cell in cells:
            cell.value = ''
        pqs.update_cells(cells)

        cells = pqs.range(f'A2:B{len(player_queue)+1}')
        for index, tup in enumerate(reversed(player_queue)):
            user_cell_index = index * worksheet_width
            times_played_index = user_cell_index + 1

            cells[user_cell_index].value = tup[0]
            cells[times_played_index].value = tup[1]
        pqs.update_cells(cells)

    def _write_player_queue(self):
        """
        Writes the player queue to a json file
        to be loaded on startup if needed.
        """
        with open(os.path.join(data_dir, f"{self.info['channel']}_player_queue.json"), 'w', encoding="utf-8") as player_file:
            json.dump(list(self.player_queue.queue), player_file, ensure_ascii=False)

    @utils.private_message_allowed
    def join(self, message, db_session):
        """
        Adds the user to the game queue.
        The players who've played the fewest
        times with the caster get priority.
        Must be whispered to the bot.

        !join
        """
        username = self.service.get_message_display_name(message)
        user = db_session.query(models.User).filter(models.User.name == username).one_or_none()
        if not user:
            user = models.User(name=username)
            db_session.add(user)
        try:
            self.player_queue.push(username, user.times_played)
            self._write_player_queue()
            utils.add_to_appropriate_chat_queue(self, message, f"{username}, you've joined the queue.")
            try:
                del self.ready_user_dict[username]
            except KeyError:
                pass
            queue_snapshot = copy.deepcopy(self.player_queue.queue)
            utils.add_to_command_queue(self, '_update_player_queue_spreadsheet', {'player_queue': queue_snapshot})
        except RuntimeError:
            utils.add_to_appropriate_chat_queue(self, message, f"{username}, you're already in the queue and can't join again.")



    @utils.private_message_allowed
    def leave(self, message):
        """
        Leaves the player queue once you've joined it.

        !leave
        """
        username = self.service.get_message_display_name(message)
        for tup in self.player_queue.queue:
            if tup[0] == username:
                self.player_queue.queue.remove(tup)
                self._write_player_queue()
                queue_snapshot = copy.deepcopy(self.player_queue.queue)
                utils.add_to_command_queue(self, '_update_player_queue_spreadsheet', {'player_queue': queue_snapshot})
                utils.add_to_appropriate_chat_queue(self, message, f"{username}, you've left the queue.")
                break
        else:
            utils.add_to_appropriate_chat_queue(self, message, f"{username}, you're not in the queue and must join before leaving.")

    @utils.private_message_allowed
    @utils.public_message_disallowed
    def confirm(self, message):
        """
        Confirms that you're present. 
        This is so the bot can send you your invite to play with the streamer.
        
        !confirm
        """
        player = self.service.get_message_display_name(message)
        self.ready_user_dict[player]['user_ready'] = True
        utils.add_to_private_chat_queue(self, player, self.ready_user_dict[player]['credential_str'])

    def spot(self, message):
        """
        Shows user current location in queue and current priority.

        !spot
        """
        try:
            username = self.service.get_message_display_name(message)
            for index, tup in enumerate(self.player_queue.queue):
                if tup[0] == username:
                    position = len(self.player_queue.queue) - index
                    utils.add_to_appropriate_chat_queue(self, message, f'{username} is number {position} in the queue. This may change as other players join.')
        except UnboundLocalError:
            utils.add_to_appropriate_chat_queue(self, message, f"{username}, you're not in the queue. Feel free to join it.")

    def show_player_queue(self, message):
        """
        Links the google spreadsheet containing the queue list

        !show_player_queue
        """
        user = self.service.get_message_display_name(message)
        web_view_link = self.spreadsheets['player_queue'][1]
        short_url = self.shortener.short(web_view_link)
        utils.add_to_appropriate_chat_queue(self, message, f'View the the queue at: {short_url}')

    def _create_credentials_message(self, channel, player, credentials=None):
        """
        Takes a set of crednentials and combines them with some reddit factoid 
        """
        subreddit = random.choice(['todayilearned', 'showerthoughts'])
        reddit_cleverness = utils.fetch_random_reddit_post_title(subreddit, time_filter='week', limit=100)
        if credentials is not None:
            whisper_str = f"{player}, you may now join {channel} to play. The credentials you need are: {credentials} Now here's something from Reddit. {reddit_cleverness}"
        else:
            whisper_str = f"{player}, you may now join {channel} to play. Now here's something from Reddit. {reddit_cleverness}"
        return whisper_str

    def _update_user_ready_dict(self, player):
        """
        Takes a player and checks if they've used the !confirm command to set their ready attribute to true
        If not, create a message object with the content that _create_credentials message will use to 
        generate a credentials string and pass it to cycle_one, along with a db_session.
        Either way, delete the player's entry in the ready_user_dict
        """
        if not self.ready_user_dict[player]['user_ready']:
            msg_obj = Message(content=self.ready_user_dict[player]['msg_content'])
            db_session = self.Session()
            self.cycle_one(message=msg_obj, db_session=db_session)
            db_session.commit()
            db_session.close()
        del self.ready_user_dict[player]

    @utils.private_message_allowed
    @utils.mod_only
    def cycle(self, message, db_session):
        """
        Sends out a message to the next set of players.

        !cycle
        !cycle Password!1
        """
        msg_content = self.service.get_message_content(message)
        msg_list = msg_content.split(' ')
        players = self.player_queue.pop_all()
        self._write_player_queue()
        players_str = ' '.join(players)
        channel = self.info['channel']
        if len(msg_list) > 1:
            self.player_queue_credentials = ' '.join(msg_list[1:])
        else:
            self.player_queue_credentials = None

        for player in players:
            player_obj = db_session.query(models.User).filter(models.User.name == player).one()
            player_obj.times_played += 1
            credentials_message = self._create_credentials_message(channel, player, self.player_queue_credentials)
            self.ready_user_dict[player] = {'user_ready': False,
                                            'channel': channel,
                                            'msg_content': msg_content,
                                            'credential_str': credentials_message}
            t = threading.Timer(45.0, self._update_user_ready_dict, [player])
            t.start()
            queue_snapshot = copy.deepcopy(self.player_queue.queue)
            utils.add_to_command_queue(self, '_update_player_queue_spreadsheet', {'player_queue': queue_snapshot})
        utils.add_to_public_chat_queue(self, f"{players_str} it is your turn to play! Please whisper the bot !confirm to confirm that you're here.")
        utils.add_to_public_chat_queue(self, f'There are {len(self.player_queue.queue)} people left in the queue')

    @utils.private_message_allowed
    @utils.mod_only
    def cycle_one(self, message, db_session):
        """
        Sends out a message to the next player.
        !cycle_one
        !cycle_one Password!1
        """
        msg_content = self.service.get_message_content(message)
        msg_list = msg_content.split(' ')
        channel = self.info['channel']
        try:
            player = self.player_queue.pop()
            player_obj = db_session.query(models.User).filter(models.User.name == player).one()
            player_obj.times_played += 1
            self._write_player_queue()
            if len(msg_list) > 1:
                credential_str = ' '.join(msg_list[1:])
            elif self.player_queue_credentials is not None:
                credential_str = self.player_queue_credentials
            else:
                credential_str = None

            credentials_message = self._create_credentials_message(channel, player, credential_str)
            self.ready_user_dict[player] = {'user_ready': False,
                                            'channel': channel,
                                            'msg_content': msg_content,
                                            'credential_str': credentials_message}
            t = threading.Timer(45.0, self._update_user_ready_dict, [player])
            t.start()
            utils.add_to_public_chat_queue(self, f'{player} it is your turn to play. Whisper !confirm to the bot')
            utils.add_to_public_chat_queue(self, f'There are {len(self.player_queue.queue)} people left in the queue.')
            queue_snapshot = copy.deepcopy(self.player_queue.queue)
            utils.add_to_command_queue(self, '_update_player_queue_spreadsheet', {'player_queue': queue_snapshot})
        except IndexError:
            utils.add_to_public_chat_queue(self, 'Sorry, there are no more players in the queue')

    @utils.mod_only
    def reset_queue(self, message, db_session):
        """
        Creates a new queue with the default room size
        and resets all players stats for how many
        times they've played with the caster.

        !reset_queue
        """
        self.player_queue = PlayerQueue()
        queue_snapshot = copy.deepcopy(self.player_queue.queue)
        utils.add_to_command_queue(self, '_update_player_queue_spreadsheet', {'player_queue': queue_snapshot})
        try:
            os.remove(os.path.join(data_dir, f"{self.info['channel']}_player_queue.json"))
        except FileNotFoundError:
            pass
        db_session.execute(sqlalchemy.update(models.User.__table__, values={models.User.__table__.c.times_played: 0}))
        utils.add_to_appropriate_chat_queue(self, message, 'The queue has been emptied and all players start fresh.')

    @utils.mod_only
    def set_cycle_number(self, message):
        """
        Sets the number of players to cycle
        in when it's time to play with new people.
        By default this value is 7.

        !set_cycle_number 5
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1 and msg_list[1].isdigit() and int(msg_list[1]) > 0:
            cycle_num = int(msg_list[1])
            self.player_queue.cycle_num = cycle_num
            utils.add_to_appropriate_chat_queue(self, message, f'The new room size is {cycle_num}.')
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'Make sure the command is followed by an integer greater than 0.')

    @utils.mod_only
    def promote(self, message, db_session):
        """
        Promotes a player in the player queue.

        !promote testuser
        """
        msg_list = self.service.get_message_content(message).split(' ')
        player = msg_list[1]
        for index, tup in enumerate(self.player_queue.queue):
            if tup[0] == player:
                times_played = tup[1]
                if times_played != 0:
                    result = db_session.query(models.User).filter(models.User.name == player).one()
                    result.times_played -= 1
                    self.player_queue.queue.remove(tup)
                    self.player_queue.push(player, times_played-1)
                    self._write_player_queue()
                    queue_snapshot = copy.deepcopy(self.player_queue.queue)
                    utils.add_to_command_queue(self, '_update_player_queue_spreadsheet',
                                               {'player_queue': queue_snapshot})
                else:
                    utils.add_to_appropriate_chat_queue(self, message, f'{player} cannot be promoted in the queue.')
                break
        else:
            utils.add_to_appropriate_chat_queue(self, message, f'{player} is not in the player queue.')

    @utils.mod_only
    def demote(self, message, db_session):
        """
        Demotes a player in the player queue.

        !demote testuser
        """
        msg_list = self.service.get_message_content(message).split(' ')
        player = msg_list[1]
        for index, tup in enumerate(self.player_queue.queue):
            if tup[0] == player:
                times_played = tup[1]
                result = db_session.query(models.User).filter(models.User.name == player).one()
                result.times_played += 1
                self.player_queue.queue.remove(tup)
                self.player_queue.push(player, times_played+1)
                self._write_player_queue()
                queue_snapshot = copy.deepcopy(self.player_queue.queue)
                utils.add_to_command_queue(self, '_update_player_queue_spreadsheet', {'player_queue': queue_snapshot})
                break
        else:
            utils.add_to_appropriate_chat_queue(self, message, f'{player} is not in the player queue.')
