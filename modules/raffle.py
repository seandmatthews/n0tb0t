def enter_contest(self, message, db_session):
        """
        Adds the user to the contest entrants
        or informs them that they're already entered if they've already
        entered since the last time the entrants were cleared.

        !enter_contest
        """
        username = self.ts.get_user(message)
        user = db_session.query(db.User).filter(db.User.name == username).one_or_none()
        if user:
            if user.entered_in_contest:
                self._add_to_whisper_queue(user, 'You\'re already entered into the contest, you can\'t enter again.')
            else:
                user.entered_in_contest = True
                self._add_to_whisper_queue(user, 'You\'re entered into the contest!')
        else:
            user = db.User(name=username, entered_in_contest=True)
            db_session.add(user)
            self._add_to_whisper_queue(user, 'You\'re entered into the contest!')

    @_mod_only
    def show_contest_winner(self, db_session):
        """
        Selects a contest entrant at random.
        Sends their name to the chat.

        !show_contest_winner
        """
        users_contest_list = db_session.query(db.User).filter(db.User.entered_in_contest.isnot(False)).all()
        if len(users_contest_list) > 0:
            winner = random.choice(users_contest_list)
            self._add_to_chat_queue('The winner is {}!'.format(winner))
        else:
            self._add_to_chat_queue('There are currently no entrants for the contest.')

    @_mod_only
    def clear_contest_entrants(self, db_session):
        """
        Sets the entrants list to be an empty list and then writes
        that to the entrants file.

        !clear_contest_entrants
        """
        db_session.execute(sqlalchemy.update(db.User.__table__, values={db.User.__table__.c.entered_in_contest: False}))
        self._add_to_chat_queue("Contest entrants cleared.")
