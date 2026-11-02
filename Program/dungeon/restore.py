"""Replace the active workspace with a backup (PRD persistence section).

The current workspace is never overwritten: its database moves to `replaced-<time>/` beside it first, and moves
back if the restore fails. Settings are not rolled back (from Companion, Vanta, 2026-10-08): the current workspace's
settings, model connections and image backends carry over. Restoring with no current workspace (a new computer)
drops the restored one's saved credentials, since its connections belonged to another machine
(backup.hold_for_review).
"""
import json
import re
import shutil
import sqlite3
import zipfile
from pathlib import Path

from dungeon import backup
from dungeon.clock import Clock, stamp
from dungeon.database import Database
from dungeon.errors import DomainError, require

MOVED = ('images',)
# What "settings" means for a restore, parents before the tables that refer to them.
KEPT_SETTINGS = ('workspace_settings', 'model_profiles', 'model_routes', 'model_mix', 'model_mix_state',
                 'image_backends', 'builtin_recall', 'prompt_overrides', 'debug_time', 'local_programs')


def database_files(path: Path) -> list[Path]:
    return [path, path.with_name(path.name + '-wal'), path.with_name(path.name + '-shm')]


def settle(path: Path):
    connection = sqlite3.connect(path)
    try:
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:
        connection.close()


def set_aside(database_path: Path, aside: Path) -> list[tuple[Path, Path]]:
    moves = [(item, aside / item.name) for item in database_files(database_path) if item.exists()]
    moves += [(database_path.parent / name, aside / name) for name in MOVED if (database_path.parent / name).exists()]
    aside.mkdir(parents=True)
    done = []
    try:
        for source, target in moves:
            shutil.move(source, target)
            done.append((source, target))
    except OSError as error:
        put_back(done)
        raise DomainError('The current workspace could not be moved aside; it is in use or locked. '
                          'Nothing was restored.', 409) from error
    return done


def put_back(moves: list[tuple[Path, Path]]):
    for source, target in reversed(moves):
        shutil.move(target, source)


def keep_settings(database: Database, previous: Path):
    """The settings of the workspace being replaced, instead of the backup's (or the hold a restore starts with)."""
    copy_settings(database.path, previous, KEPT_SETTINGS, database.now())


def copy_settings(target: Path, source: Path, tables: tuple[str, ...], timestamp: str):
    """`tables` in the workspace at `target` become those of the one at `source`: a restore keeps the current
    settings, and switching worlds carries them along (dungeon/worlds.py). `tables` lists parents first."""
    connection = sqlite3.connect(target, isolation_level=None)
    try:
        # A plain path: URI filenames in ATTACH need SQLite built with them on, which Windows' is not.
        connection.execute('ATTACH DATABASE ? AS kept', (str(Path(source).resolve()),))
        connection.execute('BEGIN IMMEDIATE')
        for table in reversed(tables):
            connection.execute(f'DELETE FROM main.{table}')
        for table in tables:
            ours = {row[1] for row in connection.execute(f'PRAGMA main.table_info({table})')}
            columns = ', '.join(row[1] for row in connection.execute(f'PRAGMA kept.table_info({table})')
                                if row[1] in ours)
            if columns:
                connection.execute(f'INSERT INTO main.{table} ({columns}) SELECT {columns} FROM kept.{table}')
        connection.execute('COMMIT')
    except BaseException:
        if connection.in_transaction:
            connection.execute('ROLLBACK')
        raise
    finally:
        connection.close()


def replace_workspace(archive: Path, database_path: Path, clock=None) -> dict:
    backup.inspect(archive)  # Refuse a damaged or foreign archive before anything moves.
    previous = None
    moves = []
    if database_path.exists():
        settle(database_path)
        moment = stamp((clock or Clock()).now())
        aside = database_path.parent / f"replaced-{moment[:19].replace(':', '').replace('-', '')}"
        require(not aside.exists(), 'A workspace was already set aside this second; try again.', 409)
        moves = set_aside(database_path, aside)
        previous = aside / database_path.name
    try:
        restored = backup.restore(archive, database_path, clock)
    except BaseException:
        put_back(moves)
        if previous:
            previous.parent.rmdir()
        raise
    if previous:
        keep_settings(restored, previous)
    return {'restored': str(database_path), 'previous': str(previous.parent) if previous else None}


# Restoring from the interface: the running app cannot replace its own open workspace, so it
# records the choice and the launcher applies it on the next start, before anything opens it.
PENDING = 'pending-restore.json'
BACKUP_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*\.zip$')


def backups_folder(workspace: Path) -> Path:
    return workspace / 'backups'


def archive_path(workspace: Path, name: str) -> Path:
    require(bool(BACKUP_NAME.match(name)), 'Choose a backup from the list.', 404)
    path = backups_folder(workspace) / name
    require(path.is_file(), 'That backup is no longer in the backups folder.', 404)
    return path


# Backups the app makes on its own, named for what they came before (dungeon/upgrade.py, worlds.py), and
# the automatic ones (dungeon/auto_backup.py).
KINDS = ('pre-upgrade', 'before-reset', 'before-delete', 'before-debug', 'auto')


def kind(name: str) -> str:
    return next((item for item in KINDS if name.startswith(item + '-')), 'backup')


def listing(workspace: Path) -> dict:
    """Backups in the workspace's folder, newest first, read from their manifests only."""
    items = []
    folder = backups_folder(workspace)
    found = [path for path in folder.glob('*.zip') if not path.name.startswith('.')] if folder.is_dir() else []
    for path in sorted(found, key=lambda item: item.name, reverse=True):  # Not macOS's `._` Finder files.
        entry = {'name': path.name, 'bytes': path.stat().st_size, 'kind': kind(path.name), 'readable': False}
        try:
            with zipfile.ZipFile(path) as handle:
                manifest = json.loads(handle.read(backup.MANIFEST_ENTRY))
            entry.update(readable=manifest.get('format') == backup.ARCHIVE_FORMAT,
                         created_at=manifest.get('created_at'), app_version=manifest.get('app_version'))
        except (OSError, zipfile.BadZipFile, KeyError, ValueError):
            pass
        items.append(entry)
    return {'backups': items, 'pending': pending(workspace)}


def pending(workspace: Path) -> dict | None:
    try:
        value = json.loads((workspace / PENDING).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) and BACKUP_NAME.match(str(value.get('name', ''))) else None
    except (OSError, ValueError):
        return None


def schedule(workspace: Path, name: str, timestamp: str) -> dict:
    """Checked in full now, so a damaged backup is refused while the user is still here."""
    backup.inspect(archive_path(workspace, name))
    (workspace / PENDING).write_text(json.dumps({'name': name, 'requested_at': timestamp}), encoding='utf-8')
    return listing(workspace)


def cancel(workspace: Path) -> dict:
    (workspace / PENDING).unlink(missing_ok=True)
    return listing(workspace)


def apply_pending(database_path: Path) -> tuple[str, dict | DomainError] | None:
    """Run a restore chosen in the interface. The request is consumed either way, so a restore that
    fails is reported once and never retried on every start."""
    workspace = database_path.parent
    chosen = pending(workspace)
    (workspace / PENDING).unlink(missing_ok=True)
    if not chosen:
        return None
    try:
        return chosen['name'], replace_workspace(archive_path(workspace, chosen['name']), database_path)
    except DomainError as error:
        return chosen['name'], error
