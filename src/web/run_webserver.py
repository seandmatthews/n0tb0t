from inspect import getsourcefile
import os
import sys

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
grandparent_dir = os.path.join(current_dir, os.pardir, os.pardir)
sys.path.insert(0, grandparent_dir)

from src.web.flask_webserver import app

if __name__ == '__main__':
    # Are you a dev who runs a bunch of different stuff on localhost?
    # In that case, you may want to pick a different port.
    app.run(port=8080)
