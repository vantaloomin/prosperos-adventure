"""Where the workspace lives, and moving it into the app's own folder (portable mode).

By default the workspace is in the user's app-data folder (identity.default_dir). A `Data` folder
beside Windows/, Mac/ and Program/ (identity.portable_dir) takes over when it exists, so a copy on
an external drive carries its companions with it. Moving there is chosen in Settings and runs on the
next start, before anything opens the workspace, like a restore (dungeon/restore.py): the open
database cannot be copied safely while the app uses it.

The move copies into `Data.moving`, checks every file arrived at full size and the database reads
back whole, and only then renames it to `Data`. The old folder is left as it was, with a note saying
where the data went, so a move that goes wrong never costs anything.
"""
import ctypes
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from dungeon import identity
from dungeon.errors import require

PENDING = 'pending-move.json'
MOVED_NOTE = 'MOVED.txt'
PARTIAL_SUFFIX = '.moving'
SPARE_BYTES = 200 * 1024 * 1024
# Folders that sync files to the cloud. SQLite keeps its database in several files, and a sync client
# that copies them one at a time, or holds them open, can damage the workspace.
CLOUD_PARTS = ('onedrive', 'dropbox', 'google drive', 'googledrive', 'icloud drive', 'icloud', 'mobile documents',
               'cloudstorage', 'box', 'box sync', 'pcloud drive', 'nextcloud', 'owncloud')
NETWORK_TYPES = ('smbfs', 'afpfs', 'nfs', 'nfs4', 'cifs', 'smb3', 'webdav', 'sshfs', 'fuse.sshfs', '9p')
DRIVE_REMOVABLE, DRIVE_REMOTE = 2, 4


def pinned() -> bool:
    """DUNGEON_DATA_DIR or DUNGEON_DB choose the folder themselves (dev mode, CI, tests)."""
    return bool(os.environ.get(identity.DATA_ENV) or os.environ.get(identity.DATABASE_ENV))


def same(first: Path, second: Path) -> bool:
    return os.path.normcase(str(first.resolve())) == os.path.normcase(str(second.resolve()))


def in_app_folder(workspace: Path) -> bool:
    return same(workspace, identity.portable_dir())


def cloud_synced(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    if any(part in CLOUD_PARTS or part.startswith(('onedrive -', 'onedrive-', 'dropbox (')) for part in parts):
        return True
    if sys.platform == 'darwin':
        # iCloud's "Desktop & Documents Folders" syncs these two folders without changing their paths.
        home = Path.home()
        icloud = home / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
        for name in ('Desktop', 'Documents'):
            if path.is_relative_to(home / name) and (icloud / name).is_dir():
                return True
    return False


def mount_type(path: Path) -> str:
    """The file system type of the mount holding path, or '' when it cannot be told."""
    try:
        if sys.platform.startswith('linux'):
            lines = Path('/proc/mounts').read_text().splitlines()
            mounts = [(line.split()[1].replace('\\040', ' '), line.split()[2]) for line in lines if len(line.split()) > 2]
        elif sys.platform == 'darwin':
            output = subprocess.run(['/sbin/mount'], capture_output=True, text=True, timeout=5).stdout
            mounts = []
            for line in output.splitlines():
                # "//user@host/share on /Volumes/share (smbfs, nodev, ...)"
                if ' on ' in line and ' (' in line:
                    point, kind = line.split(' on ', 1)[1].rsplit(' (', 1)
                    mounts.append((point, kind.split(',')[0]))
        else:
            return ''
    except (OSError, subprocess.SubprocessError, ValueError):
        return ''
    # Resolve symlinks on a real folder; a path that is not there is matched as written (POSIX form).
    resolved = path.resolve().as_posix() if path.exists() else path.as_posix()
    best = max((item for item in mounts if resolved == item[0] or resolved.startswith(item[0].rstrip('/') + '/')),
               key=lambda item: len(item[0]), default=None)
    return best[1] if best else ''


def drive_type(path: Path) -> int | None:
    if sys.platform != 'win32':
        return None
    try:
        anchor = str(path.resolve().anchor)
        return ctypes.windll.kernel32.GetDriveTypeW(anchor)
    except (AttributeError, OSError):
        return None


def network(path: Path) -> bool:
    if str(path).startswith('\\\\') or str(path.resolve()).startswith('\\\\'):
        return True
    if drive_type(path) == DRIVE_REMOTE:
        return True
    return mount_type(path) in NETWORK_TYPES


def removable(path: Path) -> bool:
    if drive_type(path) == DRIVE_REMOVABLE:
        return True
    return sys.platform == 'darwin' and str(path.resolve()).startswith('/Volumes/')


def writable(folder: Path) -> bool:
    probe = folder / '.companion-write-check'
    try:
        probe.write_bytes(b'')
        probe.unlink()
        return True
    except OSError:
        return False


def folder_bytes(folder: Path) -> int:
    return sum(item.stat().st_size for item in folder.rglob('*') if item.is_file())


def refusal(workspace: Path) -> str | None:
    """Why the workspace cannot move into the app folder now, or None when it can."""
    target = identity.portable_dir()
    if pinned():
        return 'DUNGEON_DATA_DIR or DUNGEON_DB chooses the data folder for this copy, so it stays there.'
    if in_app_folder(workspace):
        return None
    if target.exists():
        return f'{target} already exists. Rename or remove it first.'
    if network(identity.APP_FOLDER):
        return 'The app folder is on a network drive. The database can be damaged there, so data stays where it is.'
    if cloud_synced(identity.APP_FOLDER):
        return ('The app folder is inside a folder that syncs to the cloud (like OneDrive, Dropbox or iCloud). '
                'Syncing can damage the database while the app runs, so data stays where it is.')
    if not writable(identity.APP_FOLDER):
        return 'The app folder cannot be written to (it may be read-only or on a disk image), so data stays where it is.'
    needed = (folder_bytes(workspace) if workspace.is_dir() else 0) + SPARE_BYTES
    if shutil.disk_usage(identity.APP_FOLDER).free < needed:
        return f'The drive with the app folder needs about {needed // (1024 * 1024)} MB free for the copy.'
    return None


def pending(workspace: Path) -> bool:
    return (workspace / PENDING).is_file()


def status(workspace: Path) -> dict:
    target = identity.portable_dir()
    portable = in_app_folder(workspace)
    reason = None if portable else refusal(workspace)
    notes = []
    if portable and removable(target):
        notes.append('Keep this drive connected while the Dungeon is running.')
    return {'path': str(workspace), 'portable': portable, 'pinned': pinned(), 'target': str(target),
            'default': str(identity.default_dir()), 'can_move': not portable and reason is None,
            'reason': reason, 'pending': pending(workspace), 'notes': notes}


def schedule(workspace: Path, timestamp: str) -> dict:
    reason = refusal(workspace)
    require(not in_app_folder(workspace), 'Your data is already in the app folder.', 409)
    require(reason is None, reason or '', 409)
    (workspace / PENDING).write_text(json.dumps({'target': str(identity.portable_dir()), 'requested_at': timestamp}),
                                     encoding='utf-8')
    return status(workspace)


def cancel(workspace: Path) -> dict:
    (workspace / PENDING).unlink(missing_ok=True)
    return status(workspace)


def open_folder(workspace: Path) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'win32':
        os.startfile(workspace)  # noqa: S606 - opens the user's own folder in Explorer.
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(workspace)])
    return {'folder': str(workspace)}


def settle(database: Path):
    """Fold the write-ahead log into the database so the copied file is complete on its own."""
    connection = sqlite3.connect(database)
    try:
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:
        connection.close()


def verify(source: Path, copy: Path):
    for item in source.rglob('*'):
        if item.is_file():
            copied = copy / item.relative_to(source)
            if not copied.is_file() or copied.stat().st_size != item.stat().st_size:
                raise OSError(f'{item.relative_to(source)} did not copy completely.')
    database = copy / 'dungeon.sqlite3'
    if database.exists():
        connection = sqlite3.connect(f'{database.resolve().as_uri()}?mode=ro', uri=True)
        try:
            result = connection.execute('PRAGMA quick_check').fetchone()[0]
        finally:
            connection.close()
        if result != 'ok':
            raise OSError('The copied database did not pass its check.')


def apply_pending(workspace: Path) -> str | None:
    """Run a move chosen in Settings. The request is consumed either way, so a move that fails is
    reported once and never retried on every start. Returns what to tell the user."""
    if not pending(workspace):
        return None
    (workspace / PENDING).unlink()
    if in_app_folder(workspace):
        return None
    reason = refusal(workspace)
    if reason:
        return f'Your data was not moved. {reason}'
    target = identity.portable_dir()
    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    try:
        if partial.exists():
            shutil.rmtree(partial)  # Left by an earlier move that stopped part way; only this code makes it.
        database = workspace / 'dungeon.sqlite3'
        if database.exists():
            settle(database)
        shutil.copytree(workspace, partial, ignore=shutil.ignore_patterns(MOVED_NOTE))
        verify(workspace, partial)
        partial.rename(target)
    except (OSError, sqlite3.Error, shutil.Error) as error:
        shutil.rmtree(partial, ignore_errors=True)
        return f'Your data was not moved and is still in {workspace}. {error}'
    try:
        (workspace / 'pending-restore.json').unlink(missing_ok=True)  # The copy in Data runs it instead.
        (workspace / MOVED_NOTE).write_text(
            f'Your Prospero Dungeon data now lives in {target}\n\n'
            'This folder was left as it was in case anything went wrong. It is no longer used while that '
            'Data folder exists. Once the Dungeon works from the new folder you can delete this one.\n',
            encoding='utf-8')
    except OSError:
        pass
    return (f'Moved your data to {target}. The old folder {workspace} was left as it was; '
            'delete it once everything looks right.')
