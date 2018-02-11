import arrow
import logging
import os
import re
import sqlite3
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import mediafile
from collections import namedtuple
from contextlib import closing
from gmusicapi import Musicmanager


APP_DIR = os.path.expandvars('$HOME/.gmusic-sync')
LibraryPaths = namedtuple('LibraryPaths', ['base', 'db_file', 'oauth_file'])
TrackRow = namedtuple('TrackRow', ['id', 'gmusic_track_id', 'gmusic_sync_time'])


# silence warnings from Musicmanager
logging.basicConfig(level=logging.ERROR)


def format_sync_time(value):
    if value is None:
        return None
    return value.isoformat()


def get_library_paths(library_name):
    base_path = os.path.join(APP_DIR, library_name)
    return LibraryPaths(
        base=base_path,
        db_file=os.path.join(base_path, 'sync.db'),
        oauth_file=os.path.join(base_path, 'oauth'),
    )


def make_command(name, func, **kwargs):
    c = Subcommand(name, **kwargs)
    c.func = func
    return c


def open_db(db_file_path):
    return DB(db_file_path)


def parse_sync_time(value):
    if value is None:
        return None
    return arrow.get(value)


class DB:
    def __init__(self, file_path):
        self._conn = sqlite3.connect(file_path)
        self.migrate()

    def migrate(self):
        self._conn.executescript('''
            CREATE TABLE IF NOT EXISTS tracks (
                id integer NOT NULL,
                gmusic_track_id text,
                gmusic_sync_time text,

                PRIMARY KEY (id)
            );
        ''')

    def get_track(self, id):
        with closing(self._conn.cursor()) as c:
            c.execute('SELECT id, gmusic_track_id, gmusic_sync_time FROM tracks WHERE id = ?', (id,))
            r = c.fetchone()
            if r is not None:
                return TrackRow(
                    id=r[0],
                    gmusic_track_id=r[1],
                    gmusic_sync_time=parse_sync_time(r[2]),
                )
            return None

    def update_track(self, track):
        with closing(self._conn.cursor()) as c:
            c.execute(
                'INSERT OR REPLACE INTO tracks (id, gmusic_track_id, gmusic_sync_time) VALUES (?, ?, ?);',
                (track.id, track.gmusic_track_id, format_sync_time(track.gmusic_sync_time)),
            )
        self._conn.commit()


class GMusicTrackError(StandardError):
    def __init__(self, reason):
        super(GMusicTrackError, self).__init__('GMusic track error: ' + reason)
        self.reason = reason


class TrackAlreadyExistsError(GMusicTrackError):
    def __init__(self, track_id, reason):
        super(TrackAlreadyExistsError, self).__init__(reason)
        self.track_id = track_id


class GMusicSync(BeetsPlugin):
    def __init__(self):
        super(GMusicSync, self).__init__()

        self._mm = Musicmanager(debug_logging=False)
        self._library_paths = get_library_paths('default')

        if not os.path.exists(self._library_paths.base):
            os.mkdir(self._library_paths.base);

        self._db = open_db(self._library_paths.db_file)

        if not os.path.exists(self._library_paths.oauth_file):
            self._mm.perform_oauth(self._library_paths.oauth_file)
        else:
            self._mm.login(self._library_paths.oauth_file)

        sync_command = make_command('gmusic-sync', self.sync_library, help='Sync library with Google Play Music')
        sync_command.parser.add_option('-p', '--pretend', dest='pretend', action='store_true', default=False)

        self._commands = [
            sync_command,
        ]

        self.config['password'].redact = True

    def commands(self):
        return self._commands

    def sync_library(self, lib, opts, args):
        total_count = 0
        uploaded_count = 0
        error_count = 0

        for item in lib.items(query=args):
            total_count = total_count + 1
            status = self.sync_track(item, pretend=opts.pretend)
            if status == 'uploaded':
                uploaded_count = uploaded_count + 1
            elif status == 'error':
                error_count = error_count + 1

        print 'Summary:'
        print '  {0} tracks analyzed.'.format(total_count)
        print '  {0} tracks {1}uploaded.'.format(uploaded_count, 'would be ' if opts.pretend else '')
        print '  {0} tracks errored.'.format(error_count)

    def sync_track(self, item, pretend=False):
        item_mtime = arrow.get(item.current_mtime())

        track_row = self._db.get_track(item.id)

        upload_track = track_row is None or \
            track_row.gmusic_sync_time is None or \
            track_row.gmusic_sync_time < item_mtime

        if upload_track:
            try:
                track_id = self.upload_track(item, pretend)

                if not pretend:
                    track_row = TrackRow(id=item.id, gmusic_track_id=track_id, gmusic_sync_time=arrow.utcnow())
                    self._db.update_track(track_row)

                return 'uploaded'
            except Exception as err:
                print '>>> track failed to upload: {0}'.format(err)
                return 'error'

        return 'ok'

    def upload_track(self, item, pretend=False):
        print u'Uploading track: {artist} - {album} - [{track}] {title}'.format(**item)
        track_id = None

        if not pretend:
            uploaded, matched, not_uploaded = self._mm.upload(item.path, enable_matching=True)
            if item.path in uploaded:
                track_id = uploaded[item.path]
                print '>>> track uploaded (gmusic_trackid: {track_id})'.format(track_id=track_id)
            elif item.path in matched:
                track_id = matched[item.path]
                print '>>> track matched (gmusic_trackid: {track_id})'.format(track_id=track_id)
            else:
                reason = not_uploaded[item.path]
                m = re.search('ALREADY_EXISTS\((.*)\)', reason)
                if not m:
                    raise GMusicTrackError(reason)

                track_id = m.group(1)
                print '>>> track already exists (gmusic_trackid: {track_id}'.format(track_id=track_id)
        else:
            track_id = '?'
            print '>>> track would be uploaded'

        return track_id