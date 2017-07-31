from inspect import getsourcefile
import os

import pafy

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
grandparent_dir = os.path.join(current_dir, os.pardir, os.pardir)
music_cache_dir = os.path.join(grandparent_dir, 'MusicCache')

url = "https://www.youtube.com/watch?v=Ppm5_AGtbTo"

video = pafy.new(url)
bestaudio = video.getbestaudio()
bestaudio_filename = f'{bestaudio.title}.{bestaudio.extension}'
already_cached = bestaudio_filename in os.listdir(music_cache_dir)
if not already_cached:
    bestaudio.download(filepath=music_cache_dir, quiet=True)


class Song:
    pass


class Playlist:
    pass


# class MusicMixin:
#     pass


