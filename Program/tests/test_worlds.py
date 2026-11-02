"""Worlds and personas (dungeon/worlds.py): more than one life for the user, each in its own world."""
import json

import pytest
from conftest import tell

from dungeon import story, tiers, worlds


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def listing(client):
    return ok(client.get('/api/worlds'))


def test_a_new_workspace_is_the_first_world_in_the_default_city(client, app):
    data = listing(client)
    assert len(data['personas']) == 1 and len(data['personas'][0]['worlds']) == 1
    world = data['world']
    assert world['first'] and world['active'] and world['city_id'] == story.DEFAULT_CITY
    assert (app.state.database.root / worlds.REGISTRY).is_file()


def test_a_new_world_has_its_own_town(client, app):
    made = ok(client.post('/api/worlds', json={}))
    assert not made['active'] and not made['first'] and made['name'] != listing(client)['world']['name']
    path = app.state.database.root / made['folder'] / worlds.DATABASE
    assert path.is_file()
    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    with app.state.database.connect() as connection:
        assert story.town_seed(connection) == made['id'][:16]
    # The town seed is the world's and outlives a change to the persona.
    persona = listing(client)['persona']
    ok(client.patch(f"/api/worlds/personas/{persona['id']}", json={'name': 'Sam'}))
    with app.state.database.connect() as connection:
        assert story.town_seed(connection) == made['id'][:16]


def test_switching_worlds_changes_the_story_and_settings_follow(client, connected, app):
    ok(client.put('/api/settings', json={'show_odds': True}))
    tell(client, 'Hello there', 'hello-message')
    made = ok(client.post('/api/worlds', json={'name': 'Somewhere else'}))
    switched = ok(client.post(f"/api/worlds/{made['id']}/switch"))
    assert switched['world']['id'] == made['id'] and switched['world']['name'] == 'Somewhere else'
    assert ok(client.get('/api/story'))['messages'] == []
    assert ok(client.get('/api/settings'))['show_odds']
    assert ok(client.get('/api/connection'))['connection']['model'] == 'local-model'
    first = next(world for world in listing(client)['personas'][0]['worlds'] if world['first'])
    ok(client.post(f"/api/worlds/{first['id']}/switch"))
    assert any(message['text'] == 'Hello there' for message in ok(client.get('/api/story'))['messages'])


def test_a_new_persona_has_a_world_of_their_own(client):
    # Who the user is stays theirs: a name is needed, and nothing they left blank is made up.
    assert client.post('/api/worlds/personas', json={}).status_code == 422
    made = ok(client.post('/api/worlds/personas', json={'name': 'Jordan'}))
    assert made['name'] == 'Jordan' and len(made['worlds']) == 1
    assert (made['gender'], made['age'], made['about'], made['birthday']) == ('', None, '', '')
    switched = ok(client.post(f"/api/worlds/personas/{made['id']}/switch"))
    assert switched['persona']['id'] == made['id'] and switched['world']['id'] == made['worlds'][0]['id']
    assert [persona['active'] for persona in listing(client)['personas']] == [False, True]


def test_the_world_the_user_was_in_opens_on_the_next_start(clock, provider, client, app):
    from dungeon.main import create_app
    from dungeon.providers.vault import MemoryVault
    made = ok(client.post('/api/worlds', json={}))
    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    again = create_app(app.state.database.home, clock=clock, vault=MemoryVault(), provider=provider, background=False)
    assert again.state.database.path == app.state.database.path
    assert worlds.active_path(app.state.database.home) == app.state.database.path


def test_nothing_switches_while_debug_time_is_on(client, app):
    made = ok(client.post('/api/worlds', json={}))
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO debug_time (id, app_anchor, real_anchor, speed, started_at, app_started_at, "
                           "snapshot, backup) VALUES (1, 'a', 'b', 1, 'c', 'd', 'e', 'f')")
    response = client.post(f"/api/worlds/{made['id']}/switch")
    assert response.status_code == 409 and 'Debug time' in response.json()['detail']


def test_deleting_a_world_keeps_a_backup_and_never_the_one_in_use(client, app):
    data = listing(client)
    assert client.delete(f"/api/worlds/{data['world']['id']}").status_code == 409
    made = ok(client.post('/api/worlds', json={}))
    ok(client.delete(f"/api/worlds/{made['id']}"))
    assert len(listing(client)['personas'][0]['worlds']) == 1
    assert not (app.state.database.root / made['folder']).exists()
    assert list((app.state.database.root / 'backups' / 'deleted-worlds').glob('*.zip'))


def test_a_world_can_move_to_another_persona(client):
    persona = ok(client.post('/api/worlds/personas', json={'name': 'Riley'}))
    first = listing(client)['world']
    moved = ok(client.patch(f"/api/worlds/{first['id']}", json={'persona_id': persona['id'], 'name': 'Home'}))
    assert moved['persona']['id'] == persona['id'] and moved['world']['name'] == 'Home'


def test_a_damaged_registry_is_not_trusted(tmp_path):
    (tmp_path / worlds.REGISTRY).write_text('{not json', encoding='utf-8')
    assert worlds.load(tmp_path) is None
    (tmp_path / worlds.REGISTRY).write_text(json.dumps({'worlds': []}), encoding='utf-8')
    assert worlds.load(tmp_path) is None


@pytest.mark.parametrize('name', ['', '  '])
def test_a_world_needs_a_name(client, name):
    world = listing(client)['world']
    assert client.patch(f"/api/worlds/{world['id']}", json={'name': name}).status_code == 422


def test_a_city_that_does_not_exist_makes_no_persona(client):
    before = len(listing(client)['personas'])
    assert client.post('/api/worlds/personas', json={'name': 'Ellis', 'city_id': 'nowhere'}).status_code == 404
    assert len(listing(client)['personas']) == before


def test_somewhere_new_is_a_town_of_the_picked_world_never_a_road(client):
    # Plain "somewhere new" stays in the world the user is in: Baltimore is outside the world packages.
    made = ok(client.post('/api/worlds', json={'city_id': worlds.SOMEWHERE_NEW}))['city_id']
    assert made != 'baltimore' and tiers.world_of(made) is None
    assert ok(client.post('/api/worlds', json={'city_id': f'{worlds.SOMEWHERE_NEW}:vallarith'}))['city_id'] == 'kingswood'
    made = {ok(client.post('/api/worlds', json={'city_id': f'{worlds.SOMEWHERE_NEW}:babel'}))['city_id'] for _ in range(4)}
    assert made <= {'the-concourse', 'hollin', 'the-gilded-bazaar'}
    assert ok(client.post('/api/worlds', json={'city_id': f'{worlds.SOMEWHERE_NEW}:havenbrooke'}))['city_id'] == 'haven'
    cities = {city['id']: city for city in ok(client.get('/api/world/cities'))}
    assert not cities['vallarith-road']['home'] and not cities['babel-floors']['home'] and cities['kingswood']['home']
    world = listing(client)['world']
    choices = ok(client.get(f"/api/worlds/{world['id']}/home"))
    assert not {'vallarith-road', 'havenbrooke-road', 'babel-floors'} & {city['id'] for city in choices['cities']}
