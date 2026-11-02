"""Application identity kept separate from Prospero's Study.

The Dungeon never shares a data directory, credential service, port or archive
marker with the writing product, so running both cannot route one into the other.
"""
import os
import sys
from pathlib import Path

APP_ID = 'prospero-dungeon'
APP_NAME = 'Prospero Dungeon'
VERSION = '0.1.0'
SCHEMA_VERSION = 2  # 2: Milestone 0's fresh schema, without the companion (dungeon/upgrade.py FRESH_FROM).
CREDENTIAL_SERVICE = 'Prospero Dungeon'
ARCHIVE_FORMAT = 'prospero-dungeon-archive'
ARCHIVE_VERSION = 2
DEFAULT_PORT = 8785
CLIENT_HEADER = 'x-dungeon-client'
WORLD_HEADER = 'x-dungeon-world'  # The world a page was opened in (dungeon/main.py stay_in_world).
DATA_ENV = 'DUNGEON_DATA_DIR'
DATABASE_ENV = 'DUNGEON_DB'
# The folder holding Windows/, Mac/ and Program/ (a checkout or ZIP copy), or the installed app's folder
# (bundle: app/dungeon). A `Data` folder there keeps everything with the app: see dungeon/data_folder.py.
APP_FOLDER = Path(__file__).resolve().parents[2]
PORTABLE_NAME = 'Data'


def portable_dir() -> Path:
    return APP_FOLDER / PORTABLE_NAME


def data_dir() -> Path:
    if os.environ.get(DATA_ENV):
        return Path(os.environ[DATA_ENV])
    if portable_dir().is_dir():
        return portable_dir()
    return default_dir()


def default_dir() -> Path:
    """Where data lives when nothing chooses another folder: the user's own app-data folder."""
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local'
        return Path(base) / 'ProsperoDungeon'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'ProsperoDungeon'
    base = os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share'
    return Path(base) / APP_ID


def database_path() -> Path:
    return Path(os.environ.get(DATABASE_ENV) or data_dir() / 'dungeon.sqlite3')
