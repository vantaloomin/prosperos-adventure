"""Town maps (dungeon/townmap.py): a street map laid out from the town's data and the campaign's seed."""
import math

import pytest

from dungeon import hexes, townmap
from dungeon.world import catalog

TOWNS = ('kingswood', 'haven', 'hollin', 'the-concourse', 'the-gilded-bazaar', 'haddon-harbor')


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_the_same_town_and_seed_give_the_same_map_and_another_seed_another():
    data = catalog.city('kingswood')
    one, again = townmap.build(data, 'one'), townmap.build(data, 'one')
    assert one == again
    other = townmap.build(data, 'two')
    assert [lot['polygon'] for lot in other['lots']] != [lot['polygon'] for lot in one['lots']]
    # The neighborhoods are the town's own whatever the seed.
    assert {district['id'] for district in other['districts']} == {district['id'] for district in one['districts']}


def test_the_era_picks_the_look_unless_the_town_says():
    assert townmap.style(catalog.city('kingswood')) == 'ink'
    assert townmap.style(catalog.city('haven')) == 'street'
    assert townmap.style(catalog.city('kingswood') | {'town_map': {'style': 'floor'}}) == 'floor'


def test_a_worlds_roads_and_wilds_have_no_town_map():
    for city_id in ('vallarith-road', 'havenbrooke-road', 'babel-floors'):
        assert not townmap.has_map(catalog.city(city_id))
    assert all(townmap.has_map(catalog.city(city_id)) for city_id in TOWNS)


@pytest.mark.parametrize('city_id', TOWNS)
def test_every_place_in_town_is_on_the_map_in_its_own_neighborhood(city_id):
    data = catalog.city(city_id)
    board = townmap.build(data, 'seed')
    away = {found['id'] for found in board['exits']}
    on_lots = {lot['place']['id']: lot for lot in board['lots'] if lot['place']}
    on_ground = {patch['place']['id'] for patch in board['patches'] if patch['place']}
    for place in data['places']:
        if place['neighborhood'] in away:
            continue
        if place['kind'] in townmap.OPEN:
            continue  # a square, park or trail takes a patch when its neighborhood has one to spare
        lot = on_lots[place['id']]
        assert lot['neighborhood'] == place['neighborhood'], place['id']
    # No place is on two lots, and no lot holds two places.
    assert len(on_lots) == sum(1 for lot in board['lots'] if lot['place'])
    assert not on_ground & set(on_lots)
    # Each employer has a building of its own, or shares the place of the same name.
    names = {place['name'].casefold() for place in data['places']}
    for employer in data['employers']:
        if employer['neighborhood'] not in away and employer['name'].casefold() not in names:
            assert on_lots[employer['id']]['neighborhood'] == employer['neighborhood']


def test_no_lot_stands_in_the_river():
    board = townmap.build(catalog.city('kingswood'), 'seed')
    river = board['water'][0]
    for lot in board['lots']:
        for point in lot['polygon']:
            assert townmap.to_line(tuple(point), [tuple(p) for p in river['points']]) > river['width'] / 2


def test_a_neighborhood_far_out_of_town_is_a_road_off_the_map():
    board = townmap.build(catalog.city('hollin'), 'seed')
    assert {found['id'] for found in board['exits']} == {'the-valley-road', 'the-reachwall'}
    assert all(found['at'] and math.hypot(*found['at']) > townmap.TOWN for found in board['exits'])
    assert 'the-reachwall' not in {district['id'] for district in board['districts']}


def test_main_roads_start_at_the_square_and_reach_the_edge():
    board = townmap.build(catalog.city('kingswood'), 'seed')
    square = next(patch for patch in board['patches'] if patch['id'] == board['square'])
    corners = {tuple(point) for point in square['polygon']}
    assert len(board['roads']) >= 3
    for road in board['roads']:
        assert tuple(road[0]) in corners
        assert math.hypot(*road[-1]) > townmap.EDGE


def test_the_story_shows_the_map_of_the_town_it_is_in(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    town = ok(client.get('/api/story/town'))['town']
    assert town['town'] == 'kingswood' and town['name'] == 'Kingswood'
    here = town['here']['place']
    assert any(lot['place'] and lot['place']['id'] == here for lot in town['lots']) or \
        any(patch['place'] and patch['place']['id'] == here for patch in town['patches'])
    assert town['here'] == {'place': 'pell-provisions', 'neighborhood': 'the-crossroads'}
    # The seed is the campaign's, so the map is the same next time.
    assert ok(client.get('/api/story/town'))['town'] == town
    # Out on the road there is no town to map.
    ok(client.put('/api/story/scene', json={'city_id': 'vallarith-road'}))
    assert ok(client.get('/api/story/town'))['town'] is None


def blank_lot(town: dict, app) -> dict:
    """A lot with nothing on it yet: not one of the town's own places, known or not."""
    with app.state.database.connect() as connection:
        board = townmap.layout(catalog.city(town['town']), hexes.seed(connection))
    own = {lot['id'] for lot in board['lots'] if lot['place']}
    return next(lot for lot in town['lots'] if not lot['place'] and not lot['found'] and lot['id'] not in own)


def test_a_blank_building_is_decided_when_looked_at_and_kept(client, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    town = ok(client.get('/api/story/town'))['town']
    lot = blank_lot(town, app)
    looked = ok(client.post(f"/api/story/town/lots/{lot['id']}/look"))
    found = looked['found']
    assert found['id'] == f"lot-{lot['id']}" and found['name'] and found['summary']
    assert found['neighborhood'] == lot['neighborhood']
    assert next(item for item in looked['town']['lots'] if item['id'] == lot['id'])['found'] == found
    # Looking again finds the same, and it is a place of the town the story can go to.
    assert ok(client.post(f"/api/story/town/lots/{lot['id']}/look"))['found'] == found
    moved = ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': found['id']}))
    assert moved['scene']['place']['name'] == found['name']
    # It does not take another lot on the map once it is a place.
    again = ok(client.get('/api/story/town'))['town']
    assert [item['id'] for item in again['lots']] == [item['id'] for item in town['lots']]
    assert again['here']['place'] == found['id']


def test_a_named_place_or_unknown_lot_cannot_be_looked_at(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    town = ok(client.get('/api/story/town'))['town']
    named = next(lot for lot in town['lots'] if lot['place'])
    assert client.post(f"/api/story/town/lots/{named['id']}/look").status_code == 400
    assert client.post('/api/story/town/lots/nowhere/look').status_code == 404


def test_what_a_lot_holds_follows_the_seed_and_the_intensity_levels():
    data = catalog.city('kingswood')
    board = townmap.build(data, 'seed')
    lots = [lot for lot in board['lots'] if not lot['place']]
    tame = dict.fromkeys(('violence', 'sex', 'horror', 'cruelty', 'drugs'), 0)
    held = [townmap.contents(data, 'seed', lot, None) for lot in lots]
    assert held == [townmap.contents(data, 'seed', lot, None) for lot in lots]
    assert len({found['entry'] for found in held}) > 5
    gated = {entry['id'] for entry in townmap.tables()['ink'] if entry.get('intensity')}
    assert not {townmap.contents(data, 'seed', lot, tame)['entry'] for lot in lots} & gated
    # A modern town's signs use modern names.
    haven = catalog.city('haven')
    lot = next(lot for lot in townmap.build(haven, 'seed')['lots'] if not lot['place'])
    assert townmap.contents(haven, 'seed', lot, None)['entry'] in {entry['id'] for entry in townmap.tables()['street']}


def test_a_building_looked_at_is_somewhere_the_player_can_walk_to_by_name(client, app):
    from dungeon import story
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_campaign (id, seed) VALUES (1, 'walk') ON CONFLICT(id) DO UPDATE SET seed='walk'")
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    town = ok(client.get('/api/story/town'))['town']
    found = ok(client.post(f"/api/story/town/lots/{blank_lot(town, app)['id']}/look"))['found']
    with app.state.database.connect() as connection:
        went = story.walked_to(connection, f"I head to {found['name']}.")
    assert went and went['id'] == found['id']


def test_the_narrator_is_told_what_is_on_the_street_outside_and_it_is_kept_on_arrival(client, app):
    from dungeon import story, story_clock
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    town = ok(client.get('/api/story/town'))['town']
    nearby = {lot['id'] for lot in town['lots'] if lot['found']}
    assert len(nearby) >= 2, 'arriving keeps the buildings outside as seen'
    with app.state.database.connect() as connection:
        view = story.scene(connection, story_clock.now(connection, app.state.database.clock))
        text = story.scene_text(view)
    assert 1 <= len(view['street']) <= townmap.STREET_LOTS
    assert 'Along the street outside' in text
    assert all(item['name'] in text for item in view['street'])
    # What the narrator was told is what the map shows, and the player can walk into one by name.
    shown = {(lot['place'] or lot['found'])['id'] for lot in town['lots'] if lot['place'] or lot['found']}
    assert {item['id'] for item in view['street']} <= shown
    blank = next(item for item in view['street'] if item['id'].startswith('lot-'))
    with app.state.database.connect() as connection:
        went = story.walked_to(connection, f"I go into {blank['name']}.")
    assert went is None or went['id'] == blank['id']


def test_no_street_on_the_road():
    assert townmap.street_text([]) == ''


# Found, not known -----------------------------------------------------------------------------------

def shown(town: dict) -> set[str]:
    return {thing['id'] for thing in [*(lot['place'] for lot in town['lots']), *(patch['place'] for patch in town['patches'])]
            if thing}


def unfound(app, data: dict) -> list[dict]:
    """The town's own places the character does not know of; which they passed on arrival is up to the seed."""
    with app.state.database.connect() as connection:
        knows = townmap.known(connection, data)
    return [place for place in data['places'] if place['id'] not in knows]


def test_a_stranger_knows_where_they_are_and_the_landmarks_but_not_the_rest(client, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    data = catalog.city('kingswood')
    town = ok(client.get('/api/story/town'))['town']
    on_map = shown(town)
    assert 'pell-provisions' in on_map
    # The temple and the market anyone could find; what they have not been to, passed or heard of, they could not.
    assert {'shrine-of-tidum', 'crossroads-market'} <= on_map
    hidden = unfound(app, data)
    assert len(hidden) > 5
    assert not {place['id'] for place in hidden} & on_map
    # Nor is any of it in the list of places to find, or named anywhere on the map.
    assert not [place['name'] for place in hidden if f"'{place['name']}'" in str(town)]
    with app.state.database.connect() as connection:
        knows = townmap.known(connection, data)
    assert knows['pell-provisions'] == 'visited' and knows['shrine-of-tidum'] in {'landmark', 'passed'}


def test_a_place_named_in_the_story_is_known_from_then_on(client, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    data = catalog.city('kingswood')
    first, second = unfound(app, data)[:2]
    with app.state.database.connect(write=True) as connection:
        told = townmap.heard(connection, data, f'"Try {first["name"]}, or else {second["name"]}," she says.')
    assert {first['id'], second['id']} <= set(told)  # an employer of the same name is known with its place
    assert {first['id'], second['id']} <= shown(ok(client.get('/api/story/town'))['town'])
    with app.state.database.connect() as connection:
        assert townmap.known(connection, data)[first['id']] == 'told'
    # A name is matched with its capitals, so the Green is not any green thing; one with none in any case.
    assert townmap.named_in('the Green', 'Out on the Green.') and not townmap.named_in('the Green', 'Green eyes, she has.'[6:])
    assert townmap.named_in('the charcoal kilns', 'Past the Charcoal Kilns.')
    assert not townmap.named_in('the Inn', 'At the Inn.')


def test_looking_at_a_building_finds_the_place_in_it(client, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    data = catalog.city('kingswood')
    hidden = {place['id'] for place in unfound(app, data)}
    with app.state.database.connect() as connection:
        board = townmap.layout(data, hexes.seed(connection))
    lot = next(lot for lot in board['lots'] if lot['place'] and lot['place']['id'] in hidden)
    place = lot['place']['id']
    town = ok(client.get('/api/story/town'))['town']
    assert next(item for item in town['lots'] if item['id'] == lot['id'])['place'] is None
    looked = ok(client.post(f"/api/story/town/lots/{lot['id']}/look"))
    assert looked['found']['id'] == place and 'summary' in looked['found']
    assert next(item for item in looked['town']['lots'] if item['id'] == lot['id'])['place']['id'] == place
    # Found once, it is on the map like any other named place.
    assert client.post(f"/api/story/town/lots/{lot['id']}/look").status_code == 400


def test_open_ground_nobody_told_them_of_is_found_by_looking(client, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    town = ok(client.get('/api/story/town'))['town']
    hidden = [patch for patch in town['patches'] if patch.get('hidden')]
    if not hidden:
        pytest.skip('every open place in this layout is a landmark')
    looked = ok(client.post(f"/api/story/town/lots/open-{hidden[0]['id']}/look"))
    assert looked['found']['id'] in shown(looked['town'])
    assert client.post('/api/story/town/lots/open-99999/look').status_code == 404


def test_going_somewhere_makes_it_known_and_a_character_from_the_town_knows_it_all(client, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'tannery'}))
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    data = catalog.city('kingswood')
    with app.state.database.connect() as connection:
        assert townmap.known(connection, data)['tannery'] == 'visited'
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO persona (id, persona_id, home_city_id, updated_at) VALUES (1, 'p', 'kingswood', 'now') "
                           "ON CONFLICT(id) DO UPDATE SET home_city_id='kingswood'")
    with app.state.database.connect() as connection:
        knows = townmap.known(connection, data)
    assert {place['id'] for place in data['places']} <= set(knows)
    # What they had not found they knew of anyway, as one from the town.
    assert knows['tannery'] == 'visited' and 'home' in knows.values()
    assert not {'landmark', 'told', 'looked'} & set(knows.values())
    # A hidden place is hidden from a local too.
    hidden = data | {'places': [*data['places'], data['places'][0] | {'id': 'cellar', 'tags': ['secret']}]}
    with app.state.database.connect() as connection:
        assert 'cellar' not in townmap.known(connection, hidden)
