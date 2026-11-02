"""Record model calls (Settings > Developer): every chat model request and its response, in full, for debugging.

Off by default (workspace `record_model_calls`), because the files hold the user's chats word for word. While it is
on, each call the app makes to a chat model (one-on-one replies, groups, Story, life wording,
memory suggestions, picture descriptions, the character helper) is appended as one JSON line to
`logs/model-calls/YYYY-MM-DD.jsonl` in the data folder:

- `caller`: the part of the app that asked (its module), `provider`, `model`, `base_url` (no query string);
- `request`: the system prompt, the messages and the exact request body the provider is sent;
- `response`: the text and the thinking as they streamed, the finish reason and token usage, or the error;
- `started_at` and `seconds`.

The key never reaches the file: it travels in headers, which are not recorded, and the address loses its query
string. Files older than `KEEP_DAYS` are deleted as new calls are written. `bundle` zips the folder for support.
"""
import io
import json
import sys
import threading
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dungeon.clock import stamp
from dungeon.database import identifier, settings
from dungeon.providers.chat import provider_of
from dungeon.providers.config import CLI_PROVIDERS
from dungeon.providers.requests import REQUESTS, transcript

KEEP_DAYS = 7
FOLDER = Path('logs') / 'model-calls'
LOCK = threading.Lock()


def folder(database) -> Path:
    return database.path.parent / FOLDER


def recording(database) -> bool:
    with database.connect() as connection:
        return bool(settings(connection)['record_model_calls'])


def address(url: str | None) -> str | None:
    """The service address without a query string, which some services use for the key."""
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))


def request_body(config: dict, system: str, messages: list[dict]):
    """The body the provider is sent (dungeon/providers/requests.py); Codex gets the transcript on stdin."""
    provider = provider_of(config)
    try:
        if provider in CLI_PROVIDERS:
            return transcript(system, messages)
        return REQUESTS[provider]({**config, 'provider': provider}, system, messages)[1]
    except Exception as error:  # noqa: BLE001 - the call itself reports a broken setting; the record says so.
        return {'unavailable': str(error)}


class Recording:
    """Wraps the chat provider: every call goes through unchanged, and is written down while recording is on."""

    def __init__(self, inner, database):
        self.inner = inner
        self.database = database

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def stream(self, config: dict, key: str | None, system: str, messages: list[dict]):
        caller = sys._getframe(1).f_globals.get('__name__', '?')
        if not recording(self.database):
            return self.inner.stream(config, key, system, messages)
        return self.recorded(caller, config, key, system, messages)

    async def recorded(self, caller: str, config: dict, key: str | None, system: str, messages: list[dict]):
        call = {'id': identifier(), 'started_at': stamp(self.database.clock.now()), 'caller': caller,
                'provider': provider_of(config), 'model': config.get('model'),
                'base_url': address(config.get('base_url')),
                'request': {'system': system, 'messages': messages,
                            'body': request_body(config, system, messages)}}
        response = {'text': '', 'reasoning': '', 'finish_reason': None, 'usage': {}}
        began = time.monotonic()
        try:
            async for chunk in self.inner.stream(config, key, system, messages):
                response['reasoning' if chunk.reasoning else 'text'] += chunk.text
                response['finish_reason'] = chunk.finish_reason or response['finish_reason']
                response['usage'] = chunk.usage or response['usage']
                yield chunk
        except GeneratorExit:
            call['error'] = 'Stopped before the end (the reply was stopped or no longer needed).'
            raise
        except BaseException as error:
            call['error'] = f'{type(error).__name__}: {error}'
            raise
        finally:
            call['response'] = response
            call['seconds'] = round(time.monotonic() - began, 3)
            write(self.database, call)


def write(database, call: dict):
    directory = folder(database)
    today = database.clock.now().date()
    with LOCK:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f'{today.isoformat()}.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(call, ensure_ascii=False, default=str) + '\n')
        prune(directory, today)


def prune(directory: Path, today: date):
    oldest = (today - timedelta(days=KEEP_DAYS - 1)).isoformat()
    for path in directory.glob('*.jsonl'):
        if path.stem < oldest:
            path.unlink(missing_ok=True)


def summary(database) -> dict:
    files = sorted(folder(database).glob('*.jsonl')) if folder(database).is_dir() else []
    return {'recording': recording(database), 'folder': str(folder(database)), 'keep_days': KEEP_DAYS,
            'files': len(files), 'bytes': sum(path.stat().st_size for path in files)}


def bundle(database) -> bytes:
    """The recorded days as one zip, to send to whoever is helping."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        if folder(database).is_dir():
            for path in sorted(folder(database).glob('*.jsonl')):
                archive.write(path, path.name)
    return buffer.getvalue()


def clear(database) -> None:
    if folder(database).is_dir():
        for path in folder(database).glob('*.jsonl'):
            path.unlink(missing_ok=True)
