import collections


class PlayerQueue:
    def __init__(self, cycle_num=7, input_iterable=None):
        self.queue = collections.deque()
        self.cycle_num = cycle_num
        if input_iterable is not None:
            for tup in input_iterable:
                self.push(tup[0], tup[1])

    def push(self, player, priority):
        '''
        @params:
            player is the twitch username of a prospective player
            priority 

        @todo(n0t1337): think about this
                    you mentioned some bug that you can't quite nail down
                    -it has to do with promoting and demoting people
                    -pulling them out and changing their priority
                    I(aaron)
        '''
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
        '''
        @todo(n0t1337): Write three page essay on:
            what this function is for
            the context it should be used in
            etc
        '''
        return self.queue.pop()[0]

    def pop_all(self):
        '''
        It pops up to cycle_num players, which is 7 by default.
        If there are not enough then it will pop all available players.
        '''
        return_list = []
        players = min(self.cycle_num, len(self.queue))
        for player in range(players):
            return_list.append(self.pop())
        return return_list
