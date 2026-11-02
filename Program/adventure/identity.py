"""Application identity kept separate from Prospero's Study.

Adventure never shares a data directory, credential service, port or archive
marker with the writing product, so running both cannot route one into the other.
"""
import os
import sys
from pathlib import Path

APP_ID = 'prospero-adventure'
APP_NAME = 'Prospero Adventure'
VERSION = '0.1.0'
SCHEMA_VERSION = 2  # 2: Milestone 0's fresh schema, without the companion (adventure/upgrade.py FRESH_FROM).
CREDENTIAL_SERVICE = 'Prospero Adventure'
ARCHIVE_FORMAT = 'prospero-adventure-archive'
ARCHIVE_VERSION = 2
DEFAULT_PORT = 8805
CLIENT_HEADER = 'x-adventure-client'
WORLD_HEADER = 'x-adventure-world'  # The world a page was opened in (adventure/main.py stay_in_world).
DATA_ENV = 'ADVENTURE_DATA_DIR'
DATABASE_ENV = 'ADVENTURE_DB'
# The folder holding Windows/, Mac/ and Program/ (a checkout or ZIP copy), or the installed app's folder
# (bundle: app/adventure). A `Data` folder there keeps everything with the app: see adventure/data_folder.py.
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
        return Path(base) / 'ProsperoAdventure'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'ProsperoAdventure'
    base = os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share'
    return Path(base) / APP_ID


def database_path() -> Path:
    return Path(os.environ.get(DATABASE_ENV) or data_dir() / 'adventure.sqlite3')
