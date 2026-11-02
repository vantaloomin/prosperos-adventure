"""Havenbrooke in play: the world's own start date, the school a premade starts in, and trips by car or bus."""
from datetime import datetime

from conftest import tell
from test_travel import Road, clock_at, ok, reply

from dungeon import campaign, factions, institutions, packages, tiers, travel
from dungeon.life import cards


def begin(client, premade='michael-reeves', place='nexus-housing'):
    ok(client.put('/api/story/scene', json={'city_id': 'haven', 'place_id': place}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': premade}))


def test_the_package_and_its_engine_data_hang_together(app):
    """With the data folder in use, as in the app: the school is in the package's own engine data."""
    assert 'havenbrooke' in packages.builtin_ids()
    assert tiers.world_of('haven') == tiers.world_of('havenbrooke-road') == 'havenbrooke'
    school = institutions.find('havenbrooke', 'havenbrooke-university')
    assert factions.find('havenbrooke', school['faction'])
    classes = {item['id'] for item in school['classes']}
    for premade in campaign.premades('haven'):
        assert sum(premade['stats'].values()) <= 60
        assert set(premade['enrolled'][0]['classes']) <= classes
    assert cards.problems(cards.deck('havenbrooke')) == []


def test_a_campaign_starts_in_fall_2009_enrolled_in_the_premades_classes(client, app):
    begin(client)
    assert clock_at(app) == datetime(2009, 8, 31, 8)
    journal = ok(client.get('/api/story/journal'))['institutions']
    assert [item['term'] for item in journal] == ['Fall 2009']
    assert {item['id'] for item in journal[0]['classes']} == {'cs-230', 'cs-215', 'bus-210', 'hum-101'}
    # Michael has no car; the kit says how he gets about, as Austin's says he drives.
    carried = {item['item_id'] for item in ok(client.get('/api/story/gear'))['items']}
    assert 'shuttle-pass' in carried and 'truck-keys' not in carried
    begin(client, 'austin-hallward')
    assert 'truck-keys' in {item['item_id'] for item in ok(client.get('/api/story/gear'))['items']}


def test_a_trip_goes_by_car_or_bus_and_eats_nothing_from_the_pack(client, connected, provider, app):
    begin(client)
    app.state.dice = Road(99)
    before = clock_at(app)
    reply(provider)
    tell(client, 'I head to Ithaca.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert (story['scene']['city']['id'], story['scene']['place']['id']) == ('havenbrooke-road', 'ithaca')
    assert (clock_at(app) - before).total_seconds() >= 42 * 60
    journey = provider.requests[-1]['system'].split('## The journey')[1]
    assert 'from Haven to Ithaca by car or bus on Route 34B along the lake: 42 minutes on the road' in journey
    assert 'hungry' not in journey and 'on foot' not in journey
    assert travel.duration(1) == 'an hour' and travel.duration(4.5) == '4.5 hours'


def test_heading_to_class_goes_to_the_room_so_the_class_is_attended(client, connected, provider, app):
    # Playtest m6a: "I head to my first class" left the lead at home, and the class was missed.
    begin(client)
    first = next(item for item in ok(client.get('/api/story/journal'))['institutions'][0]['today'] if item['place_id'])
    reply(provider)
    tell(client, 'I check my schedule and head to my first class of the day.', 'story-0001')
    assert ok(client.get('/api/story'))['scene']['place']['id'] == first['place_id']


def test_going_on_after_class_passes_the_class_first_so_it_is_attended(client, connected, provider, app):
    # Playtest m6b: "After class I go to Commons Coffee" left the room at 08:50, before the 9:00 class.
    begin(client)
    first = next(item for item in ok(client.get('/api/story/journal'))['institutions'][0]['today'] if item['place_id'])
    reply(provider)
    tell(client, 'I head to my first class of the day.', 'story-0001')
    reply(provider)
    tell(client, 'After class I go to Commons Coffee.', 'story-0002')
    with app.state.database.connect() as connection:
        attended = connection.execute('SELECT attended, missed FROM story_attendance').fetchone()
    assert attended['attended'] >= 1 and clock_at(app).time() > datetime.strptime(first['at'], '%H:%M').time()


def woods() -> dict:
    return next(found for found in travel.maps() if found.get('wild', {}).get('id') == 'the-back-woods')


def test_the_woods_are_a_hex_crawl_of_mile_hexes_and_the_roads_stay_roads():
    from dungeon import hexes
    roads = next(found for found in travel.maps() if any(node['id'] == 'haven' for node in found['nodes']))
    assert not hexes.is_hex(roads) and hexes.is_hex(woods())
    # Playtest: the woods once walked on the roads map's grid, as both were keyed by the world.
    assert hexes.key(woods()) != hexes.key(roads) and hexes._grid(hexes.key(woods()), 'seed', None).miles == 1
    board = hexes.Grid(woods(), 'seed')
    around = [board.cell(at) for at in hexes.ring(board.places['ironroot-trailhead'], 15)]
    kinds = {cell['terrain'] for cell in around}
    # Trees, hills, fields, swamp and lakes: no waste or mountains in the Finger Lakes.
    assert 'forest' in kinds and not kinds & {'waste', 'mountains'}
    # A mile of woods is half an hour's walking, not the three hours of a six-mile hex.
    forest = next(cell for cell in around if cell['terrain'] == 'forest')
    assert board.hours(forest, False) == 0.5 and board.text(forest, False) == 'the woods'


def test_whatever_the_seed_no_lake_shuts_a_trailhead_in():
    from dungeon import hexes
    for seed in ('31', '44', '61', 'fixed'):
        board = hexes.Grid(woods(), seed)
        for place in ('ironroot-trailhead', 'riverwalk-end'):
            assert all(board.heading(board.places[place], way, 5, 'clear')[0] for way in hexes.DIRECTIONS)


def test_from_ironroot_a_walk_goes_into_the_woods_and_a_drive_still_takes_the_road(client, connected, provider, app):
    begin(client, place='ironroot-woods')
    app.state.dice = Road(99)
    reply(provider)
    before = clock_at(app)
    tell(client, 'I set out west into the trees.', 'story-0001')
    story = ok(client.get('/api/story'))
    # A ramble into the woods, not a day's march, and the line's own time is the walk's (playtest).
    walked = provider.requests[-1]['system'].split('on foot by ')[1].split(' hours of walking')[0].split(': ')[-1]
    assert (clock_at(app) - before).total_seconds() / 3600 <= float(walked) + 0.6 <= 3
    # No late bus in the woods: the roads' cards keep to the roads.
    with app.state.database.connect() as connection:
        assert not connection.execute("SELECT card_id FROM story_cards WHERE scene='road' AND card_id IS NOT NULL"
                                      ).fetchall()
    assert story['scene']['place']['id'] == 'the-back-woods' and story['map']['hexes']
    narrator = provider.requests[-1]['system']
    assert 'strikes out west from Ironroot Woods' in narrator and '## Out in the wild' in narrator
    reply(provider, 'The truck starts on the second try.')
    tell(client, 'I walk back out and drive to Ithaca.', 'story-0002')
    assert ok(client.get('/api/story'))['scene']['place']['id'] == 'ithaca'


def test_the_narrator_keeps_to_2009_and_a_later_thing_is_flagged(client, connected, provider, app):
    # Ported from Companion's Back when (dungeon/world/decades.py).
    from test_pace import Slow
    begin(client)
    app.state.pace_clock = Slow()
    reply(provider, 'The lounge is half empty.\n\nAcross the room, a girl scrolls Instagram on her phone.')
    tell(client, 'I look around the lounge.', 'story-0001')
    narrator = provider.requests[-1]['system']
    year = narrator.split('## The year: 2009')[1]
    assert 'flip' in year and 'Not yet invented' in year and 'Instagram' in year
    flags = ok(client.get('/api/story'))['messages'][-1]['flags']
    assert [flag['passage'] for flag in flags] == ['Across the room, a girl scrolls Instagram on her phone.']
    assert 'only came in 2010' in flags[0]['why'][0]
