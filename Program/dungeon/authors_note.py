"""Author's note: a short note of the user's that rides along with every reply in one chat (Hit List #48).

One note per chat; the story (`story`) is the only chat there is now. While it is on, it goes last in the notes sent
with the message being answered, right before the user's own words, so it is the last thing the model reads; it sits in
the volatile tail and leaves the cached part of the prompt alone. It is never a message: not in the transcript,
not read for memories, not exported, and an out-of-character message (OOC:) is answered without it.

The wording around the note is an editable prompt (Settings > Developer > Prompts, "Author's note").
"""
import re

from dungeon import prompt_library
from dungeon.database import optional
from dungeon.errors import DomainError

LIMIT = 1000
# Every reply while it is on (no "every N replies" or depth); the note follows this line. Iris's wording, A/B tested
# on 9 models (2026-10-13): it never took a character out of character, so it ships over an OOC-style wording.
HEADER = "[Author's note from the user, for this reply. Follow it, but never mention or quote it:]"
CHAT = re.compile(r'^story$')
# Closes the notes sent with the message being answered, so the model reads the user's own words next.
NOTE_CLOSE = "[End of notes. The user's message:]"


def check_chat(_connection, chat: str):
    """The chat must exist: the story."""
    if not CHAT.match(chat):
        raise DomainError('That is not a chat.', 404, 'no_chat')


def read(connection, chat: str) -> dict:
    row = optional(connection, 'SELECT text, enabled, updated_at FROM authors_notes WHERE chat=?', (chat,))
    if row is None:
        return {'chat': chat, 'text': '', 'enabled': True, 'updated_at': None}
    return {'chat': chat, 'text': row['text'], 'enabled': bool(row['enabled']), 'updated_at': row['updated_at']}


def save(connection, chat: str, text: str, enabled: bool, now: str) -> dict:
    check_chat(connection, chat)
    text = text[:LIMIT] if text.strip() else ''
    connection.execute('INSERT INTO authors_notes (chat, text, enabled, updated_at) VALUES (?, ?, ?, ?) '
                       'ON CONFLICT(chat) DO UPDATE SET text=excluded.text, enabled=excluded.enabled, '
                       'updated_at=excluded.updated_at', (chat, text, int(enabled), now))
    return read(connection, chat)


def active(connection, chat: str) -> str:
    """The note's text while it is on, else ''."""
    row = optional(connection, 'SELECT text, enabled FROM authors_notes WHERE chat=?', (chat,))
    return row['text'].strip() if row and row['enabled'] else ''


def prompt_text(connection, chat: str) -> str:
    """The note as the model reads it, '' when there is none or it is switched off."""
    note = active(connection, chat)
    if not note:
        return ''
    return f"{prompt_library.text(connection, 'authors-note')}\n{note}"
