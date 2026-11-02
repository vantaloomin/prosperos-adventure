"""Away from Haven: every Havenbrooke travel node that is not Haven itself, as places of one city, so a trip can end
anywhere on the travel map (docs/story.md "Journeys"), like Vallarith's Road. Each town has where one arrives and
somewhere to eat. Run `python scripts/world/havenbrooke_road.py` to rewrite it."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'world'))
import haven  # noqa: E402 - away from Haven shares its money, names, climate and prices

OUT = ROOT / 'dungeon' / 'world' / 'data' / 'cities' / 'havenbrooke-road.json'
SRC = haven.SRC
ALL_DAY = ('morning', 'afternoon', 'evening', 'late')

# The town (a neighborhood here), where it is, and what it is like.
TOWNS = {
    'ithaca-town': ('Ithaca', 42.44, -76.5, 'Forty minutes southwest of Haven: gorges, two colleges, the bus '
                    'station, and restaurants that charge more than fifteen dollars an entree.',
                    ['college-town', 'shopping', 'gorges']),
    'seneca-shore': ('Seneca Lake', 42.6, -76.9, 'An hour west: rented lake houses with loose dock boards, cold '
                     'water, wineries and cheap fireworks.', ['lake', 'summer', 'wineries']),
    'syracuse-city': ('Syracuse', 43.05, -76.15, 'Ninety minutes north: the Amtrak station, the airport and the '
                      'malls.', ['city', 'trains', 'airport']),
    'manhattan': ('New York City', 40.75, -73.99, 'Four and a half hours by bus: the supernatural fashion houses, '
                  'The Veil, WESC and the firms everyone wants to work for.', ['big-city', 'fashion', 'media']),
    'back-bay': ('Boston', 42.35, -71.08, 'Old coven money, Brahmin witch families and the ritual consultancies, '
                 'six hours east.', ['city', 'covens', 'old-money']),
    'pennsylvania-suburbs': ('the Kessler suburbs', 40.3, -76.6, 'Suburban Pennsylvania, five hours south: cul-de-sacs, '
                             'a registry pipeline and the Kessler and Hallward houses three doors apart.',
                             ['suburbs', 'home', 'family']),
}


def stop(id, name, kind, town, summary, spots, cuisine='', cost='free', setting='outdoor'):
    return {'id': id, 'name': name, 'kind': kind, 'neighborhood': town, 'summary': summary, 'tags': ['travel'],
            'cost': cost, 'setting': setting, 'good_for': ['solo', 'friends', 'date'], 'day_parts': list(ALL_DAY),
            'seasons': [], 'cuisine': cuisine, 'spots': spots, 'source': SRC}


# Each node's arrival place (its id is the node's) and a place to eat.
PLACES = [
    stop('ithaca', 'the Ithaca bus station', 'square', 'ithaca-town', 'The Greyhound and Shortline station on '
         'West State Street, where the Havenbrooke shuttle drops off.', ['the ticket window', 'the curb']),
    stop('ithaca-commons', 'the Ithaca Commons', 'restaurant', 'ithaca-town', 'A pedestrian street of cafes, '
         'bookstores and restaurants, busy on any night with students from three schools.', ['the benches'],
         'american', '$$', 'mixed'),
    stop('seneca-lake', 'the lake house', 'landmark', 'seneca-shore', 'A rented house on the east shore with a '
         'screened porch, a dock with two loose boards and a grill nobody cleaned.', ['the dock', 'the porch',
                                                                                        'the fire pit']),
    stop('lakeside-winery', 'a lakeside winery', 'bar', 'seneca-shore', 'A tasting room with a deck over the '
         'vineyard: five pours for eight dollars and a view of the whole lake.', ['the deck'], 'wine', '$$', 'mixed'),
    stop('syracuse', 'the Syracuse train station', 'square', 'syracuse-city', 'The Regional Transportation '
         'Center, where Amtrak and the long-distance buses stop.', ['the platform', 'the waiting room']),
    stop('syracuse-diner', 'a station diner', 'restaurant', 'syracuse-city', 'A diner across from the station that '
         'feeds people waiting for the 6:10 to New York.', ['the counter'], 'diner', '$', 'indoor'),
    stop('new-york', 'Port Authority', 'square', 'manhattan', 'The bus terminal on Eighth Avenue, where the '
         'upstate buses come in, loud and fluorescent at any hour.', ['the gates', 'the escalators', 'Eighth Avenue']),
    stop('midtown-deli', 'a Midtown deli', 'restaurant', 'manhattan', 'A twenty-four-hour deli with a hot bar and '
         'sandwiches the size of a textbook.', ['the hot bar'], 'deli', '$', 'indoor'),
    stop('boston', 'South Station', 'square', 'back-bay', 'The train and bus station at the edge of the '
         'financial district.', ['the concourse', 'the bus gates']),
    stop('boston-pub', 'a Boston pub', 'bar', 'back-bay', 'A narrow pub near the station with low ceilings and a '
         'witch behind the bar who knows the Corwins.', ['the snug'], 'pub food', '$$', 'indoor'),
    stop('kessler-hometown', 'the Kessler house', 'landmark', 'pennsylvania-suburbs', "Deirdre Kessler's house on a "
         'cul-de-sac, with the twins\' rooms kept as they left them.', ['the kitchen', 'the twins\' rooms',
                                                                         'the driveway']),
    stop('suburb-diner', 'the Route 22 diner', 'restaurant', 'pennsylvania-suburbs', 'The diner where everyone from '
         'the high school ends up at Thanksgiving.', ['the back booth'], 'diner', '$', 'indoor'),
]


def build() -> dict:
    city = haven.CITY
    return {
        'schema_version': 1, 'id': 'havenbrooke-road', 'name': 'away from Haven', 'setting': city['setting'],
        'era': city['era'], 'category': city['category'], 'basis': "The places in Vanta's Havenbrooke a trip from "
        'Haven can reach.', 'region': 'the Northeast', 'country': 'US', 'timezone': city['timezone'],
        'aliases': [], 'summary': 'Out of Haven: a bus station, a lake house, a city or home for the holidays.',
        'home': False, 'town_map': {'style': 'none'},
        'lat': city['lat'], 'lon': city['lon'], 'intensity': city['intensity'], 'currency': city['currency'],
        'rent_period': city['rent_period'], 'speeds': city['speeds'], 'sources': city['sources'],
        'neighborhoods': [{'id': town, 'name': name, 'summary': summary, 'vibe': vibe, 'lat': lat, 'lon': lon,
                           'rent_tier': 'mid', 'housing': ['apartment'], 'walkability': 'medium', 'transit': ['car'],
                           'source': SRC} for town, (name, lat, lon, summary, vibe) in TOWNS.items()],
        'places': PLACES,
        'transit': [item for item in city['transit'] if item['id'] == 'car'],
        'careers': [], 'employers': [], 'career_hubs': [], 'climate': city['climate'], 'annual_events': [],
        'local_color': [], 'names': city['names'], 'prices': city['prices'], 'water': [], 'notables': [],
        'kinds': city['kinds'],
    }


CITY = build()

if __name__ == '__main__':
    OUT.write_text(json.dumps(CITY, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
