import os

from src.web.flask_webserver import music_cache_dir


def get_playlist():
    return [(file.split(".")[0], file) for file in os.listdir(music_cache_dir)]
