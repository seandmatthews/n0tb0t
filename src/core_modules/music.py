import collections
from inspect import getsourcefile
import os
import threading
import time

import gspread
import pafy

import src.utils as utils


class Song:
    def __init__(self, video_id, title, file_name, requester_id, requester_name):
        self.id = video_id
        self.title = title
        self.file_name = file_name
        self.requester_id = requester_id
        self.requester_name = requester_name


class SongQueue:
    def __init__(self):
        self._queue = collections.deque()

    def insert(self, song_obj):
        self._queue.appendleft(song_obj)

    def get_next_song(self):
        return self._queue.pop()

    def list_songs(self):
        return list(reversed(self._queue))


class MusicMixin:
    def __init__(self):
        self.starting_spreadsheets_list.append('songs')

        current_path = os.path.abspath(getsourcefile(lambda: 0))
        current_dir = os.path.dirname(current_path)
        grandparent_dir = os.path.join(current_dir, os.pardir, os.pardir)
        self.music_cache_dir = os.path.join(grandparent_dir, 'MusicCache')
        if not os.path.exists(self.music_cache_dir):
            os.mkdir(self.music_cache_dir)

        self.song_queue = SongQueue()
        self.song_download_queue = collections.deque()
        self.max_song_length = 300

        self.song_download_thread = threading.Thread(target=self._process_song_download_queue,
                                                     kwargs={})
        self.song_download_thread.daemon = True
        self.song_download_thread.start()

    @utils.retry_gspread_func
    def _initialize_songs_spreadsheet(self, spreadsheet_name):
        """
        Populate the songrequest google sheet with its initial data.
        """
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            qs = sheet.worksheet('Songs')
        except gspread.exceptions.WorksheetNotFound:
            qs = sheet.add_worksheet('Songs', 1000, 2)
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        qs.update_acell('A1', 'Song Title')
        qs.update_acell('B1', 'Requester')

        self.update_songs_spreadsheet()

    @utils.retry_gspread_func
    @utils.mod_only
    def update_songs_spreadsheet(self):
        """
        Updates the quote spreadsheet from the database.
        Only call directly if you really need to as the bot
        won't be able to do anything else while updating.

        !update_quote_spreadsheet
        """
        db_session = self.Session()
        spreadsheet_name, web_view_link = self.spreadsheets['songs']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        qs = sheet.worksheet('Songs')
        worksheet_width = 2

        songs = self.song_queue.list_songs()
        cells = qs.range(f'A2:B{len(songs)+11}')
        for cell in cells:
            cell.value = ''
        qs.update_cells(cells)

        cells = qs.range(f'A2:B{len(songs)+1}')
        for index, quote_obj in enumerate(songs):
            song_title_cell_index = index * worksheet_width
            requester_cell_index = song_title_cell_index + 1

            cells[song_title_cell_index].value = songs[index].title
            cells[requester_cell_index].value = songs[index].requester_name
        qs.update_cells(cells)

        db_session.commit()
        db_session.close()

    def _process_song_download_queue(self):
        while True:
            if len(self.song_download_queue) > 0:
                bestaudio = self.song_download_queue.pop()
                bestaudio.download(filepath=self.music_cache_dir, quiet=True)
            time.sleep(1)

    def _ensure_song_is_downloaded(self, pafy_obj):
        bestaudio = pafy_obj.getbestaudio()
        video_id = pafy_obj.videoid
        song_title = bestaudio.title
        bestaudio_filename = f'{pafy_obj.videoid}-{bestaudio.title}.{bestaudio.extension}'
        already_cached = bestaudio_filename in os.listdir(self.music_cache_dir)
        if not already_cached:
            self.song_download_queue.appendleft(bestaudio)
        return video_id, song_title, bestaudio_filename

    def _get_valid_video(self, url):
        """
        Verifies that the music link is from a valid website
        (Currently just youtube) and that the length of the song
        in seconds is less than self.max_song_length
        """
        try:
            video = pafy.new(url)
        except ValueError:
            raise RuntimeError('Must be valid Youtube URL or identifier')
        if video.length > self.max_song_length:
            raise RuntimeError(f'Song must be less than {self.max_song_length} seconds')
        return video

    def _get_next_song(self):
        return self.song_queue.get_next_song()

    def songrequest(self, message):
        """
        Adds a song to the song request queue.
        Takes a youtube url or 11 digit identifier.

        !songrequest https://www.youtube.com/watch?v=Ppm5_AGtbTo
        !songrequest Ppm5_AGtbTo
        """
        requester_id = message.user
        requester_name = self.service.get_message_display_name(message)
        message_list = self.service.get_message_content(message).split(' ')
        try:
            video = self._get_valid_video(message_list[1])
            video_id, song_title, file_name = self._ensure_song_is_downloaded(video)
            song = Song(video_id, song_title, file_name, requester_id, requester_name)
            self.song_queue.insert(song)
            utils.add_to_command_queue(self, 'update_songs_spreadsheet')
        except RuntimeError as e:
            utils.add_to_appropriate_chat_queue(self, message, str(e))
