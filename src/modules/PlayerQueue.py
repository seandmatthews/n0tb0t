import collections
import json
import os

import gspread
import sqlalchemy

import src.models as models
import src.modules.Utils as Utils


class PlayerQueue:
    def __init__(self, cycle_num=7, input_iterable=None):
        self.queue = collections.deque()
        self.cycle_num = cycle_num
        if input_iterable is not None:
            for tup in input_iterable:
                self.push(tup[0], tup[1])

    def push(self, player, priority):
        """
        @params:
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
        Removes one player, priority tuple from the player queue and returns them
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
    def _delete_last_row(self):
        """
        Deletes the last row of the player_queue spreadsheet
        """
        spreadsheet_name, _ = self.spreadsheets['player_queue']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        ws = sheet.worksheet('Player Queue')
        records = ws.get_all_records()
        last_row_index = len(records) + 1

        ws.update_cell(last_row_index, 1, '')
        ws.update_cell(last_row_index, 2, '')

    def _insert_into_player_queue_spreadsheet(self, username, times_played, player_queue):
        """
        Used by the join command.
        """
        spreadsheet_name, _ = self.spreadsheets['player_queue']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        ws = sheet.worksheet('Player Queue')

        records = ws.get_all_records()
        records = records[1:]  # We don't want the blank space
        for i, tup in enumerate(player_queue):
            try:
                if records[i]['User'] != tup[0]:
                    ws.insert_row([username, times_played], index=i + 3)
                    break
            except IndexError:
                ws.insert_row([username, times_played], index=i + 3)

    def _write_player_queue(self):
        """
        Writes the player queue to a json file
        to be loaded on startup if needed.
        """
        with open(f"{self.info['channel']}_player_queue.json", 'w', encoding="utf-8") as player_file:
            json.dump(list(self.player_queue.queue), player_file, ensure_ascii=False)

    def join(self, message, db_session):
        """
        Adds the user to the game queue.
        The players who've played the fewest
        times with the caster get priority.

        !join
        """
        username = self.ts.get_user(message)
        user = db_session.query(models.User).filter(models.User.name == username).one_or_none()
        if not user:
            user = models.User(name=username)
            db_session.add(user)
        try:
            self.player_queue.push(username, user.times_played)
            self._write_player_queue()
            self._add_to_chat_queue("{0}, you've joined the queue.".format(username))
            user.times_played += 1
        except RuntimeError:
            self._add_to_chat_queue("{0}, you're already in the queue and can't join again.".format(username))

            # queue_snapshot = copy.deepcopy(self.player_queue.queue)
            # self.command_queue.appendleft(('_insert_into_player_queue_spreadsheet',
            #                                {'username': username, 'times_played':user.times_played, 'player_queue': queue_snapshot}))

    def leave(self, message, db_session):
        """
        Leaves the player queue once you've joined it.

        !leave
        """
        username = self.ts.get_user(message)
        user = db_session.query(models.User).filter(models.User.name == username).one_or_none()
        if not user:
            user = models.User(name=username)
            db_session.add(user)
        for tup in self.player_queue.queue:
            if tup[0] == username:
                self.player_queue.queue.remove(tup)
                self._write_player_queue()
                self._add_to_chat_queue("{0}, you've left the queue.".format(username))
                user.times_played -= 1
                break
        else:
            self._add_to_chat_queue("You're not in the queue and must join before leaving.")

    def spot(self, message):
        """
        Shows user current location in queue and current priority.

        !spot
        """
        try:
            username = self.ts.get_user(message)
            for index, tup in enumerate(self.player_queue.queue):
                if tup[0] == username:
                    position = len(self.player_queue.queue) - index
            self._add_to_chat_queue(
                "{0} is number {1} in the queue. This may change as other players join.".format(username, position))
        except UnboundLocalError:
            self._add_to_chat_queue("{0} not in the queue. Feel free to join it.".format(username))

    def show_player_queue(self, message):
        """
        Sends the user a whisper with the current contents of the player queue

        !show_player_queue
        """
        user = self.ts.get_user(message)
        queue_str = ', '.join([str(item) for item in self.player_queue.queue])
        self._add_to_whisper_queue(user, queue_str)

    def show_player_queue(self, message):
        """
        Links the google spreadsheet containing the queue list

        !show_player_queue
        """
        user = self.ts.get_user(message)
        web_view_link = self.spreadsheets['player_queue'][1]
        short_url = self.shortener.short(web_view_link)
        self._add_to_whisper_queue(user, 'View the the queue at: {}'.format(short_url))

    @Utils._mod_only
    def cycle(self, message):
        """
        Sends out a message to the next set of players.

        !cycle
        !cycle Password!1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        players = self.player_queue.pop_all()
        self._write_player_queue()
        players_str = ' '.join(players)
        channel = self.info['channel']
        if len(msg_list) > 1:
            credential_str = ' '.join(msg_list[1:])
            whisper_str = 'You may now join {} to play. The credentials you need are: {}'.format(
                    channel, credential_str)
            self.player_queue_credentials = credential_str
        else:
            whisper_str = 'You may now join {} to play.'.format(channel)
            self.player_queue_credentials = None
        for player in players:
            self._add_to_whisper_queue(player, whisper_str)
            # self.command_queue.appendleft(('_delete_last_row', {}))
        self._add_to_chat_queue("Invites sent to: {} and there are {} people left in the queue".format(
            players_str, len(self.player_queue.queue)))

    @Utils._mod_only
    def cycle_one(self, message):
        """
        Sends out a message to the next player.

        !cycle_one
        !cycle_one Password!1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        channel = self.info['channel']
        try:
            player = self.player_queue.pop()
            self._write_player_queue()
            if len(msg_list) > 1:
                credential_str = ' '.join(msg_list[1:])
                whisper_str = 'You may now join {} to play. The credentials you need are: {}'.format(
                        channel, credential_str)
            elif self.player_queue_credentials is not None:
                credential_str = self.player_queue_credentials
                whisper_str = 'You may now join {} to play. The credentials you need are: {}'.format(
                        channel, credential_str)
            else:
                whisper_str = 'You may now join {} to play.'.format(channel)
            self._add_to_whisper_queue(player, whisper_str)
            self._add_to_chat_queue("Invite sent to: {} and there are {} people left in the queue".format(player, len(self.player_queue.queue)))
            # self.command_queue.appendleft(('_delete_last_row', {}))
        except IndexError:
            self._add_to_chat_queue('Sorry, there are no more players in the queue')

    @Utils._mod_only
    def reset_queue(self, db_session):
        """
        Creates a new queue with the default room size
        and resets all players stats for how many
        times they've played with the caster.

        !reset_queue
        """
        for _ in self.player_queue.queue:
            self.command_queue.appendleft(('_delete_last_row', {}))
        self.player_queue = PlayerQueue.PlayerQueue()
        try:
            os.remove(f"{self.info['channel']}_player_queue.json")
        except FileNotFoundError:
            pass
        db_session.execute(sqlalchemy.update(models.User.__table__, values={models.User.__table__.c.times_played: 0}))
        self._add_to_chat_queue('The queue has been emptied and all players start fresh.')

    @Utils._mod_only
    def set_cycle_number(self, message):
        """
        Sets the number of players to cycle
        in when it's time to play with new people.
        By default this value is 7.

        !set_cycle_number 5
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        user = self.ts.get_user(message)
        if len(msg_list) > 1 and msg_list[1].isdigit() and int(msg_list[1]) > 0:
            cycle_num = int(msg_list[1])
            self.player_queue.cycle_num = cycle_num
            self._add_to_whisper_queue(user, "The new room size is {}.".format(cycle_num))
        else:
            self._add_to_whisper_queue(user, "Make sure the command is followed by an integer greater than 0.")

    @Utils._mod_only
    def promote(self, message, db_session):
        """
        Promotes a player in the player queue.

        !promote testuser

        # TODO(n0t1337): fix the bug in here, maybe move it to player_queue
                move some of the logic
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        user = self.ts.get_user(message)
        player = msg_list[1]
        for index, tup in enumerate(self.player_queue.queue):
            if tup[0] == player:
                times_played = tup[1]
                if times_played != 0:
                    result = db_session.query(models.User).filter(models.User.name == player).one()
                    result.times_played -= 1
                    self.player_queue.queue.remove(tup)
                    self.player_queue.push(player, times_played-1)
                else:
                    self._add_to_whisper_queue(user, '{} cannot be promoted in the queue.'.format(player))
                break
        else:
            self._add_to_whisper_queue(user, '{} is not in the player queue.'.format(player))

    @Utils._mod_only
    def demote(self, message, db_session):
        """
        Demotes a player in the player queue.

        !demote testuser

        # TODO(n0t1337): fix the bug in here, maybe move it to player_queue
                move some of the logic
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        user = self.ts.get_user(message)
        player = msg_list[1]
        for index, tup in enumerate(self.player_queue.queue):
            if tup[0] == player:
                times_played = tup[1]
                result = db_session.query(models.User).filter(models.User.name == player).one()
                result.times_played += 1
                self.player_queue.queue.remove(tup)
                self.player_queue.push(player, times_played+1)
                break
        else:
            self._add_to_whisper_queue(user, '{} is not in the player queue.'.format(player))