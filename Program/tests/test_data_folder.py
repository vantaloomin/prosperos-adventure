"""Keeping the workspace in the app's own folder (dungeon/data_folder.py, identity.portable_dir)."""
from pathlib import Path

import pytest

from dungeon import data_folder, identity, launch


@pytest.fixture
def app_folder(tmp_path, monkeypatch):
    folder = tmp_path / 'external drive' / 'prosperos-dungeon'
    folder.mkdir(parents=True)
    monkeypatch.setattr(identity, 'APP_FOLDER', folder)
    monkeypatch.delenv(identity.DATA_ENV, raising=False)
    monkeypatch.delenv(identity.DATABASE_ENV, raising=False)
    monkeypatch.setattr(data_folder, 'network', lambda path: False)
    return folder


def test_a_data_folder_in_the_app_folder_wins_over_the_default(app_folder, monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'home'))
    monkeypatch.setattr(identity.sys, 'platform', 'linux')
    assert identity.data_dir() == tmp_path / 'home' / 'prospero-dungeon'
    (app_folder / 'Data').mkdir()
    assert identity.data_dir() == app_folder / 'Data'
    monkeypatch.setenv(identity.DATA_ENV, str(tmp_path / 'chosen'))
    assert identity.data_dir() == tmp_path / 'chosen'


def test_settings_shows_the_folder_and_schedules_a_move(client, app, app_folder):
    workspace = app.state.database.path.parent
    shown = client.get('/api/backups/data-folder').json()
    assert shown['path'] == str(workspace) and shown['target'] == str(app_folder / 'Data')
    assert shown['can_move'] and not shown['portable'] and not shown['pending']
    moving = client.post('/api/backups/data-folder/move')
    assert moving.status_code == 200, moving.text
    assert moving.json()['pending'] and (workspace / data_folder.PENDING).is_file()
    assert not client.delete('/api/backups/data-folder/move').json()['pending']


def test_a_failed_copy_leaves_everything_where_it_was(client, app, app_folder, monkeypatch):
    workspace = app.state.database.path.parent
    assert client.post('/api/backups/data-folder/move').status_code == 200
    client.close()

    def broken(source, copy):
        raise OSError('dungeon.sqlite3 did not copy completely.')

    monkeypatch.setattr(data_folder, 'verify', broken)
    told = data_folder.apply_pending(workspace)
    assert 'was not moved' in told and str(workspace) in told
    assert not (app_folder / 'Data').exists() and not (app_folder / 'Data.moving').exists()
    assert not (workspace / data_folder.PENDING).exists()


@pytest.mark.parametrize('parts', [('OneDrive', 'Apps'), ('OneDrive - Contoso',), ('Dropbox',), ('Library', 'CloudStorage')])
def test_cloud_synced_folders_are_refused(tmp_path, monkeypatch, parts):
    folder = tmp_path.joinpath(*parts, 'prosperos-dungeon')
    folder.mkdir(parents=True)
    monkeypatch.setattr(identity, 'APP_FOLDER', folder)
    monkeypatch.delenv(identity.DATA_ENV, raising=False)
    monkeypatch.delenv(identity.DATABASE_ENV, raising=False)
    assert 'syncs to the cloud' in data_folder.refusal(tmp_path / 'workspace')


def test_a_chosen_folder_or_existing_data_folder_blocks_the_move(app_folder, monkeypatch, tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (app_folder / 'Data').mkdir()
    assert 'already exists' in data_folder.refusal(workspace)
    monkeypatch.setenv(identity.DATA_ENV, str(workspace))
    assert 'DUNGEON_DATA_DIR' in data_folder.refusal(workspace)


def test_network_mounts_are_read_from_the_mount_table(monkeypatch):
    monkeypatch.setattr(data_folder.sys, 'platform', 'linux')
    table = '/dev/sda1 / ext4 rw 0 0\n//nas/share /mnt/nas cifs rw 0 0\n'
    monkeypatch.setattr(data_folder.Path, 'read_text', lambda self, *args, **kwargs: table)
    assert data_folder.mount_type(Path('/mnt/nas/apps')) == 'cifs'
    assert data_folder.mount_type(Path('/home/me')) == 'ext4'


def test_the_launcher_moves_before_opening_the_workspace(app_folder, tmp_path, monkeypatch, capsys):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'note.txt').write_text('kept')
    (workspace / data_folder.PENDING).write_text('{}')
    monkeypatch.setenv(identity.DATABASE_ENV, '')
    monkeypatch.setattr('dungeon.identity.database_path', lambda: workspace / 'dungeon.sqlite3')
    launch.move_chosen_data()
    assert (app_folder / 'Data' / 'note.txt').read_text() == 'kept'
    assert 'Moved your data' in capsys.readouterr().out
