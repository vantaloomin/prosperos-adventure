"""Art on request (dungeon/art.py): portraits, places and passages, routed to the image backends."""
import pytest
from conftest import Chunk, tell
from fastapi.testclient import TestClient
from test_images import FakeAdapter, local_comfy, ok, png

from dungeon import art, combat, record
from dungeon.identity import CLIENT_HEADER
from dungeon.images.adapters.base import AdapterError
from dungeon.main import create_app
from dungeon.providers.vault import MemoryVault


@pytest.fixture
def adapters():
    return {'comfyui': FakeAdapter(), 'codex': FakeAdapter(), 'hosted': FakeAdapter()}


@pytest.fixture
def app(tmp_path, clock, provider, adapters):
    return create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(),
                      provider=provider, background=False, image_adapters=adapters)


@pytest.fixture
def client(app):
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        ok(test_client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
        ok(test_client.delete('/api/story'))
        ok(test_client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
        yield test_client


def ask(client, kind, subject=''):
    return ok(client.post('/api/story/art', json={'kind': kind, 'subject': subject}))


def made(answer):
    return next(item for item in answer['art'] if item['id'] == answer['asked'])


def test_a_portrait_of_the_character_is_built_from_what_the_game_tracks_and_becomes_their_reference(client, adapters):
    local_comfy(client)
    first = made(ask(client, 'portrait', 'player'))
    assert first['status'] == 'done' and first['reference'] and first['kind'] == 'portrait'
    sent = adapters['comfyui'].requests[0]
    assert 'Portrait of Agna Holt' in sent.prompt and 'They are unhurt.' in sent.prompt
    assert sent.width < sent.height  # a portrait is tall
    assert client.get(first['url']).content == png()
    second = made(ask(client, 'portrait', 'player'))
    assert second['status'] == 'done' and not second['reference']
    with client.app.state.database.connect() as connection:
        assert art.reference_of(connection, client.app.state.database, 'portrait', 'player') == png()


def test_a_picture_goes_out_of_date_when_what_it_shows_changes(client):
    local_comfy(client)
    ask(client, 'portrait', 'player')
    assert not ok(client.get('/api/story/art'))['art'][0]['stale']
    with client.app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 3)
    assert ok(client.get('/api/story/art'))['art'][0]['stale']


def test_a_failed_backend_passes_the_picture_on_and_with_none_it_is_refused(client, adapters):
    refused = made(ask(client, 'place'))
    assert refused['status'] == 'refused' and 'No image backend' in refused['error']
    local_comfy(client)
    ok(client.post('/api/images/backends', json={'kind': 'comfyui', 'base_url': 'http://127.0.0.1:8189',
                                                 'accept_disclosure': True}))
    adapters['comfyui'].outcomes = [AdapterError('timeout', 'It took too long.'), png(96, 64)]
    place = made(ask(client, 'place'))
    assert place['status'] == 'done' and (place['width'], place['height']) == (96, 64)
    assert len(adapters['comfyui'].requests) == 2 and 'Pell' in adapters['comfyui'].requests[0].prompt


def test_a_passage_is_pictured_from_its_own_words_and_nsfw_stays_off_safe_only_backends(client, adapters):
    ok(client.post('/api/images/backends', json={'kind': 'codex', 'accept_disclosure': True}))
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_messages (id, seq, role, text, city_id, place_id, created_at) VALUES "
                           "('m-1', 900, 'narrator', 'The reeve counts coins by candlelight.', 'kingswood', "
                           "'pell-provisions', 'x'), ('m-2', 901, 'narrator', 'She stands nude in the rain.', "
                           "'kingswood', 'pell-provisions', 'x')")
    passage = made(ask(client, 'passage', 'm-1'))
    assert passage['status'] == 'done' and 'counts coins by candlelight' in adapters['codex'].requests[0].prompt
    nude = made(ask(client, 'passage', 'm-2'))
    assert nude['status'] == 'refused' and 'NSFW' in nude['error'] and len(adapters['codex'].requests) == 1
    assert client.post('/api/story/art', json={'kind': 'passage', 'subject': 'nope'}).status_code == 404


def test_someone_met_is_pictured_as_the_town_knows_them_with_their_feelings_on_their_face(client, adapters):
    local_comfy(client)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, notes, "
                           "fear) VALUES ('town:kingswood:the-green:0', 'kingswood', 'Fenwick Cutter', 'x', 'x', 'x', "
                           "'[\"Fenwick wipes honey from his beard.\"]', 3)")
    portrait = made(ask(client, 'portrait', 'town:kingswood:the-green:0'))
    sent = adapters['comfyui'].requests[0].prompt
    assert portrait['status'] == 'done' and 'Portrait of Fenwick Cutter (he/him, 49 years old, hawker)' in sent
    assert 'wipes honey from his beard' in sent and 'a frightened, wary look' in sent
    assert client.post('/api/story/art', json={'kind': 'portrait', 'subject': 'stranger'}).status_code == 404


def test_passive_art_pictures_the_place_after_a_turn_once_and_stops_at_the_cap(client, adapters, provider, monkeypatch):
    client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model', 'api_key': 'k'})
    provider.respond = lambda system, messages: ([Chunk('{"facts": []}'), Chunk('', 'stop')] if system.startswith(record.EXTRACT)
                                                 else [Chunk('Pell looks up.'), Chunk('', 'stop')])
    local_comfy(client)
    tell(client, 'I look around.', 'art-0001')
    assert ok(client.get('/api/story/art'))['art'] == []  # off by default
    ok(client.put('/api/settings', json={'passive_art': True}))
    tell(client, 'I look around again.', 'art-0002')
    pictured = ok(client.get('/api/story/art'))['art']
    assert [(item['kind'], item['status']) for item in pictured] == [('place', 'done')]
    tell(client, 'I wait.', 'art-0003')
    assert len(ok(client.get('/api/story/art'))['art']) == 1  # the place has its picture
    monkeypatch.setattr(art, 'PASSIVE_CAP', 0)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute('DELETE FROM story_art')
    tell(client, 'I wait some more.', 'art-0004')
    assert ok(client.get('/api/story/art'))['art'] == []


def test_someone_here_in_the_scene_can_be_pictured_before_the_record_has_met_them(client, adapters):
    # Playtest m6a: the first person in the scene was refused as not met.
    from dungeon import story, story_clock
    local_comfy(client)
    with client.app.state.database.connect() as connection:
        view = story.scene(connection, story_clock.now(connection, client.app.state.database.clock))
    here = view['people'][0]['sheet']
    # The screen has their key, though not their name (playtest m6b).
    shown = ok(client.get('/api/story'))['scene']['present']
    assert here['key'] in [item['key'] for item in shown] and here['name'] not in str(shown)
    portrait = made(ask(client, 'portrait', here['key']))
    assert portrait['status'] == 'done' and f"Portrait of {here['name']}" in adapters['comfyui'].requests[0].prompt


def test_the_stage_shows_the_places_picture_and_portraits_of_who_is_here(client, adapters):
    from dungeon import story, story_clock
    local_comfy(client)
    assert ok(client.get('/api/story/art/stage'))['portraits'] == []
    with client.app.state.database.connect(write=True) as connection:
        view = story.scene(connection, story_clock.now(connection, client.app.state.database.clock))
        here = view['people'][0]['sheet']
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, notes) "
                           "VALUES (?, 'kingswood', ?, 'x', 'x', 'x', '[]')", (here['key'], here['name']))
    ask(client, 'place')
    ask(client, 'portrait', here['key'])
    staged = ok(client.get('/api/story/art/stage'))
    assert staged['background']['url'].endswith('/file')
    assert [(item['key'], item['name']) for item in staged['portraits']] == [(here['key'], here['name'])]
    # Live-state portraits: once their feelings change, passive art makes them again.
    with client.app.state.database.connect(write=True) as connection:
        assert not art.stale_portrait(connection, client.app.state.database, here['key'])
        connection.execute('UPDATE story_people SET fear=4 WHERE key=?', (here['key'],))
        assert art.stale_portrait(connection, client.app.state.database, here['key'])
        assert art.wanted(connection, client.app.state.database, [here['key']]) == ('portrait', here['key'])


# Default backdrops ---------------------------------------------------------------------------------

def test_every_world_lists_backdrops_that_can_be_picked():
    import json

    from dungeon import packages
    lots = json.loads((packages.DATA / 'town_lots.json').read_text(encoding='utf-8'))
    for world in ('vallarith', 'havenbrooke', 'babel'):
        entries = art.backdrops(world)
        ids = [entry['id'] for entry in entries]
        assert len(ids) == len(set(ids)) and sum(bool(entry.get('default')) for entry in entries) == 1
        assert all(entry['prompt'] for entry in entries)
        look = 'street' if world == 'havenbrooke' else 'ink'
        known = {item['id'] for item in lots[look]}
        assert {lot for entry in entries for lot in entry.get('lots', [])} <= known
    # Every blank-lot entry of the fantasy and modern maps has its own picture.
    assert {item['id'] for item in lots['ink']} <= {lot for entry in art.backdrops('vallarith') for lot in entry.get('lots', [])}
    assert {item['id'] for item in lots['street']} <= {lot for entry in art.backdrops('havenbrooke')
                                                       for lot in entry.get('lots', [])}


def test_a_backdrop_is_picked_by_the_place_then_wild_lot_tags_kind_street_default():
    entries = art.backdrops('vallarith')
    pick = lambda place, wild=None, street=False: art.pick(entries, place, wild, street)['id']  # noqa: E731
    smithy = {'kind': 'workshop', 'tags': ['smith', 'weapons', 'tools']}
    assert pick(smithy) == 'smithy'
    assert pick(smithy | {'backdrop': 'tannery'}) == 'tannery'
    assert pick({'kind': 'workshop', 'tags': ['lot', 'cooper']}) == 'cooper'
    assert pick({'kind': 'workshop', 'tags': ['hidden']}) == 'workshop'
    assert pick({'kind': 'trail', 'tags': []}, wild=('ruin', 'hills')) == 'ruin'
    assert pick({'kind': 'trail', 'tags': []}, wild=(None, 'marsh')) == 'marsh'
    assert pick({'kind': 'landmark', 'tags': []}, street=True) == 'town-street'
    assert pick({'kind': 'nowhere', 'tags': []}) == 'road'
    assert art.pick(art.backdrops('havenbrooke'), {'kind': 'landmark', 'tags': ['esoteric-sciences', 'classes']},
                    None, False)['id'] == 'esoteric-classroom'


def test_with_no_picture_made_the_stage_shows_the_default_backdrop_in_the_hours_light(client, adapters, monkeypatch):
    from dungeon import world_data
    real = world_data.asset
    monkeypatch.setattr(world_data, 'asset', lambda world, name: b'RIFF0000WEBP' if name.startswith('backdrops/')
                        and not name.endswith('-night.webp') else real(world, name))
    background = ok(client.get('/api/story/art/stage'))['background']
    # Pell's Provisions is a general store.
    assert background['default'] and background['url'] == '/api/story/art/backdrop/vallarith/general-store.webp'
    served = client.get(background['url'])
    assert served.status_code == 200 and served.content == b'RIFF0000WEBP'
    assert client.get('/api/story/art/backdrop/vallarith/..%2Fmaps%2Fvallarith.jpg').status_code == 404
    # A picture made of the place wins over the default.
    local_comfy(client)
    ask(client, 'place')
    assert ok(client.get('/api/story/art/stage'))['background']['url'].endswith('/file')


def test_a_worlds_assets_are_read_from_its_package(client):
    from dungeon import packages, world_data
    shipped = (packages.BUILTIN / 'vallarith' / 'assets' / 'maps' / 'vallarith.jpg').read_bytes()
    assert world_data.paths() and world_data.asset('vallarith', 'maps/vallarith.jpg') == shipped
    assert world_data.asset('babel', 'maps/vallarith.jpg') is None


def test_an_outdoor_backdrop_has_night_and_dusk_light():
    from datetime import datetime
    assert [art.light(datetime(2009, 9, 1, hour)) for hour in (3, 6, 12, 19, 22)] == ['night', 'dawn', 'day', 'dusk',
                                                                                         'night']


# Default portraits ---------------------------------------------------------------------------------

def test_every_world_lists_stock_portraits_with_defaults_for_each_age_and_pronoun(client):
    for world in ('vallarith', 'havenbrooke', 'babel'):
        entries = art.stock_portraits(world)
        ids = [entry['id'] for entry in entries]
        assert len(ids) == len(set(ids)) and all(entry['prompt'] for entry in entries)
        assert all(entry['age'] in ('young', 'middle', 'old') for entry in entries)
        assert all(entry.get('roles') or entry.get('folk') or entry.get('default') for entry in entries)
        defaults = {(entry['pronouns'], entry['age']) for entry in entries if entry.get('default')}
        assert {pronoun for pronoun, _age in defaults} == {'he', 'she'} and len({age for _p, age in defaults}) == 3
        # Every portrait the list names has been made.
        assert all(art.stock_portrait(world, {'key': 'x', 'folk': entry['folk'][0]} if entry.get('folk') else
                                      {'key': 'x', 'pronouns': 'he/him', 'age': 40}) for entry in entries)


def test_a_stock_portrait_is_picked_by_folk_then_job_then_pronouns_and_age(client):
    entries = art.stock_portraits('vallarith')
    pick = lambda **sheet: art.portrait_pick(entries, {'key': 'town:kingswood:forge:0', **sheet})['id']  # noqa: E731
    assert pick(occupation='smith', role='regular', pronouns='he/him', age=44) == 'smith-man'
    assert pick(occupation='smith', role='regular', pronouns='she/her', age=40) == 'smith-woman'
    assert pick(occupation='innkeeper', pronouns='he/him', age=63) == 'innkeeper-old'
    assert pick(occupation='smith', pronouns='he/him', age=44, folk='halfling') == 'halfling-man'
    assert pick(occupation='astrologer', pronouns='she/her', age=75) == 'townswoman-old'
    assert pick(occupation='', pronouns='he/him', age=22) == 'townsman-young'
    # They/them fit any; people who fit the same portraits are spread across them by key, the same each time.
    spread = {art.portrait_pick(entries, {'key': f'town:kingswood:forge:{n}', 'occupation': 'smith', 'age': 40,
                                          'pronouns': 'they/them'})['id'] for n in range(12)}
    assert spread == {'smith-man', 'smith-woman'}
    assert art.portrait_pick(art.stock_portraits('havenbrooke'), {'key': 'k', 'occupation': 'head of MTO',
                                                                  'pronouns': 'he/him', 'age': 50})['id'] == 'enchanter-man'
    assert art.portrait_pick([], {'key': 'k'}) is None


def test_someone_met_with_no_portrait_stands_on_the_stage_in_a_stock_one(client, adapters):
    from dungeon import story, story_clock
    with client.app.state.database.connect(write=True) as connection:
        view = story.scene(connection, story_clock.now(connection, client.app.state.database.clock))
        here = view['people'][0]['sheet']
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, notes) "
                           "VALUES (?, 'kingswood', ?, 'x', 'x', 'x', '[]')", (here['key'], here['name']))
    stock = ok(client.get('/api/story/art/stage'))['portraits']
    assert [(item['key'], item['default']) for item in stock] == [(here['key'], True)]
    assert stock[0]['url'] == art.stock_portrait('vallarith', here)
    served = client.get(stock[0]['url'])
    assert served.status_code == 200 and served.content[:4] == b'RIFF'
    assert client.get('/api/story/art/portrait/vallarith/..%2Fmaps%2Fvallarith.jpg').status_code == 404
    # A portrait made of them wins over the stock one.
    local_comfy(client)
    ask(client, 'portrait', here['key'])
    made_one = ok(client.get('/api/story/art/stage'))['portraits']
    assert made_one[0]['url'].endswith('/file') and 'default' not in made_one[0]


def test_a_hosted_failure_reaches_a_local_comfyui_and_a_refusal_skips_safe_only_backends(client, adapters):
    def hosted(provider, model):
        return ok(client.post('/api/images/backends', json={'kind': 'hosted', 'provider': provider, 'model': model,
                                                            'api_key': 'k', 'accept_disclosure': True}))
    hosted('openrouter', 'm')
    hosted('openai', 'gpt-image-1')
    local_comfy(client)
    adapters['hosted'].outcomes = [AdapterError('auth', 'The provider rejected the API key.'), png(96, 64)]
    assert made(ask(client, 'place'))['status'] == 'done'
    assert len(adapters['hosted'].requests) == 2 and adapters['comfyui'].requests == []
    adapters['hosted'].outcomes = [AdapterError('refused', 'The provider refused this image under its content rules.')]
    assert made(ask(client, 'place'))['status'] == 'done'
    # The OpenAI API takes safe requests only, so after a refusal the picture goes straight to the local ComfyUI.
    assert len(adapters['hosted'].requests) == 3 and len(adapters['comfyui'].requests) == 1
