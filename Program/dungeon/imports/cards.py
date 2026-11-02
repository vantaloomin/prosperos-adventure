"""Character Card files (JSON, or PNG with the card embedded) read into plain text for the character helper.

Copied from prosperos-study at bbcbde4: `chunks` and `embedded_card` from
server/library_formats/png_cards.py and `card_data` from server/library_formats/cards.py. Changes:
errors are `DomainError`s, the card is never converted to Library files, and `card_text` lays the
card's fields out as text the user reviews in the paste box before anything is sent to a model.
Nothing is saved, no asset is fetched and no macro is run.
"""
import base64
import binascii
import json
from pathlib import PureWindowsPath
from struct import unpack
from zlib import crc32

from dungeon.errors import DomainError

MAX_SOURCE_BYTES = 10 * 1024 * 1024
SIGNATURE = b'\x89PNG\r\n\x1a\n'
TEXT_LIMIT = 40000
# The card fields that describe the character, in the order a person would read them.
SECTIONS = (('description', 'Description'), ('personality', 'Personality'), ('scenario', 'Scenario'),
            ('first_mes', 'First message'), ('mes_example', 'Example messages'), ('creator_notes', "Creator's notes"))
MACROS = (('{{char}}', None), ('<BOT>', None), ('{{user}}', 'the user'), ('<USER>', 'the user'))


def problem(message: str) -> DomainError:
    return DomainError(message, 422, 'card_unreadable')


def chunks(source):
    if not source.startswith(SIGNATURE) or len(source) > MAX_SOURCE_BYTES:
        raise problem('Choose a PNG Character Card no larger than 10 MiB.')
    offset = 8
    count = 0
    while offset + 12 <= len(source):
        length = unpack('>I', source[offset:offset + 4])[0]
        kind = source[offset + 4:offset + 8]
        end = offset + length + 12
        if end > len(source) or count >= 10000:
            raise problem('This PNG has incomplete or too many chunks.')
        payload = source[offset + 8:end - 4]
        expected = unpack('>I', source[end - 4:end])[0]
        if crc32(kind + payload) & 0xffffffff != expected:
            raise problem('This PNG has a damaged chunk checksum.')
        yield kind, payload
        offset = end
        count += 1
        if kind == b'IEND':
            return
    raise problem('This PNG has no complete image ending.')


def embedded_card(source) -> bytes:
    payloads = {}
    for kind, payload in chunks(source):
        if kind == b'tEXt':
            key, separator, value = payload.partition(b'\0')
            if separator and key in {b'ccv3', b'chara'}:
                payloads[key] = value
    key = b'ccv3' if b'ccv3' in payloads else b'chara'
    if key not in payloads:
        raise problem('No character card was found in this picture. Paste the character as text instead.')
    try:
        return base64.b64decode(payloads[key], validate=True)
    except (ValueError, binascii.Error) as error:
        raise problem('The character card in this picture is not valid base64.') from error


def card_data(value) -> dict:
    if not isinstance(value, dict):
        raise problem('A Character Card must be a JSON object.')
    spec = value.get('spec')
    if spec is None:
        return value
    if spec not in {'chara_card_v2', 'chara_card_v3'}:
        raise problem('Supported card formats are V1, chara_card_v2 and chara_card_v3.')
    data = value.get('data')
    if not isinstance(data, dict):
        raise problem('A V2/V3 card must contain a data object.')
    return data


def card_text(data: dict) -> dict:
    """The card's name and its describing fields as headed plain text, with {{char}} and {{user}} spelled out."""
    name = data.get('name') if isinstance(data.get('name'), str) else ''
    parts = [f'Name: {name.strip()}'] if name.strip() else []
    for key, label in SECTIONS:
        if isinstance(data.get(key), str) and data[key].strip():
            parts.append(f'{label}:\n{data[key].strip()}')
    book = data.get('character_book')
    entries = book.get('entries') if isinstance(book, dict) else None
    notes = [entry['content'].strip() for entry in entries or [] if isinstance(entry, dict)
             and isinstance(entry.get('content'), str) and entry['content'].strip() and entry.get('enabled', True)]
    if notes:
        parts.append('Notes:\n' + '\n'.join(f'- {note}' for note in notes))
    text = '\n\n'.join(parts)
    for macro, value in MACROS:
        text = text.replace(macro, value if value is not None else (name.strip() or 'the character'))
    if not text.strip():
        raise problem('This character card has no text describing the character.')
    return {'name': name.strip(), 'text': text[:TEXT_LIMIT], 'truncated': len(text) > TEXT_LIMIT}


def read_card(filename: str, encoded: str) -> dict:
    try:
        source = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise problem('Choose the card file again; it did not arrive whole.') from error
    if len(source) > MAX_SOURCE_BYTES:
        raise problem('Character cards are limited to 10 MiB.')
    suffix = PureWindowsPath(filename).suffix.lower()
    if suffix == '.png' or source.startswith(SIGNATURE):
        source = embedded_card(source)
    elif suffix != '.json':
        raise problem('Choose a character card saved as JSON or PNG, or paste the character as text.')
    try:
        value = json.loads(source.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise problem('This file is not a readable character card.') from error
    return card_text(card_data(value))
