import json
import random

import requests

import src.utils as utils


class StrawPollMixin:
    def _get_poll_info(self, poll_id):
        """
        Returns options and votes for poll ID in json format.
        """
        url = 'https://strawpoll.me/api/v2/polls/{}'.format(poll_id)
        for attempt in range(5):
            try:
                r = requests.get(url)
                poll_options = r.json()['options']
                poll_votes = r.json()['votes']
            except ValueError:
                continue
            except TypeError:
                continue
            else:
                return poll_options, poll_votes
        else:
            raise RuntimeError("Sorry, there was a problem talking to the strawpoll api. Maybe wait a bit and retry your command?")

    @utils.mod_only
    def create_poll(self, message):
        """
        Generates strawpoll and fetches ID for later use with !end_poll.
        The title is the bit between "title:" and (the first) "options:"
        Options are delineated by space - space; using space - space in your options will break things.

        !create_poll Title: Poll Title Options: Option 1 - Option 2 - ... Option N
        """
        msg_list = self.service.get_message_content(message).split(' ')
        title_index = -1
        options_index = -1
        for index, word in enumerate(msg_list):
            if word.lower() == 'title:':
                title_index = index
            elif word.lower() == 'options:':
                options_index = index
                break
        if title_index == -1 or options_index == -1:
            utils.add_to_appropriate_chat_queue(self, message, 'Please form the command correctly')
        else:
            title = ' '.join(msg_list[title_index+1:options_index])
            options_str = ' '.join(msg_list[options_index+1:])
            options = options_str.split(' - ')
            payload = {'title': title, 'options': options}
            url = 'https://strawpoll.me/api/v2/polls'
            r = requests.post(url, data=json.dumps(payload))
            try:
                self.strawpoll_id = r.json()['id']
                utils.add_to_public_chat_queue(self, f'New strawpoll is up at https://www.strawpoll.me/{self.strawpoll_id}')
            except KeyError:
                # Strawpoll got angry at us, possibly due to not enough options
                utils.add_to_appropriate_chat_queue(self, message, 'Strawpoll has rejected the poll. If you have fewer than two options, you need at least two.')

    @utils.mod_only
    def end_poll_weighted(self, message):
        """
        Ends the poll that was started with the !create_poll and picks the result based on a weighted average.
        A strawpoll.me id can be specified after the command to end a specific poll.

        !end_poll_weighted
        !end_poll_weighted 111111111
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 1 and self.strawpoll_id == '':
            utils.add_to_appropriate_chat_queue(self, message, 'No ID supplied, please try again')
            holder_id = None
        elif len(msg_list) == 1 and self.strawpoll_id != '':
            holder_id = self.strawpoll_id
            self.strawpoll_id = ''
        elif len(msg_list) == 2:
            holder_id = msg_list[1]
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'Sorry, no ID could be found. Please ensure the command is formatted correctly.')
            holder_id = None
        if holder_id is not None:
            try:
                holder_options, holder_votes = self._get_poll_info(holder_id)
                probability_list = []
                for vote_number in holder_votes:
                    try:
                        temp_prob = vote_number*(1/sum(holder_votes))
                        probability_list.append(temp_prob)
                    except ZeroDivisionError:
                        utils.add_to_public_chat_queue(self, 'No one has voted yet! You will need to end the poll again by specifying the ID.')
                        return
                die_roll = random.random()
                for index, probability in enumerate(probability_list):
                    if die_roll <= sum(probability_list[0:index+1]):
                        winning_chance = round(probability*100)
                        utils.add_to_public_chat_queue(self, f'{holder_options[index]} won the poll choice with {holder_votes[index]} votes and had a {winning_chance}% chance to win!')
                        break
            except RuntimeError as e:
                utils.add_to_appropriate_chat_queue(self, message, str(e))

    @utils.mod_only
    def end_poll(self, message):
        """
        Ends the poll that was started with the !create_poll and picks the result based votes only.
        A strawpoll.me id can be specified after the command to end a specific poll.

        !end_poll
        !end_poll 111111111
        """
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) == 1 and self.strawpoll_id == '':
            utils.add_to_appropriate_chat_queue(self, message, 'No ID supplied, please try again')
            holder_id = None
        elif len(msg_list) == 1 and self.strawpoll_id != '':
            holder_id = self.strawpoll_id
            self.strawpoll_id = ''
        elif len(msg_list) == 2:
            holder_id = msg_list[1]
        else:
            utils.add_to_appropriate_chat_queue(self, message, 'Sorry, no ID could be found. Please ensure the command is formatted correctly.')
            holder_id = None
        if holder_id is not None:
            try:
                holder_options, holder_votes = self._get_poll_info(holder_id)
                max_votes = 0
                max_votes_list = None
                for index, num_votes in enumerate(holder_votes):
                    if num_votes > max_votes:
                        max_votes = num_votes
                        max_votes_list = [index]
                    elif num_votes == max_votes and max_votes != 0:
                        max_votes_list.append(index)
                if max_votes_list is None:
                    utils.add_to_appropriate_chat_queue(self, message, 'No one has voted yet!')
                elif len(max_votes_list) > 1:
                    winners_list = []
                    for index in max_votes_list:
                        winners_list.append(holder_options[index])
                    utils.add_to_appropriate_chat_queue(self, message, f"It's a tie! The winners are {', '.join(winners_list)}!")
                else:
                    utils.add_to_appropriate_chat_queue(self, message, f"The winner is {holder_options[max_votes_list[0]]}!")
            except RuntimeError as e:
                utils.add_to_appropriate_chat_queue(self, message, str(e))

