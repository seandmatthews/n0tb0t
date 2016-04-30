import collections


class PlayerQueue:
    def __init__(self, cycle_num=7):
        self.queue = collections.deque()
        self.cycle_num = cycle_num

    def push(self, player, priority):
        index = None
        for i, tup in enumerate(self.queue):
            if player == tup[0]:
                raise RuntimeError('That player already exists in this queue')
            elif index is None and priority >= tup[1]:
                index = i

        if index is not None:
            self.queue.insert(index, (player, priority))
        else:
            self.queue.append((player, priority,))

    def pop(self):
        return self.queue.pop()[0]

    def pop_all(self):
        return_list = []
        players = min(self.cycle_num, len(self.queue))
        for player in range(players):
            return_list.append(self.pop())
        return return_list


def join_queue(self, message, db_session):
        """
        Adds the user to the game queue.
        The players who've played the fewest
        times with the caster get priority.

        !join_queue
        """
        username = self.ts.get_user(message)
        user = db_session.query(db.User).filter(db.User.name == username).one_or_none()
        if not user:
            user = db.User(name=username)
            db_session.add(user)
        try:
            self.player_queue.push(username, user.times_played)
            self._add_to_whisper_queue(username, "You've joined the queue.")
        except RuntimeError:
            self._add_to_whisper_queue(username, "You're already in the queue and can't join again.")
        user.times_played += 1

    @_mod_only
    def cycle(self, message):
        """
        Sends out a message to the next set of players.

        !cycle
        !cycle Password!1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        players = self.player_queue.pop_all()
        players_str = ' '.join(players)
        channel = SOCKET_ARGS['channel']
        if len(msg_list) > 1:
            credential_str = ' '.join(msg_list[1:])
            whisper_str = 'You may now join {} to play. The credentials you need are: {}'.format(
                    channel, credential_str)
        else:
            whisper_str = 'You may now join {} to play.'.format(channel)
        for player in players:
            self._add_to_whisper_queue(player, whisper_str)
        self._add_to_chat_queue("Invites sent to: {} and there are {} people left in the queue".format(
            players_str, len(self.player_queue.queue)
        ))

    @_mod_only
    def cycle_one(self, message):
        """
        Sends out a message to the next player.

        !cycle_one
        !cycle_one Password!1
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        channel = SOCKET_ARGS['channel']
        try:
            player = self.player_queue.pop()
        except IndexError:
            self._add_to_chat_queue('Sorry, there are no more players in the queue')
        if len(msg_list) > 1:
            credential_str = ' '.join(msg_list[1:])
            whisper_str = 'You may now join {} to play. The credentials you need are: {}'.format(
                    channel, credential_str)
        else:
            whisper_str = 'You may now join {} to play.'.format(channel)
        self._add_to_whisper_queue(player, whisper_str)
        self._add_to_chat_queue("Invite sent to: {} and there are {} people left in the queue".format(
            player, len(self.player_queue.queue)
        ))


    @_mod_only
    def reset_queue(self, db_session):
        """
        Creates a new queue with the default room size
        and resets all players stats for how many
        times they've played with the caster.

        !reset_queue
        """
        self.player_queue = PlayerQueue.PlayerQueue()
        db_session.execute(sqlalchemy.update(db.User.__table__, values={db.User.__table__.c.times_played: 0}))
        self._add_to_chat_queue('The queue has been emptied and all players start fresh.')

    @_mod_only
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