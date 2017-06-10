from pynput.keyboard import Key, Listener, KeyCode

import src.utils as utils


class KeyboardListenerMixin:
    def _on_press(self, key):
        # print('{0} pressed'.format(key))
        # print(key, type(key))
        # print(isinstance(key, KeyCode))
        pass

    def _on_release(self, key):
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

    @utils.mod_only
    def enable_key_listener(self):
        self.keyboard_listener = Listener(on_press=self._on_press, on_release=self._on_release)
        self.keyboard_listener.start()

    @utils.mod_only
    def disable_key_listener(self):
        self.keyboard_listener.stop()
