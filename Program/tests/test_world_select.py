"""The title screen's worlds (dungeon/world_select.py): each playable world with its key art, and going to one."""
from dungeon import story, world_select


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_the_title_screen_offers_every_built_in_world_with_key_art(client):
    found = ok(client.get('/api/story/worlds'))
    ids = [world['id'] for world in found['worlds']]
    assert ids[:3] == ['vallarith', 'havenbrooke', 'babel']
    for world in found['worlds']:
        assert world['name'] and world['pitch'] and world['art']
        picture = client.get(world['art'])
        assert picture.status_code == 200 and picture.headers['content-type'] == 'image/webp'
    assert sum(world['here'] for world in found['worlds']) == (1 if found['here'] else 0)


def test_a_new_campaign_starts_in_the_worlds_first_town():
    assert world_select.start_city('vallarith', {'settlement': 'kingswood'}) == 'kingswood'
    assert world_select.start_city('havenbrooke', {'settlement': 'havenbrooke-campus'}) == 'haven'
    assert world_select.start_city('babel', {'settlement': 'the-concourse'}) == 'the-concourse'


def test_going_to_a_world_makes_one_once_then_goes_back_to_it(client, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood'}))
    assert ok(client.get('/api/story/worlds'))['here'] == 'vallarith'
    babel = ok(client.post('/api/story/worlds/babel/enter'))['world']
    assert babel['city_id'] == 'the-concourse'
    with app.state.database.connect() as connection:
        assert story.scene_row(connection)['city_id'] == 'the-concourse'
    assert ok(client.post('/api/story/worlds/babel/enter'))['world']['id'] == babel['id']
    haven = ok(client.post('/api/story/worlds/havenbrooke/enter'))['world']
    with app.state.database.connect() as connection:
        assert story.scene_row(connection) == {'city_id': 'haven', 'place_id': 'nexus-housing'}
    found = ok(client.get('/api/story/worlds'))
    assert found['here'] == 'havenbrooke' and next(world for world in found['worlds'] if world['id'] == 'babel')['yours']
    assert ok(client.post('/api/story/worlds/babel/enter'))['world']['id'] == babel['id']
    assert ok(client.post('/api/story/worlds/havenbrooke/enter'))['world']['id'] == haven['id']
    assert client.post('/api/story/worlds/nowhere/enter').status_code == 404


def test_a_world_made_on_the_worlds_page_opens_in_its_own_town(client, app):
    """Playtest 2026-10-26: a Havenbrooke world made on the Worlds page had no scene there, so going to it left the
    story outside Havenbrooke and the title screen came back each time."""
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood'}))
    persona = ok(client.get('/api/worlds'))['active_persona_id']
    made = ok(client.post('/api/worlds', json={'persona_id': persona, 'city_id': 'haven'}))
    assert ok(client.post('/api/story/worlds/havenbrooke/enter'))['world']['id'] == made['id']
    with app.state.database.connect() as connection:
        assert story.scene_row(connection)['city_id'] == 'haven'
    assert ok(client.get('/api/story/worlds'))['here'] == 'havenbrooke'
