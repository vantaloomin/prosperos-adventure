"""Spots inside places: the kitchen, the terrace, the café on the fifth floor (Hit List #46).

A place or home gets a short list of named spots, used only as detail ("Spent most of it out on the
back patio.", a "Spots here" line for the Story narrator, the map's place card). Nobody walks between
spots and no location is tracked. A city pack may list a place's own spots (`spots` on a place, like
an imported world's rooms); otherwise rules pick two to four by the place's kind, seeded by its id, so
a place always has the same ones. Each spot is written with how a sentence puts someone there
("out on the back patio"); `name` drops that for display ("the back patio").
"""
import re

from dungeon.world import generators

# Spots by place kind, with the preposition that puts someone there.
BY_KIND = {
    'cafe': ('at the window counter', 'at the corner table by the window', 'out on the back patio',
             'at the long shared table', 'in the armchairs at the back'),
    'restaurant': ('at the bar seats', 'in a booth at the back', 'at the table by the window', 'out on the patio',
                   "at the chef's counter"),
    'bar': ('at the end of the bar', 'in the back booths', 'out on the patio', 'by the pool table',
            'in the jukebox corner'),
    'nightlife': ('on the dance floor', 'up on the mezzanine', 'out on the smoking terrace', 'at the side bar'),
    'library': ('in the reading room', 'at the study carrels', "in the children's corner", 'at the periodicals table',
                'in the café on the ground floor'),
    'museum': ('in the main hall', 'in the museum café', 'in the gift shop', 'in the sculpture court',
               'in the top-floor gallery'),
    'park': ('on the bench by the pond', 'out on the big lawn', 'by the playground', 'along the shady path',
             'at the picnic tables'),
    'garden': ('in the rose beds', 'by the fountain', 'in the glasshouse', 'on the bench under the arbour'),
    'market': ('at the fruit stalls', 'at the hot food stands', 'by the flower seller', 'at the back tables'),
    'shopping': ('in the food court', 'by the escalators', 'in the bookshop upstairs', 'at the café on the top floor'),
    'fitness': ('in the weights room', 'on the treadmills', 'in the studio at the back', 'in the changing rooms'),
    'venue': ('in the lobby bar', 'up in the balcony seats', 'near the front of the stage', 'out in the foyer'),
    'stadium': ('in the upper stands', 'at the concourse food stands', 'in the seats behind the goal'),
    'attraction': ('at the viewing deck', 'in the gift shop', 'in the queue at the entrance', 'at the café inside'),
    'landmark': ('on the front steps', 'at the viewpoint', 'by the plaque', 'in the courtyard'),
    'beach': ('down by the water', 'up on the boardwalk', 'at the snack shack', 'by the lifeguard tower'),
    'trail': ('at the lookout', 'at the trailhead', 'by the creek crossing', 'on the bench halfway up'),
    'tavern': ('by the fire', 'at the long table', 'at the bar', 'in the snug at the back'),
    'inn': ('in the common room', 'by the hearth', 'out in the stable yard', 'at the corner table'),
    'temple': ('in the main hall', 'in the courtyard', 'on the front steps', 'in the quiet side chapel'),
    'guildhall': ('in the great hall', 'in the records room', 'out on the front steps'),
    'workshop': ('at the workbench', 'by the forge', 'in the storeroom', 'out front by the door'),
    'square': ('by the fountain', 'on the steps of the old hall', 'at the market corner', 'under the clock'),
    'docks': ('at the end of the pier', 'by the fish sellers', 'on the harbour wall', 'outside the harbour office'),
}
ANYWHERE = ('at the entrance', 'in a quiet corner', 'by the front windows')
# Spots only a modern place has: no jukebox in a 1925 speakeasy, no food court in Grandport.
MODERN_ERAS = {'modern', 'future'}
MODERN_SPOTS = {'in the jukebox corner', 'in the food court', 'by the escalators', 'at the café on the top floor',
                'in the weights room', 'on the treadmills', 'in the studio at the back', 'in the changing rooms',
                'in the museum café', 'in the gift shop', 'at the viewing deck', 'at the café inside',
                'in the queue at the entrance', 'at the concourse food stands', 'at the snack shack',
                'by the lifeguard tower', 'at the study carrels', 'in the café on the ground floor', 'by the playground',
                "at the chef's counter", 'out on the smoking terrace', 'by the pool table', 'in the bookshop upstairs',
                'out on the back patio', 'out on the patio', 'at the long shared table'}
# What an era's places have in their place: stools at a 1925 soda fountain's counter, not a back patio.
ERA_SPOTS = {'jazz-age': {'cafe': ('on a stool at the counter', 'in a booth by the window'),
                          'restaurant': ('on a stool at the counter',),
                          'bar': ('in the back room',)}}
PREPOSITION = re.compile(r'^(?:out on|up on|up in|down by|out in|along|at|in|on|by|under) ', re.IGNORECASE)
LEAD = re.compile(r'^(?:at|in|on|by|out|up|down|along|under|inside|near) ', re.IGNORECASE)
SENTENCES = ('Spent most of it {where}.', 'Ended up {where}.', 'Settled down {where} for a while.')
HOME_SENTENCES = ('Mostly {where}.', 'Stayed {where} for most of it.')
# Which room an activity at home happens in, when the home has it.
HOME_ROOMS = {'home-cooking': ('in the galley kitchen', 'in the kitchen'),
              'reading': ('in the bay window seat', 'out on the balcony', 'in the living room', 'by the hearth'),
              'nap': ('in the bedroom', 'by the hearth'),
              'chores': ('in the kitchen', 'in the living room'),
              'slow': ('out on the balcony', 'out in the little yard', 'in the living room', 'by the hearth')}
# A home feature that adds a room or nook.
FEATURE_SPOTS = {'balcony': 'out on the balcony', 'galley kitchen': 'in the galley kitchen',
                 'bay window': 'in the bay window seat', 'hearth': 'by the hearth', 'little yard': 'out in the little yard',
                 'clawfoot tub': 'in the bath'}
SHARE = 0.3
# Features only an old-world home has (dungeon/life/home.py FEATURES[False]).
OLD_WORLD = ('hearth', 'low beams', 'creaky stair')
WORKING = {'steady-shift', 'busy-shift', 'library', 'study-cafe'}
LIMIT = 8


def name(spot: str) -> str:
    """'out on the back patio' -> 'the back patio'."""
    return PREPOSITION.sub('', spot)


def placed(spot: str) -> str:
    """A pack's plain spot name with a preposition: 'the café on L5' -> 'at the café on L5'."""
    return spot if LEAD.match(spot) else f'at {spot}'


def for_place(place: dict, era: str | None = 'modern') -> list[str]:
    """Two to four spots for a place (any dict with id, kind and maybe spots), the same every time, fitting the
    city's era."""
    own = [placed(spot.strip()) for spot in place.get('spots') or () if spot and spot.strip()]
    if own:
        return own[:LIMIT]
    options = list(BY_KIND.get(place.get('kind', ''), ANYWHERE))
    if (era or 'modern') not in MODERN_ERAS:
        options = [spot for spot in options if spot not in MODERN_SPOTS] + \
            list(ERA_SPOTS.get(era, {}).get(place.get('kind', ''), ())) or list(ANYWHERE)
    count = 2 + int(generators.unit(place.get('id', ''), 'spot-count') * 3)
    ranked = sorted(options, key=lambda spot: generators.unit(place.get('id', ''), 'spot', spot))
    return ranked[:min(count, len(options))]


def for_home(home: dict | None) -> list[str]:
    """The rooms of a home item (dungeon/life/home.py): the basics plus any its features add."""
    if not home:
        return []
    features = ' '.join(home.get('features') or ()).lower()
    modern = not any(word in features for word in OLD_WORLD)
    basics = ['in the kitchen', 'in the living room', 'in the bedroom'] if modern else ['by the hearth', 'in the bedroom']
    if home.get('bedrooms') == 'studio':
        basics = ['in the kitchen corner', 'by the window']
    extra = [spot for word, spot in FEATURE_SPOTS.items() if word in features]
    if 'in the galley kitchen' in extra:
        basics = [spot for spot in basics if spot != 'in the kitchen']
    return list(dict.fromkeys(basics + extra))


def names(spots: list[str]) -> list[str]:
    return [name(spot) for spot in spots]


def sentence(entry: dict, seed: str, home: dict | None = None, era: str | None = 'modern') -> str:
    """Now and then a short detail for an agenda entry: where in the place (or at home) it happened.
    Empty most of the time, and always when the entry has no place and nothing fits at home."""
    if generators.unit(seed, 'inside') >= SHARE:
        return ''
    place = entry.get('place')
    if place:
        spot = generators.pick(seed, 'inside-spot', for_place(place, era))
        return generators.pick(seed, 'inside-line', list(SENTENCES)).format(where=spot) if spot else ''
    rooms = set(for_home(home))
    fitting = [room for room in HOME_ROOMS.get(entry.get('activity', ''), ()) if room in rooms]
    if not fitting:
        return ''
    return generators.pick(seed, 'inside-line', list(HOME_SENTENCES)).format(where=fitting[0])


def touch(entry: dict | None, seed: str, home: dict | None = None, era: str | None = 'modern') -> dict | None:
    """The entry with a spot detail added to its summary, when one is drawn. An entry another hook
    already added to (a belonging, a home change) is left alone, so a summary never piles up details."""
    if not entry or entry.get('home') or entry.get('wardrobe') or entry.get('inside') or entry.get('activity') in WORKING:
        return entry
    line = sentence(entry, seed, home, era)
    if not line:
        return entry
    return {**entry, 'summary': f"{entry['summary'].rstrip()} {line}", 'inside': line}
