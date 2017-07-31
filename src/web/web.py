from inspect import getsourcefile
import random
import os

from flask import Flask, render_template, send_from_directory

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
grandparent_dir = os.path.join(current_dir, os.pardir, os.pardir)
music_cache_dir = os.path.join(grandparent_dir, 'MusicCache')

app = Flask(__name__, static_folder=os.path.join(current_dir, 'static'))


@app.route('/')
def welcome():
    return render_template('index.html')


@app.route('/audio')
def audio():
    playlist = [song_tuple[0] for song_tuple in get_playlist()]
    return render_template('AudioPlayer.html', playlist=playlist)


def get_playlist():
    return [(file.split(".")[0], file) for file in os.listdir(music_cache_dir)]


@app.route('/next_song')
@app.route('/next_song/<ignore_cache_date>')  # Sometimes we need to work around Chrome's shittiness
def next_song(ignore_cache_date=None):
    # The ignore_cache_date parameter is useless, we just need to convince chrome that we're fetching a different page
    # so it doesn't cache responses. Firefox does it correctly out of the gate.
    # Chrome tries to be too clever for its own good.
    del ignore_cache_date

    song_file = random.choice(get_playlist())[1]
    return send_from_directory(music_cache_dir, song_file, cache_timeout=0)


if __name__ == '__main__':
    # Are you a dev who runs a bunch of different stuff on localhost?
    # In that case, you may want to pick a different port.
    app.run(port=80)
