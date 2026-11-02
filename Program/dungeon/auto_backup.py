"""Automatic backups (Settings > Data): every world is backed up on its own while the app runs.

On by default, once a day; the user can make it weekly or turn it off (workspace_settings.auto_backups, which
follows them into every world). Each world keeps its backups in its own Backups folder, beside its database, so a
portable Data folder backs up next to itself. A world nobody has opened since its last backup is not backed up
again. The last 7 daily backups are kept, and one a week for the 4 weeks before them; older ones are deleted.

A backup is a verified archive like the ones made by hand (dungeon/backup.py), without reference pictures.
It never calls a model, and it waits while a reply is being written.
"""
import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from dungeon import backup, worlds
from dungeon.database import settings
from dungeon.errors import DomainError

PREFIX = 'auto-'
CHECK_EVERY = 15 * 60
# The first check waits a little after a start, so opening the app stays quick.
FIRST_CHECK = 2 * 60
DAILY_KEPT = 7
WEEKLY_KEPT = 4
EVERY = {'daily': timedelta(days=1), 'weekly': timedelta(days=7)}


def made_on(path: Path) -> datetime | None:
    """When an automatic backup was made, from its name (auto-YYYYMMDDTHHMMSS.zip)."""
    try:
        return datetime.strptime(path.stem[len(PREFIX):], '%Y%m%dT%H%M%S')
    except ValueError:
        return None


def made(folder: Path) -> list[tuple[datetime, Path]]:
    """The automatic backups in a Backups folder, newest first."""
    found = [(when, path) for path in folder.glob(f'{PREFIX}*.zip') if (when := made_on(path))] \
        if folder.is_dir() else []
    return sorted(found, reverse=True)


def changed_since(database_path: Path, moment: datetime) -> bool:
    files = backup_sources(database_path)
    return any(datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(tzinfo=None) > moment for path in files)


def backup_sources(database_path: Path) -> list[Path]:
    return [path for path in (database_path, database_path.with_name(database_path.name + '-wal')) if path.exists()]


def due(database_path: Path, now: datetime, every: str) -> bool:
    """No backup within the chosen interval, and something in the world changed since the last one."""
    existing = made(database_path.parent / 'backups')
    if not existing:
        return True
    newest = existing[0][0]
    return now - newest >= EVERY[every] - timedelta(hours=1) and changed_since(database_path, newest)


def kept(entries: list[tuple[datetime, Path]]) -> set[Path]:
    """The newest backup of each of the last DAILY_KEPT days with one, then the newest of each of WEEKLY_KEPT weeks
    before them. A week the dailies reach into is theirs, so the weeklies cover WEEKLY_KEPT whole weeks further back."""
    days: dict[date, Path] = {}
    weeks: dict[tuple, Path] = {}
    for when, path in entries:  # Newest first, so the first seen of a day or week is its newest.
        if len(days) < DAILY_KEPT or when.date() in days:
            days.setdefault(when.date(), path)
            continue
        week = when.isocalendar()[:2]
        if week == min(days).isocalendar()[:2]:
            continue
        if len(weeks) < WEEKLY_KEPT or week in weeks:
            weeks.setdefault(week, path)
    return set(days.values()) | set(weeks.values())


def prune(folder: Path) -> int:
    entries = made(folder)
    keep = kept(entries)
    gone = [path for _when, path in entries if path not in keep]
    for path in gone:
        path.unlink(missing_ok=True)
    return len(gone)


def back_up(database_path: Path, now: datetime, created_at: str) -> Path:
    folder = database_path.parent / 'backups'
    target = folder / f"{PREFIX}{now.strftime('%Y%m%dT%H%M%S')}.zip"
    backup.archive(database_path, target, created_at)
    prune(folder)
    return target


def world_paths(database) -> list[Path]:
    data = worlds.load(database.root)
    found = [worlds.world_path(database.home, world) for world in data['worlds']] if data else [database.path]
    return [path for path in found if path.exists()]


def chosen(database) -> str:
    with database.connect() as connection:
        return settings(connection)['auto_backups']


async def run_once(state) -> list[Path]:
    """Back up every world that is due; a failure is logged and the next world still gets its turn."""
    database = state.database
    every = chosen(database)
    if every == 'off':
        return []
    done = []
    for path in world_paths(database):
        now = database.clock.real().astimezone(UTC).replace(tzinfo=None)
        if not due(path, now, every):
            continue
        try:
            done.append(await asyncio.to_thread(back_up, path, now, database.now()))
        except (OSError, DomainError) as error:
            logging.getLogger('dungeon').warning('An automatic backup of %s failed: %s', path.parent.name or
                                                   'the first world', getattr(error, 'message', error))
    return done


async def run_forever(state):
    await asyncio.sleep(FIRST_CHECK)
    while True:
        await run_once(state)
        await asyncio.sleep(CHECK_EVERY)


def status(database) -> dict:
    """For Settings > Data: how often, and when this world was last backed up on its own."""
    entries = made(database.path.parent / 'backups')
    return {'auto_backups': chosen(database), 'last_auto_backup': entries[0][0].isoformat() if entries else None,
            'auto_backup_count': len(entries)}

