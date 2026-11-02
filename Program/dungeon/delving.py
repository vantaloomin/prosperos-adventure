"""Walking an interior (requirements "### Interiors"): in through the way in, room by room along passages, and out.

An interior is an authored one (dungeon/interiors.py), or for a rolled hex site (a ruin, cave, lair or barrow) one
laid out from the campaign seed and the site the first time it is entered (`generated`): the same campaign always
finds the same rooms, and nothing about it is stored but what the character has seen and done.

- **In and out.** "I go in" where an interior's way in is (a town's place, a travel-map stop, or the hex of a site
  out in the wild) enters its entrance room. "I go back outside" from the entrance leaves it. While inside, the
  scene is still the place outside, but journeys wait until the character comes out.
- **Moving.** A line names a room the character has been in, a way out they can see ("the stairs", "the low door")
  or "back". Each move takes MOVE_MINUTES. A locked passage wants its key from the pack, or a roll to pick or force
  it (a failed roll and the character stays where they are). A trapped passage rolls its trap the first time it is
  passed, sprung or not. A room's hazard is rolled the first time the character is in it.
- **Foes.** A room's foes, until a fight with them is over, roll each turn the character is in the room to stay
  unseen; a failed roll, or attacking them, starts the fight (dungeon/story.py fight_round, `foe_for`).
- **Searching.** "I search the room" takes SEARCH_MINUTES and a Mind roll: on a success the hidden ways out of the
  room are found, and what is lying there goes into the pack.
- **Dark.** In a dark room without a light in the pack every roll is a step harder.
- **Wandering.** Every `wander_every` moves the interior's own encounter table is rolled, like a region's road.

What the character has seen and done is game state, branched with the story (story_interior, story_interior_rooms,
story_interior_ways in dungeon/timeline.py SAVED); a line's move is decided once (story_delves).
"""
import hashlib
import random
import re

from dungeon import hexes, interiors, inventory, travel, world_data
from dungeon.database import decode, encode, many, optional
from dungeon.world.schema import Interior

MOVE_MINUTES = 5
LOCK_MINUTES = 10
SEARCH_MINUTES = 20
SEARCH_STAT = 'Mind'
LOCK_STAT = 'Vitality'
DANGER_STAT = 'Luck'
BITES = ('critical_failure', 'failure', 'failure_upside')
HARDER = hexes.HARDER
# What in the pack gives light.
LIGHTS = re.compile(r'lantern|lamp(?!-oil)|torch|candle', re.I)

ENTER = re.compile(r"\b(?:go|head|walk|step|climb|venture|creep|sneak|crawl|slip|duck|make (?:my|our) way)\s+(?:back\s+)?"
                   r"(?:in|inside|into|down into|through the (?:gate|door|doorway|mouth))\b|\benter(?:s|ing)?\b|\bexplore\b",
                   re.I)
LEAVE = re.compile(r"\b(?:leave|get out|go out|head out|walk out|back outside|go outside|step outside|out of here|"
                   r"climb out|back out into|outside again|out into the (?:air|daylight|light|open))\b", re.I)
SEARCH = re.compile(r"\b(?:search(?:es|ing)?|look (?:around )?for (?:anything )?(?:hidden|secret)|feel along|check the walls|"
                    r"hunt (?:around )?for|go over the room|sound the walls)\b", re.I)
GO = re.compile(r"\b(?:go|goes|head|walk|take|climb|follow|step|cross|move|crawl|wade|swim|squeeze|descend|ascend|"
                r"return|make for|try|through|down|up|back|into)\b", re.I)
BACK = re.compile(r"\b(?:go back|head back|back the way|the way (?:I|we) came|retrace|back to where)\b", re.I)
# Words for passage kinds a line may use for a way out ("the stairs", "the trapdoor").
KIND_WORDS = {'stairs': ('stair', 'stairs', 'steps', 'stairway', 'stairwell'), 'ladder': ('ladder',),
              'shaft': ('shaft', 'chimney', 'drop', 'hole'), 'door': ('door', 'doorway', 'gate'),
              'crawl': ('crawl', 'crawlway', 'tunnel', 'squeeze', 'gap'), 'water': ('water', 'pool', 'swim', 'wade'),
              'secret': ('secret', 'hidden'), 'open': ('arch', 'archway', 'passage', 'opening', 'way')}
STOP_WORDS = {'the', 'a', 'an', 'of', 'to', 'in', 'into', 'and', 'old', 'room', 'little', 'great'}


# What the character has seen and done --------------------------------------------------------------------------

def inside(connection) -> dict | None:
    """Where the character is inside an interior: its id, room, the room before, moves since a wander, and for a
    generated one the site it was laid out from."""
    row = optional(connection, 'SELECT * FROM story_interior WHERE id=1')
    return row and dict(row) | {'site': decode(row['site']) if row['site'] else None}


def interior_of(connection, where: dict) -> dict:
    """The interior the character is in, authored or laid out again from its site."""
    if where.get('site'):
        site = where['site']
        return generated(hexes.seed(connection), site['world'], site)
    return interiors.get(where['interior'])


def rooms_state(connection, interior_id: str) -> dict[str, dict]:
    return {row['room']: dict(row) for row in many(connection, 'SELECT * FROM story_interior_rooms WHERE interior=?',
                                                  (interior_id,))}


def ways_state(connection, interior_id: str) -> dict[frozenset, dict]:
    return {frozenset((row['a'], row['b'])): dict(row)
            for row in many(connection, 'SELECT * FROM story_interior_ways WHERE interior=?', (interior_id,))}


def mark_room(connection, interior_id: str, room_id: str, **flags):
    connection.execute('INSERT OR IGNORE INTO story_interior_rooms (interior, room) VALUES (?, ?)', (interior_id, room_id))
    for flag in flags:
        connection.execute(f'UPDATE story_interior_rooms SET {flag}=1 WHERE interior=? AND room=?', (interior_id, room_id))


def mark_way(connection, interior_id: str, between: list[str], **flags):
    a, b = sorted(between)
    connection.execute('INSERT OR IGNORE INTO story_interior_ways (interior, a, b) VALUES (?, ?, ?)', (interior_id, a, b))
    for flag in flags:
        connection.execute(f'UPDATE story_interior_ways SET {flag}=1 WHERE interior=? AND a=? AND b=?', (interior_id, a, b))


def found_from(interior: dict, room_id: str, ways: dict) -> frozenset[str]:
    """The rooms behind hidden passages out of this room that the character has found."""
    return frozenset(other for passage in interior['passages'] if room_id in passage['between']
                     for other in passage['between'] if other != room_id
                     and ways.get(frozenset(passage['between']), {}).get('found'))


def visible_ways(interior: dict, room_id: str, ways: dict) -> list[dict]:
    return interiors.ways_out(interior, room_id, found_from(interior, room_id, ways))


def lit(connection) -> bool:
    return any(LIGHTS.search(row['item_id']) for row in many(connection, 'SELECT item_id FROM story_inventory WHERE qty > 0'))


def in_the_dark(connection, room: dict) -> bool:
    return room['light'] == 'dark' and not lit(connection)


# Generated interiors -------------------------------------------------------------------------------------------

def table_for(world: str, kind: str) -> dict | None:
    return ((world_data.read('interior_tables', world) or {}).get('kinds') or {}).get(kind)


def site_id(site: dict) -> str:
    return f"site-{site['map']}-{site['q']}-{site['r']}".replace('_', '-').lower()


def weighted(rng: random.Random, entries: list[dict]) -> dict | None:
    if not entries:
        return None
    roll = rng.randint(1, sum(entry.get('weight', 1) for entry in entries))
    for entry in entries:
        roll -= entry.get('weight', 1)
        if roll <= 0:
            return entry
    return entries[-1]


def capital(name: str) -> str:
    return name[:1].upper() + name[1:]


def generated(seed: str, world: str, site: dict, levels: dict[str, int] | None = None) -> dict:
    """The inside of a rolled site, laid out from the campaign seed and the site's hex: the same rooms every time.
    `site` holds the map, q, r, kind and name; `levels` the intensity levels kept with it when it was entered."""
    table = table_for(world, site['kind'])
    if table is None:
        raise ValueError(f"No interior table for a {site['kind']} in {world}.")
    levels = site.get('levels', levels)
    digest = hashlib.sha256(f"{seed}:interior:{site['map']}:{site['q']}:{site['r']}".encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    allowed = lambda entries: [entry for entry in entries if hexes.allowed(entry, levels)]  # noqa: E731
    count = rng.randint(*table['rooms'])
    level_list = table.get('levels') or []
    entrance = {'id': 'way-in', **table['entrance'], 'source': 'seeded'}
    if level_list:
        entrance['level'] = level_list[0]['id']
    rooms, passages, used = [entrance], [], set()
    for index in range(1, count):
        depth = index / max(1, count - 1)
        level = next((item['id'] for item in reversed(level_list) if depth >= item.get('from', 0)), None)
        unused = [entry for entry in table['rooms_table'] if entry['name'] not in used]
        pool = [entry for entry in unused if entry.get('level') in (level, None)] or unused
        entry = weighted(rng, pool)
        if entry is None:
            break
        used.add(entry['name'])
        room = {key: value for key, value in entry.items() if key not in ('weight', 'level', 'name')}
        room |= {'id': f'room-{index}', 'name': capital(entry['name']), 'source': 'seeded'}
        if level:
            room['level'] = level
        if rng.randint(1, 100) <= table.get('foe_odds', 0) and (foe := weighted(rng, allowed(table.get('foes', [])))):
            room['foes'] = [foe['foe']]
        if rng.randint(1, 100) <= table.get('hazard_odds', 0) and (hazard := weighted(rng, table.get('hazards', []))):
            room['hazard'] = {key: value for key, value in hazard.items() if key != 'weight'}
        if rng.randint(1, 100) <= table.get('loot_odds', 0) and table.get('loot'):
            room['loot'] = [rng.choice(table['loot'])]
        # Each room hangs off one laid out before it, on its own level or the one above.
        earlier = [item for item in rooms if item.get('level') == level] or rooms
        parent = rng.choice(earlier[-3:])
        if level and parent.get('level') != level and table.get('down'):
            way = dict(table['down'])
        else:
            way = {key: value for key, value in (weighted(rng, table['passages']) or {'kind': 'open'}).items()
                   if key != 'weight'}
        rooms.append(room)
        passages.append({'between': [parent['id'], room['id']], **way})
    interior = {'schema_version': 1, 'id': site_id(site), 'name': capital(site['name']), 'world': world,
                'style': table['style'], 'summary': site.get('text') or capital(site['name']),
                'at': {'site': site_id(site)}, 'entrance': 'way-in', 'levels': [
                    {key: value for key, value in item.items() if key != 'from'} for item in level_list
                    if any(room.get('level') == item['id'] for room in rooms)],
                'rooms': rooms, 'passages': passages, 'wanders': table.get('wanders', []),
                'sources': {'seeded': {'kind': 'other', 'title': 'Laid out from the campaign seed', 'license': 'n/a',
                                       'retrieved': '2026-11-02'}}}
    return Interior.model_validate(interior).model_dump(mode='json')


# Where the way in is -------------------------------------------------------------------------------------------

def way_in(connection, city_id: str, place_id: str) -> tuple[dict, dict | None] | None:
    """The interior whose way in is where the scene is (and for a rolled site, the site it is laid out from)."""
    found = travel.node_at(city_id, place_id)
    world = found[0].get('world') if found else None
    node = found[1]['id'] if found else None
    if (authored := interiors.entered_from(world=world, city=city_id, place=place_id, node=node)):
        return authored, None
    if not found or not travel.is_wild(found[0], node) or not hexes.is_hex(found[0]):
        return None
    travel_map = found[0]
    board = hexes.grid(connection, travel_map)
    where = hexes.position(connection, board)
    site = hexes.site(connection, board, where['at']) if where else None
    if not site or (site['q'], site['r']) not in hexes.found_sites(connection, board):
        return None
    site = site | {'map': hexes.key(travel_map), 'world': world or travel_map.get('world') or '',
                   'levels': hexes.levels(connection)}
    if (authored := interiors.entered_from(world=world, site=site_id(site))):
        return authored, None
    if not table_for(site['world'], site['kind']):
        return None
    return generated(hexes.seed(connection), site['world'], site), site


# Reading a line ------------------------------------------------------------------------------------------------

def words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z']+", text.lower()) if word not in STOP_WORDS and len(word) > 2}


def moving(text: str) -> bool:
    """Whether a line moves inside an interior, searches it or leaves it (its time is the move's)."""
    return bool(GO.search(text) or SEARCH.search(text) or LEAVE.search(text) or BACK.search(text))


def room_named(interior: dict, text: str, known: set[str]) -> str | None:
    """A room the character knows that the line names: its whole name first, then a word of it only it has."""
    lowered = text.lower()
    rooms = [room for room in interior['rooms'] if room['id'] in known]
    whole = [room for room in rooms if re.sub(r'^the\s+', '', room['name'].lower()) in lowered]
    if whole:
        return max(whole, key=lambda room: len(room['name']))['id']
    said = words(text)
    hits = [room for room in rooms if words(room['name']) & said]
    return hits[0]['id'] if len(hits) == 1 else None


def way_named(ways: list[dict], text: str, rooms_seen: dict, interior: dict) -> dict | None:
    """A way out the line names: by the room it goes to (one the character has been in), its kind, or its words."""
    said = words(text)
    for way in ways:
        target = interiors.room(interior, way['to'])
        if way['to'] in rooms_seen and words(target['name']) & said:
            return way
    # Its kind ("the stairs") and the words of its description ("behind the hearth") both count; the most wins.
    scored = [(bool(said & set(KIND_WORDS.get(way['passage']['kind'], ()))) * 2
               + len(words(way['passage'].get('summary', '')) & said), index, way) for index, way in enumerate(ways)]
    best = max(scored, key=lambda item: (item[0], -item[1]), default=None)
    if best and best[0] > 0 and [item[0] for item in scored].count(best[0]) == 1:
        return best[2]
    if best and best[0] >= 2:
        return best[2]
    if len(ways) == 1 and re.search(r'\b(?:on|onward|further|deeper|ahead|the only way)\b', text, re.I):
        return ways[0]
    return None


def path(interior: dict, start: str, goal: str, ways: dict, rooms_seen: dict) -> list[str] | None:
    """The rooms to walk through to a room the character has been in, by passages they have passed (a known way)."""
    todo, came = [start], {start: None}
    while todo:
        here = todo.pop(0)
        if here == goal:
            route = []
            while here != start:
                route.append(here)
                here = came[here]
            return route[::-1]
        for way in visible_ways(interior, here, ways):
            if way['to'] not in came and ways.get(frozenset(way['passage']['between']), {}).get('passed') \
                    and way['to'] in rooms_seen:
                came[way['to']] = here
                todo.append(way['to'])
    return None


def plan(connection, city_id: str, place_id: str, text: str, rng=None) -> dict | None:
    """What a line does inside an interior, or to get into one: None when it does neither."""
    rng = rng or random.SystemRandom()
    where = inside(connection)
    if where is None:
        return entering(connection, city_id, place_id, text, rng)
    interior = interior_of(connection, where)
    rooms_seen, ways = rooms_state(connection, interior['id']), ways_state(connection, interior['id'])
    here = where['room']
    if LEAVE.search(text) and here == interior['entrance']:
        return {'kind': 'leave', 'interior': interior['id']}
    if SEARCH.search(text):
        return {'kind': 'search', 'interior': interior['id'], 'room': here,
                'difficulty': harder_in_dark(connection, interiors.room(interior, here), 'normal')}
    out = visible_ways(interior, here, ways)
    target = next((way for way in out if way['to'] == where.get('previous')), None) if BACK.search(text) else None
    if target is None and GO.search(text):
        target = way_named(out, text, rooms_seen, interior)
        named = room_named(interior, text, set(rooms_seen)) if target is None else None
        if named and named != here and (route := path(interior, here, named, ways, rooms_seen)):
            return {'kind': 'walk', 'interior': interior['id'], 'route': route}
    if target is None:
        return stay(connection, interior, where, rooms_seen)
    return going(connection, interior, where, target, ways, rng)


def entering(connection, city_id: str, place_id: str, text: str, rng) -> dict | None:
    if not ENTER.search(text) or (found := way_in(connection, city_id, place_id)) is None:
        return None
    interior, site = found
    return arrive({'kind': 'enter', 'interior': interior['id'], 'site': site, 'to': interior['entrance']},
                  connection, interior, rng)


def going(connection, interior: dict, where: dict, target: dict, ways: dict, rng) -> dict:
    """A move along a passage: its lock (a key in the pack, or a roll), its trap, and the room it leads to."""
    here = where['room']
    move = {'kind': 'move', 'interior': interior['id'], 'from': here, 'to': target['to'],
            'between': target['passage']['between']}
    state = ways.get(frozenset(target['passage']['between']), {})
    lock = target['passage'].get('lock')
    if lock and not state.get('opened'):
        key = lock.get('key')
        if key and optional(connection, 'SELECT 1 FROM story_inventory WHERE item_id=? AND qty > 0', (key,)):
            move['key'] = key
        else:
            move['lock'] = {'difficulty': harder_in_dark(connection, interiors.room(interior, here),
                                                          lock.get('difficulty', 'normal'))}
    trap = target['passage'].get('trap')
    if trap and not state.get('sprung'):
        move['trap'] = trap
    if 'lock' in move:
        return move
    return arrive(move, connection, interior, rng, where)


def stay(connection, interior: dict, where: dict, rooms_seen: dict) -> dict | None:
    """A line that stays in the room: its foes may notice the character, and a hazard not yet met is met."""
    room = interiors.room(interior, where['room'])
    seen = rooms_seen.get(room['id'], {})
    checks = room_checks(connection, room, seen)
    return {'kind': 'stay', 'interior': interior['id'], 'room': room['id'], **checks} if checks else None


def harder_in_dark(connection, room: dict, difficulty: str) -> str:
    return HARDER[difficulty] if in_the_dark(connection, room) else difficulty


def room_checks(connection, room: dict, seen: dict) -> dict:
    checks = {}
    if room.get('hazard') and not seen.get('hazard_met'):
        checks['hazard'] = room['hazard'] | {'difficulty': harder_in_dark(connection, room, room['hazard']['difficulty'])}
    if room.get('foes') and not seen.get('cleared'):
        checks['foes'] = {'difficulty': harder_in_dark(connection, room, 'normal')}
    return checks


def arrive(move: dict, connection, interior: dict, rng, where: dict | None = None) -> dict:
    """A move that will get there: the room's checks, and a wandering encounter when one is due."""
    room = interiors.room(interior, move['to'])
    seen = rooms_state(connection, interior['id']).get(room['id'], {})
    move |= room_checks(connection, room, seen)
    moves = (where or {}).get('moves', 0) + 1
    if interior['wanders'] and moves >= interior['wander_every']:
        move['wander'] = weighted(rng, interior['wanders'])
    return move


# The rolls a line calls for --------------------------------------------------------------------------------------

def threat_text(threat) -> str:
    return threat if isinstance(threat, str) else threat['text']


def foe_label(foe: dict) -> str:
    return foe['name'] if foe.get('count', 1) == 1 else f"{foe.get('count')} {foe['name']}s"


def noticed(room: dict) -> str:
    """The threat of a room's foes noticing the character (and what fight_round looks up to start their fight)."""
    foe = room['foes'][0]
    return f"In {room['name'].lower()}, {foe_label(foe)} see the character and come at them."


def decide(connection, message_id: str, city_id: str, place_id: str, text: str, rng=None) -> list[dict]:
    """The line's move, planned once, and the rolls it calls for."""
    row = optional(connection, 'SELECT plan FROM story_delves WHERE message_id=?', (message_id,))
    planned = decode(row['plan']) if row else plan(connection, city_id, place_id, text, rng)
    if planned is None:
        return []
    if row is None:
        connection.execute('INSERT INTO story_delves (message_id, plan) VALUES (?, ?)', (message_id, encode(planned)))
    return actions_for(connection, planned)


def actions_for(connection, planned: dict) -> list[dict]:
    actions = []
    if planned['kind'] == 'search':
        actions.append({'action': 'search the room for hidden ways and anything left there', 'stat': SEARCH_STAT,
                        'difficulty': planned['difficulty'], 'threat': 'They find nothing, and the time is spent.'})
    if lock := planned.get('lock'):
        actions.append({'action': 'pick or force the lock', 'stat': LOCK_STAT, 'difficulty': lock['difficulty'],
                        'threat': 'The lock holds, and the noise carries.'})
    if trap := planned.get('trap'):
        actions.append({'action': trap['action'], 'stat': DANGER_STAT, 'difficulty': trap['difficulty'],
                        'threat': threat_text(trap['threat'])})
    if hazard := planned.get('hazard'):
        actions.append({'action': hazard['action'], 'stat': DANGER_STAT, 'difficulty': hazard['difficulty'],
                        'threat': threat_text(hazard['threat'])})
    if planned.get('foes'):
        where = inside(connection)
        interior = interior_of(connection, where) if where else interior_by(connection, planned)
        room = interiors.room(interior, planned.get('to') or planned.get('room'))
        actions.append({'action': f"keep out of sight of the {room['foes'][0]['name']}s" if room['foes'][0].get('count', 1) > 1
                        else f"keep out of sight of the {room['foes'][0]['name']}", 'stat': DANGER_STAT,
                        'difficulty': planned['foes']['difficulty'], 'threat': noticed(room)})
    wander = planned.get('wander') or {}
    if wander.get('action'):
        actions.append({'action': wander['action'], 'stat': DANGER_STAT, 'difficulty': wander['difficulty'],
                        'threat': threat_text(wander['threat'])})
    return actions


def interior_by(connection, planned: dict) -> dict:
    if planned.get('site'):
        return generated(hexes.seed(connection), planned['site']['world'], planned['site'])
    return interiors.get(planned['interior'])


def foe_for(connection, threat: str) -> dict | None:
    """The foe a threat inside the interior brings into a fight: the room's foes, a trap's, a hazard's or a
    wandering encounter's."""
    where = inside(connection)
    if where is None:
        return None
    interior = interior_of(connection, where)
    for room in interior['rooms']:
        if room.get('foes') and noticed(room) == threat:
            return room['foes'][0]
        hazard = room.get('hazard') or {}
        if isinstance(hazard.get('threat'), dict) and hazard['threat']['text'] == threat and hazard['threat'].get('foe'):
            return hazard['threat']['foe']
    for entry in [*interior['wanders'], *(passage.get('trap') or {} for passage in interior['passages'])]:
        found = entry.get('threat') if isinstance(entry, dict) else None
        if isinstance(found, dict) and found['text'] == threat and found.get('foe'):
            return found['foe']
    return None


def room_foe(connection) -> dict | None:
    """The foes of the room the character is in, while no fight with them is over."""
    where = inside(connection)
    if where is None:
        return None
    interior = interior_of(connection, where)
    room = interiors.room(interior, where['room'])
    if not room.get('foes') or rooms_state(connection, interior['id']).get(room['id'], {}).get('cleared'):
        return None
    return room['foes'][0]


def fought(connection, fighting: bool, alive: bool):
    """After a fight round inside: the fight began here, and once it is over with the character alive, the room's
    foes are dealt with."""
    where = inside(connection)
    if where is None:
        return
    if fighting:
        connection.execute('UPDATE story_interior SET fighting=? WHERE id=1', (where['room'],))
    elif where.get('fighting'):
        if alive:
            mark_room(connection, where['interior'], where['fighting'], cleared=1)
        connection.execute('UPDATE story_interior SET fighting=NULL WHERE id=1')


# Playing a line ------------------------------------------------------------------------------------------------

def bitten(rolls: list[dict], threat: str) -> bool:
    return any(roll.get('threat') == threat and roll['band'] in BITES for roll in rolls)


def kept(connection, message_id: str) -> dict | None:
    row = optional(connection, 'SELECT plan, lines FROM story_delves WHERE message_id=?', (message_id,))
    return row and decode(row['plan']) | {'lines': decode(row['lines']) if row['lines'] else None}


def walked(connection, message_id: str, rolls: list[dict], city_id: str) -> tuple[list[str], int]:
    """What the line's move came to, played once: the lines for the narrator, and the minutes it took."""
    planned = kept(connection, message_id)
    if planned is None:
        return [], 0
    if planned['lines'] is not None:
        return planned['lines'], 0
    lines, minutes = play(connection, planned, rolls, city_id)
    connection.execute('UPDATE story_delves SET lines=? WHERE message_id=?', (encode(lines), message_id))
    return lines, minutes


def play(connection, planned: dict, rolls: list[dict], city_id: str) -> tuple[list[str], int]:
    kind = planned['kind']
    if kind == 'enter':
        interior = interior_by(connection, planned)
        connection.execute('INSERT INTO story_interior (id, interior, room, previous, moves, site) VALUES (1, ?, ?, NULL, 0, ?) '
                           'ON CONFLICT(id) DO UPDATE SET interior=excluded.interior, room=excluded.room, previous=NULL, '
                           'moves=0, site=excluded.site, fighting=NULL',
                           (interior['id'], planned['to'], encode(planned['site']) if planned.get('site') else None))
        mark_room(connection, interior['id'], planned['to'], visited=1)
        return [f"The character goes into {interior['name']}."] + met(connection, interior, planned, rolls), MOVE_MINUTES
    where = inside(connection)
    interior = interior_of(connection, where)
    if kind == 'leave':
        connection.execute('DELETE FROM story_interior WHERE id=1')
        return [f"The character comes back out of {interior['name']} into the open."], MOVE_MINUTES
    if kind == 'search':
        return searched(connection, interior, where, rolls, city_id), SEARCH_MINUTES
    if kind == 'stay':
        return met(connection, interior, planned, rolls), 0
    if kind == 'walk':
        for room_id in planned['route']:
            move_to(connection, where, room_id)
            where = inside(connection)
        target = interiors.room(interior, planned['route'][-1])
        return [f"The character goes back the way they know to {target['name'].lower()}."], MOVE_MINUTES * len(planned['route'])
    return moved(connection, interior, where, planned, rolls)


def move_to(connection, where: dict, room_id: str):
    connection.execute('UPDATE story_interior SET previous=room, room=?, moves=moves+1 WHERE id=1', (room_id,))
    mark_room(connection, where['interior'], room_id, visited=1)


def moved(connection, interior: dict, where: dict, planned: dict, rolls: list[dict]) -> tuple[list[str], int]:
    lines, minutes = [], MOVE_MINUTES
    passage = next(item for item in interior['passages'] if sorted(item['between']) == sorted(planned['between']))
    way = way_text(passage)
    if planned.get('key'):
        lines.append(f"They open {way} with the {planned['key'].replace('-', ' ')}.")
        mark_way(connection, interior['id'], passage['between'], opened=1)
    if planned.get('lock'):
        minutes += LOCK_MINUTES
        if bitten(rolls, 'The lock holds, and the noise carries.'):
            return [f"{capital(way)} is locked, and stays locked: the character is still in "
                    f"{interiors.room(interior, where['room'])['name'].lower()}."], minutes
        lines.append(f"They get {way} open.")
        mark_way(connection, interior['id'], passage['between'], opened=1)
    if trap := planned.get('trap'):
        mark_way(connection, interior['id'], passage['between'], sprung=1)
        lines.append(f"A trap on {way}: {threat_text(trap['threat'])}" if bitten(rolls, threat_text(trap['threat']))
                     else f"There is a trap on {way}, and the character gets past it: they manage to {trap['action']}.")
    mark_way(connection, interior['id'], passage['between'], passed=1, found=1)
    move_to(connection, where, planned['to'])
    target = interiors.room(interior, planned['to'])
    lines.insert(0, f"The character goes by {way} into {target['name'].lower()}.")
    if planned.get('lock'):
        return lines, minutes  # what is in the room meets them next line
    return lines + met(connection, interior, planned, rolls), minutes


def met(connection, interior: dict, planned: dict, rolls: list[dict]) -> list[str]:
    """What the room the line ends in did to the character: its hazard, its foes, and a wandering encounter."""
    where = inside(connection)
    room = interiors.room(interior, where['room'])
    lines = []
    if hazard := planned.get('hazard'):
        mark_room(connection, interior['id'], room['id'], hazard_met=1)
        lines.append(threat_text(hazard['threat']) if bitten(rolls, threat_text(hazard['threat']))
                     else f"They manage to {hazard['action']}.")
    if planned.get('foes'):
        lines.append(f"The {foe_label(room['foes'][0])} see them: a fight." if bitten(rolls, noticed(room))
                     else f"The {foe_label(room['foes'][0])} here have not seen the character.")
    if wander := planned.get('wander'):
        connection.execute('UPDATE story_interior SET moves=0 WHERE id=1')
        if wander.get('text'):
            lines.append(wander['text'])
        if wander.get('action'):
            lines.append(threat_text(wander['threat']) if bitten(rolls, threat_text(wander['threat']))
                         else f"They manage to {wander['action']}.")
    return lines


def searched(connection, interior: dict, where: dict, rolls: list[dict], city_id: str) -> list[str]:
    room = interiors.room(interior, where['room'])
    if bitten(rolls, 'They find nothing, and the time is spent.'):
        return [f"The character searches {room['name'].lower()} and finds nothing."]
    lines = [f"The character searches {room['name'].lower()}."]
    hidden = [passage for passage in interior['passages'] if room['id'] in passage['between'] and passage['hidden']
              and not (passage['one_way'] and passage['between'][0] != room['id'])]
    for passage in hidden:
        mark_way(connection, interior['id'], passage['between'], found=1)
        lines.append(f"They find a hidden way out: {way_text(passage)}.")
    seen = rooms_state(connection, interior['id']).get(room['id'], {})
    if room.get('loot') and not seen.get('looted'):
        names = []
        for item_id in room['loot']:
            town = loot_town(interior['world'], item_id) or city_id
            inventory.add_item(connection, town, item_id)
            names.append((inventory.item(town, item_id) or {'name': item_id})['name'])
        mark_room(connection, interior['id'], room['id'], looted=1)
        lines.append(f"They find and take: {', '.join(names)}.")
    mark_room(connection, interior['id'], room['id'], searched=1)
    if room.get('lore'):
        lines.append(f"Looking closely: {room['lore']}")
    if len(lines) == 1:
        lines.append('There is nothing hidden here.')
    return lines


def loot_town(world: str, item_id: str) -> str | None:
    """A town of the world whose goods include this item (loot names the world's items)."""
    travel_map = world_data.read('travel', world) or {}
    for node in travel_map.get('nodes', []):
        if node.get('city') and inventory.item(node['city'], item_id):
            return node['city']
    return next((key for key in world_data.keys('items') if inventory.item(key, item_id)), None)


# What the narrator is told ---------------------------------------------------------------------------------------

def way_text(passage: dict) -> str:
    if passage.get('summary'):
        return passage['summary']
    return {'open': 'an open way', 'door': 'a door', 'stairs': 'a stair', 'ladder': 'a ladder', 'shaft': 'a shaft',
            'crawl': 'a crawlway', 'water': 'a way through water', 'secret': 'a secret door'}[passage['kind']]


def here_text(connection) -> str:
    """Where the character is inside, for the narrator: the room, what is in it, and the ways out they can see."""
    where = inside(connection)
    if where is None:
        return ''
    interior = interior_of(connection, where)
    room = interiors.room(interior, where['room'])
    rooms_seen, ways = rooms_state(connection, interior['id']), ways_state(connection, interior['id'])
    dark = in_the_dark(connection, room)
    lines = [f"The player's character is inside {interior['name']} ({interior['summary']})",
             f"They are in {room['name'].lower()}: {room['summary']}"]
    if room['features'] and not dark:
        lines.append(f"In it: {'; '.join(room['features'])}.")
    if dark:
        lines.append('It is pitch dark here and they carry no light: they feel their way, and every roll is harder.')
    elif room['light'] != 'lit':
        lines.append(f"It is {room['light']} here.")
    if room.get('foes') and not rooms_state(connection, interior['id']).get(room['id'], {}).get('cleared'):
        lines.append(f"Here: {foe_label(room['foes'][0])}.")
    out = []
    for way in visible_ways(interior, room['id'], ways):
        target = interiors.room(interior, way['to'])
        to = f" to {target['name'].lower()}" if way['to'] in rooms_seen else ''
        locked = way['passage'].get('lock') and not ways.get(frozenset(way['passage']['between']), {}).get('opened')
        out.append(f"{way_text(way['passage'])}{to}{' (locked)' if locked else ''}")
    if room['id'] == interior['entrance']:
        out.append('the way back outside')
    lines.append(f"Ways out they can see: {'; '.join(out)}." if out else 'They see no way out of here.')
    lines.append('Code moves the character between rooms: the narrator tells only the room they are in and does not '
                 'move them on, or describe rooms they have not entered.')
    return '\n'.join(lines)


def prompt_text(lines: list[str]) -> str:
    return '## Inside (decided by the game; write it as it went)\n' + '\n'.join(lines) if lines else ''


def view(connection) -> dict | None:
    """The interior map widget: the rooms the character has seen and the passages they know, with where they are."""
    where = inside(connection)
    if where is None:
        return None
    interior = interior_of(connection, where)
    rooms_seen, ways = rooms_state(connection, interior['id']), ways_state(connection, interior['id'])
    known = set(rooms_seen)
    rooms = [{'id': room['id'], 'name': room['name'], 'level': room.get('level'), 'kind': room['kind'],
              'map': room.get('map'), 'here': room['id'] == where['room'],
              'cleared': bool(rooms_seen[room['id']].get('cleared'))} for room in interior['rooms'] if room['id'] in known]
    passages = []
    for room_id in known:
        for way in visible_ways(interior, room_id, ways):
            pair = sorted(way['passage']['between'])
            entry = {'between': pair, 'kind': way['passage']['kind'], 'to_known': way['to'] in known}
            if entry not in passages:
                passages.append(entry)
    return {'id': interior['id'], 'name': interior['name'], 'style': interior['style'],
            'levels': [level for level in interior['levels'] if any(room['level'] == level['id'] for room in rooms)],
            'rooms': rooms, 'passages': passages}

