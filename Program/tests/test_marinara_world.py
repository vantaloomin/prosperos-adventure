"""Bring your Marinara world (dungeon/world/marinara.py): a Marinara Engine world map becomes a city and world lore,
with no review step. The sample is small and invented; real exports are private and stay out of the repo."""
import copy

import pytest

from dungeon.world import catalog, marinara, naming

TODAY = '2026-10-12'


def place(id_, parent, name, kind, **extra) -> dict:
    return {'id': id_, 'parentId': parent, 'name': name, 'kind': kind, 'description': f'About {name}.',
            'modelMemory': '', 'awarenessSummary': '', 'icon': '', 'links': [], 'status': 'active',
            'sortOrder': 0, **extra}


def sample() -> dict:
    """Two top regions, districts, a street, a home with a room, a business with floors and rooms, an archived
    place, labelled and unlabelled links, carried lore and one picture."""
    locations = [
        place('city', None, 'Lisbon', 'region', awarenessSummary='A hilly harbour city.'),
        place('alder', 'city', 'Alder Quarter', 'region', placement={'x': 20, 'y': 30},
              links=[{'targetId': 'bright', 'label': 'Tram 4', 'bidirectional': True, 'state': 'available'},
                     {'targetId': 'bright', 'bidirectional': True, 'state': 'available'}]),
        place('lane', 'alder', 'Fennel Lane', 'region', modelMemory='Cobbled and steep.'),
        place('home', 'lane', "Mara's Apartment", 'building'),
        place('bedroom', 'home', "Mara's Bedroom", 'room', modelMemory='Postcards on every wall.'),
        place('kettle', 'alder', 'Copper Kettle', 'place', icon='☕', awarenessSummary='A tiny corner cafe.',
              modelMemory='The owner remembers every order.'),
        place('pier', 'alder', 'Old Pier', 'place', status='archived'),
        place('stall', 'pier', 'Lost Stall', 'place'),
        place('bright', 'city', 'Brightwater', 'region', placement={'x': 70, 'y': 70}),
        place('owl', 'bright', 'Night Owl', 'place', icon='🍸',
              links=[{'targetId': 'board', 'label': 'Hallway', 'bidirectional': True, 'state': 'available'},
                     {'targetId': 'kettle', 'label': 'Secret Tunnel', 'bidirectional': True, 'state': 'hidden'}]),
        place('hall', 'bright', 'Starlight Hall', 'building', icon='🎭'),
        place('tower', 'city', 'Gilded Tower', 'building', placement={'x': 75, 'y': 65}),
        place('floor', 'tower', 'Executive Floor', 'floor'),
        place('board', 'floor', 'Boardroom', 'room'),
        place('cafe', 'floor', 'Tower Cafe', 'place', icon='☕'),
        place('vale', None, 'Outer Vale', 'region', sortOrder=1),
        place('cabin', 'vale', "Wren's Cabin", 'building'),
        place('loft', 'cabin', 'Loft Room', 'room'),
    ]
    return {'format': 'marinara-hierarchical-map', 'formatVersion': 4, 'name': 'Harbourlight, chapter 3',
            'definition': {'schemaVersion': 1, 'locations': locations, 'startingLocationId': 'home'},
            'hierarchyProfile': {'types': [{'id': 'type_shop', 'label': 'Shop', 'baseKind': 'place'}],
                                 'locationTypeIds': {'kettle': 'type_shop', 'owl': 'type_shop'}},
            'portableLore': {'books': [{'entries': [{'keys': ['the Tide'], 'content': 'The tide turns at noon.',
                                                     'constant': False}]}], 'references': []},
            'artwork': [{'filename': 'a.png', 'data': ''}, {'filename': 'b.png', 'data': ''}]}


@pytest.fixture
def made() -> dict:
    return marinara.convert(sample(), TODAY)


def by_name(records: list[dict]) -> dict:
    return {record['name']: record for record in records}


def test_a_world_map_becomes_one_city_that_loads_without_mending(made):
    city = catalog.prepare(made['city'], mend=True)
    assert 'import_notes' not in city
    assert (city['name'], city['timezone'], city['setting'], city['era']) == ('Lisbon', 'Europe/Lisbon', 'original',
                                                                               'modern')
    # The second top region folds in as a neighbourhood; streets fold into theirs.
    assert [hood['name'] for hood in city['neighborhoods']] == ['Alder Quarter', 'Brightwater', 'Outer Vale']
    places = by_name(city['places'])
    assert {name: place['kind'] for name, place in places.items()} == {
        'Copper Kettle': 'cafe', 'Night Owl': 'bar', 'Starlight Hall': 'venue', 'Tower Cafe': 'cafe'}
    assert places['Copper Kettle']['summary'] == 'A tiny corner cafe.'
    assert places['Copper Kettle']['day_parts'] == ['morning', 'afternoon']
    assert places['Night Owl']['day_parts'] == ['evening', 'late']


def test_homes_rooms_and_archived_places_are_never_public_places(made):
    names = {place['name'] for place in made['city']['places']}
    assert not names & {"Mara's Apartment", "Mara's Bedroom", "Wren's Cabin", 'Loft Room', 'Old Pier', 'Lost Stall'}
    assert any("Mara's Apartment (Alder Quarter)" in note for note in made['notes'])
    assert '1 archived place left out.' in made['notes']
    assert '2 pictures not imported.' in made['notes']


def test_a_building_with_rooms_is_an_employer_in_the_nearest_neighbourhood(made):
    employer = by_name(made['city']['employers'])['Gilded Tower']
    assert employer['neighborhood'] == 'brightwater'
    # Mostly offices, with a café on one floor: office work first, the café's too.
    assert employer['careers'] == ['marketing-coordinator', 'barista'] and employer['sector'] == 'business'
    assert 'Inside: Executive Floor, Boardroom.' in employer['summary']
    assert by_name(made['city']['places'])['Tower Cafe']['neighborhood'] == 'brightwater'


def test_labelled_links_between_places_become_transit(made):
    lines = made['city']['transit']
    assert [(line['name'], line['kind']) for line in lines] == [('Tram 4', 'tram')]
    hoods = by_name(made['city']['neighborhoods'])
    assert hoods['Alder Quarter']['transit'] == hoods['Brightwater']['transit'] == ['tram-4']
    assert any('links without a label, hidden, blocked or between rooms' in note for note in made['notes'])


def test_map_positions_become_small_offsets_from_the_centre(made):
    hoods = by_name(made['city']['neighborhoods'])
    alder, bright = hoods['Alder Quarter'], hoods['Brightwater']
    # Up and left on the map is north and west; the two sit about 14 km apart.
    assert alder['lat'] > 0 > alder['lon'] and bright['lat'] < 0 < bright['lon']
    assert 10 < catalog.distance_km(alder, bright) < 20
    assert (hoods['Outer Vale']['lat'], hoods['Outer Vale']['lon']) == (0.0, 0.0)


def test_notes_become_one_world_lorebook_keyed_by_place_names(made):
    book = made['book']
    assert book['name'] == 'Harbourlight, chapter 3' and book['format'] == 'Marinara world map'
    entries = {entry['title']: entry for entry in book['entries']}
    assert entries['Copper Kettle']['keywords'] == ['Copper Kettle']
    assert 'The owner remembers every order.' in entries['Copper Kettle']['text']
    assert entries["Mara's Bedroom"]['text'].startswith("A room in Mara's Apartment, in Alder Quarter.")
    tide = next(entry for entry in book['entries'] if entry['keywords'] == ['the Tide'])
    assert tide['text'] == 'The tide turns at noon.' and tide['enabled']
    assert 'Lost Stall' not in entries


def test_older_bare_definitions_are_read_and_other_files_are_not():
    bare = {'locations': sample()['definition']['locations']}
    assert marinara.detect(bare) and marinara.detect(sample())
    assert not marinara.detect({'locations': [{'id': 'x', 'name': 'X'}]}) and not marinara.detect([])
    made = marinara.convert(bare, TODAY)
    assert made['city']['name'] == 'Lisbon' and not any('pictures' in note for note in made['notes'])


def test_a_city_name_no_zone_knows_keeps_utc():
    value = sample()
    value['definition']['locations'][0]['name'] = 'Port Ellery'
    made = marinara.convert(value, TODAY)
    assert made['city']['timezone'] == 'UTC' and made['city']['id'] == 'port-ellery'
    assert any('uses UTC' in note for note in made['notes'])


def world_books(client) -> list[str]:
    return [book['name'] for book in client.get('/api/lore').json()['books'] if book['world']]


def settle_in(client, world_id: str, city_id: str):
    """Switch to a new world and make its first companion there, as the user does (it starts with none)."""
    assert client.post(f"/api/worlds/{world_id}/switch").status_code == 200
    made = client.post('/api/companion', json={'name': 'Wren', 'timezone': 'Europe/Lisbon', 'home_city': city_id})
    assert made.status_code == 200, made.text


def test_a_city_with_no_country_takes_it_from_its_time_zone_so_names_are_local():
    value = copy.deepcopy(sample())
    value['definition']['locations'][0]['name'] = 'Seoul'
    made = marinara.convert(value, TODAY)
    assert (made['city']['country'], made['city']['timezone']) == ('South Korea', 'Asia/Seoul')
    assert any('so it is South Korea' in note for note in made['notes'])
    assert naming.local_culture(made['city']['country']) == 'korea'
