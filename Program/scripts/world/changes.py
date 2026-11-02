"""Wording for the small changes a city goes through. Run `python scripts/world/changes.py` to rewrite the shipped JSON.

`dungeon/world/changes.py` picks when and where a change happens from seeds; this file only says how it reads in
each style of setting. Openings name a new place from two word lists (`first` and `second`, joined by a space) for a
place kind the city already has, so the new place copies an existing one's hours, setting and price level.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'dungeon' / 'world' / 'data' / 'changes.json'


def opening(first, second, summary):
    return {'first': first, 'second': second, 'summary': summary}


MODERN = {
    'openings': {
        'cafe': opening(['Little', 'Second', 'Copper', 'Juniper', 'Paper Lantern', 'Slow Morning', 'Northside',
                         'Golden Hour', 'Blue Door', 'Sparrow'],
                        ['Coffee', 'Coffee Bar', 'Espresso', 'Roasters', 'Coffee House'],
                        'A new cafe with pastries and a few tables by the window.'),
        'restaurant': opening(['Olive', 'Ember', 'Harbor', 'Fig', 'Saffron', 'Lantern', 'Oak', 'Pepper', 'Juniper',
                               'Corner'],
                              ['Kitchen', 'Table', 'Bistro', 'Eatery', 'Noodle House', 'Taqueria', 'Grill'],
                              'A new restaurant that is still finding its regulars.'),
        'bar': opening(['Last', 'Velvet', 'Neon', 'Copper', 'Night', 'Hollow', 'Paper', 'Lucky'],
                       ['Call', 'Room', 'Owl', 'Tap', 'Social', 'Lounge'],
                       'A new bar with a short cocktail list and a loud Friday crowd.'),
        'shopping': opening(['Common', 'Thread', 'Fern', 'Second Hand', 'Odd', 'Good'],
                            ['Goods', 'Supply', 'Vintage', 'Books', 'Market', 'Store'],
                            'A new shop people keep mentioning.'),
        'fitness': opening(['Core', 'Iron', 'Rise', 'Flow', 'Summit', 'Pulse'],
                           ['Studio', 'Gym', 'Climbing', 'Yoga', 'Cycle'],
                           'A new studio running opening-month deals.'),
    },
    'renovation': ['closed for renovation', 'closed for a remodel', 'closed for a refit',
                   'closed for repairs after a burst pipe'],
    'closing': ['closed for good', 'closed when the lease ran out', 'closed after the owners retired',
                'closed; the space is for lease'],
    'roadworks': [{'summary': 'road works on the main street', 'delay': 8},
                  {'summary': 'a water main replacement', 'delay': 10},
                  {'summary': 'repaving with lane closures', 'delay': 6},
                  {'summary': 'utility work with a lane closed', 'delay': 5},
                  {'summary': 'a new bike lane being built', 'delay': 4}],
}

VICTORIAN = {
    'openings': {
        'cafe': opening(['Albion', 'Crown', 'Rose', 'Kingsway', 'Brass', 'Gaslight'],
                        ['Tea Rooms', 'Coffee House', 'Dining Rooms'],
                        'Newly opened tea rooms, much talked of by the neighbours.'),
        'restaurant': opening(['Albion', 'Royal', 'Kingsway', 'Garland', 'Victoria'],
                              ['Chop House', 'Dining Rooms', 'Grill Room', 'Oyster Rooms'],
                              'A newly opened dining room, still finding its custom.'),
        'bar': opening(['Red', 'Old', 'Three', 'Golden', 'Brass'], ['Lion', 'Crown', 'Feathers', 'Anchor', 'Bell'],
                       'A public house lately opened under a new landlord.'),
        'tavern': opening(['Red', 'Old', 'Three', 'Golden'], ['Lion', 'Crown', 'Feathers', 'Anchor'],
                          'A public house lately opened under a new landlord.'),
        'shopping': opening(['Hartley', 'Pemberton', 'Ashby', 'Crane'],
                            ['& Sons', 'Emporium', 'Drapers', 'Booksellers'],
                            'A new shop front, its windows freshly lettered.'),
        'workshop': opening(['Gearing', 'Hartley', 'Crane', 'Copperfield'], ['Works', 'Foundry', 'Instrument Makers'],
                            'A workshop newly set up, its bench still bare.'),
    },
    'renovation': ['closed for refitting', 'shut while the front is rebuilt', 'closed after a chimney fire'],
    'closing': ['shut for good', 'closed when the lease fell in', 'gone; the premises are to let'],
    'roadworks': [{'summary': 'new gas mains being laid', 'delay': 10},
                  {'summary': 'the cobbles taken up for new drains', 'delay': 12},
                  {'summary': 'the bridge closed for repairs', 'delay': 15},
                  {'summary': 'tram rails being relaid', 'delay': 8}],
}

MEDIEVAL = {
    'openings': {
        'tavern': opening(['Green', 'Golden', 'Laughing', 'Wandering', 'Silver'],
                          ['Dragon', 'Goose', 'Hart', 'Boar', 'Kettle'], 'A new alehouse with a bush hung at its door.'),
        'inn': opening(['Green', 'Golden', 'Laughing', 'Wandering'], ['Dragon', 'Goose', 'Hart', 'Boar'],
                       'A new inn that has taken in its first travellers.'),
        'market': opening(['Wool', 'Hay', 'Fish', 'Spice'], ['Stalls', 'Market', 'Row'],
                          'New stalls set out by traders lately come to town.'),
        'workshop': opening(['Weaver', 'Cooper', 'Tanner', 'Chandler'], ['Workshop', 'Yard', 'Shop'],
                            'A craftsman newly set up in town.'),
        'cafe': opening(['Hearth', 'Honey', 'Baker'], ['House', 'Ovens', 'Loaves'],
                        'A new bakehouse that sells warm bread at dawn.'),
        'restaurant': opening(['Hearth', 'Spit', 'Bramble'], ['Cookshop', 'Hall', 'Board'],
                              'A new cookshop selling pies and pottage.'),
    },
    'renovation': ['shut while the roof is rethatched', 'closed for mending after a storm',
                   'closed while the walls are limewashed'],
    'closing': ['shut for good', 'abandoned when its keeper left town', 'closed after a quarrel with the guild'],
    'roadworks': [{'summary': 'the high road torn up for new paving stones', 'delay': 12},
                  {'summary': 'the bridge closed for mending', 'delay': 20},
                  {'summary': 'the ditch beside the road being re-dug', 'delay': 8}],
}

FRONTIER = {
    'openings': {
        'bar': opening(['Silver', 'Lucky', 'Red', 'Golden', 'Prospector’s'], ['Dollar', 'Strike', 'Horseshoe', 'Nugget'],
                       'A saloon that opened with a free first round.'),
        'tavern': opening(['Silver', 'Lucky', 'Red', 'Golden'], ['Dollar', 'Strike', 'Horseshoe', 'Nugget'],
                          'A saloon that opened with a free first round.'),
        'restaurant': opening(['Railroad', 'Miner’s', 'Union', 'Widow Parker’s'], ['Eating House', 'Lunch Room', 'Chop House'],
                              'A new eating house serving beans, biscuits and coffee.'),
        'cafe': opening(['Railroad', 'Union', 'Main Street'], ['Bakery', 'Coffee House'],
                        'A new bakery with coffee on the stove all day.'),
        'shopping': opening(['Hartley', 'Union', 'Pioneer', 'Frontier'], ['Mercantile', 'Dry Goods', 'Outfitters'],
                            'A new store just in from back East.'),
        'inn': opening(['Railroad', 'Grand', 'Union'], ['Hotel', 'House', 'Boarding House'],
                       'A new hotel with a fresh coat of paint on its false front.'),
    },
    'renovation': ['closed while a new front is built', 'shut after a fire scare', 'closed while the floor is relaid'],
    'closing': ['closed for good', 'shut when the owner went bust', 'boarded up; the owner left for the next strike'],
    'roadworks': [{'summary': 'the main street mired after a burst flume', 'delay': 10},
                  {'summary': 'a new rail spur being laid across the road', 'delay': 8},
                  {'summary': 'the boardwalk being rebuilt', 'delay': 4}],
}

JAZZ_AGE = {
    'openings': {
        'cafe': opening(['Busy Bee', 'Majestic', 'Corner', 'Liberty', 'Bluebird', 'Main Street', 'Little Gem'],
                        ['Lunch Counter', 'Soda Fountain', 'Coffee Shop', 'Luncheonette', 'Tea Room'],
                        'A new lunch counter with a marble soda fountain and pie under glass.'),
        'restaurant': opening(['Wilton', 'Columbia', 'Liberty', 'Sunset', 'Rialto', 'Gold Coast', 'Mama Rosa’s'],
                              ['Grill', 'Chop House', 'Cafeteria', 'Oyster Bar', 'Restaurant', 'Spaghetti House'],
                              'A new restaurant with white tablecloths and a fifty-cent blue-plate special.'),
        'bar': opening(['Blue', 'Green', 'Gilded', 'Velvet', 'Hidden', 'Back Room', 'Side Door'],
                       ['Door', 'Parrot', 'Lantern', 'Club', 'Room', 'Cellar'],
                       'A new speakeasy behind an unmarked door; you need the password.'),
        'nightlife': opening(['Moonlight', 'Starlight', 'Paradise', 'Peacock', 'Red Lantern', 'Gilded Cage'],
                             ['Club', 'Ballroom', 'Supper Club', 'Dance Hall', 'Revue'],
                             'A new club with a hot band, a chorus line and a doorman who knows everyone.'),
        'shopping': opening(['Hartwell', 'Kessler', 'Liberty', 'Modern', 'Empire', 'Bon Ton'],
                            ['Dry Goods', 'Haberdashery', 'Millinery', 'Five-and-Dime', 'Department Store'],
                            'A new shop with electric lights in the window and the latest from Paris.'),
        'inn': opening(['Hotel', 'The'], ['Halcyon', 'Linden', 'Wexford', 'Marlowe', 'Garland'],
                       'A new hotel with an elevator, a barbershop off the lobby and a radio in the lounge.'),
        'venue': opening(['Roxy', 'Bijou', 'Palace', 'Orpheum', 'Strand', 'Capitol'],
                         ['Theatre', 'Picture Palace', 'Vaudeville House'],
                         'A new picture palace with a Wurlitzer organ and an usher in braid.'),
    },
    'renovation': ['closed while it is wired for electric light', 'shut after a Prohibition raid',
                   'closed while a new marble front goes up'],
    'closing': ['closed for good', 'padlocked by the Prohibition agents', 'shut when the owner lost everything on the '
                'market'],
    'roadworks': [{'summary': 'the streetcar tracks being relaid', 'delay': 10},
                  {'summary': 'a new subway line being dug under the street', 'delay': 12},
                  {'summary': 'the cobbles being paved over with asphalt', 'delay': 6}],
}

CHANGES = {
    'schema_version': 1,
    'source': {'kind': 'curated', 'title': 'City change wording written for Prospero Dungeon', 'license': 'CC0-1.0',
               'retrieved': '2026-10-05',
               'note': 'Invented names and phrasing for fictional changes; no real business is meant.'},
    'styles': {'modern': MODERN, 'victorian': VICTORIAN, 'medieval': MEDIEVAL, 'frontier': FRONTIER,
               'jazz-age': JAZZ_AGE},
    'eras': {'modern': 'modern', 'future': 'modern', 'other': 'modern', 'victorian': 'victorian',
             'steampunk': 'victorian', 'medieval': 'medieval', 'fantasy': 'medieval', 'frontier': 'frontier',
             'jazz-age': 'jazz-age'},
}

if __name__ == '__main__':
    OUT.write_text(json.dumps(CHANGES, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
