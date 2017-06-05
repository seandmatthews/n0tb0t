from threading import Thread

from pynput.keyboard import Key, Listener



class KeyboardListener(Thread):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    def run(self):
        # Collect events until released
        with Listener(
                on_press=self.on_press,
                on_release=self.on_release) as listener:
            listener.join()

    def on_press(self, key):
        print('{0} pressed'.format(
            key))
        if key == '+':
            db_session = self.bot.Session()
            self.bot._add_death(db_session)
            db_session.commit()
            db_session.close()

    @staticmethod
    def on_release(key):
        print('{0} release'.format(
            key))
        if key == Key.esc:
            # Stop listener
            return False


class KeyboardListenerMixin:
    def __init__(self):
        self.listener = Listener(self)
        self.listener.start()
