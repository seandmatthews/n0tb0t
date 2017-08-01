from inspect import getsourcefile
import os

from flask import Flask


current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
great_grandparent_dir = os.path.join(current_dir, os.pardir, os.pardir, os.pardir)
music_cache_dir = os.path.join(great_grandparent_dir, 'MusicCache')

app = Flask(__name__, static_folder=os.path.join(current_dir, 'static'))

import src.web.flask_webserver.views
