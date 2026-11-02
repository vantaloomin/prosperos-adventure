import json
import zipfile

import pytest

from dungeon import backup
from dungeon.errors import DomainError


def test_backup_round_trip_keeps_the_story_and_drops_saved_keys(client, app, told, tmp_path, clock):
    created = client.post('/api/backups').json()
    assert created['format'] == 'prospero-dungeon-archive' and created['path'].endswith('.zip')
    assert backup.Path(created['path']).name.startswith('dungeon-')
    restored = backup.restore(backup.Path(created['path']), tmp_path / 'restored' / 'dungeon.sqlite3', clock)
    with restored.connect() as connection:
        said = [row[0] for row in connection.execute("SELECT text FROM story_messages WHERE role='user'")]
        reference = connection.execute('SELECT credential_ref FROM model_profiles').fetchone()[0]
    assert said == ['I step inside out of the rain.']
    assert reference is None


def test_restore_refuses_an_existing_target(tmp_path, app, told):
    created = backup.create(app.state.database, tmp_path / 'archives')
    with pytest.raises(DomainError):
        backup.restore(backup.Path(created['path']), app.state.database.path)


def test_foreign_and_damaged_archives_are_rejected(tmp_path, app, told):
    foreign = tmp_path / 'study.zip'
    with zipfile.ZipFile(foreign, 'w') as archive:
        archive.writestr('manifest.json', json.dumps({'format': 'roleplay-archive'}))
        archive.writestr('dungeon.sqlite3', b'')
    with pytest.raises(DomainError):
        backup.inspect(foreign)
    created = backup.create(app.state.database, tmp_path / 'archives')
    damaged = tmp_path / 'damaged.zip'
    with zipfile.ZipFile(created['path']) as source, zipfile.ZipFile(damaged, 'w') as target:
        target.writestr('manifest.json', source.read('manifest.json'))
        target.writestr('dungeon.sqlite3', source.read('dungeon.sqlite3') + b'x')
    with pytest.raises(DomainError):
        backup.inspect(damaged)
