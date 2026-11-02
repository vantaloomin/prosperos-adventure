"""Character files from other apps read into one shape: the character's text, their own lorebook and a picture.

The range is Prospero's Study's (prosperos-study at bbcbde4, server/library_formats/): Character Cards V1, V2 and
V3 as JSON or PNG (SillyTavern, Chub, Agnai, RisuAI and most card sites), CHARX containers, Backyard Archive
(BYAF) files, Marinara Engine's own .marinara.json exports (a V2 card or a lorebook in an envelope), Pygmalion and Backyard / Faraday legacy JSON, and lorebooks from SillyTavern, NovelAI, Agnai and
RisuAI (dungeon/imports/lorebooks.py). The ZIP checks are the Study's containers.py, unchanged in substance.
Nothing is downloaded, no script or macro runs and no model is asked; files that only point at pictures on the
web are read without them.
"""
import base64
import binascii
import json
import re
import stat
import zlib
from io import BytesIO
from pathlib import PurePosixPath, PureWindowsPath
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from dungeon.imports import lorebooks
from dungeon.imports.cards import MAX_SOURCE_BYTES, SIGNATURE, card_data, embedded_card, problem

MAX_CONTAINER_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 256
FIELDS = ('name', 'description', 'personality', 'scenario', 'first_mes', 'mes_example')
# Other apps' own character JSON, by the fields only they write (json_formats.FORMATS), mapped to card fields
# (native_characters.FIELD_MAPS).
NATIVE = (
    ('Pygmalion character', lambda value: 'char_name' in value and 'char_persona' in value,
     {'name': ('char_name',), 'description': ('char_persona',), 'scenario': ('world_scenario',),
      'first_mes': ('char_greeting',), 'mes_example': ('example_dialogue',)}),
    ('Backyard / Faraday character', lambda value: 'aiName' in value and 'aiPersona' in value,
     {'name': ('aiDisplayName', 'aiName'), 'description': ('aiPersona',), 'scenario': ('scenario',),
      'first_mes': ('firstMessage', 'greeting', 'first_mes'), 'mes_example': ('customDialogue', 'examples',
                                                                             'mes_example'),
      'personality': ('personality',)}),
)
IMAGES = ('.png', '.jpg', '.jpeg', '.webp')


def text(value, key) -> str:
    found = value.get(key)
    return found if isinstance(found, str) else ''


def decoded(encoded: str) -> bytes:
    try:
        source = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise problem('Choose the file again; it did not arrive whole.') from error
    if len(source) > MAX_SOURCE_BYTES:
        raise problem('Character and lorebook files are limited to 10 MiB.')
    return source


def read(filename: str, encoded: str) -> dict:
    """{format, character (card fields) or None, book or None, picture bytes or None} from one file."""
    source = decoded(encoded)
    suffix = PureWindowsPath(filename).suffix.lower()
    stem = PureWindowsPath(filename).stem or 'Lorebook'
    if suffix in {'.charx', '.byaf'} or source.startswith(b'PK\x03\x04'):
        return container(source)
    if suffix == '.png' or source.startswith(SIGNATURE):
        found = from_json(embedded_card(source), stem)
        if found['character'] is None:
            raise problem('The card in this picture holds no character.')
        return {**found, 'format': f"{found['format']} (PNG)", 'picture': source}
    if suffix not in {'.json', '.lorebook'}:
        raise problem('Choose a character card (PNG, JSON, CHARX or BYAF) or a lorebook (JSON or .lorebook).')
    return from_json(source, stem)


def parsed(source: bytes):
    try:
        return json.loads(source.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise problem('This file is not readable JSON.') from error


def from_json(source: bytes, stem: str) -> dict:
    value = parsed(source)
    if not isinstance(value, dict):
        raise problem('This file is not a character card or a lorebook.')
    if str(value.get('type', '')).startswith('marinara_'):
        return marinara(value, stem)
    if value.get('spec') == 'lorebook_v3' and isinstance(value.get('data'), dict):
        return {'format': 'Character Card V3 lorebook', 'character': None, 'picture': None,
                'book': lorebooks.book(value['data'], 'portable', 'Character Card V3 lorebook', stem[:120])}
    if 'spec' in value or all(key in value for key in FIELDS):
        return card(value)
    for label, matches, fields in NATIVE:
        if matches(value):
            return {'format': label, 'character': {key: next((text(value, name) for name in names if name in value), '')
                                                   for key, names in fields.items()}, 'book': None, 'picture': None}
    kind = lorebooks.kind_of(value)
    if kind is None and value.get('format') == 'marinara-hierarchical-map':
        raise problem('This is a Marinara world map. Open it in Settings, Life & cities, with "Open a city file", and it '
                      'becomes a city with its own lore.')
    if kind is None:
        raise problem('This file is not a character card or a lorebook the Dungeon can read.')
    return {'format': kind[1], 'character': None, 'book': lorebooks.book(value, kind[0], kind[1], stem[:120]),
            'picture': None}


def card(value: dict) -> dict:
    data = card_data(value)
    version = {'chara_card_v2': 'V2', 'chara_card_v3': 'V3'}.get(value.get('spec'), 'V1')
    character = {key: text(data, key) for key in (*FIELDS, 'creator_notes')}
    if not character['name'].strip() and not character['description'].strip():
        raise problem('This character card has no name or description.')
    return {'format': f'Character Card {version}', 'character': character, 'book': card_book(data, character),
            'picture': None}


def marinara(value: dict, stem: str) -> dict:
    """Marinara Engine's native export (checked against its source at c565014, packages/shared/src/types/export.ts):
    {type, version: 1, data}. A character's data is a V2 card plus `avatar` (a data URL), sprites and a gallery; its
    backstory and appearance sit in the card's extensions, which only Marinara's "compatible" export folds into the
    description. A lorebook's data is {lorebook, entries}. Sprites, gallery pictures and presets are not used."""
    kind, data = value.get('type'), value.get('data')
    if value.get('version') != 1 or not isinstance(data, dict):
        raise problem('Only version 1 Marinara Engine exports can be read.')
    if kind == 'marinara_lorebook':
        about = data.get('lorebook') if isinstance(data.get('lorebook'), dict) else {}
        found = data.get('entries')
        entries = [entry for entry in found if isinstance(entry, dict)] if isinstance(found, list) else []
        if not entries:
            raise problem('This Marinara Engine lorebook has no entries to bring over.')
        name = re.sub(r'\.marinara$', '', stem, flags=re.IGNORECASE)
        made = lorebooks.book({**about, 'entries': entries}, 'portable', 'Marinara Engine lorebook', name[:120])
        return {'format': 'Marinara Engine lorebook', 'character': None, 'picture': None, 'book': made}
    if kind == 'marinara_persona':
        raise problem('Only Marinara Engine characters and lorebooks can be brought over. Your persona stays yours to '
                      'set in Settings.')
    if kind != 'marinara_character':
        raise problem('Only Marinara Engine characters and lorebooks can be brought over.')
    made = card(data)
    extensions = card_data(data).get('extensions')
    extensions = extensions if isinstance(extensions, dict) else {}
    character = {**made['character'], 'backstory': text(extensions, 'backstory'),
                 'appearance': text(extensions, 'appearance')}
    if extensions.get('imageAppearanceEnabled') in (True, 'true'):
        character['in_photos'] = text(extensions, 'imageAppearance')
    return {**made, 'format': 'Marinara Engine character', 'character': character,
            'picture': data_url(data.get('avatar')), 'portrait': True}


def data_url(value) -> bytes | None:
    """The picture in a `data:image/...;base64,` URL, or None when there is none or it is unreadable."""
    if not isinstance(value, str) or not value.startswith('data:image/') or ';base64,' not in value:
        return None
    try:
        return base64.b64decode(value.split(',', 1)[1], validate=True)
    except (ValueError, binascii.Error):
        return None


def card_book(data: dict, character: dict) -> dict | None:
    found = data.get('character_book')
    if not isinstance(found, dict) or not isinstance(found.get('entries'), list):
        return None
    made = lorebooks.book(found, 'portable', 'Character lorebook', f"{character['name'].strip() or 'Their'} lore")
    return made if made['entries'] else None


# Containers -------------------------------------------------------------------------------------------

def safe_member(name) -> str:
    if not isinstance(name, str) or not name or len(name) > 240:
        raise problem('This file has a damaged or unusual path inside it.')
    parts = name.rstrip('/').split('/')
    if any(part in {'', '.', '..'} or part.endswith((' ', '.')) for part in parts) or \
            any(ord(char) < 32 or char in '<>:"\\|?*' for char in name):
        raise problem('This file has a path inside it that points outside itself, so it was not opened.')
    return name.rstrip('/')


def checked(archive) -> list:
    entries, seen, total = archive.infolist(), set(), 0
    if len(entries) > MAX_MEMBERS:
        raise problem(f'Character files are limited to {MAX_MEMBERS} files inside.')
    for entry in entries:
        name = safe_member(entry.orig_filename).casefold()
        mode = stat.S_IFMT(entry.external_attr >> 16)
        total += entry.file_size
        if name in seen or entry.flag_bits & 1 or mode not in {0, stat.S_IFREG, stat.S_IFDIR} or \
                entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
            raise problem('This file is encrypted, holds links or uses an unusual ZIP layout, so it was not opened.')
        if entry.file_size > MAX_SOURCE_BYTES or total > MAX_CONTAINER_BYTES:
            raise problem('The files inside are limited to 10 MiB each and 32 MiB in all.')
        seen.add(name)
    return [entry for entry in entries if not entry.is_dir()]


def members(source: bytes) -> dict[str, bytes]:
    try:
        with ZipFile(BytesIO(source)) as archive:
            found = {}
            for entry in checked(archive):
                with archive.open(entry) as stream:
                    raw = stream.read(MAX_SOURCE_BYTES + 1)
                if len(raw) != entry.file_size:
                    raise problem('A file inside does not match its stated size.')
                found[entry.filename] = raw
            return found
    except (BadZipFile, RuntimeError, OSError, NotImplementedError, zlib.error) as error:
        raise problem('This character file is damaged or uses an unsupported ZIP encoding.') from error


def member_json(found: dict, path: str) -> dict:
    if safe_member(path) not in found:
        raise problem(f'This file is missing {path}.')
    value = parsed(found[path])
    if not isinstance(value, dict):
        raise problem(f'{path} is not a JSON object.')
    return value


def container(source: bytes) -> dict:
    found = members(source)
    if ('card.json' in found) == ('manifest.json' in found):
        raise problem('Choose a CHARX file (with card.json) or a Backyard Archive (with manifest.json).')
    return charx(found) if 'card.json' in found else byaf(found)


def picture(found: dict, paths: list[str]) -> bytes | None:
    return next((found[path] for path in paths if path in found and PurePosixPath(path).suffix.lower() in IMAGES),
                None)


def charx(found: dict) -> dict:
    value = member_json(found, 'card.json')
    if value.get('spec') != 'chara_card_v3':
        raise problem('A CHARX file must hold a V3 character card.')
    made = card(value)
    assets = value['data'].get('assets')
    assets = [item for item in assets if isinstance(item, dict) and isinstance(item.get('uri'), str)] \
        if isinstance(assets, list) else []
    icons = sorted(assets, key=lambda item: item.get('type') != 'icon')
    paths = [item['uri'].removeprefix('embeded://') for item in icons if item['uri'].startswith('embeded://')]
    return {**made, 'format': 'CHARX (Character Card V3)', 'picture': picture(found, paths)}


def byaf(found: dict) -> dict:
    manifest = member_json(found, 'manifest.json')
    listed = manifest.get('characters')
    if manifest.get('schemaVersion') != 1 or not isinstance(listed, list) or not listed or \
            not isinstance(listed[0], str):
        raise problem('Only Backyard Archive version 1 files can be read.')
    person = member_json(found, listed[0])
    name = text(person, 'displayName').strip() or text(person, 'name')
    scenarios = [member_json(found, path) for path in manifest.get('scenarios') or [] if isinstance(path, str)][:32]
    first = scenarios[0] if scenarios else {}
    examples = [item for item in first.get('exampleMessages') or [] if isinstance(item, dict)]
    greetings = [item for item in first.get('firstMessages') or [] if isinstance(item, dict)]
    character = {'name': name, 'description': text(person, 'persona'), 'personality': '',
                 'scenario': text(first, 'narrative'), 'first_mes': text(greetings[0], 'text') if greetings else '',
                 'mes_example': '\n\n'.join(text(item, 'text') for item in examples)}
    lore = [{'keys': [item['key']], 'content': item['value']} for item in person.get('loreItems') or []
            if isinstance(item, dict) and isinstance(item.get('key'), str) and isinstance(item.get('value'), str)]
    book = lorebooks.book({'entries': lore}, 'portable', 'Backyard lore', f'{name.strip() or "Their"} lore') \
        if lore else None
    folder = PurePosixPath(listed[0]).parent
    images = [str(folder / item['path']) for item in person.get('images') or []
              if isinstance(item, dict) and isinstance(item.get('path'), str)]
    return {'format': 'Backyard Archive (BYAF)', 'character': character, 'book': book,
            'picture': picture(found, images)}
