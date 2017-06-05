from pynput.keyboard import Key, Listener, KeyCode


class KeyboardListenerMixin:
    def __init__(self):
        keyboard_listener = Listener(on_press=self.on_press, on_release=self.on_release)
        keyboard_listener.start()

    def on_press(self, key):
        # print('{0} pressed'.format(key))
        # print(key, type(key))
        # print(isinstance(key, KeyCode))
        pass

    def on_release(self, key):
        # print('{0} released'.format(key))
        if isinstance(key, KeyCode):
            if key.char == '+':
                db_session = self.Session()
                self._add_death(db_session)
                db_session.commit()
                db_session.close()
            elif key.char == '-':
                db_session = self.Session()
                self._remove_death(db_session)
                db_session.commit()
                db_session.close()

        # if key == Key.esc:
        #     # Stop listener
        #     return False
