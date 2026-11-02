"""Debug time (Settings > Developer): see the world days from now in minutes.

Everything that reads the time reads the app clock (clock.AppClock on Database.clock): the story's local time and
weather and where the townsfolk are. Debug time moves that clock ahead and can run it faster, so all of them follow
without special cases.

Starting takes a verified backup (Settings > Data, "Before debug time") and a plain copy of the database. Returning
to real time restores the copy, so real-time history stays as it was; the user can keep what happened instead.
"""
from datetime import datetime, timedelta
from pathlib import Path

from dungeon import backup
from dungeon.clock import parse, stamp, zone
from dungeon.database import Database, optional, settings
from dungeon.errors import DomainError, require

FOLDER = 'debug-time'
SPEEDS = (1, 10, 60, 360, 1440)
MAX_JUMP = timedelta(days=30)


def snapshot_path(database: Database) -> Path:
    return database.path.parent / FOLDER / 'before-debug.sqlite3'


def load(database: Database):
    """Apply a debug time saved by an earlier run of the app, so it survives a restart."""
    with database.connect() as connection:
        row = optional(connection, 'SELECT * FROM debug_time WHERE id=1')
    if row is None:
        database.clock.reset()
        return
    database.clock.shift(parse(row['app_anchor']), row['speed'])
    database.clock.anchor_real = parse(row['real_anchor'])


def save(database: Database):
    clock = database.clock
    with database.connect(write=True) as connection:
        connection.execute('UPDATE debug_time SET app_anchor=?, real_anchor=?, speed=? WHERE id=1',
                           (stamp(clock.anchor_app), stamp(clock.anchor_real), clock.speed))


def status(database: Database) -> dict:
    clock = database.clock
    with database.connect() as connection:
        row = optional(connection, 'SELECT * FROM debug_time WHERE id=1')
    view = {'active': row is not None, 'now': stamp(clock.now()), 'real_now': stamp(clock.real()),
            'speed': clock.speed, 'speeds': list(SPEEDS), 'started_at': None, 'app_started_at': None,
            'backup': None}
    if row:
        view.update(started_at=row['started_at'], app_started_at=row['app_started_at'], backup=row['backup'])
    return view


def start(database: Database) -> None:
    """Back up first; the copy is taken before the debug row exists, so restoring it ends debug time too."""
    with database.connect() as connection:
        if optional(connection, 'SELECT id FROM debug_time WHERE id=1'):
            return
    created_at = database.now()
    name = f"before-debug-{created_at[:19].replace(':', '').replace('-', '')}.zip"
    backup.archive(database.path, database.path.parent / 'backups' / name, created_at)
    copy = snapshot_path(database)
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.unlink(missing_ok=True)
    backup.snapshot(database.path, copy)
    now = database.clock.now()
    database.clock.shift(now, 1)
    with database.connect(write=True) as connection:
        connection.execute('INSERT INTO debug_time (id, app_anchor, real_anchor, speed, started_at, app_started_at, '
                           'snapshot, backup) VALUES (1, ?, ?, 1, ?, ?, ?, ?)',
                           (stamp(now), stamp(database.clock.anchor_real), stamp(database.clock.real()), stamp(now),
                            copy.name, name))


def require_active(database: Database):
    with database.connect() as connection:
        require(optional(connection, 'SELECT id FROM debug_time WHERE id=1') is not None,
                'Debug time is not on.', 409)


def set_speed(database: Database, speed: float):
    require(speed in SPEEDS, 'Choose one of the listed speeds.', 422)
    require_active(database)
    database.clock.shift(database.clock.now(), speed)
    save(database)


def target(database: Database, hours: float | None, local: str | None) -> datetime:
    """Where a jump lands: some hours ahead, or a date and time in the user's own timezone. Time only
    moves forward here."""
    now = database.clock.now()
    if local is not None:
        with database.connect() as connection:
            user_zone = zone(settings(connection)['user_timezone'])
        try:
            moment = datetime.fromisoformat(local)
        except ValueError:
            raise DomainError('Give a date and time.', 422) from None
        landing = (moment if moment.tzinfo else moment.replace(tzinfo=user_zone)).astimezone(now.tzinfo)
    else:
        require(hours is not None and hours > 0, 'Jump ahead by some hours, or pick a date and time.', 422)
        landing = now + timedelta(hours=hours)
    require(landing > now, 'Pick a time after the current one. To go back, return to real time.', 422)
    require(landing - now <= MAX_JUMP, 'Jump at most 30 days at a time.', 422)
    return landing


def jump(database: Database, hours: float | None = None, local: str | None = None) -> dict:
    require_active(database)
    database.clock.shift(target(database, hours, local), database.clock.speed)
    save(database)
    return status(database)


def finish(database: Database, keep: bool) -> dict:
    """Back to real time. Unless kept, the database copy from the start replaces everything since; the verified
    backup stays in Settings > Data."""
    require_active(database)
    copy = snapshot_path(database)
    if keep:
        with database.connect(write=True) as connection:
            connection.execute('DELETE FROM debug_time')
    else:
        require(copy.is_file(), 'The copy from before debug time is missing; restore the "Before debug time" '
                                'backup from Settings > Data instead.', 409)
        backup.snapshot(copy, database.path)
    database.clock.reset()
    copy.unlink(missing_ok=True)
    return {'kept': keep, **status(database)}
