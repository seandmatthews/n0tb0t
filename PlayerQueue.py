import collections


class PlayerQueue:
    def __init__(self, cycle_num=7, dump=None):
        self.queue = collections.deque()
        self.cycle_num = cycle_num
        if dump != None:
            for tup in dump:
                self.push(tup[0], tup[1])

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
    
    def dumpable(self):
        return_list = []
        for tup in self.queue:
            return_list.append(tup)
        return return_list
