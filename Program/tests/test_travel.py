"""Journeys on the travel map (dungeon/travel.py): fog of war, the way and its time and food, road encounters."""
from datetime import datetime

from conftest import Chunk, tell
from test_inventory import begin

from dungeon import travel


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


class Road:
    """The d100s in the order given (a road's encounter roll, then the turn's own), then 50; every other die rolls
    low."""

    def __init__(self, *hundreds):
        self.hundreds = list(hundreds)

    def randint(self, low, high):
        if high == 100:
            return self.hundreds.pop(0) if self.hundreds else 50
        return low

    def choice(self, items):
        return items[0]


def reply(provider, text='The road goes on.'):
    provider.replies = [[Chunk(text), Chunk('', 'stop')]]


def clock_at(app) -> datetime:
    with app.state.database.connect() as connection:
        return datetime.fromisoformat(connection.execute('SELECT at FROM story_clock WHERE id=1').fetchone()[0])


def test_the_map_shows_where_the_character_has_been_and_has_heard_of(client, connected):
    begin(client)
    seen = {place['id']: place for place in ok(client.get('/api/story'))['map']['places']}
    # Kingswood, its roads' ends, and the capitals everybody knows; the rest is fog.
    assert set(seen) == {'kingswood', 'convila', 'eriane', 'abandoned-keep', 'cyrel', 'asania'}
    assert seen['kingswood']['here'] and seen['kingswood']['visited'] and not seen['eriane']['visited']
    roads = {(road['from'], road['to']) for road in ok(client.get('/api/story'))['map']['roads']}
    assert ('kingswood', 'eriane') in roads and ('eriane', 'cyrel') in roads


def test_a_journey_takes_the_road_its_hours_and_the_food_in_the_pack(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_inventory (id, city_id, item_id, qty) VALUES ('b', 'kingswood', 'bread', 1)")
    app.state.dice = Road(99)
    before = clock_at(app)
    reply(provider)
    tell(client, 'I set out for Eriane.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert (story['scene']['city']['id'], story['scene']['place']['id']) == ('vallarith-road', 'eriane')
    assert [message['text'] for message in story['messages'] if message['role'] == 'scene'][-1] == 'You arrive at Eriane.'
    # Twelve hours on foot is two days: a night camped between them, and a day's food each.
    hours = (clock_at(app) - before).total_seconds() / 3600
    assert hours >= 12 + travel.NIGHT_HOURS
    narrator = provider.requests[-1]['system']
    assert '## The journey' in narrator and 'from Kingswood to Eriane on foot by the Cyrel road: 13 hours' in narrator
    assert 'black bread' in narrator.split('## The journey')[1] and 'go hungry' in narrator
    seen = {place['id']: place for place in story['map']['places']}
    assert seen['eriane']['here'] and seen['kingswood']['visited']
    # Telling it again walks no further and eats nothing more.
    arrived = clock_at(app)
    reply(provider, 'The road goes on, again.')
    ok(client.post('/api/story/retry'))
    assert clock_at(app) == arrived
    assert ok(client.get('/api/story'))['scene']['place']['id'] == 'eriane'


def test_a_place_not_on_any_known_road_is_not_reached(client, connected, provider):
    begin(client)
    reply(provider)
    tell(client, 'I head for Bastion.', 'story-0001')
    assert ok(client.get('/api/story'))['scene']['city']['id'] == 'kingswood'
    assert 'does not know the way to Bastion' in provider.requests[-1]['system']


def test_bandits_on_the_road_stop_the_journey_where_they_strike(client, connected, provider, app, monkeypatch):
    begin(client)
    monkeypatch.setattr(travel, 'pick', lambda entries, rng: next(entry for entry in entries if 'Bandits' in str(entry)))
    # The first hex of the road turns up an encounter (1 in 100, under its share of the road's 15), it is the bandits,
    # and the Luck roll fails; the fight is out on the road, and the journey ends at the next place, Eriane.
    app.state.dice = Road(1, 15)
    reply(provider)
    tell(client, 'I set out for Eriane.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert story['scene']['place']['id'] == 'eriane'
    assert {foe['name'] for foe in story['fight']['fight']['foes']} <= {'road bandit 1', 'road bandit 2'}
    narrator = provider.requests[-1]['system']
    assert 'Bandits come out of the ditch' in narrator and 'The journey stops here' in narrator


def test_a_sight_on_the_road_is_woven_in_without_a_roll(client, connected, provider, app):
    begin(client)
    app.state.dice = Road(5)
    travel_map = next(found for found in travel.maps() if found['world'] == 'vallarith')
    sight = travel_map['encounters']['kingdom-of-cyrel'][0]
    planned = travel.travelled({'legs': [{'from': 'kingswood', 'to': 'eriane', 'hours': 12, 'terrain': 'the Cyrel road',
                                          'danger': 'low'}], 'encounter': {'leg': 0, 'entry': sight}}, [])
    assert planned[1] == [f"On the Cyrel road: {sight['text']}"]


def test_a_modern_world_sets_out_by_car_or_bus():
    haven = next(item for item in travel.maps() if any(node['id'] == 'haven' for node in item['nodes']))
    assert travel.destination(haven, 'haven', 'I borrow a car and drive to Ithaca for the afternoon.')['id'] == 'ithaca'
    assert travel.destination(haven, 'haven', 'I take the bus to Syracuse.')['id'] == 'syracuse'
