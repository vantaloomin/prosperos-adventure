"""Plain words for a failure nobody planned for: what failed, the likely reason where it can be told, what to try,
and a one-line detail for a bug report. Never a traceback; that goes to the log (dungeon/logs.py)."""
import errno
import sqlite3

# The part of the app each request belongs to, longest prefix first.
AREAS = (
    ('/api/world', 'the cities'), ('/api/worlds', 'worlds'), ('/api/images', 'pictures'),
    ('/api/story', 'the story'), ('/api/authors-notes', "the author's note"),
    ('/api/models', 'model settings'), ('/api/connection', 'model settings'),
    ('/api/builtin-recall', 'built-in recall'), ('/api/hardware', 'the hardware check'),
    ('/api/backups', 'backups'), ('/api/debug-time', 'Debug time'), ('/api/model-calls', 'Record model calls'),
    ('/api/townsfolk-mix', 'Townsfolk mix'), ('/api/import', 'the import'), ('/api/prompts', 'prompts'),
)
DETAIL_LIMIT = 300


def area(path: str) -> str:
    return next((name for prefix, name in AREAS if path == prefix or path.startswith(prefix + '/')), 'the Dungeon')


def detail(error: BaseException) -> str:
    """The error's type and first line, for a bug report."""
    text = ' '.join(str(error).split())
    line = f'{type(error).__name__}: {text}' if text else type(error).__name__
    return line if len(line) <= DETAIL_LIMIT else line[:DETAIL_LIMIT - 1] + '…'


# What SQLite says when its file, not the app, is the problem, and what to tell the player.
DATABASE_REASONS = (
    (('locked', 'busy'), 'Its data file was busy with other work. Wait a moment and try again.'),
    (('readonly', 'read-only', 'unable to open'), 'It could not write to its data folder. Check that the drive is '
     'connected and not read-only (Settings > Data shows where the data folder is).'),
    (('full',), 'The drive holding its data folder is full. Free some space, then try again.'),
    (('disk i/o',), 'The drive holding its data folder did not answer. Check that it is still connected.'),
    (('malformed',), 'Its data file looks damaged. Restoring a backup from Settings > Data should fix it.'),
)


def reason(error: BaseException) -> str | None:
    """The likely cause and what to try, for the failures that can be told apart. None: probably a bug."""
    if isinstance(error, sqlite3.DatabaseError):
        text = str(error).lower()
        return next((said for words, said in DATABASE_REASONS if any(word in text for word in words)), None)
    if isinstance(error, PermissionError):
        return f'It was not allowed to open {error.filename or "a file it needs"}. Check the folder permissions.'
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return 'The drive is full. Free some space, then try again.'
    if isinstance(error, FileNotFoundError):
        return f'A file it needs is missing: {error.filename or "unknown"}. Updating the app may restore it.'
    if isinstance(error, MemoryError):
        return 'The computer ran out of memory. Closing other programs may help.'
    return None


def describe(action: str, place: str, error: BaseException, log: str | None = None) -> str:
    """One message for the page: `action` says what failed ("Couldn't load", "Couldn't finish that in")."""
    cause = reason(error) or 'This looks like a bug in the Dungeon. Try again; if it keeps happening, please report it.'
    where = f' The log at {log} has the full report.' if log else ''
    return f'{action} {place}. {cause}{where} Details: {detail(error)}'


def for_request(method: str, path: str, error: BaseException, log: str | None = None) -> str:
    action = "Couldn't load" if method == 'GET' else "Couldn't finish that in"
    return describe(action, area(path), error, log)
