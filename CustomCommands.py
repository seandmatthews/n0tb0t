    @_retry_gspread_func
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
            sheet1 = sheet.worksheet('Sheet1')
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

        for index in range(len(self.sorted_methods['for_all'])+10):
            cs.update_cell(index+2, 1, '')
            cs.update_cell(index+2, 2, '')

        for index, method in enumerate(self.sorted_methods['for_all']):
            cs.update_cell(index+2, 1, '!{}'.format(method))
            cs.update_cell(index+2, 2, getattr(self, method).__doc__)

        for index in range(len(self.sorted_methods['for_mods'])+10):
            cs.update_cell(index+2, 4, '')
            cs.update_cell(index+2, 5, '')

        for index, method in enumerate(self.sorted_methods['for_mods']):
            cs.update_cell(index+2, 4, '!{}'.format(method))
            cs.update_cell(index+2, 5, getattr(self, method).__doc__)

        # self.update_command_spreadsheet()


    @_mod_only
    @_retry_gspread_func
    def update_command_spreadsheet(self, db_session):
        """
        Updates the commands google sheet with all available user commands.
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.
        """
        spreadsheet_name, web_view_link = self.spreadsheets['commands']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        cs = sheet.worksheet('Commands')

        db_commands = db_session.query(db.Command).all()
        everyone_commands = []
        user_specific_commands = []
        for command in db_commands:
            if bool(command.permissions) is False:
                everyone_commands.append(command)
            else:
                user_specific_commands.append(command)

        for index in range(len(everyone_commands)+10):
            cs.update_cell(index+2, 7, '')
            cs.update_cell(index+2, 8, '')

        for index, command in enumerate(everyone_commands):
            cs.update_cell(index+2, 7, '!{}'.format(command.call))
            cs.update_cell(index+2, 8, command.response)

        for index in range(len(everyone_commands)+10):
            cs.update_cell(index+2, 10, '')
            cs.update_cell(index+2, 11, '')
            cs.update_cell(index+2, 12, '')

        for index, command in enumerate(user_specific_commands):
            users = [permission.user_entity for permission in command.permissions]
            users_str = ', '.join(users)
            cs.update_cell(index+2, 10, '!{}'.format(command.call))
            cs.update_cell(index+2, 11, command.response)
            cs.update_cell(index+2, 12, users_str)

    @_mod_only
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
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        for index, word in enumerate(msg_list[1:]):  # exclude !add_user_command
            if word[0] == '!':
                command = word
                users = msg_list[1:index + 1]
                response = ' '.join(msg_list[index + 2:])
                break
        else:
            self._add_to_whisper_queue(user, 'Sorry, the command needs to have an ! in it.')
            return
        db_commands = db_session.query(db.Command).all()
        if command[1:] in [db_command.call for db_command in db_commands]:
            self._add_to_whisper_queue(user, 'Sorry, that command already exists. Please delete it first.')
        else:
            db_command = db.Command(call=command[1:], response=response)
            if len(users) != 0:
                users = [user.lower() for user in users]
                permissions = []
                for user in users:
                    permissions.append(db.Permission(user_entity=user))
                db_command.permissions = permissions
            db_session.add(db_command)
            self._add_to_whisper_queue(user, 'Command added.')
            my_thread = threading.Thread(target=self.update_command_spreadsheet,
                                         kwargs={'db_session': db_session})
            my_thread.daemon = True
            my_thread.start()

    @_mod_only
    def delete_command(self, message, db_session):
        """
        Removes a user created command.
        Takes the name of the command.

        !delete_command !test
        """
        user = self.ts.get_user(message)
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        command_str = msg_list[1][1:]
        db_commands = db_session.query(db.Command).all()
        for db_command in db_commands:
            if command_str == db_command.call:
                db_session.delete(db_command)
                self._add_to_whisper_queue(user, 'Command deleted.')
                my_thread = threading.Thread(target=self.update_command_spreadsheet,
                                             kwargs={'db_session': db_session})
                my_thread.daemon = True
                my_thread.start()
                break
        else:
            self._add_to_whisper_queue(user, 'Sorry, that command doesn\'t seem to exist.')

    def show_commands(self, message):
        """
        Links the google spreadsheet containing all commands in chat

        !show_commands
        """
        user = self.ts.get_user(message)
        web_view_link = self.spreadsheets['commands'][1]
        short_url = self.shortener.short(web_view_link)
        self._add_to_whisper_queue(user, 'View the commands at: {}'.format(short_url))
