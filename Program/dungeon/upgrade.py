"""Upgrade a workspace created by an earlier version without risking it (PRD persistence section).

Opening a workspace whose schema differs from this version's runs here first, before the server
accepts requests:

1. Compatibility: `inspect_existing` has already refused another app's database and a workspace
   from a newer schema version.
2. A verified pre-upgrade backup is written to `backups/pre-upgrade-*.zip` in the original schema.
3. The upgrade runs on a copy, which must pass SQLite's integrity check.
4. Only then does the copy replace the workspace. Any failure leaves the original untouched and
   names the backup, which restores through the normal restore path.

A workspace from before Milestone 0 (schema version 1, the companion's) is not migrated: the copy is a fresh
workspace that keeps only the user's settings, models, persona and cities. The pre-upgrade backup keeps the rest.
"""
import os
import sqlite3
from pathlib import Path

from dungeon import backup
from dungeon.database import initialize, stored_identity
from dungeon.errors import DomainError

BACKUP_DIRECTORY = 'backups'
KEEP_PRE_UPGRADE = 3
# The first schema version of Milestone 0's fresh schema; older workspaces start fresh (`fresh`).
FRESH_FROM = 2


def sidecars(path: Path) -> tuple[Path, Path]:
    return path.with_name(path.name + '-wal'), path.with_name(path.name + '-shm')


def remove(path: Path):
    for item in (path, *sidecars(path)):
        item.unlink(missing_ok=True)


def migrate(staging: Path, timestamp: str):
    connection = sqlite3.connect(staging, isolation_level=None)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN IMMEDIATE')
        initialize(connection, timestamp)
        connection.commit()
        result = connection.execute('PRAGMA integrity_check').fetchone()[0]
        if result != 'ok':
            raise DomainError(f'The upgraded copy failed its integrity check: {result}', 500)
        connection.execute('PRAGMA journal_mode=DELETE')
    finally:
        connection.close()


def fresh(staging: Path, original: Path, timestamp: str):
    """A new workspace in place of a pre-Milestone 0 one, keeping what the user set up rather than what happened."""
    from dungeon import restore
    connection = sqlite3.connect(staging, isolation_level=None)
    try:
        connection.execute('BEGIN IMMEDIATE')
        initialize(connection, timestamp)
        connection.commit()
    finally:
        connection.close()
    restore.copy_settings(staging, original, restore.KEPT_SETTINGS + ('world_cities', 'persona'), timestamp)
    migrate(staging, timestamp)


def settle(path: Path):
    """Fold the original's write-ahead log in, so no stale log is replayed over the upgraded file."""
    connection = sqlite3.connect(path)
    try:
        busy = connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]
    finally:
        connection.close()
    wal, shm = sidecars(path)
    if busy or (wal.exists() and wal.stat().st_size):
        raise DomainError('Another program is using the workspace. Close it and start the Dungeon again.', 409)
    wal.unlink(missing_ok=True)
    shm.unlink(missing_ok=True)


def prune(directory: Path):
    for old in sorted(directory.glob('pre-upgrade-*.zip'))[:-KEEP_PRE_UPGRADE]:
        old.unlink(missing_ok=True)


def run(path: Path, timestamp: str) -> dict:
    stored = stored_identity(path)
    directory = path.parent / BACKUP_DIRECTORY
    stamp = timestamp[:19].replace(':', '').replace('-', '')
    saved = backup.archive(path, directory / f'pre-upgrade-{stamp}.zip', timestamp,
                           schema_version=int(stored.get('schema_version', 0)),
                           app_version=stored.get('app_version', 'unknown'))
    staging = path.with_name(path.name + '.upgrading')
    remove(staging)
    try:
        if int(stored.get('schema_version', 0)) < FRESH_FROM:
            fresh(staging, path, timestamp)
        else:
            backup.snapshot(path, staging)
            migrate(staging, timestamp)
        settle(path)
        os.replace(staging, path)
    except BaseException as error:
        remove(staging)
        if not isinstance(error, Exception):
            raise
        detail = error.message if isinstance(error, DomainError) else 'The upgrade could not be completed.'
        raise DomainError(f'{detail} Your workspace was not changed. A backup from before the upgrade is at '
                          f"{saved['path']}.", getattr(error, 'status', 500)) from error
    prune(directory)
    return saved
