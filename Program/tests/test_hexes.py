"""The hex crawl (dungeon/hexes.py): authored hexes, land generated past them from the seed, roads, fog of war."""
from datetime import datetime

from conftest import Chunk, tell
from test_inventory import begin
from test_travel import Road

from dungeon import hexes, story_clock, travel, turn


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def vallarith() -> dict:
    return next(found for found in travel.maps() if found.get('world') == 'vallarith')


def test_worlds_crawl_hexes_unless_their_map_opts_out():
    assert hexes.is_hex(vallarith())
    # Havenbrooke goes by car or bus, and BABEL climbs the Stair: both keep their roads.
    assert {found['world'] for found in travel.maps() if not hexes.is_hex(found)} >= {'havenbrooke'}
    babel = next(found for found in travel.maps() if any(node['id'] == 'the-concourse' for node in found['nodes']))
    assert not hexes.is_hex(babel)


def test_the_authored_map_is_canon_and_its_places_sit_on_land():
    board = hexes.Grid(vallarith(), 'one')
    other = hexes.Grid(vallarith(), 'two')
    for node in vallarith()['nodes']:
        at = board.places[node['id']]
        assert board.cell(at)['terrain'] != 'water' and board.cell(at)['place'] == node['id']
        assert board.cell(at)['region'] == node['region']
    # Inside the authored map the seed changes nothing.
    assert all(board.cell((q, 60)) == other.cell((q, 60)) for q in range(20, 80))


def test_land_past_the_map_comes_from_the_seed_alone_whatever_order_it_is_seen_in():
    far = [(200 + q, r) for q in range(12) for r in range(-30, -18)]
    forward, backward = hexes.Grid(vallarith(), 'seed'), hexes.Grid(vallarith(), 'seed')
    ahead = [forward.cell(at) for at in far]
    behind = [backward.cell(at) for at in reversed(far)][::-1]
    assert ahead == behind
    elsewhere = [hexes.Grid(vallarith(), 'another seed').cell(at) for at in far]
    assert elsewhere != ahead
    # Out there it is the wilds, and the land is of more than one kind.
    land = [cell for cell in ahead if cell['terrain'] != 'water']
    assert land and {cell['region'] for cell in land} == {'wilds'}
    assert len({cell['terrain'] for cell in ahead}) > 1


def test_a_map_without_authored_hexes_is_generated_around_its_places():
    travel_map = {'world': 'nowhere', 'nodes': [
        {'id': 'a', 'name': 'A', 'region': 'r', 'city': 'c', 'place': 'p', 'safe': True, 'map': {'x': 0.1, 'y': 0.1}},
        {'id': 'b', 'name': 'B', 'region': 'r', 'city': 'c', 'place': 'q', 'safe': True, 'map': {'x': 0.2, 'y': 0.1}}],
        'routes': [{'from': 'a', 'to': 'b', 'hours': 5, 'terrain': 'the old road', 'danger': 'low'}],
        'regions': {'r': {'danger': 'low'}}}
    board = hexes.Grid(travel_map, 'seed')
    legs = board.way(board.places['a'], board.places['b'])
    assert legs and legs[-1]['place'] == 'b'
    assert {leg['terrain'] for leg in legs} == {'the old road'}
    assert sum(leg['hours'] for leg in legs) == hexes.distance(board.places['a'], board.places['b'])


def test_two_roads_side_by_side_are_not_one_road():
    travel_map = vallarith()
    board = hexes.Grid(travel_map, 'seed')
    eriane = board.places['eriane']
    for leg in board.way(board.places['kingswood'], eriane):
        assert leg['terrain'] == 'the Cyrel road' and leg['hours'] == hexes.ROAD_HOURS


def test_a_fight_out_in_the_wild_ends_the_journey_at_the_next_place():
    entry = next(entry for entry in vallarith()['encounters']['kingdom-of-cyrel'] if 'Bandits' in str(entry))
    legs = [{'from': [0, 0], 'to': [1, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low'},
            {'from': [1, 0], 'to': [2, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low'},
            {'from': [2, 0], 'to': [3, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low', 'place': 'eriane'},
            {'from': [3, 0], 'to': [4, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low', 'place': 'cyrel'}]
    rolls = [{'threat': entry['threat']['text'], 'band': 'failure'}]
    walked, lines = travel.travelled({'mode': 'hex', 'legs': legs, 'encounter': {'leg': 0, 'entry': entry}}, rolls)
    assert walked == legs[:3] and travel.end_of({'mode': 'hex'}, walked) == 'eriane'
    assert travel.STOPPED in lines[-1]


def test_a_journey_shows_the_hexes_it_crosses(client, connected, provider, app):
    begin(client)
    before = ok(client.get('/api/story'))['map']
    assert before['hexes'] and any(cell['place'] == 'kingswood' and cell['visited'] for cell in before['hexes'])
    app.state.dice = Road(99)
    provider.replies = [[Chunk('The road goes on.'), Chunk('', 'stop')]]
    tell(client, 'I set out for Eriane.', 'story-0001')
    after = ok(client.get('/api/story'))['map']
    walked = {(cell['q'], cell['r']) for cell in after['hexes'] if cell['visited']}
    board = hexes.Grid(vallarith(), 'any')
    assert {board.places['kingswood'], board.places['eriane']} <= walked
    assert len(after['hexes']) > len(before['hexes'])
    with app.state.database.connect() as connection:
        seed = connection.execute('SELECT seed FROM story_campaign WHERE id=1').fetchone()[0]
    assert seed


def test_a_line_strikes_out_in_a_direction_from_town_only_when_it_leaves():
    assert travel.heading('I head north-east.', True) == 'north-east'
    assert travel.heading('We keep walking west.', True) == 'west'
    assert travel.heading('I walk north down the street to the well.', False) is None
    assert travel.heading('I leave town and strike out southwest.', False) == 'south-west'
    assert travel.heading('I set out east at dawn.', False) == 'east'


def test_due_east_zigzags_between_the_two_sides_of_a_hex():
    board = hexes.Grid(vallarith(), 'seed')
    legs, _ = board.heading(board.places['kingswood'], 'east', 40, 'clear')
    steps = {tuple(leg['to'])[0] - tuple(leg['from'])[0] for leg in legs}
    assert steps == {1} and len({leg['to'][1] - leg['from'][1] for leg in legs}) == 2


def strike(app, text: str):
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE story_campaign SET seed='fixed' WHERE id=1")
        return travel.plan(connection, 'kingswood', 'pell-provisions', text, Road())


def test_striking_out_ends_the_day_out_in_the_wild(client, connected, provider, app):
    begin(client)
    direction = next(word for word in ('south-east', 'north-east', 'south', 'north', 'east', 'west')
                     if (found := strike(app, f'I set out {word}.')) and found['legs']
                     and not found['legs'][-1].get('place'))
    app.state.dice = Road(99)
    provider.replies = [[Chunk('The land goes on.'), Chunk('', 'stop')]]
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE story_campaign SET seed='fixed' WHERE id=1")
    tell(client, f'I set out {direction} across country.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert story['scene']['place']['id'] == 'the-wilds'
    assert [message['text'] for message in story['messages'] if message['role'] == 'scene'][-1].startswith('You stop in')
    narrator = provider.requests[-1]['system']
    assert f'strikes out {direction} from Kingswood' in narrator and '## Out in the wild' in narrator
    assert 'The nearest place they know of' in narrator
    board = hexes.Grid(vallarith(), 'fixed')
    at = story['map']['at']
    assert not story['map']['places'] or not any(place['here'] for place in story['map']['places'])
    assert hexes.distance(board.places['kingswood'], (at['q'], at['r'])) >= 2 and not at['lost']
    # Out there, a line naming a place walks there from the hex the character is in.
    provider.replies = [[Chunk('Back.'), Chunk('', 'stop')]]
    tell(client, 'I head back to Kingswood.', 'story-0002')
    assert ok(client.get('/api/story'))['scene']['city']['id'] == 'kingswood'


def test_losing_the_way_drifts_off_course_and_the_map_shows_where_they_think_they_are(client, connected, provider,
                                                                                      app, monkeypatch):
    begin(client)
    direction = next((word for word in hexes.TURNS
                      if (found := strike(app, f'I set out {word}.')) and found.get('lost')
                      and found['lost']['astray'][-1]['to'] != found['legs'][-1]['to']
                      and not found['legs'][-1].get('place') and not found['lost']['astray'][-1].get('place')), None)
    assert direction, 'some way out of Kingswood crosses ground one can get lost in'
    monkeypatch.setattr(travel, 'strayed', lambda plan_, rolls: bool(plan_.get('lost')))
    app.state.dice = Road(99)
    provider.replies = [[Chunk('Trees.'), Chunk('', 'stop')]]
    tell(client, f'I set out {direction}.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert story['map']['at']['lost']
    assert 'lost their bearings' in provider.requests[-1]['system']
    # Playtest: walking on the next day while still lost, with no new check that day, crashed on the missing check.
    monkeypatch.setattr(travel, 'strayed', lambda plan_, rolls: False)
    provider.replies = [[Chunk('More trees.'), Chunk('', 'stop')]]
    tell(client, f'I keep walking {direction}.', 'story-0002')
    assert ok(client.get('/api/story'))['messages'][-1]['text'] == 'More trees.'


def site_hexes(board: hexes.Grid, visible: bool) -> list[tuple[int, int]]:
    return [at for at in hexes.ring(board.places['kingswood'], 12)
            if (site := board.site(at)) and site['visible'] == visible]


def test_sites_come_from_the_seed_and_keep_off_roads_places_and_water():
    board = hexes.Grid(vallarith(), 'fixed')
    around = hexes.ring(board.places['kingswood'], 20)
    sites = {at: board.site(at) for at in around if board.site(at)}
    assert sites and len(sites) < len(around) * 0.1
    assert sites == {at: hexes.Grid(vallarith(), 'fixed').site(at) for at in sites}
    for at in sites:
        cell = board.cell(at)
        assert cell['terrain'] != 'water' and not cell['road'] and not cell['place']
    assert {site['kind'] for site in sites.values()} <= {'ruin', 'shrine', 'cave', 'lair', 'battlefield', 'camp',
                                                         'hamlet'}


def test_a_walk_stops_at_a_site_it_comes_upon_but_not_at_one_it_knows():
    board = hexes.Grid(vallarith(), 'fixed')
    at = site_hexes(board, True)[0]
    legs = [{'from': [0, 0], 'to': [1, 0]}, {'from': [1, 0], 'to': list(at)}, {'from': list(at), 'to': [9, 9]}]
    cut, site = board.came_upon(legs, set())
    assert cut == legs[:2] and site['name'] == board.site(at)['name']
    assert board.came_upon(legs, {at}) == (legs, None)


def out_in_the_wild(app, at: tuple[int, int]):
    with app.state.database.connect(write=True) as connection:
        # The campaign row may not exist yet when no story was started, and the seed would then be a new one.
        connection.execute("INSERT INTO story_campaign (id, seed) VALUES (1, 'fixed') "
                           "ON CONFLICT(id) DO UPDATE SET seed='fixed'")
        # Likewise the story clock: without it, the walk's daylight would come from the wall clock.
        connection.execute("INSERT INTO story_clock (id, at) VALUES (1, '2026-10-05T09:00:00') "
                           "ON CONFLICT(id) DO NOTHING")
        connection.execute("UPDATE story_scene SET city_id='vallarith-road', place_id='the-wilds' WHERE id=1")
        connection.execute("INSERT INTO story_position (id, map, q, r, believed_q, believed_r) "
                           "VALUES (1, 'vallarith', ?, ?, ?, ?)", (*at, *at))


def test_searching_a_hex_turns_up_what_is_hidden_there(client, connected, provider, app):
    begin(client)
    board = hexes.Grid(vallarith(), 'fixed')
    at = site_hexes(board, False)[0]
    out_in_the_wild(app, at)
    app.state.dice = Road()
    provider.replies = [[Chunk('Found it.'), Chunk('', 'stop')]]
    tell(client, 'I search the area carefully.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert f"finds {board.site(at)['name']}" in narrator
    cells = {(cell['q'], cell['r']): cell for cell in ok(client.get('/api/story'))['map']['hexes']}
    assert cells[at]['site'] == board.site(at)['name']
    # And a site found is somewhere to set out for.
    provider.replies = [[Chunk('Back to Kingswood.'), Chunk('', 'stop')]]
    tell(client, 'I set out for Kingswood.', 'story-0002')
    provider.replies = [[Chunk('Back to it.'), Chunk('', 'stop')]]
    tell(client, f"I head back to {board.site(at)['name']}.", 'story-0003')
    story = ok(client.get('/api/story'))
    assert story['scene']['place']['id'] == 'the-wilds' and (story['map']['at']['q'], story['map']['at']['r']) == at
    assert f"Here: {board.site(at)['name']}" in provider.requests[-1]['system']


def test_lower_intensity_leaves_out_sites_it_does_not_allow_and_a_found_site_stays_as_found(app):
    board = hexes.Grid(vallarith(), 'fixed')
    around = hexes.ring(board.places['kingswood'], 25)
    gentle = dict.fromkeys(('violence', 'sex', 'horror', 'cruelty', 'drugs'), 1)
    harsh = [at for at in around if (site := board.site(at)) and site['kind'] == 'lair']
    assert harsh, 'some lair near Kingswood to leave out'
    softer = [board.site(at, gentle) for at in around]
    assert all(site is None or site['kind'] != 'lair' for site in softer if site)
    assert any(softer), 'the gentler table still has ruins, camps and hamlets'
    with app.state.database.connect(write=True) as connection:
        hexes.find_site(connection, board, harsh[0], board.site(harsh[0]))
        # Found at full intensity, it is still the lair after the levels go down.
        assert hexes.found_sites(connection, board)[harsh[0]]['kind'] == 'lair'


def test_a_hamlet_found_out_in_the_wild_is_a_place_of_its_own_on_the_road(client, connected, provider, app):
    begin(client)
    board = hexes.Grid(vallarith(), 'fixed')
    at = next(at for radius in range(2, 30) for at in hexes.ring(board.places['kingswood'], radius)
              if (site := board.site(at)) and site['kind'] == 'hamlet')
    hamlet = board.site(at)
    beside = next(other for other in hexes.neighbours(*at) if board.cell(other)['terrain'] != 'water'
                  and not board.cell(other)['place'] and not board.site(other))
    out_in_the_wild(app, beside)
    with app.state.database.connect(write=True) as connection:
        hexes.find_site(connection, board, at, hamlet)
        connection.execute("INSERT INTO story_map (node_id, visited) VALUES ('kingswood', 1)")
    app.state.dice = Road(99)
    provider.replies = [[Chunk('Smoke from a few chimneys.'), Chunk('', 'stop')]]
    tell(client, f"I head over to {hamlet['name']}.", 'story-0001')
    story = ok(client.get('/api/story'))
    place = story['scene']['place']
    assert place['id'] == hexes.hamlet_id(at) and place['name'] == hamlet['name']
    assert (story['map']['at']['q'], story['map']['at']['r']) == at
    assert f"Here: {hamlet['name']}" in provider.requests[-1]['system']
    # Playtest: somebody lives there.
    assert story['scene']['around']
    # It is somewhere one can leave again by road or across country.
    provider.replies = [[Chunk('Back to Kingswood.'), Chunk('', 'stop')]]
    tell(client, 'I set out for Kingswood.', 'story-0002')
    assert ok(client.get('/api/story'))['scene']['place']['id'] != hexes.hamlet_id(at)


def test_a_walk_for_an_hour_stops_after_an_hour_and_a_road_encounter_keeps_to_the_road():
    assert travel.walking_hours('I keep going north for an hour or so.') == 1
    assert travel.walking_hours('We walk west for 30 minutes.') == 0.5 and travel.walking_hours('I head north.') is None
    cyrel = vallarith()['encounters']['kingdom-of-cyrel']
    off_road = {'danger': 'high', 'hours': 10, 'region': 'kingdom-of-cyrel'}
    # Road(1): the encounter happens, and the pick takes the first entry that fits.
    entry = travel.encounter_on(vallarith(), [off_road], True, Road(1))['entry']
    assert entry.get('where') == 'wild' and entry in cyrel
    on_road = travel.encounter_on(vallarith(), [off_road | {'road': True}], True, Road(1))['entry']
    assert on_road.get('where') != 'wild'


def test_striking_out_for_an_hour_walks_about_an_hour_and_rolls_nothing_for_the_walking(client, connected, provider,
                                                                                         app):
    begin(client)
    planned = strike(app, 'I set out north for an hour.')
    assert planned['legs'] and (sum(leg['hours'] for leg in planned['legs'][:-1]) < 1)
    app.state.dice = Road(99)
    provider.replies = [[Chunk('North.'), Chunk('', 'stop')]]
    tell(client, 'I strike out north-east.', 'story-0001')
    with app.state.database.connect() as connection:
        user = connection.execute("SELECT id FROM story_messages WHERE role='user' ORDER BY created_at DESC").fetchone()
        stats = {roll['stat'] for roll in turn.saved(connection, user['id'])}
    # Striking out is no attack, and walking no feat of strength: only the journey's own rolls.
    assert 'Vitality' not in stats


def test_lost_out_in_the_wild_a_day_s_setting_out_can_bring_the_bearings_back(client, connected, app):
    begin(client)
    board = hexes.Grid(vallarith(), 'fixed')
    at = next(other for other in hexes.ring(board.places['kingswood'], 4) if board.cell(other)['terrain'] == 'hills'
              and not board.site(other))
    out_in_the_wild(app, at)
    with app.state.database.connect(write=True) as connection:
        connection.execute('UPDATE story_position SET believed_q=believed_q+2 WHERE id=1')
        planned = travel.plan(connection, 'vallarith-road', 'the-wilds', 'I head south.', Road())
    # With a view from the hills it is easy.
    assert planned['regain'] == {'difficulty': 'easy'}
    legs = [{'from': list(at), 'to': [at[0], at[1] + 1]}]
    roll = {'threat': travel.STILL_LOST}
    with app.state.database.connect() as connection:
        lines = []
        kept = travel.belief(connection, vallarith(), board, planned, legs, [roll | {'band': 'failure'}], lines)
        assert kept == (at[0] + 2, at[1] + 1) and not lines
        found = travel.belief(connection, vallarith(), board, planned, legs, [roll | {'band': 'success'}], lines)
        assert found == (at[0], at[1] + 1) and 'work out where they really are' in lines[0]


def test_a_search_that_goes_as_well_as_it_can_finds_the_nearest_site_close_by(app):
    board = hexes.Grid(vallarith(), 'fixed')
    with app.state.database.connect(write=True) as connection:
        # No story started here: the campaign row may not exist yet, and without it the seed would be a new one.
        connection.execute("INSERT INTO story_campaign (id, seed) VALUES (1, 'fixed') "
                           "ON CONFLICT(id) DO UPDATE SET seed='fixed'")
        levels = hexes.levels(connection)
        at = next(other for radius in range(3, 20) for other in hexes.ring(board.places['kingswood'], radius)
                  if board.cell(other)['terrain'] != 'water' and not board.site(other, levels)
                  and any(board.site(near, levels) for near in hexes.neighbours(*other)))
        plan_ = {'from': 'the-wilds', 'start': list(at), 'search': {'hours': 2}}
        _, plain = travel.search(connection, plan_, [{'threat': travel.NOTHING, 'band': 'success'}])
        assert 'nothing hidden here' in plain[-1]
        _, great = travel.search(connection, plan_, [{'threat': travel.NOTHING, 'band': 'critical_success'}])
        assert 'signs of something 1 hex' in great[0] and 'finds' in great[-1]


def test_a_walk_stops_at_a_hamlet_it_knows_on_the_way_and_waits_for_light_at_night(app):
    board = hexes.Grid(vallarith(), 'fixed')
    at = next(at for radius in range(2, 30) for at in hexes.ring(board.places['kingswood'], radius)
              if (site := board.site(at)) and site['kind'] == 'hamlet')
    # Two hexes short of it, walking its way.
    way, (dq, dr) = next((way, step) for way, step in hexes.DIRECTIONS.items()
                         if all(board.cell((at[0] - dq_ * n, at[1] - dr_ * n))['terrain'] != 'water'
                                and not board.cell((at[0] - dq_ * n, at[1] - dr_ * n))['place']
                                for dq_, dr_ in [step] for n in (1, 2)))
    start = (at[0] - 2 * dq, at[1] - 2 * dr)
    out_in_the_wild(app, start)
    with app.state.database.connect(write=True) as connection:
        # A morning's start on a fixed day: the walk's daylight and weather follow the story clock, not the wall clock.
        story_clock.start(connection, datetime(2026, 10, 5, 8, 0))
        hexes.find_site(connection, board, at, board.site(at))
        planned = travel.plan(connection, 'vallarith-road', 'the-wilds', f'I strike out {way}.', Road())
        assert tuple(planned['legs'][-1]['to']) == at and planned['stop'] == 'site'
        end, opening, lines = travel.ending(connection, vallarith(), planned, planned['legs'], [])
    # Seen from afar, it is reached as somewhere known, not come upon.
    assert end['place'] == hexes.hamlet_id(at) and opening.startswith('You reach') and 'already knew of' in lines[-1]
    late = datetime(2026, 10, 5, 22, 28)
    assert travel.till_light(late, planned) == 7 * 60 + 32
    assert travel.till_light(late.replace(hour=9), planned) == 0
    assert travel.till_light(late, planned | {'dark': True}) == 0


def test_a_day_s_walk_ends_at_dusk_unless_the_line_walks_on_in_the_dark(client, connected, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE story_clock SET at='2026-10-05T17:00:00' WHERE id=1")
    late = strike(app, 'I set out west.')
    assert len(late['legs']) == 1 or sum(leg['hours'] for leg in late['legs']) <= 4
    assert late['stop'] in ('dusk', 'water', 'place', 'site')
    through = strike(app, 'I set out west and walk through the night.')
    assert sum(leg['hours'] for leg in through['legs']) > sum(leg['hours'] for leg in late['legs'])


def river_map(flow: float) -> dict:
    """Ten by six hexes of open country with a river down the middle column, a lake, and a road across it."""
    river = [[5, row - 2] for row in range(6)]  # column 5 as axial hexes
    return {'world': 'riverland', 'nodes': [
        {'id': 'a', 'name': 'A', 'region': 'r', 'city': 'c', 'place': 'p', 'safe': True, 'map': {'x': 0.1, 'y': 0.3}},
        {'id': 'b', 'name': 'B', 'region': 'r', 'city': 'c', 'place': 'q', 'safe': True, 'map': {'x': 0.9, 'y': 0.3}}],
        'routes': [{'from': 'a', 'to': 'b', 'hours': 7, 'terrain': 'the mill road', 'danger': 'low'}],
        'regions': {'r': {'danger': 'low'}},
        'hex_map': {'miles': 6, 'legend': {'.': 'plains'}, 'region_legend': {'r': 'r'},
                    'terrain': ['.' * 10] * 6, 'regions': ['r' * 10] * 6,
                    'places': {'a': [1, 2], 'b': [8, -2]},
                    'rivers': [{'id': 'river-1', 'name': 'the Wend', 'cells': river, 'flow': [flow] * 6}],
                    'lakes': [[2, 4]]}}


def test_a_river_takes_an_hour_to_ford_off_the_road_but_not_to_walk_beside():
    board = hexes.Grid(river_map(0.8), 'seed')
    assert board.cell((5, 2))['river']['name'] == 'the Wend' and board.cell((4, 2))['river'] is None
    across = board.step((4, 2), (5, 2))
    assert across['crossing'] == {'river': 'the Wend', 'by': 'wading', 'hours': hexes.FORD_HOURS}
    assert across['hours'] == hexes.TERRAINS['plains']['hours'] + hexes.FORD_HOURS
    # Walking downstream along the bank crosses nothing.
    along = board.step((5, 1), (5, 2))
    assert 'crossing' not in along and along['hours'] == hexes.TERRAINS['plains']['hours']
    # A storm slows the wading too.
    assert board.step((4, 2), (5, 2), 'storm')['hours'] == across['hours'] * hexes.SLOW['storm']


def test_a_road_crosses_a_big_river_on_a_bridge_and_a_small_one_by_a_ford():
    for flow, by in ((0.8, 'bridge'), (0.1, 'ford')):
        board = hexes.Grid(river_map(flow), 'seed')
        legs = board.way(board.places['a'], board.places['b'])
        crossed = [leg for leg in legs if leg.get('crossing')]
        assert len(crossed) == 1 and crossed[0]['road'] and crossed[0]['crossing']['by'] == by
        assert crossed[0]['hours'] == hexes.ROAD_HOURS


def test_a_lake_is_water_and_the_narrator_hears_of_each_crossing():
    board = hexes.Grid(river_map(0.8), 'seed')
    assert board.cell((2, 4))['terrain'] == 'water' and board.cell((2, 4))['river'] is None
    legs = [board.step((4, 2), (5, 2)), board.step((5, 2), (6, 1))]
    assert 'cross the Wend wading across (an hour more' in ' '.join(
        travel.lines_for(river_map(0.8), {'from': 'a'}, legs + [{'to': 'b', 'hours': 1, 'terrain': 'x'}], 0, [], 0))
    bridge = {'crossing': {'river': 'the Wend', 'by': 'bridge', 'hours': 0}}
    ford = {'crossing': {'river': 'Cold Brook', 'by': 'ford', 'hours': 0}}
    assert travel.crossings([bridge, bridge, ford]) == "the Wend by the bridge, and Cold Brook at the road's ford"
