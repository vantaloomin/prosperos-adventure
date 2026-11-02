"""The world editor (dungeon/package_edit.py): a package's entries searched, changed with validation, and undone."""
import test_packages
from test_travel import ok

from dungeon import packages

BASE = '/api/packages/vallarith'


def test_entries_are_listed_by_section_searched_and_filtered_by_hidden_truths(client):
    found = ok(client.get(f'{BASE}/entries', params={'section': 'cast', 'q': 'Ilvar'}))
    assert {item['id'] for item in found['entries']} == {'melton-ilvar', 'edith-ilvar'}
    cast = next(item for item in found['sections'] if item['id'] == 'cast')
    assert cast['entries'] > 20 and cast['hidden'] > 0
    hidden = ok(client.get(f'{BASE}/entries', params={'section': 'cast', 'hidden': True}))['entries']
    assert hidden and all(item['hidden'] for item in hidden)
    sara = ok(client.get(f'{BASE}/entries/cast/mistress-sara'))
    assert sara['hidden'] and sara['hidden_fields'] == ['secret']
    assert {'section': 'factions', 'id': 'brotherhood-of-man', 'field': 'faction'} in sara['names']
    trein = ok(client.get(f'{BASE}/entries/settlements/trein'))
    assert {'section': 'cast', 'id': 'mistress-sara', 'field': 'settlement'} in trein['named_by']


def test_a_change_validates_marks_the_world_edited_and_can_be_undone(client, app):
    sara = ok(client.get(f'{BASE}/entries/cast/mistress-sara'))['entry']
    bad = client.put(f'{BASE}/entries/cast/mistress-sara', json={'entry': sara | {'settlement': 'atlantis'}})
    assert bad.status_code == 422 and 'settlement atlantis is not in settlements' in bad.text
    renamed = client.put(f'{BASE}/entries/settlements/trein', json={'entry': {'id': 'trein-city', 'name': 'Trein'}})
    assert renamed.status_code == 422 and 'still named by' in renamed.text
    saved = ok(client.put(f'{BASE}/entries/cast/mistress-sara', json={'entry': sara | {'secret': ''}}))
    assert not saved['hidden']
    added = ok(client.post(f'{BASE}/entries/cast', json={'entry': {'id': 'old-tam', 'name': 'Old Tam'}}))
    assert added['entry']['name'] == 'Old Tam'
    assert client.post(f'{BASE}/entries/cast', json={'entry': {'id': 'old-tam'}}).status_code == 422
    # A bad id names the entry, not its place in the list (playtest m5).
    bad_id = client.post(f'{BASE}/entries/cast', json={'entry': {'id': 'Old Tam Two', 'name': 'Old Tam'}})
    assert bad_id.status_code == 422 and 'cast "Old Tam Two" needs a lowercase kebab-case id' in bad_id.json()['detail']
    assert [item['change'] for item in ok(client.get(f'{BASE}/history'))['history'][:2]] == ['added', 'changed']
    root = app.state.database.root
    # An edited built-in world is not rebuilt from the shipped files.
    assert packages.summary(packages.installed(root, 'vallarith'))['edited']
    ok(client.post(f'{BASE}/undo'))
    assert client.get(f'{BASE}/entries/cast/old-tam').status_code == 404
    ok(client.post(f'{BASE}/undo'))
    assert ok(client.get(f'{BASE}/entries/cast/mistress-sara'))['entry']['secret'].startswith('She is the Eternal')
    assert client.post(f'{BASE}/undo').status_code == 409
    # Deleting what others name is refused; a reset brings the shipped world back.
    assert client.delete(f'{BASE}/entries/settlements/trein').status_code == 409
    ok(client.delete(f'{BASE}/entries/cast/mistress-sara'))
    assert not ok(client.post(f'{BASE}/reset'))['edited']
    assert ok(client.get(f'{BASE}/entries/cast/mistress-sara'))['entry']['name'] == 'Mistress Sara'


def test_the_first_entry_of_a_new_section_makes_the_section(client, tmp_path, app):
    folder = test_packages.folder.__wrapped__(tmp_path)
    ok(client.post('/api/packages/import', json={'folder': str(folder)}))
    ok(client.post('/api/packages/ashmoor/entries/lore', json={'entry': {'id': 'the-fen', 'title': 'The Fen',
                                                                         'keywords': ['fen'], 'text': 'Grey water.'}}))
    contents = packages.read(app.state.database.root / packages.FOLDER / 'ashmoor.sqlite')
    assert contents['sections']['lore']['entries'][0]['id'] == 'the-fen'
