import threading

import gspread

import src.models as models
import src.utils as utils


class CommandsMixin:
    def show_commands(self):
        """
        Links the google spreadsheet containing all commands in chat

        !show_commands
        """
        web_view_link = self.spreadsheets['commands'][1]
        short_url = self.shortener.short(web_view_link)
        self._add_to_chat_queue('View the commands at: {}'.format(short_url))

    @utils.mod_only
    @utils.retry_gspread_func
    def update_command_spreadsheet(self):
        """
        Updates the commands google sheet with all available user commands.
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.

        !update_command_spreadsheet
        """
        db_session = self.Session()
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

        # for index in range(len(everyone_commands) + 10):
        #     cs.update_cell(index + 2, 7, '')
        #     cs.update_cell(index + 2, 8, '')
        #
        # for index, command in enumerate(everyone_commands):
        #     cs.update_cell(index + 2, 7, '!{}'.format(command.call))
        #     cs.update_cell(index + 2, 8, command.response)

        for index in range(len(user_specific_commands) + 10):
            cs.update_cell(index + 2, 10, '')
            cs.update_cell(index + 2, 11, '')
            cs.update_cell(index + 2, 12, '')

        for index, command in enumerate(user_specific_commands):
            users = [permission.user_entity for permission in command.permissions]
            users_str = ', '.join(users)
            cs.update_cell(index + 2, 10, '!{}'.format(command.call))
            cs.update_cell(index + 2, 11, command.response)
            cs.update_cell(index + 2, 12, users_str)

        db_session.commit()
        db_session.close()

    @utils.mod_only
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
        msg_list = self.service.get_message_content(message).split(' ')
        for index, word in enumerate(msg_list[1:]):  # exclude !add_command
            if word[0] == '!':
                command_str = word[1:].lower()
                users = msg_list[1:index + 1]
                command_response = ' '.join(msg_list[index + 2:])
                response_str = self._add_command(db_session, command_str, users, command_response)
                self._add_to_chat_queue(response_str)
                break
        else:
            self._add_to_chat_queue('Sorry, the command needs to have an ! in it.')

    @utils.mod_only
    def edit_command(self, message, db_session):
        """
        Edits existing commands.
        
        !edit_command !test_command New command message.
        """
        msg_list = self.service.get_message_content(message).split(' ')
        command_str = msg_list[1][1:].lower()
        response = ' '.join(msg_list[2:])
        response_str = self._edit_command(db_session, command_str, response)
        self._add_to_chat_queue(response_str)
        
    @utils.mod_only
    def delete_command(self, message, db_session):
        """
        Removes a user created command.
        Takes the name of the command.

        !delete_command !test
        """
        msg_list = self.service.get_message_content(message).split(' ')
        command_str = msg_list[1][1:].lower()
        response_str = self._delete_command(db_session, command_str)
        self._add_to_chat_queue(response_str)

    @utils.mod_only
    def command(self, message, db_session):
        msg_list = self.service.get_message_content(message).split(' ')
        action = msg_list[1].lower()
        if action == 'add':
            for index, word in enumerate(msg_list[2:]):  # exclude !command add
                if word[0] == '!':
                    command_str = word[1:].lower()
                    users = msg_list[2:index + 1]
                    response = ' '.join(msg_list[index + 3:])
                    response_str = self._add_command(db_session, command_str, users, response)
                    break
                else:
                    response_str = 'Sorry, the command needs to have an ! in it.'
        elif action == 'edit':
            command_str = msg_list[2][1:].lower()
            response = ' '.join(msg_list[3:])
            response_str = self._edit_command(db_session, command_str, response)
        elif action == 'delete':
            command_str = msg_list[2][1:].lower()
            response_str = self._delete_command(db_session, command_str)
        self._add_to_chat_queue(response_str)


    """
    These functions do most of the heavy lifting.
    """
    def _add_command(self, db_session, command_str, users, response):
        if db_session.query(models.Command).filter(models.Command.call == command_str).one_or_none():
            return 'Sorry, that command already exists. Please delete it first.'
        else:
            db_command = models.Command(call=command_str, response=response)
            if len(users) != 0:
                users = [user.lower() for user in users]
                permissions = []
                for user in users:
                    permissions.append(models.Permission(user_entity=user))
                db_command.permissions = permissions
            db_session.add(db_command)
            self._add_to_command_queue('update_command_spreadsheet')
            return 'Command added.'

    def _edit_command(self, db_session, command_str, response):
        command_obj = db_session.query(models.Command).filter(models.Command.call == command_str).one_or_none()
        if command_obj is None:
            response_str = 'Sorry, that command does not exist.'
        else:
            command_obj.response = response
            self._add_to_command_queue('update_command_spreadsheet')
            response_str = 'Command edited.'
        return response_str

    def _delete_command(self, db_session, command_str):
        command_obj = db_session.query(models.Command).filter(models.Command.call == command_str).one_or_none()
        if command_obj is not None:
            db_session.delete(command_obj)
            response_str = 'Command deleted.'
            self._add_to_command_queue('update_command_spreadsheet')
        else:
            response_str = "Sorry, that command doesn't exist."
        return response_str
