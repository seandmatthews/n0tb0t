import threading

import gspread

import src.models as models
import src.modules.Utils as Utils


class CommandsMixin:

    @Utils._mod_only
    @Utils._retry_gspread_func
    def update_command_spreadsheet(self, db_session):
        """
        Updates the commands google sheet with all available user commands.
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.

        !update_command_spreadsheet
        """
        spreadsheet_name, web_view_link = self.spreadsheets['commands']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        cs = sheet.worksheet('Commands')

        db_commands = db_session.query(models.Command).all()
        everyone_commands = []
        user_specific_commands = []
        for command in db_commands:
            if bool(command.permissions) is False:
                everyone_commands.append(command)
            else:
                user_specific_commands.append(command)

        for index in range(len(everyone_commands) + 10):
            cs.update_cell(index + 2, 7, '')
            cs.update_cell(index + 2, 8, '')

        for index, command in enumerate(everyone_commands):
            cs.update_cell(index + 2, 7, '!{}'.format(command.call))
            cs.update_cell(index + 2, 8, command.response)

        for index in range(len(everyone_commands) + 10):
            cs.update_cell(index + 2, 10, '')
            cs.update_cell(index + 2, 11, '')
            cs.update_cell(index + 2, 12, '')

        for index, command in enumerate(user_specific_commands):
            users = [permission.user_entity for permission in command.permissions]
            users_str = ', '.join(users)
            cs.update_cell(index + 2, 10, '!{}'.format(command.call))
            cs.update_cell(index + 2, 11, command.response)
            cs.update_cell(index + 2, 12, users_str)

    @Utils._mod_only
    def add_command(self, message, db_session):
        """
        Adds a new command.
        The first word after !add_command with an exclamation mark is the command.
        The rest of the sentence is the reply.
        Optionally takes the names of twitch users before the command.
        This would make the command only available to those users.

        !add_command !test_command This is a test.
        !add_command TestUser1 TestUser2 !test_command This is a test
        """
        user = self.ts.get_username(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        for index, word in enumerate(msg_list[1:]):  # exclude !add_user_command
            if word[0] == '!':
                command = word.lower()
                users = msg_list[1:index + 1]
                response = ' '.join(msg_list[index + 2:])
                break
        else:
            # TODO: Fix Whisper Stuff
            self._add_to_chat_queue('Sorry, the command needs ot have an ! in it.')
            # self._add_to_whisper_queue(user, 'Sorry, the command needs to have an ! in it.')
            return
        db_commands = db_session.query(models.Command).all()
        if command[1:] in [db_command.call for db_command in db_commands]:
            # TODO: Fix Whisper Stuff
            self._add_to_chat_queue('Sorry, that command already exists. Please delete it first.')
            # self._add_to_whisper_queue(user, 'Sorry, that command already exists. Please delete it first.')
        else:
            db_command = models.Command(call=command[1:], response=response)
            if len(users) != 0:
                users = [user.lower() for user in users]
                permissions = []
                for user in users:
                    permissions.append(models.Permission(user_entity=user))
                db_command.permissions = permissions
            db_session.add(db_command)
            # TODO: Fix Whisper Stuff
            self._add_to_chat_queue('Command added.')
            # self._add_to_whisper_queue(user, 'Command added.')
            my_thread = threading.Thread(target=self.update_command_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()


    @Utils._mod_only
    def delete_command(self, message, db_session):
        """
        Removes a user created command.
        Takes the name of the command.

        !delete_command !test
        """
        user = self.ts.get_username(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        command_str = msg_list[1][1:].lower()
        db_commands = db_session.query(models.Command).all()
        for db_command in db_commands:
            if command_str == db_command.call:
                db_session.delete(db_command)
                # TODO: Fix Whisper Stuff
                # self._add_to_whisper_queue(user, 'Command deleted.')
                self._add_to_chat_queue('Command deleted.')
                my_thread = threading.Thread(target=self.update_command_spreadsheet,
                                             kwargs={'db_session': db_session})
                my_thread.daemon = True
                my_thread.start()
                break
        else:
            # TODO: Fix Whisper Stuff
            # self._add_to_whisper_queue(user, 'Sorry, that command doesn\'t exist.')
            self._add_to_chat_queue('Sorry, that command doesn\'t exist.')

    def show_commands(self, message):
        """
        Links the google spreadsheet containing all commands in chat

        !show_commands
        """
        user = self.ts.get_username(message)
        web_view_link = self.spreadsheets['commands'][1]
        short_url = self.shortener.short(web_view_link)
        # TODO: Fix Whisper Stuff
        # self._add_to_whisper_queue(user, 'View the commands at: {}'.format(short_url))
        self._add_to_chat_queue('View the commands at: {}'.format(short_url))