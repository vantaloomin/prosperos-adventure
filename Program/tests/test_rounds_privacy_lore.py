"""Lore visibility (spec "Who sees what"; adventure/lore.py "Who may read it", adventure/package_lore.py "Package
facts"): every lore entry and package fact carries a tag, untagged lore is public, and a package's hidden truths and
cast secrets are GM only or known to their owner, never public."""
from test_lore_timers import ok, said, start

from adventure import lore, package_import, package_lore, packages, world_data

SENTINEL = 'SENTINEL-GM-ONLY-the-bell-was-cast-from-a-drowned-man'


def entry(client) -> dict:
    return ok(client.get('/api/lore'))['books'][0]['entries'][0]


def test_untagged_lore_is_public_and_the_narrator_reads_it(client, provider):
    found = start(client, [{'key': ['bell'], 'content': 'The bell rings for the drowned.'}])
    assert (found[0]['visibility'], found[0]['known_to']) == ('public', [])
    assert 'rings for the drowned' in said(client, provider, 'I hear the bell.', 1)


def test_gm_only_and_known_lore_stay_out_of_the_narrator(client, provider):
    start(client, [{'key': ['bell'], 'content': SENTINEL}])
    entry_id = entry(client)['id']
    shown = ok(client.put(f'/api/lore/entries/{entry_id}/visibility', json={'visibility': 'gm'}))
    assert shown['books'][0]['entries'][0]['visibility'] == 'gm'
    assert SENTINEL not in said(client, provider, 'I hear the bell.', 1)
    ok(client.put(f'/api/lore/entries/{entry_id}/visibility',
                  json={'visibility': 'known', 'known_to': ['hesk-varro', ' hesk-varro ', '']}))
    assert entry(client)['known_to'] == ['hesk-varro']
    assert SENTINEL not in said(client, provider, 'I hear the bell again.', 2)
    ok(client.put(f'/api/lore/entries/{entry_id}/visibility', json={'visibility': 'public', 'known_to': ['x']}))
    assert (entry(client)['visibility'], entry(client)['known_to']) == ('public', [])
    assert SENTINEL in said(client, provider, 'The bell, once more.', 3)


def test_a_tag_the_editor_cannot_read_is_refused(client):
    start(client, [{'key': ['bell'], 'content': 'The bell.'}])
    entry_id = entry(client)['id']
    assert client.put(f'/api/lore/entries/{entry_id}/visibility', json={'visibility': 'secret'}).status_code == 422
    assert client.put(f'/api/lore/entries/{entry_id}/visibility', json={'visibility': 'known'}).status_code == 422
    assert entry(client)['visibility'] == 'public'


def test_a_reader_gets_public_lore_and_what_its_own_characters_know(client, app):
    start(client, [{'key': ['bell'], 'content': 'Public.'}, {'key': ['bell'], 'content': 'Hesk knows.'},
                   {'key': ['bell'], 'content': SENTINEL}])
    ids = [item['id'] for item in ok(client.get('/api/lore'))['books'][0]['entries']]
    ok(client.put(f'/api/lore/entries/{ids[1]}/visibility', json={'visibility': 'known', 'known_to': ['hesk']}))
    ok(client.put(f'/api/lore/entries/{ids[2]}/visibility', json={'visibility': 'gm'}))
    with app.state.database.connect() as connection:
        rows = connection.execute('SELECT * FROM lore_entries ORDER BY position').fetchall()
    rows = [dict(row) for row in rows]
    texts = {name: [row['text'] for row in rows if lore.readable(row, knowers)]
             for name, knowers in (('hesk', frozenset({'hesk'})), ('mira', frozenset({'mira'})),
                                   ('public', frozenset()), ('gm', None))}
    assert texts == {'hesk': ['Public.', 'Hesk knows.'], 'mira': ['Public.'], 'public': ['Public.'],
                     'gm': ['Public.', 'Hesk knows.', SENTINEL]}


def test_a_file_tag_is_read_and_one_that_cannot_be_is_gm_only():
    assert lore.tagged({}) == ('public', [])
    assert lore.tagged({'known_to': ['hesk']}) == ('known', ['hesk'])
    assert lore.tagged({'visibility': 'public', 'known_to': ['hesk']}) == ('public', [])
    assert lore.tagged({'visibility': 'known', 'known_to': []}) == ('gm', [])
    assert lore.tagged({'visibility': 'Secret'}) == ('gm', [])
    assert lore.tagged({'visibility': 'gm', 'known_to': 'hesk'}) == ('gm', [])
    assert lore.readable({}, frozenset()) is True


# A world package --------------------------------------------------------------------------------------------

def contents() -> dict:
    cast = [{'id': 'old-tam', 'name': 'Old Tam', 'secret': 'He drowned the miller.'},
            {'id': 'jess', 'name': 'Jess', 'secret': 'She is the miller\'s daughter.', 'visibility': 'gm'},
            {'id': 'wren', 'name': 'Wren', 'secret': 'She saw it.', 'known_to': ['jess'], 'visibility': 'public'}]
    return {'world': {'id': 'ashmoor', 'name': 'Ashmoor'}, 'documents': {}, 'engine': {}, 'assets': {}, 'sections': {
        'cast': {'cast': cast},
        'personas': {'personas': [{'id': 'reed', 'name': 'Reed', 'secret': 'Reed owes Tam.'}]},
        'factions': {'factions': [{'id': 'wardens', 'name': 'Wardens', 'secret': 'They take bribes.'}]},
        'deities': {'powers': [{'id': 'mire', 'name': 'The Mire', 'guise': {'name': 'Old Tam', 'cast': 'old-tam'},
                                'mortal_life': 'A ferryman once.'}]},
        'hidden-truths': {'truths': [
            {'id': 'the-miller', 'truth': 'The miller was drowned.', 'known_by': ['old-tam', 'wren suspects', 'the fen']},
            {'id': 'the-bell', 'truth': SENTINEL, 'known_by': ['the bell-ringers'], 'visibility': 'public'}]},
        'lore': {'entries': [{'id': 'reedby', 'title': 'Reedby', 'keywords': ['Reedby'], 'text': 'Stilts.'},
                             {'id': 'toll', 'title': 'Toll', 'keywords': ['toll'], 'text': 'Tam skims it.',
                              'visibility': 'known', 'known_to': ['old-tam']}]}}}


def by_id(found: list[dict]) -> dict:
    return {(fact['id'], fact['field']): (fact['visibility'], fact['known_to']) for fact in found}


def test_package_facts_are_never_public_and_go_to_their_owners():
    tags = by_id(package_lore.facts(contents()))
    assert tags == {
        ('old-tam', 'secret'): ('known', ['old-tam']),
        # Kept even from its owner.
        ('jess', 'secret'): ('gm', []),
        # A "public" tag on a secret is ignored; known_to adds a knower.
        ('wren', 'secret'): ('known', ['wren', 'jess']),
        ('reed', 'secret'): ('known', ['reed']),
        ('wardens', 'secret'): ('gm', []),
        # A power's secrets are known to the cast member it walks as.
        ('mire', 'guise'): ('known', ['old-tam']), ('mire', 'mortal_life'): ('known', ['old-tam']),
        # Only cast ids know a hidden truth: "wren suspects" and "the fen" are not people.
        ('the-miller', 'truth'): ('known', ['old-tam']),
        ('the-bell', 'truth'): ('gm', [])}


def test_package_lore_comes_in_with_its_tags():
    found = {item['title']: lore.tagged(item) for item in package_lore.entries(contents(), None)}
    assert found == {'Reedby': ('public', []), 'Toll': ('known', ['old-tam'])}


def test_the_importer_refuses_tags_it_cannot_read():
    good = contents()
    assert package_lore.tag_problems(good) == []
    bad = contents()
    bad['sections']['lore']['entries'] += [
        {'id': 'a', 'text': 'A.', 'visibility': 'secret'}, {'id': 'b', 'text': 'B.', 'visibility': 'known'},
        {'id': 'c', 'text': 'C.', 'known_to': ['nobody-here']}, {'id': 'd', 'text': 'D.', 'known_to': 'old-tam'}]
    assert package_import.checked(bad) == [
        'lore a: visibility is public, known or gm', 'lore b: known needs known_to, the cast or persona ids who know it',
        'lore c: known_to nobody-here is not in cast or personas', 'lore d: known_to is a list of cast or persona ids']


def test_a_tagged_lore_entry_is_marked_as_hiding_a_truth():
    assert packages.hidden('lore', {'visibility': 'gm'}) and packages.hidden('lore', {'known_to': ['old-tam']})
    assert not packages.hidden('lore', {'visibility': 'public'}) and not packages.hidden('lore', {})


def test_a_package_file_gives_the_same_facts_as_its_contents(tmp_path):
    path = packages.write(contents(), tmp_path / packages.FOLDER / 'ashmoor.sqlite')
    world_data.use(tmp_path)
    try:
        assert by_id(world_data.facts('ashmoor')) == by_id(package_lore.facts(packages.read(path)))
        assert world_data.facts('nowhere') == []
    finally:
        world_data.use(None)


def test_no_built_in_hidden_truth_or_secret_is_public():
    for world in packages.builtin_ids():
        found = world_data.facts(world)
        assert found and all(fact['visibility'] in ('known', 'gm') for fact in found)
        assert all(fact['known_to'] for fact in found if fact['visibility'] == 'known')
    babel = by_id(world_data.facts('babel'))
    assert babel[('the-usher-is-rachel', 'truth')] == ('known', ['rachel-ostrowski'])


def test_city_lore_carried_to_a_new_world_keeps_its_tags(tmp_path):
    import sqlite3

    from adventure import database
    source, target = tmp_path / 'old.sqlite3', tmp_path / 'new.sqlite3'
    for path in (source, target):
        with sqlite3.connect(path) as connection:
            connection.executescript(database.SCHEMA)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO lore_books (id, city_id, name, created_at) VALUES ('b', 'reedby', 'Reedby', 'now')")
        connection.execute("INSERT INTO lore_entries (id, book_id, position, text, visibility, known_to) VALUES "
                           "('e', 'b', 0, ?, 'known', '[\"old-tam\"]')", (SENTINEL,))
    lore.carry_city_lore(target, source, {'id': 'reedby'})
    with sqlite3.connect(target) as connection:
        assert connection.execute('SELECT text, visibility, known_to FROM lore_entries').fetchall() == [
            (SENTINEL, 'known', '["old-tam"]')]
