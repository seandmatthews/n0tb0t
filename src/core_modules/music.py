from inspect import getsourcefile
import os

import pafy


url = "https://www.youtube.com/watch?v=Ppm5_AGtbTo"


class Song:
    pass


class SongQueue:
    pass


class MusicMixin:
    def __init__(self):
        current_path = os.path.abspath(getsourcefile(lambda: 0))
        current_dir = os.path.dirname(current_path)
        grandparent_dir = os.path.join(current_dir, os.pardir, os.pardir)
        self.music_cache_dir = os.path.join(grandparent_dir, 'MusicCache')
        if not os.path.exists(self.music_cache_dir):
            os.mkdir(self.music_cache_dir)

        self.song_queue = SongQueue()
        self.max_song_length = 300

    def _ensure_song_is_downloaded(self, url):
        video = pafy.new(url)
        bestaudio = video.getbestaudio()
        bestaudio_filename = f'{bestaudio.title}.{bestaudio.extension}'
        already_cached = bestaudio_filename in os.listdir(self.music_cache_dir)
        if not already_cached:
            bestaudio.download(filepath=self.music_cache_dir, quiet=True)

    @staticmethod
    def _is_valid_music_link_url(url):
        """
        Verifies that the music link is from a valid website
        (Currently just youtube) and that the length of the song
        in seconds is less than self.max_song_length
        """
        # We are lazy
        # TODO: Actually do this bit
        return True

    def songrequest(self, message):
        message_list = self.service.get_message_content(message).split(' ')
        if self.is_valid_music_link_url(message_list[1]):
            song = Song(url=message_list[1])
            self.song_queue.append(song)

