import collections


class PlayerQueue:
    def __init__(self, lobby_size=7):
        self._queue = collections.deque()
        self.lobby_size = lobby_size

    def push(self, player, priority):
        index = None
        for i, tup in enumerate(self._queue):
            if player == tup[0]:
                raise RuntimeError('That player already exists in this queue')
            elif index is None and priority >= tup[1]:
                index = i

        if index is not None:
            self._queue.insert(index, (player, priority))
        else:
            self._queue.append((player, priority,))

    def pop(self):
        return self._queue.pop()[0]

    def pop_all(self):
        return_list = []
        players = min(self.lobby_size, len(self._queue))
        for player in range(players):
            return_list.append(self.pop())
        return return_list


pq = PlayerQueue()

pq.push('fuck you', 2)
pq.push('bunz', 1)
pq.push('double fuck you', 1)
try:
    pq.push('bunz', 0)
except RuntimeError as e:
    print(e)

pq.push('Sky', 4)
pq.push('Erin', 2)
pq.push('n0t1337', 0)
pq.push('hyphen', 2)
pq.push('LS', 1)

blah = pq.pop_all()
print(blah)

blah = pq.pop_all()
print(blah)