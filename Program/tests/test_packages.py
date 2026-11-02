"""World packages (dungeon/packages.py): one SQLite file per world, and the folder of Markdown and JSON it round-trips
with."""
import json
import shutil

import pytest
from conftest import tell
from test_combat import kingswood
from test_rulesets import reply
from test_travel import ok

from dungeon import director, inventory, package_lore, packages, story, world_data
from dungeon.errors import DomainError
from dungeon.world import catalog


@pytest.fixture
def folder(tmp_path):
    """A small world folder."""
    root = tmp_path / 'ashmoor'
    (root / 'canon').mkdir(parents=True)
    (root / 'assets' / 'maps').mkdir(parents=True)
    packages.dump(root / 'world.json', {'id': 'ashmoor', 'name': 'Ashmoor', 'currency': 'marks'})
    packages.dump(root / 'regions.json', {'schema_version': 1, 'regions': [{'id': 'fen', 'name': 'The Fen'}]})
    packages.dump(root / 'settlements.json', {'schema_version': 1, 'settlements': [
        {'id': 'reedby', 'name': 'Reedby', 'region': 'fen'}]})
    packages.dump(root / 'cast.json', {'schema_version': 1, 'fields': {'secret': 'hidden'}, 'cast': [
        {'id': 'old-tam', 'name': 'Old Tam', 'settlement': 'reedby', 'secret': 'He drowned the miller.'},
        {'id': 'jess', 'name': 'Jess', 'settlement': 'reedby'}]})
    (root / 'canon' / 'overview.md').write_text('# Ashmoor\n\nA wet country.\n', encoding='utf-8')
    (root / 'assets' / 'maps' / 'fen.png').write_bytes(b'\x89PNG fake')
    return root


def test_a_world_folder_round_trips_through_its_package(folder, tmp_path):
    contents = packages.folder_contents(folder)
    path = packages.write(contents, tmp_path / 'ashmoor.sqlite')
    summary = packages.summary(path)
    assert summary['sections']['cast'] == {'entries': 2, 'hidden': 1} and summary['assets'] == 1
    out = packages.export(path, tmp_path / 'out')
    assert json.loads((out / 'cast.json').read_text()) == json.loads((folder / 'cast.json').read_text())
    assert (out / 'canon' / 'overview.md').read_text() == '# Ashmoor\n\nA wet country.\n'
    assert packages.fingerprint(packages.folder_contents(out)) == packages.fingerprint(contents)


@pytest.mark.parametrize(('change', 'detail'), [
    (lambda data: data['cast'].append({'id': 'jess', 'name': 'Jess again'}), 'two entries with the id jess'),
    (lambda data: data['cast'].append({'id': 'Bad Id'}), 'lowercase kebab-case id'),
    (lambda data: data['cast'].append({'id': 'wren', 'settlement': 'nowhere'}), 'settlement nowhere is not in settlements'),
])
def test_the_validator_refuses_a_folder_with_problems(folder, change, detail):
    data = json.loads((folder / 'cast.json').read_text())
    change(data)
    packages.dump(folder / 'cast.json', data)
    with pytest.raises(DomainError, match=detail):
        packages.folder_contents(folder)


def test_a_broken_json_file_is_named(folder):
    (folder / 'regions.json').write_text('{oops', encoding='utf-8')
    with pytest.raises(DomainError, match='regions.json is not valid JSON'):
        packages.folder_contents(folder)


def test_vallarith_builds_with_its_engine_data_and_rebuilds_when_its_sources_change(tmp_path, monkeypatch):
    path = packages.installed(tmp_path, 'vallarith')
    summary = packages.summary(path)
    assert summary['name'] == 'Vallarith' and summary['sections']['hidden-truths']['hidden'] > 0
    contents = packages.read(path)
    assert ('travel', 'vallarith') in contents['engine'] and ('adventures', 'kingswood') in contents['engine']
    built = path.stat().st_mtime_ns
    assert packages.installed(tmp_path, 'vallarith').stat().st_mtime_ns == built
    # A changed source makes it build again.
    shipped = tmp_path / 'shipped'
    shutil.copytree(packages.BUILTIN, shipped)
    monkeypatch.setattr(packages, 'BUILTIN', shipped)
    (shipped / 'vallarith' / 'canon' / 'overview.md').write_text('Changed.', encoding='utf-8')
    assert packages.read(packages.installed(tmp_path, 'vallarith'))['documents']['canon/overview.md'] == 'Changed.'


def test_packages_over_the_api(client, folder, app):
    listed = ok(client.get('/api/packages'))['packages']
    shipped = packages.builtin_ids()
    assert 'vallarith' in shipped and [item['id'] for item in listed] == shipped
    assert all(item['builtin'] for item in listed)
    imported = ok(client.post('/api/packages/import', json={'folder': str(folder)}))
    assert imported['id'] == 'ashmoor'
    assert [item['id'] for item in ok(client.get('/api/packages'))['packages']] == [*shipped, 'ashmoor']
    exported = ok(client.post('/api/packages/ashmoor/export'))['folder']
    assert json.loads((packages.Path(exported) / 'world.json').read_text())['name'] == 'Ashmoor'
    downloaded = client.get('/api/packages/ashmoor/file')
    assert downloaded.status_code == 200 and downloaded.content.startswith(b'SQLite format 3')
    # A folder may not take a built-in world's id.
    packages.dump(folder / 'world.json', {'id': 'vallarith', 'name': 'Not Vallarith'})
    refused = client.post('/api/packages/import', json={'folder': str(folder)})
    assert refused.status_code == 409
    assert client.get('/api/packages/nowhere/file').status_code == 404


def test_a_campaign_in_vallarith_reads_the_packages_lore_by_keyword(client, connected, provider, app):
    kingswood(client, 'felled-oak')
    with app.state.database.connect() as connection:
        books = connection.execute("SELECT id, name, source_file FROM lore_books WHERE source_format='World package'"
                                   ).fetchall()
        assert [row['name'] for row in books] == ['Vallarith (world package)']
        titles = {row['title'] for row in connection.execute('SELECT title FROM lore_entries WHERE book_id=?',
                                                              (books[0]['id'],))}
    lore = packages.read(packages.installed(app.state.database.root, 'vallarith'))['sections']['lore']['entries']
    # Post-Reform only: an entry for another era alone stays out.
    assert titles == {entry['title'] for entry in lore if not entry.get('eras') or 'post-reform' in entry['eras']}
    provider.replies = [reply('Smoke over the mountains.')]
    tell(client, 'I ask about Dun Aldun.', 'story-0001')
    assert "The Dwarven Empire's capital" in provider.requests[-1]['system']
    # A second start keeps the one book; changed lore replaces it.
    with app.state.database.connect(write=True) as connection:
        assert package_lore.bring(connection, app.state.database.root, 'vallarith', 'now') is None
        assert package_lore.bring(connection, app.state.database.root, 'vallarith', 'now', 'brotherhood')['entries']
        assert connection.execute("SELECT COUNT(*) FROM lore_books WHERE source_format='World package'"
                                  ).fetchone()[0] == 1


@pytest.fixture
def in_use(tmp_path):
    world_data.use(tmp_path)
    yield tmp_path / packages.FOLDER / 'vallarith.sqlite'
    world_data.use(None)


def edit_engine(path, kind, key, change):
    with packages.connect(path) as connection:
        row = connection.execute('SELECT data FROM engine WHERE kind=? AND key=?', (kind, key)).fetchone()
        data = json.loads(row['data'])
        change(data)
        connection.execute('UPDATE engine SET data=? WHERE kind=? AND key=?', (json.dumps(data), kind, key))
    connection.close()


def test_the_game_reads_its_world_data_from_the_package_in_use(in_use):
    shipped = json.loads((packages.DATA / 'items' / 'kingswood.json').read_text(encoding='utf-8'))
    assert inventory.catalog('kingswood') == shipped
    edit_engine(in_use, 'items', 'kingswood', lambda data: data['items'].append({'id': 'reed-flute', 'name': 'Reed flute'}))
    assert inventory.item('kingswood', 'reed-flute')['name'] == 'Reed flute'


def test_a_cached_loader_reads_again_when_the_package_changes(in_use):
    first = director.data('vallarith')['arcs'][0]['id']
    edit_engine(in_use, 'arcs', 'vallarith', lambda data: data['arcs'][0].update(id='renamed'))
    assert director.data('vallarith')['arcs'][0]['id'] == 'renamed' != first


def test_with_no_package_in_use_the_shipped_files_are_read():
    world_data.use(None)
    assert world_data.read('items', 'kingswood') == json.loads(
        (packages.DATA / 'items' / 'kingswood.json').read_text(encoding='utf-8'))
    assert world_data.read('items', 'nowhere') is None and 'vallarith' in world_data.keys('travel')


def test_place_lore_comes_up_on_more_than_its_exact_name(tmp_path):
    # Playtest m5: "Dwarven steel" did not bring up Dun Aldun.
    from dungeon import lore
    contents = packages.read(packages.installed(tmp_path, 'vallarith'))
    found = {entry['title']: entry['keywords'] for entry in package_lore.entries(contents, 'post-reform')}
    assert any(lore.mentioned(word, 'a blade of dwarven steel') for word in found['Dun Aldun'])
    assert any(lore.mentioned(word, 'out past the badlands') for word in found['The Badlands'])


def test_an_imported_worlds_own_town_loads_and_a_campaign_starts_there(client, folder, app):
    """A world made in Worldsmith carries its towns' city files in its package; Dungeon only read shipped ones, so
    going to such a world failed with "No world data for city"."""
    town = json.loads((packages.DATA / 'cities' / 'kingswood.json').read_text(encoding='utf-8')) | {
        'id': 'reedby', 'name': 'Reedby'}
    packages.dump(folder / 'engine' / 'cities' / 'reedby.json', town)
    packages.dump(folder / 'engine' / 'travel' / 'ashmoor.json', {'world': 'ashmoor', 'travel': 'roads', 'nodes': [
        {'id': 'reedby', 'name': 'Reedby', 'region': 'fen', 'city': 'reedby', 'place': 'felled-oak', 'safe': True}],
        'routes': [], 'regions': {'fen': {'name': 'The Fen', 'danger': 'low'}}, 'encounters': {}, 'camp': {},
        'food': []})
    assert 'reedby' not in catalog.cities()
    ok(client.post('/api/packages/import', json={'folder': str(folder)}))
    assert catalog.city('reedby')['name'] == 'Reedby' and catalog.cities()['reedby']['origin'] == 'package'
    entered = ok(client.post('/api/story/worlds/ashmoor/enter'))['world']
    assert entered['city_id'] == 'reedby'
    with app.state.database.connect() as connection:
        assert story.scene_row(connection)['city_id'] == 'reedby'
