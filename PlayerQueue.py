import heapq


class PlayerQueue:
    def __init__(self, lobby_size=7):
        self._queue =[]
        self._index = 0
        self.lobby_size = lobby_size

    def push(self, item, priority):
        heapq.heappush(self._queue, (priority, self._index, item))
        self._index += 1

    def pop(self):
        return heapq.heappop(self._queue)[-1]

    def pop_all(self):
        players = min(self.lobby_size, len(self._queue))
        for player in range(players):
            self.pop()

