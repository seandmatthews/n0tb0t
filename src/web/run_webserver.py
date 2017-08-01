from src.web.flask_webserver import app

if __name__ == '__main__':
    # Are you a dev who runs a bunch of different stuff on localhost?
    # In that case, you may want to pick a different port.
    app.run(port=80)
