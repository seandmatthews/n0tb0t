import asyncio
import collections
import concurrent.futures as futures
import random
import time

import grpc

import proto.songqueuer_pb2_grpc
import proto.songqueuer_pb2



def generate_messages():
    while True:
        print(outgoing_song_queues)
        songs_num = random.uniform(1, 5)
        grpc_song_queue = proto.songqueuer_pb2.SongQueue()
        for i in range(songs_num):
            song = grpc_song_queue.song_queue.add()
            song.id = f'video_id{i}'
            song.title = f'title{i}'
            song.file_name = f'file_name{i}'
            song.requester_id = f'requester_id{i}'
            song.requester_name = f'requester_name{i}'
        outgoing_song_queues.appendleft(grpc_song_queue)
        await asyncio.sleep(random.uniform(5, 10))


class SongQueueExchangeServicer(proto.songqueuer_pb2_grpc.SongQueueExchangeServicer):
    def SongQueueChat(self, request_iterator, context):
        while True:
            if len(outgoing_song_queues) != 0:
                yield outgoing_song_queues.pop()
                continue
            print(request_iterator.__next__())


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    proto.songqueuer_pb2_grpc.add_SongQueueExchangeServicer_to_server(
        SongQueueExchangeServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()


if __name__ == '__main__':
    generate_messages()

    def serve():
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        proto.songqueuer_pb2_grpc.add_SongQueueExchangeServicer_to_server(
            SongQueueExchangeServicer(), server)
        server.add_insecure_port('[::]:50051')
        server.start()
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            server.stop(0)
    serve()
