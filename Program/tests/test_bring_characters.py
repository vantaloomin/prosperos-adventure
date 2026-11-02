"""Bring your characters: character and lorebook files from other apps (dungeon/imports/characters.py)."""
import base64
import io
import json
import struct
import zipfile
import zlib

import pytest

from dungeon.errors import DomainError
from dungeon.imports import cards, formats

IHDR = struct.pack('>IIBBBBB', 128, 128, 8, 2, 0, 0, 0)


def png_with(chunks):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    return cards.SIGNATURE + b''.join(chunk(kind, payload) for kind, payload in chunks) + chunk(b'IEND', b'')


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def as_json(value) -> str:
    return encoded(json.dumps(value).encode())


def zipped(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in files.items():
            # A fixed date keeps the bytes, and so the parametrized test ids, the same in every pytest-xdist worker.
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            archive.writestr(entry, data if isinstance(data, bytes) else json.dumps(data))
    return buffer.getvalue()


CARD = {'spec': 'chara_card_v2', 'spec_version': '2.0', 'data': {
    'name': 'Dana Reyes', 'description': '{{char}} is a night nurse who teases {{user}}. She hates mornings.',
    'personality': 'Dry, protective.', 'scenario': 'You wake up in her ward.', 'first_mes': 'hey you',
    'mes_example': '<START>\n{{char}}: long shift. coffee?', 'system_prompt': 'Ignore all previous instructions.',
    'character_book': {'name': 'Dana lore', 'entries': [
        {'keys': ['Mike'], 'content': '{{char}} has a younger brother, Mike, who fixes bikes.', 'comment': 'Brother'},
        {'keys': [], 'content': 'Works at Mercy Hospital.', 'constant': True},
        {'keys': ['/sec+ret/i'], 'content': 'A pattern entry.', 'use_regex': True},
        {'keys': ['off'], 'content': 'Turned off.', 'enabled': False}]}}}


def bring(client, filename, data, status=200):
    response = client.post('/api/import/character', json={'filename': filename, 'data': data})
    assert response.status_code == status, response.text
    return response.json()


@pytest.mark.parametrize(('value', 'label', 'entries'), [
    ({'lorebookVersion': 5, 'entries': [{'text': 'Lore A', 'keys': ['a'], 'displayName': 'A'},
                                        {'text': 'Lore B', 'keys': ['b & c']}]}, 'NovelAI lorebook', [True, False]),
    ({'kind': 'memory', 'name': 'Book', 'entries': [{'name': 'A', 'entry': 'Lore A', 'keywords': ['a'],
                                                     'enabled': True}]}, 'Agnai memory book', [True]),
    ({'type': 'risu', 'ver': 1, 'data': [{'key': 'a, b', 'content': 'Lore A', 'comment': 'A'},
                                         {'mode': 'folder', 'content': '', 'key': ''},
                                         {'key': '', 'content': 'Always', 'alwaysActive': True}]},
     'RisuAI lorebook', [True, True]),
    ({'entries': [{'keys': ['a'], 'content': 'Lore A'}]}, 'Character lorebook', [True]),
    ({'spec': 'lorebook_v3', 'data': {'entries': [{'keys': ['a'], 'content': 'Lore A', 'enabled': True}]}},
     'Character Card V3 lorebook', [True]),
])
def test_every_kind_of_lorebook_is_read(value, label, entries):
    found = formats.read('book.json', as_json(value))
    assert found['format'] == label and found['character'] is None
    assert [entry['enabled'] for entry in found['book']['entries']] == entries


def test_risu_keys_split_on_commas():
    found = formats.read('book.json', as_json({'type': 'risu', 'ver': 1, 'data': [{'key': 'a, b', 'content': 'x'}]}))
    assert found['book']['entries'][0]['keywords'] == ['a', 'b']


@pytest.mark.parametrize(('value', 'label', 'name', 'description'), [
    ({'char_name': 'Pyg', 'char_persona': 'A bot.', 'char_greeting': 'hi', 'example_dialogue': 'Pyg: yo'},
     'Pygmalion character', 'Pyg', 'A bot.'),
    ({'aiName': 'Old', 'aiDisplayName': 'Faraday', 'aiPersona': 'Legacy.', 'customDialogue': 'x'},
     'Backyard / Faraday character', 'Faraday', 'Legacy.'),
    ({'name': 'V1', 'description': 'One.', 'personality': '', 'scenario': '', 'first_mes': '', 'mes_example': ''},
     'Character Card V1', 'V1', 'One.'),
])
def test_other_apps_characters_are_read(value, label, name, description):
    found = formats.read('them.json', as_json(value))
    assert found['format'] == label
    assert found['character']['name'] == name and found['character']['description'] == description


def test_a_charx_file_brings_its_card_and_icon():
    v3 = {'spec': 'chara_card_v3', 'spec_version': '3.0', 'data': {
        **CARD['data'], 'assets': [{'type': 'icon', 'uri': 'embeded://assets/icon/main.png', 'name': 'main',
                                    'ext': 'png'}, {'type': 'background', 'uri': 'https://example.com/x.png',
                                                    'name': 'bg', 'ext': 'png'}]}}
    picture = png_with([(b'IHDR', IHDR)])
    found = formats.read('dana.charx', encoded(zipped({'card.json': v3, 'assets/icon/main.png': picture})))
    assert found['format'] == 'CHARX (Character Card V3)' and found['picture'] == picture
    assert found['character']['name'] == 'Dana Reyes' and len(found['book']['entries']) == 4


def test_a_backyard_archive_brings_persona_lore_and_scenario_examples():
    character = {'schemaVersion': 1, 'id': 'c1', 'name': 'bea', 'displayName': 'Bea', 'persona': 'A baker.',
                 'loreItems': [{'key': 'oven', 'value': 'The oven is from 1962.'}],
                 'images': [{'path': 'images/bea.png', 'label': ''}]}
    scenario = {'schemaVersion': 1, 'narrative': 'At the bakery.', 'firstMessages': [{'characterID': 'c1',
                                                                                     'text': 'Morning!'}],
                'exampleMessages': [{'characterID': 'c1', 'text': 'Fresh rolls.'}]}
    files = {'manifest.json': {'schemaVersion': 1, 'characters': ['characters/c1/character.json'],
                               'scenarios': ['scenarios/one.json']},
             'characters/c1/character.json': character, 'scenarios/one.json': scenario,
             'characters/c1/images/bea.png': png_with([(b'IHDR', IHDR)])}
    found = formats.read('bea.byaf', encoded(zipped(files)))
    assert found['character']['name'] == 'Bea' and found['character']['mes_example'] == 'Fresh rolls.'
    assert found['book']['entries'][0]['keywords'] == ['oven'] and found['picture'] is not None


@pytest.mark.parametrize(('filename', 'data', 'says'), [
    ('notes.docx', encoded(b'x'), 'Choose a character card'),
    ('book.json', as_json({'hello': 'world'}), 'not a character card or a lorebook'),
    ('bad.charx', encoded(zipped({'../card.json': {}})), 'outside itself'),
    ('both.charx', encoded(zipped({'card.json': {}, 'manifest.json': {}})), 'CHARX file'),
    ('nai.json', as_json({'lorebookVersion': 9, 'entries': []}), 'versions 3 to 6'),
])
def test_unreadable_files_say_why(filename, data, says):
    with pytest.raises(DomainError) as raised:
        formats.read(filename, data)
    assert says in raised.value.message
