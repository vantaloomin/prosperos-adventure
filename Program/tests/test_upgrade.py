import sqlite3
import zipfile

import pytest

from dungeon import backup, upgrade
from dungeon.database import Database, schema_digest
from dungeon.errors import DomainError


def older_workspace(path):
    """A workspace as an earlier version left it: an older digest and a table it did not have yet."""
    database = Database(path)
    with database.connect(write=True) as connection:
        connection.execute("INSERT INTO workspace_settings (id, updated_at) VALUES (1, 'x') ON CONFLICT DO NOTHING")
        connection.execute("DELETE FROM app_identity WHERE key IN ('schema_digest', 'app_version')")
        connection.execute('DROP TABLE town_levels')
    return database


def tables(path):
    connection = sqlite3.connect(path)
    try:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        connection.close()


def test_upgrade_backs_up_first_then_migrates(tmp_path):
    path = tmp_path / 'dungeon.sqlite3'
    older_workspace(path)
    assert 'town_levels' not in tables(path)

    database = Database(path)

    assert 'town_levels' in tables(path)
    with database.connect() as connection:
        marker = dict(connection.execute('SELECT key, value FROM app_identity').fetchall())
    assert marker['schema_digest'] == schema_digest()
    saved = list((tmp_path / 'backups').glob('pre-upgrade-*.zip'))
    assert len(saved) == 1
    checked = backup.inspect(saved[0])
    assert checked['manifest']['app_version'] == 'unknown'
    # The backup holds the workspace as it was, and restores through the normal path.
    restored = backup.restore(saved[0], tmp_path / 'restored' / 'dungeon.sqlite3')
    assert 'town_levels' in tables(restored.path)
    assert not (tmp_path / 'dungeon.sqlite3.upgrading').exists()


def test_current_workspace_opens_without_an_upgrade(tmp_path):
    path = tmp_path / 'dungeon.sqlite3'
    Database(path)
    Database(path)
    assert not (tmp_path / 'backups').exists()


def test_failed_upgrade_leaves_the_workspace_untouched(tmp_path, monkeypatch):
    path = tmp_path / 'dungeon.sqlite3'
    older_workspace(path)
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    connection.close()
    before = path.read_bytes()

    def broken(staging, timestamp):
        raise sqlite3.OperationalError('disk I/O error')

    monkeypatch.setattr(upgrade, 'migrate', broken)
    with pytest.raises(DomainError) as error:
        Database(path)
    assert 'was not changed' in error.value.message and 'pre-upgrade-' in error.value.message
    assert path.read_bytes() == before
    assert not (tmp_path / 'dungeon.sqlite3.upgrading').exists()
    assert 'town_levels' not in tables(path)


def test_newer_workspace_is_refused_before_any_backup(tmp_path):
    path = tmp_path / 'dungeon.sqlite3'
    database = Database(path)
    with database.connect(write=True) as connection:
        connection.execute("UPDATE app_identity SET value='999' WHERE key='schema_version'")
    with pytest.raises(DomainError) as error:
        Database(path)
    assert error.value.status == 409
    assert not (tmp_path / 'backups').exists()


def test_only_recent_pre_upgrade_backups_are_kept(tmp_path):
    directory = tmp_path / 'backups'
    directory.mkdir()
    for day in range(1, 6):
        (directory / f'pre-upgrade-2026100{day}T000000.zip').write_bytes(b'')
    upgrade.prune(directory)
    assert sorted(item.name for item in directory.iterdir()) == [
        'pre-upgrade-20261003T000000.zip', 'pre-upgrade-20261004T000000.zip', 'pre-upgrade-20261005T000000.zip']


def test_a_workspace_from_before_milestone_0_starts_fresh_and_keeps_the_settings(tmp_path):
    path = tmp_path / 'dungeon.sqlite3'
    database = Database(path)
    with database.connect(write=True) as connection:  # As the companion's schema (version 1) left it.
        connection.execute("UPDATE workspace_settings SET color_scheme='moss'")
        connection.execute("UPDATE app_identity SET value='1' WHERE key='schema_version'")
        connection.execute("DELETE FROM app_identity WHERE key='schema_digest'")
        connection.execute('CREATE TABLE companions (id TEXT PRIMARY KEY)')
        connection.execute("INSERT INTO story_messages (id, seq, role, text, city_id, place_id, created_at) "
                           "VALUES ('m1', 1, 'user', 'Hello', 'baltimore', 'cafe', 'x')")

    database = Database(path)

    assert 'companions' not in tables(path)
    with database.connect() as connection:
        assert connection.execute('SELECT color_scheme FROM workspace_settings').fetchone()[0] == 'moss'
        assert connection.execute('SELECT COUNT(*) FROM story_messages').fetchone()[0] == 0
        marker = dict(connection.execute('SELECT key, value FROM app_identity').fetchall())
    assert marker['schema_version'] == str(upgrade.FRESH_FROM)
    # What happened before is kept in the pre-upgrade backup.
    saved = list((tmp_path / 'backups').glob('pre-upgrade-*.zip'))
    assert len(saved) == 1
    with zipfile.ZipFile(saved[0]) as archive:
        name = next(item for item in archive.namelist() if item.endswith('.sqlite3'))
        archive.extract(name, tmp_path / 'old')
    assert 'companions' in tables(tmp_path / 'old' / name)
