"""Journeys on the travel map (requirements "Time and travel"; docs/story.md "Journeys").

Each world has a travel map (world/data/travel/<world>.json): places joined by roads, each road with its hours on
foot, its terrain and its danger, and each region with its road encounters. A place is a whole town (its city and
the place one arrives at) or a place on the Road (world/data/cities/vallarith-road.json) for one not yet built out.

- **Fog of war.** The character knows the places they have been, the places next to those, and the famous ones
  everybody has heard of (a capital). The rest stay hidden until found.
- **A journey is decided before the narrator writes it.** "I set out for Eriane" plans the way by the shortest
  roads and rolls each road against its danger. A road that turns up an encounter draws one from the region's
  table: a sight or a meeting the narrator weaves in, or a danger to get past (a Luck roll, like a dangerous place
  in town); one that brings foes starts a fight where it happens, and the journey stops there.
- **Every road costs time and food.** Walking takes the road's hours, nights on the road pass in camp, and each day
  eats one food from the pack (bread, dried meat, cheese); without it the character goes hungry. A modern world's map
  says how people get about instead (`by`: "car or bus", Havenbrooke's), and with no `food` a trip eats nothing.

The places known are game state, branched with the story (dungeon/timeline.py SAVED); each line's journey is kept
with it, so telling the turn again changes nothing.
"""
import heapq
import math
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from dungeon import hexes, inventory, sworn, world_data
from dungeon.database import decode, encode, many, optional

MAPS = Path(__file__).parent / 'world' / 'data' / 'travel'
STAT = 'Luck'
BITES = ('critical_failure', 'failure', 'failure_upside')
NIGHT_HOURS = 14
STOPPED = 'The journey stops here'
LOST_STAT = 'Mind'
SEARCHING = re.compile(r'\b(search\w*|scour\w*|explor\w*|look(s|ing)? around|poke around|scout\w*|comb(s|ing)? the)\b',
                       re.I)
NOTHING = 'The search turns up nothing the character can find.'
# How far a search that goes as well as it can ranges for a site, in hexes.
SEARCH_REACH = 3
# Walking across country waits for first light at night, unless the line means to walk in the dark.
DAWN, DUSK = 6, 21
DARK = re.compile(r'\b(through the night|in the dark|by night|by moonlight|by torchlight|at night|tonight)\b',
                  re.I)
STILL_LOST = 'The character still cannot work out where they are.'
# How hard it is to get one's bearings back when lost, by the land one is in: easy with a view, hard under trees.
BEARINGS = {'hills': 'easy', 'mountains': 'easy', 'plains': 'normal', 'waste': 'normal', 'forest': 'hard',
            'marsh': 'hard'}
# "I walk north for an hour or so": how long a walk across country goes on for, when the line says.
FOR_A_WHILE = re.compile(r'\bfor (?:about |around |roughly |maybe )?(?P<count>an?|one|two|three|four|five|six|seven|'
                         r'eight|a couple of|a few|half an?|\d+(?:\.\d+)?) (?P<unit>hours?|minutes?|days?)\b', re.I)
COUNTS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
          'a couple of': 2, 'a few': 3, 'half a': 0.5, 'half an': 0.5}
# Striking out across country in a direction (a hex crawl): from a town it takes a word for leaving; out in the wild
# any word for going will do.
COMPASS = re.compile(r'\b(?:(north|south)[- ]?(east|west)?|(east|west))(?:wards?|ward)?\b', re.I)
LEAVING = re.compile(r'\b(set(s|ting)? (out|off)|strike|strikes|striking|struck|head\w* out|leave|leaves|leaving|'
                     r'cross(es|ing)? country|travel\w*|journey\w*|march\w*|out of (town|the town|the city))\b', re.I)
# Setting out, on foot or (in a modern world such as Havenbrooke) by car, bus or train.
GOING = re.compile(r'\b(travel\w*|set(s|ting)? (out|off)|head\w*|ride|rides|riding|walk\w*|journey\w*|march\w*|'
                   r'make (my|our|their) way|go|goes|going|leave|leaves|leaving|return\w*|drive|drives|driving|'
                   r'drove|take (a|the) (bus|train)|catch (a|the) (bus|train))\b', re.I)


@world_data.memo
def maps() -> tuple[dict, ...]:
    return tuple(world_data.read('travel', key) for key in world_data.keys('travel'))


def nodes(travel_map: dict) -> dict[str, dict]:
    """The map's places, and its stand-in for out in the wild (`wild`) if it has one."""
    found = {node['id']: node for node in travel_map['nodes']}
    return found | ({travel_map['wild']['id']: travel_map['wild']} if travel_map.get('wild') else {})


def is_wild(travel_map: dict, node_id: str) -> bool:
    return bool(travel_map.get('wild')) and travel_map['wild']['id'] == node_id


def nodes_at(city_id: str, place_id: str) -> list[tuple[dict, dict]]:
    """Every travel map and place on it the scene is at, the closest first: the place itself (on the Road, a trailhead
    into Havenbrooke's woods) or out in the wild, then the whole town."""
    exact, town = [], []
    for travel_map in maps():
        wild = travel_map.get('wild')
        if wild and wild['city'] == city_id and (wild['place'] == place_id or place_id.startswith('hamlet-')):
            exact.append((travel_map, wild))
        elif found := next((node for node in travel_map['nodes'] if node['city'] == city_id
                            and node['place'] == place_id), None):
            exact.append((travel_map, found))
        elif found := next((node for node in travel_map['nodes'] if node['city'] == city_id
                            and node['city'] != 'vallarith-road'), None):
            town.append((travel_map, found))
    return exact + town


def node_at(city_id: str, place_id: str) -> tuple[dict, dict] | None:
    """The travel map and the place on it where the scene is (the closest of nodes_at)."""
    found = nodes_at(city_id, place_id)
    return found[0] if found else None


def neighbours(travel_map: dict, node_id: str) -> list[tuple[str, dict]]:
    return [(route['to'] if route['from'] == node_id else route['from'], route) for route in travel_map['routes']
            if node_id in (route['from'], route['to'])]


def here_hex(connection, travel_map: dict, board: hexes.Grid, node_id: str) -> tuple[int, int]:
    """The hex the character is in: their place's, or where they stopped out in the wild."""
    if is_wild(travel_map, node_id) and (where := hexes.position(connection, board)):
        return where['at']
    return board.places.get(node_id) or next(iter(board.places.values()))


def region_of(connection, travel_map: dict, node: dict) -> str:
    """The region the character is in: their place's, or out in the wild the region of their hex."""
    if is_wild(travel_map, node['id']) and hexes.is_hex(travel_map):
        board = hexes.grid(connection, travel_map)
        if (where := hexes.position(connection, board)) and (region := board.cell(where['at'])['region']):
            return region
    return node['region']


def walked(connection, travel_map: dict, plan_: dict, legs: list[dict]):
    """The places and, on a hex crawl, the hexes the walked legs went through."""
    if not is_wild(travel_map, plan_['from']):
        visit(connection, travel_map, plan_['from'])
    if plan_.get('mode') != 'hex':
        for leg in legs:
            visit(connection, travel_map, leg['to'])
        return
    board = hexes.grid(connection, travel_map)
    hexes.reveal(connection, board, [tuple(plan_['start']), *(tuple(leg['to']) for leg in legs)])
    for leg in legs:
        if leg.get('place'):
            visit(connection, travel_map, leg['place'])


def visit(connection, travel_map: dict, node_id: str):
    """The character has been here, and has heard of every place one road away."""
    connection.execute('INSERT INTO story_map (node_id, visited) VALUES (?, 1) ON CONFLICT(node_id) DO UPDATE SET '
                       'visited=1', (node_id,))
    for other, _ in neighbours(travel_map, node_id):
        connection.execute('INSERT OR IGNORE INTO story_map (node_id, visited) VALUES (?, 0)', (other,))


def known(connection, travel_map: dict, here: str) -> dict[str, bool]:
    """Each place the character knows of, and whether they have been there; where they are counts as visited. On a
    hex crawl, a place in a hex they have seen is known too."""
    rows = {row['node_id']: bool(row['visited']) for row in many(connection, 'SELECT * FROM story_map')}
    rows[here] = True
    for other, _ in neighbours(travel_map, here):
        rows.setdefault(other, False)
    if hexes.is_hex(travel_map):
        board = hexes.grid(connection, travel_map)
        for at in hexes.seen(connection, board, here_hex(connection, travel_map, board, here)):
            if at in board.at_place:
                rows.setdefault(board.at_place[at], False)
    return {node['id']: rows.get(node['id'], False) for node in travel_map['nodes']
            if node['id'] in rows or node.get('famous')}


def find(node_id: str) -> tuple[dict, dict]:
    return next((travel_map, node) for travel_map in maps() for node in nodes(travel_map).values()
                if node['id'] == node_id)


def bare(name: str) -> str:
    return re.sub(r'^the\s+', '', name, flags=re.I)


def destination(travel_map: dict, here: str, text: str) -> dict | None:
    """The place a line sets out for ("I set out for Eriane"), if it names one."""
    going = GOING.search(text)
    if not going:
        return None
    after = text[going.end():]
    found = [(match.start(), node) for node in travel_map['nodes'] if node['id'] != here
             if (match := re.search(rf'(?<![\w-]){re.escape(bare(node["name"]))}(?![\w-])', after, re.I))]
    return min(found, key=lambda pair: pair[0])[1] if found else None


def way(travel_map: dict, start: str, goal: str) -> list[dict] | None:
    """The roads from one place to another, shortest in hours, each as {from, to, hours, terrain, danger}."""
    queue, best = [(0, start, [])], {start: 0}
    while queue:
        hours, node, legs = heapq.heappop(queue)
        if node == goal:
            return legs
        for other, route in neighbours(travel_map, node):
            total = hours + route['hours']
            if total < best.get(other, math.inf):
                best[other] = total
                heapq.heappush(queue, (total, other, [*legs, route | {'from': node, 'to': other}]))
    return None


def pick(entries: list[dict], rng) -> dict:
    roll, at = rng.randint(1, sum(entry['weight'] for entry in entries)), 0
    for entry in entries:
        at += entry['weight']
        if roll <= at:
            return entry
    return entries[-1]


def threat_text(threat: str | dict) -> str:
    return threat if isinstance(threat, str) else threat['text']


def heading(text: str, wild: bool) -> str | None:
    """The direction a line strikes out in ("I head north-east", "we leave town and walk west"), if it names one; from
    a town it takes a word for leaving, so walking north along a street goes nowhere."""
    if not LEAVING.search(text) and not (wild and GOING.search(text)):
        return None
    found = COMPASS.search(text)
    if not found:
        return None
    if found.group(3):
        return found.group(3).lower()
    return found.group(1).lower() + (f'-{found.group(2).lower()}' if found.group(2) else '')


def encounter_on(travel_map: dict, legs: list[dict], crawl: bool, rng) -> dict | None:
    """The first leg that turns something up, and what: a road's odds are for a day's walking, a hex's are its share
    of a day. An entry's `where` keeps it to the road or to the wild off it (toll-takers keep to the road)."""
    for index, leg in enumerate(legs):
        odds = travel_map['odds'][leg['danger']]
        if rng.randint(1, 100) <= (odds * leg['hours'] / travel_map['hours_a_day'] if crawl else odds):
            region = leg['region'] if crawl else nodes(travel_map)[leg['to']]['region']
            side = 'road' if not crawl or leg.get('road') else 'wild'
            tables = travel_map['encounters']
            candidates = [table for table in (tables.get(region), tables.get(hexes.FRONTIER[0]), *tables.values())
                          if table]
            table = next((kept for table in candidates
                          if (kept := [entry for entry in table if entry.get('where', side) == side])), candidates[0])
            return {'leg': index, 'entry': pick(table, rng)}
    return None


def walking_hours(text: str) -> float | None:
    """How long a line says to walk for ("for an hour or so", "for two hours"), in hours, if it says."""
    found = FOR_A_WHILE.search(text)
    if not found:
        return None
    count = found.group('count').lower()
    number = COUNTS.get(count) or float(count)
    unit = found.group('unit').lower()
    return number / 60 if unit.startswith('minute') else number * 24 if unit.startswith('day') else number


def today(connection, board: hexes.Grid, at: tuple[int, int]) -> str:
    """The weather where the character sets out, on the story clock's day."""
    row = optional(connection, 'SELECT at FROM story_clock WHERE id=1')
    moment = datetime.fromisoformat(row['at']) if row else datetime.now()
    return hexes.weather(board.seed, moment.date().isoformat(), board.cell(at)['region'], moment.month)


def daylight(connection) -> float:
    """The hours of light left for walking from now on the story clock; a walk set out at night waits for first light
    (`till_light`) and has the whole day."""
    row = optional(connection, 'SELECT at FROM story_clock WHERE id=1')
    now = datetime.fromisoformat(row['at']) if row else datetime.now()
    if not DAWN <= now.hour < DUSK:
        return DUSK - DAWN
    return DUSK - now.hour - now.minute / 60


def strike_out(connection, travel_map: dict, here: dict, direction: str, rng, hours: float | None = None,
               dark: bool = False) -> dict:
    """A day's walk across country in one direction, rolled for encounters and for keeping the way: if the character
    loses it, the walk drifts off to one side from there (`astray`), while they believe it went straight."""
    board = hexes.grid(connection, travel_map)
    start = here_hex(connection, travel_map, board, here['id'])
    weather = today(connection, board, start)
    found = hexes.found_sites(connection, board)
    # A walk with no length said goes on for the map's `walk_hours` (a ramble in Havenbrooke's woods), else a day.
    meant = min(travel_map['hours_a_day'], hours or travel_map.get('walk_hours') or travel_map['hours_a_day'])
    # And it ends at dusk, unless the line means to walk on in the dark. A walk of so long takes the step nearest it;
    # dusk is a hard stop.
    budget = meant if dark else min(meant, daylight(connection))
    legs, stop = board.heading(start, direction, budget, weather,
                               about=budget == meant < travel_map['hours_a_day'])
    if stop == 'day' and budget < meant:
        stop = 'dusk'
    elif stop == 'day' and budget < travel_map['hours_a_day']:
        stop = 'enough'
    legs, site = board.came_upon(legs, set(found), hexes.levels(connection))
    stop = 'site' if site else stop
    # A hamlet they know of on the way is somewhere to stop, as a place on the way is.
    if (hamlet := next((index for index, leg in enumerate(legs) if (kept := found.get(tuple(leg['to'])))
                        and kept['kind'] == 'hamlet'), None)) is not None:
        legs, stop = legs[:hamlet + 1], 'site'
    plan_ = {'from': here['id'], 'start': list(start), 'mode': 'hex', 'direction': direction, 'weather': weather,
             'legs': legs, 'stop': stop, 'encounter': encounter_on(travel_map, legs, True, rng)}
    lost = next(((index, difficulty) for index, leg in enumerate(legs)
                 if (difficulty := board.lost_odds(leg, weather))), None)
    if lost:
        index, difficulty = lost
        turns = hexes.ZIGZAG.get(direction) or (
            hexes.TURNS[(hexes.TURNS.index(direction) - 1) % 6], hexes.TURNS[(hexes.TURNS.index(direction) + 1) % 6])
        veer = turns[rng.randint(0, 1)]
        left = budget - sum(leg['hours'] for leg in legs[:index + 1])
        drift, drift_stop = board.heading(tuple(legs[index]['to']), veer, left, weather) if left > 0 else ([], 'day')
        astray, strayed_upon = board.came_upon(legs[:index + 1] + drift, set(found))
        plan_['lost'] = {'leg': index, 'difficulty': difficulty, 'terrain': legs[index]['terrain'],
                         'astray': astray, 'stop': 'site' if strayed_upon else drift_stop}
    return plan_


def plan(connection, city_id: str, place_id: str, text: str, rng=None) -> dict | None:
    """The journey a line sets out on, its roads rolled for encounters: None when it goes nowhere on the map, or the
    character is held prisoner (dungeon/combat.py captors)."""
    held = optional(connection, 'SELECT captors FROM story_wounds WHERE id=1')
    if held and held['captors']:
        return None
    rng = rng or random.SystemRandom()
    # At a trailhead into Havenbrooke's woods, a drive to Ithaca still goes by the roads.
    for travel_map, here in nodes_at(city_id, place_id):
        if (planned := plan_on(connection, travel_map, here, text, rng)) is not None:
            return planned | regaining(connection, travel_map, here) | ({'dark': True} if DARK.search(text) else {})
    return None


def setting_out(connection, city_id: str, place_id: str, text: str) -> bool:
    """Whether a line sets out on a journey from here (as `plan` would read it, without planning or rolling it): its
    time is the journey's, not a line's (dungeon/story.py received)."""
    for travel_map, here in nodes_at(city_id, place_id):
        if destination(travel_map, here['id'], text) is not None:
            return True
        if not hexes.is_hex(travel_map) or not travel_map.get('wild'):
            continue
        wild = is_wild(travel_map, here['id'])
        if heading(text, wild) or (wild and SEARCHING.search(text)):
            return True
        board = hexes.grid(connection, travel_map)
        if site_named(connection, board, text, here_hex(connection, travel_map, board, here['id'])):
            return True
    return False


def till_light(now: datetime, plan_: dict) -> int:
    """The minutes to wait for first light before walking off across country at night, unless the line set out to
    walk in the dark ("through the night", `plan_['dark']`); 0 by day."""
    if plan_.get('dark') or DAWN <= now.hour < DUSK:
        return 0
    light = now.replace(hour=DAWN, minute=0, second=0, microsecond=0)
    return round(((light if now.hour < DAWN else light + timedelta(days=1)) - now).total_seconds() / 60)


def regaining(connection, travel_map: dict, here: dict) -> dict:
    """Lost out in the wild, each day's setting out is a chance to get one's bearings back (a Mind roll): easier
    with a view from high ground, harder under trees."""
    if not is_wild(travel_map, here['id']) or not hexes.is_hex(travel_map):
        return {}
    board = hexes.grid(connection, travel_map)
    where = hexes.position(connection, board)
    if where is None or where['believed'] == where['at']:
        return {}
    return {'regain': {'difficulty': BEARINGS.get(board.cell(where['at'])['terrain'], 'normal')}}


def regained(plan_: dict, rolls: list[dict]) -> bool:
    return bool(plan_.get('regain')) and any(roll.get('threat') == STILL_LOST and roll['band'] not in BITES
                                             for roll in rolls)


def plan_on(connection, travel_map: dict, here: dict, text: str, rng) -> dict | None:
    """A line's journey on one travel map, from one place on it."""
    goal = destination(travel_map, here['id'], text)
    if goal is None:
        return off_the_map(connection, travel_map, here, text, rng)
    crawl = hexes.is_hex(travel_map)
    legs, start = None, None
    if goal['id'] in known(connection, travel_map, here['id']):
        if crawl:
            board = hexes.grid(connection, travel_map)
            start = here_hex(connection, travel_map, board, here['id'])
            legs = board.way(start, board.places[goal['id']], today(connection, board, start))
        else:
            legs = way(travel_map, here['id'], goal['id'])
    if not legs:
        return {'from': here['id'], 'to': goal['id'], 'unknown': True}
    site = None
    if crawl:
        legs, site = board.came_upon(legs, set(hexes.found_sites(connection, board)), hexes.levels(connection))
    return {'from': here['id'], 'to': goal['id'], 'legs': legs, 'encounter': encounter_on(travel_map, legs, crawl, rng)} | (
        {'mode': 'hex', 'start': list(start)} if crawl else {}) | ({'stop': 'site'} if site else {})


def off_the_map(connection, travel_map: dict, here: dict, text: str, rng) -> dict | None:
    """A line on a hex crawl that names no place on the map: searching the hex the character is in, setting out for
    a site they have found, or striking out in a direction; None for anything else."""
    if not hexes.is_hex(travel_map) or not travel_map.get('wild'):
        return None
    board = hexes.grid(connection, travel_map)
    start = here_hex(connection, travel_map, board, here['id'])
    wild = is_wild(travel_map, here['id'])
    if wild and SEARCHING.search(text) and not GOING.search(text) and not COMPASS.search(text):
        return {'from': here['id'], 'start': list(start), 'mode': 'hex', 'legs': [],
                'search': {'hours': board.hours(board.cell(start), False) or 1, 'difficulty': 'normal'}}
    if site := site_named(connection, board, text, start):
        return journey_to(connection, travel_map, board, here, start, site, rng)
    direction = heading(text, wild)
    return strike_out(connection, travel_map, here, direction, rng, walking_hours(text),
                      bool(DARK.search(text))) if direction else None


def site_named(connection, board: hexes.Grid, text: str, start: tuple[int, int]) -> dict | None:
    """A site the character has found that a line sets out for ("I head back to Hob's Tower")."""
    going = GOING.search(text)
    if not going:
        return None
    after = text[going.end():]
    found = [(match.start(), site) for at, site in hexes.found_sites(connection, board).items() if at != start
             if (match := re.search(rf'(?<![\w-]){re.escape(bare(site["name"]))}(?![\w-])', after, re.I))]
    return min(found, key=lambda pair: pair[0])[1] if found else None


def journey_to(connection, travel_map: dict, board: hexes.Grid, here: dict, start: tuple[int, int], site: dict,
               rng) -> dict:
    """The way to a site the character knows, across country, ending out in the wild at it."""
    legs = board.way(start, (site['q'], site['r']), today(connection, board, start)) or []
    legs, _ = board.came_upon(legs, set(hexes.found_sites(connection, board)), hexes.levels(connection))
    return {'from': here['id'], 'start': list(start), 'mode': 'hex', 'site': site['name'], 'legs': legs,
            'encounter': encounter_on(travel_map, legs, True, rng), 'stop': 'arrived'}


def lost_threat(lost: dict) -> str:
    return f"The character loses their bearings in {lost['terrain']} and drifts off course without knowing it."


def decide(connection, message_id: str, city_id: str, place_id: str, text: str, rng=None) -> list[dict]:
    """The line's journey, planned once, and the rolls it calls for (for the turn's rolls): its danger's, and keeping
    the way across country."""
    row = optional(connection, 'SELECT plan FROM story_journeys WHERE message_id=?', (message_id,))
    journey = decode(row['plan']) if row else plan(connection, city_id, place_id, text, rng)
    if journey is None:
        return []
    if row is None:
        connection.execute('INSERT INTO story_journeys (message_id, plan) VALUES (?, ?)', (message_id, encode(journey)))
    actions = []
    entry = (journey.get('encounter') or {}).get('entry') or {}
    if 'action' in entry:
        actions.append({'action': entry['action'], 'stat': STAT, 'difficulty': entry['difficulty'],
                        'threat': threat_text(entry['threat'])})
    if journey.get('search'):
        actions.append({'action': 'search the area for anything hidden', 'stat': LOST_STAT,
                        'difficulty': journey['search']['difficulty'], 'threat': NOTHING})
    if regain := journey.get('regain'):
        actions.append({'action': 'work out where they are from the sun, the land and the lie of the water',
                        'stat': LOST_STAT, 'difficulty': regain['difficulty'], 'threat': STILL_LOST})
    if lost := journey.get('lost'):
        actions.append({'action': f"keep their bearings in {lost['terrain']}", 'stat': LOST_STAT,
                        'difficulty': lost['difficulty'], 'threat': lost_threat(lost)})
    return actions


def journey(connection, message_id: str) -> dict | None:
    row = optional(connection, 'SELECT plan, lines FROM story_journeys WHERE message_id=?', (message_id,))
    return row and decode(row['plan']) | {'lines': decode(row['lines']) if row['lines'] else None}


def foe_for(text: str) -> dict | None:
    """The foe a road or camp threat brings into a fight (dungeon/combat.py), if it brings one."""
    for travel_map in maps():
        for entries in (*travel_map['encounters'].values(), *travel_map.get('camp', {}).values()):
            for entry in entries:
                threat = entry.get('threat')
                if isinstance(threat, dict) and threat['text'] == text and threat.get('foe'):
                    return threat['foe']
    return None


def bitten(rolls: list[dict], entry: dict) -> bool:
    return any(roll.get('threat') == threat_text(entry['threat']) and roll['band'] in BITES for roll in rolls)


def strayed(plan_: dict, rolls: list[dict]) -> bool:
    lost = plan_.get('lost')
    return bool(lost) and any(roll.get('threat') == lost_threat(lost) and roll['band'] in BITES for roll in rolls)


def travelled(plan_: dict, rolls: list[dict]) -> tuple[list[dict], list[str]]:
    """The roads actually walked (a fight on the road ends the journey where it happens), and what happened on them."""
    legs, encounter = plan_['legs'], plan_.get('encounter')
    if strayed(plan_, rolls):
        legs = plan_['lost']['astray']
        encounter = encounter if encounter and encounter['leg'] < len(legs) else None
    if not encounter:
        return legs, []
    entry, where = encounter['entry'], legs[encounter['leg']]
    if 'action' not in entry:
        return legs, [f"On {where['terrain']}: {entry['text']}"]
    if not bitten(rolls, entry):
        return legs, [f"On {where['terrain']} the character manages to {entry['action']}, and goes on."]
    lines = [f"On {where['terrain']}: {threat_text(entry['threat'])}"]
    if isinstance(entry['threat'], dict) and entry['threat'].get('foe'):
        # On a hex crawl the fight is out in the wild: a journey ends at the next place on the way, a walk across
        # country where the fight is.
        end = encounter['leg'] if plan_.get('mode') != 'hex' or plan_.get('direction') else next(
            (index for index in range(encounter['leg'], len(legs)) if legs[index].get('place')), len(legs) - 1)
        return legs[:end + 1], lines + [f'{STOPPED}, on the road, with a fight on its hands.']
    return legs, lines


def belief(connection, travel_map: dict, board: hexes.Grid, plan_: dict, legs: list[dict], rolls: list[dict],
           lines: list[str]) -> tuple[int, int]:
    """Where the character believes a walk across country left them: where it did, unless they lost their way today,
    or on an earlier day and did not get their bearings back before setting out."""
    actual = tuple(legs[-1]['to'])
    before = hexes.position(connection, board) if is_wild(travel_map, plan_['from']) else None
    if before and regained(plan_, rolls):
        lines.append('Before setting out they work out where they really are, and walk on knowing it.')
        before = {'at': before['at'], 'believed': before['at']}
    if not strayed(plan_, rolls) and not (before and before['believed'] != before['at']):
        return actual
    # A road or a place they know puts them right.
    if board.cell(actual)['road'] or legs[-1].get('road'):
        return actual
    meant = tuple(plan_['legs'][-1]['to']) if strayed(plan_, rolls) else actual
    drift = (before['believed'][0] - before['at'][0], before['believed'][1] - before['at'][1]) if before else (0, 0)
    return meant[0] + drift[0], meant[1] + drift[1]


def ending(connection, travel_map: dict, plan_: dict, legs: list[dict], rolls: list[dict]) -> tuple[dict, str,
                                                                                                    list[str]]:
    """Where the walked legs leave the character, the line that opens the scene there, and what the narrator is told
    of how the walk ended: at a place, or out in the wild (believing they are elsewhere, if they lost their way)."""
    end = end_of(plan_, legs)
    if plan_.get('mode') != 'hex':
        return nodes(travel_map)[end], f"You arrive at {nodes(travel_map)[end]['name']}.", []
    board = hexes.grid(connection, travel_map)
    actual = tuple(legs[-1]['to'])
    lines = [f"The weather on the way: {plan_['weather']}."] if plan_.get('weather') else []
    if end:
        hexes.place_at(connection, board, actual)
        return nodes(travel_map)[end], f"You arrive at {nodes(travel_map)[end]['name']}.", lines
    believed = belief(connection, travel_map, board, plan_, legs, rolls, lines)
    hexes.place_at(connection, board, actual, believed)
    cell = board.cell(actual)
    region = (travel_map['regions'].get(cell['region']) or {}).get('name', 'country nobody has named')
    stop = (plan_.get('lost') or {}).get('stop') if strayed(plan_, rolls) else plan_.get('stop')
    site = hexes.site(connection, board, actual)
    if stop in ('site', 'arrived') and site:
        known_ = actual in hexes.found_sites(connection, board)
        hexes.find_site(connection, board, actual, site)
        arrived = stop == 'arrived' or known_
        lines.append(f"They reach {site['name']}, which they already knew of." if known_ else
                     f"They {'reach' if arrived else 'come upon'} {site['name']}: {site['text']}")
        # A hamlet is a place of its own on the Road, with its own people (dungeon/story.py hamlets).
        end = travel_map['wild'] | ({'place': hexes.hamlet_id(actual), 'name': site['name']}
                                    if site['kind'] == 'hamlet' else {})
        return end, f"You {'reach' if arrived else 'come upon'} {site['name']}.", lines
    if stop == 'water':
        lines.append(f"Open water stops them: there is no walking further {plan_.get('direction', 'that way')}.")
    elif stop == 'dusk':
        lines.append(f"Dusk stops them in {board.terrain_text(cell['terrain'])} in {region}: the light is going, and "
                     'no one walks off the road in the dark by choice.')
    elif stop == 'enough':
        lines.append(f"They stop where they meant to, after {duration(sum(leg['hours'] for leg in legs))} of "
                     f"walking, in {board.terrain_text(cell['terrain'])} in {region}.")
    elif stop == 'day':
        lines.append(f"The day's walking ends in {board.terrain_text(cell['terrain'])} in {region}, with no road "
                     'or roof in sight.')
    if believed != actual and strayed(plan_, rolls):
        lines.append(f"Somewhere in {plan_['lost']['terrain']} they lost their bearings and drifted off course; they "
                     'believe they are somewhere they are not.')
    elif believed != actual:
        # Lost on an earlier day and still off course: they are no nearer to knowing it.
        lines.append('They are still off course from an earlier day, and still believe they are somewhere they are '
                     'not.')
    wild = travel_map['wild']
    return wild, f"You stop in {board.terrain_text(cell['terrain'])}, in {region}.", lines


def search(connection, plan_: dict, rolls: list[dict]) -> tuple[int, list[str]]:
    """A search of the hex the character is in: the minutes it takes, and what it turns up, if the roll holds and
    there is anything hidden there."""
    travel_map, _ = find(plan_['from'])
    board = hexes.grid(connection, travel_map)
    at = tuple(plan_['start'])
    minutes_ = round(plan_['search']['hours'] * 60)
    lines = []
    if regained(plan_, rolls):
        hexes.place_at(connection, board, at)
        lines.append('Looking about them, the character works out where they really are.')
    if any(roll.get('threat') == NOTHING and roll['band'] in BITES for roll in rolls):
        return minutes_, lines + [f"The character searches the area for {duration(plan_['search']['hours'])} and "
                                  'finds nothing worth the trouble.']
    found, levels = hexes.found_sites(connection, board), hexes.levels(connection)
    site = board.site(at, levels) if at not in found else None
    if site is None and any(roll.get('threat') == NOTHING and roll['band'] == 'critical_success' for roll in rolls):
        # A search that goes as well as it can always turns something up: the nearest site not yet found, nearby.
        near = [(radius, other) for radius in range(1, SEARCH_REACH + 1) for other in hexes.ring(at, radius)
                if hexes.distance(at, other) == radius and other not in found and board.site(other, levels)]
        if near:
            at = near[0][1]
            site = board.site(at, levels)
            away = hexes.distance(tuple(plan_['start']), at)
            lines.append(f"The search ranges wide and picks up signs of something {away} hex{'es' if away > 1 else ''} "
                         f"({away * board.miles:g} miles) to the {hexes.bearing(tuple(plan_['start']), at)}.")
    if site is None:
        return minutes_, lines + [f"The character searches the area for {duration(plan_['search']['hours'])}: there "
                                  'is nothing hidden here to find.']
    hexes.find_site(connection, board, at, site)
    return minutes_, lines + [f"Searching the area, the character finds {site['name']}: {site['text']}"]


def blocked(plan_: dict) -> list[str]:
    return [f"Open water lies {plan_['direction']} of the character: there is no walking that way."]


def minutes(legs: list[dict], hours_a_day: int) -> tuple[int, int, int]:
    """The journey's hours on foot, its nights camped on the road, and its days, in minutes, nights and days."""
    hours = sum(leg['hours'] for leg in legs)
    days = max(1, math.ceil(hours / hours_a_day))
    nights = days - 1
    return round((hours + nights * NIGHT_HOURS) * 60), nights, days


def eat(connection, food: list[str], days: int) -> tuple[list[str], int]:
    """A food from the pack for each day on the road, in the map's order; the days left without. Under Ironsworn a
    day costs a point of supply instead (dungeon/sworn.py)."""
    if (supplied := sworn.spend_supply(connection, days)) is not None:
        spent, left = supplied
        return ([f'{spent} supply ({left} left)'] if spent else []), days - spent
    if not food:
        return [], 0
    eaten = []
    for _ in range(days):
        row = next((found for item_id in food if (found := optional(
            connection, 'SELECT id, city_id, item_id FROM story_inventory WHERE item_id=? AND qty > 0 LIMIT 1',
            (item_id,)))), None)
        if row is None:
            break
        connection.execute('UPDATE story_inventory SET qty=qty-1 WHERE id=?', (row['id'],))
        entry = inventory.item(row['city_id'], row['item_id'])
        eaten.append(entry['name'] if entry else row['item_id'])
    return eaten, days - len(eaten)


def duration(hours: float) -> str:
    """'40 minutes', 'an hour', '4.5 hours'."""
    if hours < 1:
        return f'{round(hours * 60)} minutes'
    return 'an hour' if hours == 1 else f"{hours:g} hours"


def end_of(plan_: dict, legs: list[dict]) -> str | None:
    """The place a journey's walked legs end at; None out in the wild."""
    return legs[-1].get('place') if plan_.get('mode') == 'hex' else legs[-1]['to']


def lines_for(travel_map: dict, plan_: dict, legs: list[dict], nights: int, eaten: list[str],
              hungry: int) -> list[str]:
    places = nodes(travel_map)
    roads = ', then '.join(dict.fromkeys(leg['terrain'] for leg in legs))
    hours = sum(leg['hours'] for leg in legs)
    way = (f"by {travel_map['by']} on {roads}: {duration(hours)} on the road" if travel_map.get('by') else
           f'on foot by {roads}: {hours:g} hours of walking')
    if plan_.get('direction'):
        lines = [f"The player's character strikes out {plan_['direction']} from {places[plan_['from']]['name']} "
                 f"{way}."]
    else:
        lines = [f"The player's character travels from {places[plan_['from']]['name']} to "
                 f"{plan_.get('site') or places[end_of(plan_, legs)]['name']} {way}"
                 + (f", {nights} night{'s' if nights > 1 else ''} camped on the road." if nights else '.')]
    if (crossed := crossings(legs)):
        lines.append(f"On the way they cross {crossed}.")
    if eaten:
        lines.append(f"They eat from their pack on the way: {', '.join(eaten)}.")
    if hungry:
        lines.append(f"They have nothing to eat for {hungry} day{'s' if hungry > 1 else ''} of it and go hungry.")
    return lines


def crossings(legs: list[dict]) -> str:
    """The rivers a journey crossed and how: 'the Wend by the bridge, and a river wading (an hour more)'."""
    told = []
    for leg in legs:
        crossing = leg.get('crossing')
        if not crossing:
            continue
        how = {'bridge': 'by the bridge', 'ford': "at the road's ford"}.get(
            crossing['by'], f"wading across ({duration(crossing['hours'])} more, and wet to the waist)")
        told.append(f"{crossing['river']} {how}")
    told = list(dict.fromkeys(told))
    return ', and '.join([', '.join(told[:-1]), told[-1]]) if len(told) > 1 else ''.join(told)


def view(connection, city_id: str, place_id: str) -> dict | None:
    """The travel map as far as the character knows it, for the screen: places, the roads between them, here."""
    found = node_at(city_id, place_id)
    if found is None:
        return None
    travel_map, here = found
    seen = known(connection, travel_map, here['id'])
    places = [{'id': node['id'], 'name': node['name'], 'x': node['map']['x'], 'y': node['map']['y'],
               'visited': seen[node['id']], 'here': node['id'] == here['id']}
              for node in travel_map['nodes'] if node['id'] in seen]
    roads = [{'from': route['from'], 'to': route['to'], 'hours': route['hours'], 'danger': route['danger'],
              'terrain': route['terrain']} for route in travel_map['routes']
             if route['from'] in seen and route['to'] in seen]
    if not hexes.is_hex(travel_map):
        return {'places': places, 'roads': roads}
    board = hexes.grid(connection, travel_map)
    at = here_hex(connection, travel_map, board, here['id'])
    cells = [{'q': cell['q'], 'r': cell['r'], 'terrain': cell['terrain'], 'road': bool(cell['road']),
              'place': cell['place'], 'site': cell['site'], 'visited': cell['visited'],
              'river': {'name': cell['river']['name'], 'down': cell['river']['down'],
                        'flow': cell['river']['flow']} if cell['river'] else None}
             for cell in hexes.view(connection, board, at)]
    # Lost, the map shows where the character believes they are.
    where = hexes.position(connection, board) if is_wild(travel_map, here['id']) else None
    believed = where['believed'] if where else at
    return {'places': places, 'roads': roads, 'hexes': cells,
            'at': {'q': believed[0], 'r': believed[1], 'lost': bool(where) and where['believed'] != where['at']}}


def wild_text(connection, city_id: str, place_id: str) -> str:
    """Out in the wild, for the narrator: the land the character is in, the day's weather, and the nearest place
    they know of."""
    found = node_at(city_id, place_id)
    if found is None:
        return ''
    travel_map, here = found
    if not is_wild(travel_map, here['id']) or not hexes.is_hex(travel_map):
        return ''
    board = hexes.grid(connection, travel_map)
    where = hexes.position(connection, board)
    if where is None:
        return ''
    cell = board.cell(where['at'])
    region = (travel_map['regions'].get(cell['region']) or {}).get('name', 'country nobody has named')
    lines = [f"The player's character is out in the wild, off the roads, in {board.terrain_text(cell['terrain'])} "
             f"in {region}.", f"Today's weather: {today(connection, board, where['at'])}."]
    if cell['river']:
        lines.append(f"A river runs through here: {cell['river']['name']}. Crossing it off the road means wading.")
    seen = known(connection, travel_map, here['id'])
    nearby = sorted((hexes.distance(where['believed'], board.places[node]), node) for node in seen
                    if node in board.places)
    if nearby:
        hexes_away, node = nearby[0]
        lines.append(f"The nearest place they know of is {nodes(travel_map)[node]['name']}, about {hexes_away} "
                     f"hex{'es' if hexes_away != 1 else ''} ({hexes_away * board.miles} miles) to the "
                     f"{hexes.bearing(where['believed'], board.places[node])}, as far as they can tell.")
    if (site := hexes.found_sites(connection, board).get(where['at'])):
        lines.append(f"Here: {site['name']}. {site['text']}")
    if where['believed'] != where['at']:
        lines.append('They have lost their way: they are not where they believe they are, and do not know it.')
    return '## Out in the wild (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines)


def prompt_text(lines: list[str]) -> str:
    return '## The journey (decided by the game; write it as it went)\n' + '\n'.join(
        f'- {line}' for line in lines) if lines else ''
