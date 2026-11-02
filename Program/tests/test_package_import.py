"""The world importer (dungeon/package_import.py): a world's files made into a package, one reviewed section at a
time."""
import json

import pytest
from test_rulesets import reply
from test_travel import ok

from dungeon import package_import, packages
from dungeon.errors import DomainError
from dungeon.imports import lorebooks

LOREBOOK = {'entries': {'0': {'key': ['Reedby'], 'content': 'A village on stilts in the Fen.', 'comment': 'Reedby'},
                        '1': {'key': ['the Fen'], 'content': 'Grey water and reeds to the horizon.', 'comment': 'The Fen'}}}
FILES = [{'name': 'Overview.md', 'text': '# Ashmoor\n\nA wet country. Old Tam runs the ferry at Reedby.'},
         {'name': 'ashmoor-lore.json', 'text': json.dumps(LOREBOOK)}]


def start(client):
    return ok(client.post('/api/packages/drafts', json={'name': 'Ashmoor', 'files': FILES}))


def test_documents_are_kept_and_a_lorebook_becomes_the_lore_section(client):
    draft = start(client)
    assert draft['id'] == 'ashmoor' and draft['documents'] == ['canon/overview.md']
    lore = next(section for section in draft['sections'] if section['id'] == 'lore')
    assert lore['status'] == 'drafted' and lore['from'] == 'lorebook'
    assert [entry['id'] for entry in lore['entries']] == ['reedby', 'the-fen']
    # A drafted section has not been read yet: it stands in the way of finishing.
    assert draft['waiting'] == ['lore'] and not draft['ready']
    assert ok(client.get('/api/packages/drafts'))['drafts'][0]['name'] == 'Ashmoor'


def test_a_section_is_drafted_by_the_model_then_reviewed_and_the_package_written(client, connected, provider, app):
    start(client)
    cast = {'entries': [{'name': 'Old Tam', 'role': 'Ferryman', 'secret': 'He drowned the miller.'},
                        {'name': 'Old Tam', 'role': 'His twin'}, 'not an entry', {'role': 'no name'}]}
    provider.replies = [reply(json.dumps(cast))]
    draft = ok(client.post('/api/packages/drafts/ashmoor/sections/cast/draft'))
    assert 'Section: cast.' in provider.requests[-1]['system']
    assert 'Old Tam runs the ferry' in provider.requests[-1]['messages'][-1]['content']
    section = next(item for item in draft['sections'] if item['id'] == 'cast')
    assert [entry['id'] for entry in section['entries']] == ['old-tam', 'old-tam-2'] and section['hidden'] == 1
    # The author cuts the twin and approves; the lore is approved as it came.
    ok(client.put('/api/packages/drafts/ashmoor/sections/cast', json={'status': 'approved',
                                                                    'entries': section['entries'][:1]}))
    draft = ok(client.put('/api/packages/drafts/ashmoor/sections/lore', json={'status': 'approved'}))
    assert draft['ready']
    summary = ok(client.post('/api/packages/drafts/ashmoor/finish', json={}))
    assert summary['sections']['cast'] == {'entries': 1, 'hidden': 1} and summary['sections']['lore']['entries'] == 2
    contents = packages.read(app.state.database.root / packages.FOLDER / 'ashmoor.sqlite')
    assert contents['documents']['canon/overview.md'].startswith('# Ashmoor') and 'regions' not in contents['sections']
    assert client.get('/api/packages/drafts/ashmoor').status_code == 404
    # A second import of the same world does not overwrite it by accident.
    start(client)
    ok(client.put('/api/packages/drafts/ashmoor/sections/lore', json={'status': 'approved'}))
    assert client.post('/api/packages/drafts/ashmoor/finish', json={}).status_code == 409
    assert ok(client.post('/api/packages/drafts/ashmoor/finish', json={'replace': True}))['sections'].get('cast') is None


def test_the_review_refuses_bad_ids_and_finishing_refuses_broken_references(client):
    start(client)
    bad = client.put('/api/packages/drafts/ashmoor/sections/cast', json={'status': 'approved',
                                                                       'entries': [{'id': 'Old Tam'}]})
    assert bad.status_code == 422 and 'kebab-case' in bad.text
    ok(client.put('/api/packages/drafts/ashmoor/sections/cast', json={
        'status': 'approved', 'entries': [{'id': 'old-tam', 'settlement': 'reedby'}]}))
    ok(client.put('/api/packages/drafts/ashmoor/sections/settlements', json={
        'status': 'approved', 'entries': [{'id': 'reedby', 'region': 'the-fen'}]}))
    draft = ok(client.put('/api/packages/drafts/ashmoor/sections/lore', json={'status': 'empty'}))
    assert draft['problems'] == ['settlements reedby: region the-fen is not in regions'] and not draft['ready']
    assert client.post('/api/packages/drafts/ashmoor/finish', json={}).status_code == 422


def test_drafting_needs_a_model_and_a_built_in_world_cannot_be_imported_over(client):
    start(client)
    assert client.post('/api/packages/drafts/ashmoor/sections/cast/draft').status_code == 409
    assert client.post('/api/packages/drafts', json={'name': 'Vallarith', 'files': FILES}).status_code == 409
    ok(client.delete('/api/packages/drafts/ashmoor'))
    assert ok(client.get('/api/packages/drafts'))['drafts'] == []


def test_a_model_answer_with_no_entries_is_an_error():
    with pytest.raises(DomainError, match='did not answer with entries'):
        package_import.entries_from('Sorry, I cannot.')


def test_a_lorebook_entry_with_no_name_is_titled_from_its_keywords_or_its_text():
    assert lorebooks.title({}, 3, ['kingswood', 'the reeve', 'mill'], '') == 'Kingswood, the reeve'
    assert lorebooks.title({}, 3, [], 'The fens flood each spring and the road goes under.') == 'The fens flood each spring and…'
    assert lorebooks.title({'comment': ' The Fen '}, 3, ['fen'], 'x') == 'The Fen'
    assert lorebooks.title({}, 3, [], '') == 'Entry 3'
