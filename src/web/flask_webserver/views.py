import random

from flask import render_template, send_from_directory

from src.web.flask_webserver import app, music_cache_dir
from src.web.flask_webserver.web_utils import get_playlist


@app.route('/')
def welcome():
    return render_template('index.html')


@app.route('/auth_return')
def handle_redirect():
    return "Hello World!"


@app.route('/audio')
def audio():
    playlist = [song_tuple[0] for song_tuple in get_playlist()]
    return render_template('AudioPlayer.html', playlist=playlist)


@app.route('/next_song')
@app.route('/next_song/<ignore_cache_date>')  # Sometimes we need to work around Chrome's shittiness
def next_song(ignore_cache_date=None):
    # The ignore_cache_date parameter is useless, we just need to convince chrome that we're fetching a different page
    # so it doesn't cache responses. Firefox does it correctly out of the gate.
    # Chrome tries to be too clever for its own good.
    del ignore_cache_date

    song_file = random.choice(get_playlist())[1]
    return send_from_directory(music_cache_dir, song_file, cache_timeout=0)
