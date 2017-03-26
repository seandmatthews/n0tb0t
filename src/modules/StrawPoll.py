import json
import random

import requests

import src.modules.Utils as Utils


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
            self._add_to_chat_queue("Sorry, there was a problem talking to the strawpoll api. "
                                    "Maybe wait a bit and retry your command?")

    @Utils._mod_only
    def create_poll(self, message):
        """
        Generates strawpoll and fetches ID for later use with !end_poll.
        The title is the bit between "title:" and (the first) "options:"
        Options are delineated by commas; using commas in your options will break things.

        !create_poll Title: Poll Title Options: Option 1, Option 2, ... Option N
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        title_index = -1
        options_index = -1
        for index, word in enumerate(msg_list):
            print(word.lower())
            if word.lower() == 'title:':
                title_index = index
            elif word.lower() == 'options:':
                options_index = index
                break
        print(title_index, options_index)
        if title_index == -1 or options_index == -1:
            self._add_to_chat_queue('Please form the command correctly')
        else:
            title = ' '.join(msg_list[title_index+1:options_index])
            options_str = ' '.join(msg_list[options_index+1:])
            options = options_str.split(', ')
            payload = {'title': title, 'options': options}
            url = 'https://strawpoll.me/api/v2/polls'
            r = requests.post(url, data=json.dumps(payload))
            try:
                self.strawpoll_id = r.json()['id']
                self._add_to_chat_queue('New strawpoll is up at https://www.strawpoll.me/{}'.format(self.strawpoll_id))
            except KeyError:
                # Strawpoll got angry at us, possibly due to not enough options
                self._add_to_chat_queue('Strawpoll has rejected the poll. If you have fewer than two options, you need at least two.')


    @Utils._mod_only
    def end_poll(self, message):
        """
        Ends the poll that was started with the !create_poll

        !end_poll
        !end_poll 111111111
        """
        msg_list = self.ts.get_human_readable_message(message).split(' ')
        if len(msg_list) == 1 and self.strawpoll_id == '':
            self._add_to_chat_queue('No ID supplied, please try again')
            holder_id = None
        elif len(msg_list) == 1 and self.strawpoll_id != '':
            holder_id = self.strawpoll_id
            self.strawpoll_id = ''
        elif len(msg_list) == 2:
            holder_id = msg_list[1]
        else:
            self._add_to_chat_queue('Sorry, no ID could be found. Please ensure the command is formatted correctly.')
            holder_id = None
        if holder_id is not None:
            holder_options, holder_votes = self._get_poll_info(holder_id)
            probability_list = []
            for vote_number in holder_votes:
                try:
                    temp_prob = vote_number*(1/sum(holder_votes))
                    probability_list.append(temp_prob)
                except ZeroDivisionError:
                    self._add_to_chat_queue('No one has voted yet! You will need to end the poll again by specifying the ID.')
                    return
            die_roll = random.random()
            for index, probability in enumerate(probability_list):
                if die_roll <= sum(probability_list[0:index+1]):
                    winning_chance = round(probability*100)
                    self._add_to_chat_queue(
                        '{} won the poll choice with {} votes and had a {}% chance to win!'.format(holder_options[index], holder_votes[index], winning_chance))
                    break