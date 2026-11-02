"""Workspace backup archives with a Dungeon format marker.

An archive is a zip holding `manifest.json` and a consistent SQLite snapshot taken with the online backup API, listed
with its SHA-256. A Dungeon workspace keeps everything in its database, so an archive carries no other files.

Restore only targets a new workspace path, validates the marker and the digest before writing anything, and drops the
saved credential references, which belonged to the machine that made the backup. Saved API keys are never in the
database.
"""
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from dungeon.database import Database
from dungeon.errors import DomainError, require
from dungeon.identity import APP_ID, ARCHIVE_FORMAT, ARCHIVE_VERSION, SCHEMA_VERSION, VERSION

DATABASE_ENTRY = 'dungeon.sqlite3'
MANIFEST_ENTRY = 'manifest.json'
DAMAGED = 'This backup is damaged: {} does not match its recorded digest.'


def snapshot(source_path: Path, target: Path):
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def file_digest(handle) -> tuple[str, int]:
    sha, size = hashlib.sha256(), 0
    for block in iter(lambda: handle.read(1 << 20), b''):
        sha.update(block)
        size += len(block)
    return sha.hexdigest(), size


def archive(source_path: Path, path: Path, created_at: str, schema_version: int = SCHEMA_VERSION,
            app_version: str = VERSION) -> dict:
    """Write a verified archive of the workspace at source_path, whatever schema it has."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / DATABASE_ENTRY
        snapshot(source_path, copy)
        content = copy.read_bytes()
    manifest = {'format': ARCHIVE_FORMAT, 'format_version': ARCHIVE_VERSION, 'app_id': APP_ID,
                'app_version': app_version, 'schema_version': schema_version, 'created_at': created_at,
                'database_sha256': hashlib.sha256(content).hexdigest(), 'database_bytes': len(content)}
    try:
        with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as handle:
            handle.writestr(DATABASE_ENTRY, content)
            handle.writestr(MANIFEST_ENTRY, json.dumps(manifest, indent=2))
        inspect(path)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {**manifest, 'path': str(path)}


def create(database: Database, directory: Path) -> dict:
    created_at = database.now()
    name = f"dungeon-{created_at[:19].replace(':', '').replace('-', '')}.zip"
    return archive(database.path, directory / name, created_at)


def inspect(path: Path) -> dict:
    """Validate an archive, including every file digest, without restoring it."""
    try:
        with zipfile.ZipFile(path) as handle:
            manifest = json.loads(handle.read(MANIFEST_ENTRY))
            require(isinstance(manifest, dict) and manifest.get('format') == ARCHIVE_FORMAT
                    and manifest.get('app_id') == APP_ID, 'This file is not a Dungeon backup.', 422)
            require(manifest.get('format_version', 0) <= ARCHIVE_VERSION
                    and manifest.get('schema_version', 0) <= SCHEMA_VERSION,
                    'This backup was made by a newer Dungeon version.', 409)
            content = handle.read(DATABASE_ENTRY)
            require(hashlib.sha256(content).hexdigest() == manifest.get('database_sha256'),
                    DAMAGED.format('its database'), 422)
    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        raise DomainError('This file is not a Dungeon backup.', 422) from error
    return {'manifest': manifest, 'content': content}


def restore(path: Path, target: Path, clock=None) -> Database:
    require(not target.exists(), 'Restore into a new workspace; the target already exists.', 409)
    checked = inspect(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(checked['content'])
    try:
        database = Database(target, clock)
        hold_for_review(database)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return database


def hold_for_review(database: Database):
    """Credentials belonged to the machine that made the backup; the user connects again."""
    with database.connect(write=True) as connection:
        connection.execute('UPDATE model_profiles SET credential_ref=NULL')
        connection.execute('UPDATE image_backends SET credential_ref=NULL')
