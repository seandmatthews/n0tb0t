import threading

import gspread

import src.models as models
import src.utils as utils


class CommandsMixin:
    def __init__(self):
        self.starting_spreadsheets_list.append('commands')

    @utils.retry_gspread_func
    def _initialize_commands_spreadsheet(self, spreadsheet_name):
        """
        Populate the commands google sheet with its initial data.
        """
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            cs = sheet.worksheet('Commands')
        except gspread.exceptions.WorksheetNotFound:
            cs = sheet.add_worksheet('Commands', 1000, 20)
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        cs.update_acell('A1', 'Commands\nfor\nEveryone')
        cs.update_acell('B1', 'Command\nDescription')
        cs.update_acell('D1', 'Commands\nfor\nMods')
        cs.update_acell('E1', 'Command\nDescription')
        cs.update_acell('G1', 'User\nCreated\nCommands')
        cs.update_acell('H1', 'Bot Response')
        cs.update_acell('J1', 'User\nSpecific\nCommands')
        cs.update_acell('K1', 'Bot Response')
        cs.update_acell('L1', 'User List')

        for index in range(len(self.sorted_methods['for_all']) + 10):
            cs.update_cell(index + 2, 1, '')
            cs.update_cell(index + 2, 2, '')

        for index, method in enumerate(self.sorted_methods['for_all']):
            cs.update_cell(index + 2, 1, '!{}'.format(method))
            cs.update_cell(index + 2, 2, getattr(self, method).__doc__)

        for index in range(len(self.sorted_methods['for_mods']) + 10):
            cs.update_cell(index + 2, 4, '')
            cs.update_cell(index + 2, 5, '')

        for index, method in enumerate(self.sorted_methods['for_mods']):
            cs.update_cell(index + 2, 4, '!{}'.format(method))
            cs.update_cell(index + 2, 5, getattr(self, method).__doc__)

        self.update_command_spreadsheet()

    def show_commands(self, message):
        """
        Links the google spreadsheet containing all commands in chat

        !show_commands
        """
        web_view_link = self.spreadsheets['commands'][1]
        short_url = self.shortener.short(web_view_link)
        utils.add_to_appropriate_chat_queue(self, message, 'View the commands at: {}'.format(short_url))

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

        cells = cs.range(f'G2:H{len(everyone_commands) + 11}')
        for cell in cells:
            cell.value = ''
        cs.update_cells(cells)

        cells = cs.range(f'G2:H{len(everyone_commands) + 1}')
        cell_range_width = 2

        for index, command in enumerate(everyone_commands):
            cells[index*cell_range_width].value = f'!{command.call}'
            cells[(index * cell_range_width) + 1].value = command.response
        cs.update_cells(cells)

        cells = cs.range(f'J2:L{len(user_specific_commands) + 11}')
        for cell in cells:
            cell.value = ''
        cs.update_cells(cells)

        cells = cs.range(f'J2:L{len(user_specific_commands) + 1}')
        cell_range_width = 3

        for index, command in enumerate(user_specific_commands):
            users = [permission.user_entity for permission in command.permissions]
            users_str = ', '.join(users)
            cells[index * cell_range_width].value = f'!{command.call}'
            cells[(index * cell_range_width) + 1].value = command.response
            cells[(index * cell_range_width) + 2].value = users_str
        cs.update_cells(cells)

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
                utils.add_to_appropriate_chat_queue(self, message, response_str)
                break
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'Sorry, the command needs to have an ! in it.')

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
        utils.add_to_appropriate_chat_queue(self, message, response_str)
        
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
        utils.add_to_appropriate_chat_queue(self, message, response_str)

    @utils.mod_only
    def command(self, message, db_session):
        """
        Adds, edits, or deletes commands by appending add, edit, or delete to !command

        !command edit !test_command New content
        !command add !new_command Content
        !command delete !test_command
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            action = msg_list[1].lower()
            if action == 'add':
                for index, word in enumerate(msg_list[2:]):  # exclude !command add
                    if word[0] == '!':
                        command_str = word[1:].lower()
                        users = msg_list[2:index + 2]
                        response = ' '.join(msg_list[index + 3:])
                        response_str = self._add_command(db_session, command_str, users, response)
                        utils.add_to_appropriate_chat_queue(self, message, response_str)
                        break
                else:
                    response_str = 'Sorry, the command needs to have an ! in it.'
                    utils.add_to_appropriate_chat_queue(self, message, response_str)
            elif action == 'edit':
                command_str = msg_list[2][1:].lower()
                response = ' '.join(msg_list[3:])
                response_str = self._edit_command(db_session, command_str, response)
                utils.add_to_appropriate_chat_queue(self, message, response_str)
            elif action == 'delete':
                command_str = msg_list[2][1:].lower()
                response_str = self._delete_command(db_session, command_str)
                utils.add_to_appropriate_chat_queue(self, message, response_str)
            else:
                response_str = 'Sorry, the only options are add, edit and delete'
                utils.add_to_appropriate_chat_queue(self, message, response_str)
        else:
            response_str = 'You must follow command with either add edit or delete'
            utils.add_to_appropriate_chat_queue(self, message, response_str)

    # These functions interact with the database
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
            utils.add_to_command_queue(self, 'update_command_spreadsheet')
            return 'Command added.'

    def _edit_command(self, db_session, command_str, response):
        command_obj = db_session.query(models.Command).filter(models.Command.call == command_str).one_or_none()
        if command_obj is None:
            response_str = 'Sorry, that command does not exist.'
        else:
            command_obj.response = response
            utils.add_to_command_queue(self, 'update_command_spreadsheet')
            response_str = 'Command edited.'
        return response_str

    def _delete_command(self, db_session, command_str):
        command_obj = db_session.query(models.Command).filter(models.Command.call == command_str).one_or_none()
        if command_obj is not None:
            db_session.delete(command_obj)
            response_str = 'Command deleted.'
            utils.add_to_command_queue(self, 'update_command_spreadsheet')
        else:
            response_str = "Sorry, that command doesn't exist."
        return response_str
