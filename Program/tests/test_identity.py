import sqlite3

import pytest
from fastapi.testclient import TestClient

from dungeon import identity
from dungeon.database import Database, schema_digest
from dungeon.errors import DomainError


def test_new_workspace_carries_companion_marker(tmp_path):
    database = Database(tmp_path / 'dungeon.sqlite3')
    with database.connect() as connection:
        marker = dict(connection.execute('SELECT key, value FROM app_identity').fetchall())
    assert marker == {'app_id': 'prospero-dungeon', 'schema_version': str(identity.SCHEMA_VERSION),
                      'schema_digest': schema_digest(), 'app_version': identity.VERSION}
    Database(database.path)  # Reopening its own workspace succeeds.


def test_study_database_is_refused_and_left_untouched(tmp_path):
    path = tmp_path / 'roleplay.sqlite3'
    connection = sqlite3.connect(path)
    connection.execute('CREATE TABLE stories (id TEXT PRIMARY KEY)')
    connection.commit()
    connection.close()
    before = path.read_bytes()
    with pytest.raises(DomainError) as error:
        Database(path)
    assert error.value.status == 409
    assert path.read_bytes() == before
    assert not (tmp_path / 'roleplay.sqlite3-wal').exists()


def test_non_database_file_is_refused(tmp_path):
    path = tmp_path / 'notes.sqlite3'
    path.write_text('not a database')
    with pytest.raises(DomainError):
        Database(path)


def test_data_directory_is_separate_from_the_study(monkeypatch, tmp_path):
    monkeypatch.setenv(identity.DATA_ENV, str(tmp_path / 'custom'))
    monkeypatch.delenv(identity.DATABASE_ENV, raising=False)
    assert identity.database_path() == tmp_path / 'custom' / 'dungeon.sqlite3'
    monkeypatch.delenv(identity.DATA_ENV)
    assert 'roleplay' not in str(identity.data_dir()).lower()
    assert identity.DEFAULT_PORT != 8765
    assert identity.CREDENTIAL_SERVICE != 'Roleplay Interface'


@pytest.mark.parametrize(('platform', 'expected'), [
    ('darwin', ('Library', 'Application Support', 'ProsperoDungeon')),
    ('linux', ('.local', 'share', 'prospero-dungeon')),
])
def test_data_directory_follows_the_platform(monkeypatch, tmp_path, platform, expected):
    monkeypatch.delenv(identity.DATA_ENV, raising=False)
    monkeypatch.delenv('XDG_DATA_HOME', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    monkeypatch.setattr(identity.sys, 'platform', platform)
    monkeypatch.setattr(identity, 'APP_FOLDER', tmp_path / 'app')  # No Data folder there.
    assert identity.data_dir() == tmp_path.joinpath(*expected)


def test_writes_require_the_local_client_header(app):
    with TestClient(app) as client:
        assert client.get('/api/health').json()['app_id'] == 'prospero-dungeon'
        assert client.post('/api/pause').status_code == 403
