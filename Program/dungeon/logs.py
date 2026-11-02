"""Diagnostic log for the installed app (PRD persistence section).

The server writes to its window and to `logs/dungeon.log` in the data directory (1 MB, three
older files kept), so a problem can be described after the window closes. Default logs never
include message bodies or keys: request logging is off, because a URL can carry a search query,
and anything shaped like a credential is masked before a line is written.
"""
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from dungeon.identity import data_dir

SECRET = re.compile(
    r'(?i)((?:authorization["\']?\s*[:=]\s*["\']?)?(?:bearer|basic)\s+|authorization["\']?\s*[:=]\s*["\']?'
    r'|(?:api[_-]?key|token|secret|password)["\']?\s*[:=]\s*["\']?)'
    r'[^\s"\'&,;]+'
    r'|\b(?:sk|pk|rk|hf|ghp|gho|github_pat|xox[abp])[-_][A-Za-z0-9_\-]{8,}')
MASK = '[redacted]'


def redact(text: str) -> str:
    return SECRET.sub(lambda match: (match.group(1) or '') + MASK, text)


class Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def config(directory: Path | None = None) -> dict:
    """A logging configuration for uvicorn.Config(log_config=...)."""
    folder = (directory or data_dir()) / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    handlers = {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain', 'filters': ['redact'],
                    'stream': 'ext://sys.stderr'},
        'file': {'class': 'logging.handlers.RotatingFileHandler', 'formatter': 'stamped', 'filters': ['redact'],
                 'filename': str(folder / 'dungeon.log'), 'maxBytes': 1 << 20, 'backupCount': 3,
                 'encoding': 'utf-8'},
    }
    logger = {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False}
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {'redact': {'()': Redact}},
        'formatters': {'plain': {'format': '%(levelname)s: %(message)s'},
                       'stamped': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'}},
        'handlers': handlers,
        'loggers': {'uvicorn': logger, 'uvicorn.error': {**logger, 'propagate': False},
                    'dungeon': logger},
    }


def file_path() -> Path:
    """Where the log is being written: the file the running app's handler opened, else the default place."""
    for handler in logging.getLogger('dungeon').handlers:
        if isinstance(handler, logging.FileHandler):
            return Path(handler.baseFilename)
    return data_dir() / 'logs' / 'dungeon.log'


def open_folder(folder: Path) -> None:
    """Show a folder on the PC in Explorer, Finder or the desktop's file manager."""
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'win32':
        os.startfile(folder)  # noqa: S606 - opens the user's own folder in Explorer.
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(folder)])
