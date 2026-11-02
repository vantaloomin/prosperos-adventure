"""The hex crawl (requirements "### Hex crawl"; docs/story.md "Journeys").

A travel map is a hex crawl unless it says `travel: "roads"` (Havenbrooke's car-or-bus roads, BABEL's Stair). Its
hexes are flat-topped, in axial coordinates (q, r).

- **Authored, then generated.** A world's authored hexes (world/data/hexes/<map>.json, Vallarith's painted from its
  world map by scripts/world/vallarith_hexes.py) are canon. Every hex past them is generated from the campaign's
  seed and its own coordinates alone, so it comes out the same whenever and from wherever it is first seen, and the
  map can grow in any direction without end: smooth noise for land, height and wet, carrying on the authored
  coast and regions near the edge and drifting into the map's frontier regions further out. A map with no authored
  hexes is all generated around its places, set where the travel map's own positions put them.
- **Roads.** The travel map's routes are drawn as roads from place to place; a step along a road takes an hour and
  is as dangerous as its route says. Stepping onto a road from the side costs the land's own hours.
- **Rivers and lakes.** An authored map can list its rivers (each the hexes it runs through, source to mouth, with
  how much water each carries) and lakes (water hexes). Crossing a river off the road takes an extra hour to ford
  (for a six-mile hex), unless one walks along its bank; a road crosses on a bridge where the river is big and by a
  ford where it is small, at no extra time. The narrator is told of every crossing and of a river where one stops.
- **Sites.** Hexes off the roads hold ruins, lairs, camps, shrines and hamlets, rolled from the map's site table by
  the seed, leaving out entries the intensity levels do not allow (an entry's `intensity`, as cards have). A found
  site is kept as it was found (story_sites), so changing the levels later does not change it. A found hamlet is a
  place on its map's Road city (`hamlet-<q>-<r>`, dungeon/story.py city_for) until a world package builds it out.
- **Fog of war.** The hexes the character has seen are game state (story_hexes), branched with the story: walking
  into a hex shows it and the ring around it (more from hills and mountains, none past the trees in forest or marsh).
"""
import functools
import hashlib
import heapq
import json
import math
import secrets

from dungeon import world_data
from dungeon.database import many, optional

# Hours to walk across a hex off the road, how many rings around one sees from it, and how it reads to the narrator.
# And how hard it is to keep one's bearings in it off the road (None: one can't get lost there in fair weather).
TERRAINS = {
    'water': {'hours': None, 'sight': 1, 'text': 'open water', 'lost': None},
    'plains': {'hours': 2, 'sight': 1, 'text': 'open country', 'lost': None},
    'forest': {'hours': 3, 'sight': 0, 'text': 'the forest', 'lost': 'normal'},
    'hills': {'hours': 3, 'sight': 2, 'text': 'the hills', 'lost': None},
    'mountains': {'hours': 5, 'sight': 3, 'text': 'the mountains', 'lost': 'hard'},
    'waste': {'hours': 3, 'sight': 1, 'text': 'the waste', 'lost': 'normal'},
    'marsh': {'hours': 4, 'sight': 0, 'text': 'the marsh', 'lost': 'hard'},
}
ROAD_HOURS = 1
# Hours to ford a river off the road (for a six-mile hex), and how much of the map's biggest river's water a river
# must carry where a road crosses it for the road to have a bridge rather than a ford.
FORD_HOURS = 1
BRIDGE_FLOW = 0.3
DIRECTIONS = {'north': (0, -1), 'north-east': (1, -1), 'south-east': (1, 0), 'south': (0, 1), 'south-west': (-1, 1),
              'north-west': (-1, 0)}
# Due east and west run along no side of a flat-topped hex: the way zigzags between the two either side.
ZIGZAG = {'east': ('north-east', 'south-east'), 'west': ('north-west', 'south-west')}
TURNS = ('north', 'north-east', 'south-east', 'south', 'south-west', 'north-west')
# The day's weather in a region, by weight; in winter rain falls as snow. Bad weather slows walking off the road and
# makes the way harder to keep.
WEATHER = (('clear', 40), ('overcast', 22), ('rain', 18), ('fog', 9), ('storm', 11))
SLOW = {'storm': 1.5, 'snow': 1.5}
MURK = ('fog', 'storm', 'snow')
HARDER = {None: 'normal', 'easy': 'normal', 'normal': 'hard', 'hard': 'very_hard', 'very_hard': 'extreme',
          'extreme': 'extreme'}
# How far past the authored hexes the land, coast and regions still carry on from them.
REACH = 6
# Hexes across a map's unit square, for a map with no authored hexes (its places' x and y run from 0 to 1).
SPAN = 100
# How far a way may wander outside the box around its two ends looking for a better path.
MARGIN = 12
FRONTIER = ['wilds']
DANGERS = ('none', 'low', 'medium', 'high')


def is_hex(travel_map: dict) -> bool:
    return travel_map.get('travel', 'hex') == 'hex'


def key(travel_map: dict) -> str:
    return travel_map.get('hexes') or travel_map.get('world') or 'map'


def neighbours(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in DIRECTIONS.values()]


def distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[0] + a[1] - b[0] - b[1])) // 2


def ring(centre: tuple[int, int], radius: int) -> list[tuple[int, int]]:
    """Every hex within `radius` of the centre, the centre included."""
    q0, r0 = centre
    return [(q0 + dq, r0 + dr) for dq in range(-radius, radius + 1)
            for dr in range(max(-radius, -dq - radius), min(radius, -dq + radius) + 1)]


def line(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """The hexes on a straight line from one to the other."""
    steps = distance(start, end)
    cells = []
    for step in range(steps + 1):
        t = step / steps if steps else 0
        q, r = start[0] + (end[0] - start[0]) * t + 1e-6, start[1] + (end[1] - start[1]) * t + 1e-6
        s = -q - r
        rq, rr, rs = round(q), round(r), round(s)
        if abs(rq - q) > abs(rr - r) and abs(rq - q) > abs(rs - s):
            rq = -rr - rs
        elif abs(rr - r) > abs(rs - s):
            rr = -rq - rs
        if not cells or cells[-1] != (rq, rr):
            cells.append((rq, rr))
    return cells


def offset(column: int, row: int) -> tuple[int, int]:
    """An authored file's column and row as an axial hex."""
    return column, row - (column - (column & 1)) // 2


def point(q: int, r: int) -> tuple[float, float]:
    """A hex's centre on the plane, one hex across."""
    return 1.5 * q / math.sqrt(3), r + q / 2


# Seeded noise --------------------------------------------------------------------------------------

def unit(seed: str, *parts) -> float:
    """A number from 0 to 1 that only the seed and the parts decide."""
    digest = hashlib.blake2b(':'.join(map(str, (seed, *parts))).encode(), digest_size=8).digest()
    return int.from_bytes(digest, 'big') / 2 ** 64


def noise(seed: str, field: str, x: float, y: float, scale: float) -> float:
    """Smooth value noise: random at the corners of a lattice `scale` hexes apart, blended between them."""
    x, y = x / scale, y / scale
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    corner = functools.partial(unit, seed, field)
    top = corner(x0, y0) * (1 - fx) + corner(x0 + 1, y0) * fx
    bottom = corner(x0, y0 + 1) * (1 - fx) + corner(x0 + 1, y0 + 1) * fx
    return top * (1 - fy) + bottom * fy


# The grid ------------------------------------------------------------------------------------------

class Grid:
    """One travel map's hexes for one campaign seed: the authored ones, and any other generated when asked for."""

    def __init__(self, travel_map: dict, seed: str):
        self.map, self.seed = travel_map, seed
        # A map with no hexes file can say how its generated land goes in the travel map itself (`hex_map`).
        data = world_data.read('hexes', key(travel_map)) or travel_map.get('hex_map') or {}
        self.generate = data.get('generate', {})
        self.miles = data.get('miles', 6)
        self.names = data.get('names', {})
        self.authored: dict[tuple[int, int], tuple[str, str]] = {}
        legend, regions = data.get('legend', {}), data.get('region_legend', {})
        for row, (terrain_row, region_row) in enumerate(zip(data.get('terrain', []), data.get('regions', []))):
            for column, (terrain, region) in enumerate(zip(terrain_row, region_row)):
                self.authored[offset(column, row)] = (legend[terrain], regions.get(region))
        nodes = {node['id']: node for node in travel_map['nodes']}
        self.rivers = self.read_water(data)
        self.places = {node: tuple(at) for node, at in data.get('places', {}).items()}
        for node in nodes.values():
            self.places.setdefault(node['id'], self.placed(node))
        self.at_place = {at: node for node, at in self.places.items()}
        self.roads: dict[tuple[int, int], dict] = {}
        # A road is quick only along it: two roads that pass side by side are not one road.
        self.road_steps: set[frozenset] = set()
        for road in data.get('roads') or [{'name': route['terrain'], 'danger': route['danger'],
                                            'cells': line(self.places[route['from']], self.places[route['to']])}
                                           for route in travel_map['routes']]:
            cells = [tuple(at) for at in road['cells']]
            self.road_steps.update(frozenset(pair) for pair in zip(cells, cells[1:]))
            for at in road['cells']:
                held = self.roads.get(tuple(at))
                if held is None or DANGERS.index(road['danger']) < DANGERS.index(held['danger']):
                    self.roads[tuple(at)] = {'name': road['name'], 'danger': road['danger']}
        self.region_of_place = {self.places[node]: nodes[node]['region'] for node in nodes}
        self.cache: dict[tuple[int, int], dict] = {}

    def read_water(self, data: dict) -> dict[tuple[int, int], dict]:
        """Make the map's lakes water, whatever the terrain rows say, and read its rivers: each river hex with the
        river's name, the most water any river carries through it, and the next hex downstream."""
        for at in data.get('lakes') or []:
            if tuple(at) in self.authored:
                self.authored[tuple(at)] = ('water', self.authored[tuple(at)][1])
        rivers: dict[tuple[int, int], dict] = {}
        for river in data.get('rivers') or []:
            cells, flows = [tuple(at) for at in river.get('cells', [])], river.get('flow') or []
            name = river.get('name') or self.names.get('river') or 'a river'
            for index, at in enumerate(cells):
                flow = flows[index] if index < len(flows) else 0.0
                if at not in rivers or flow > rivers[at]['flow']:
                    down = list(cells[index + 1]) if index + 1 < len(cells) else None
                    rivers[at] = {'id': river.get('id', name), 'name': name, 'flow': flow, 'down': down}
        return rivers

    def placed(self, node: dict) -> tuple[int, int]:
        """Where a place with no authored hex sits: its map position, SPAN hexes to the map's width."""
        span = self.generate.get('span', SPAN)
        q = round(node['map']['x'] * span * math.sqrt(3) / 1.5)
        return q, round(node['map']['y'] * span - q / 2)

    def cell(self, at: tuple[int, int]) -> dict:
        """A hex: its terrain and region, and the road and place on it, if any."""
        if at not in self.cache:
            terrain, region = self.authored.get(at) or self.generated(at)
            if at in self.region_of_place:
                region = self.region_of_place[at]
            if terrain == 'water' and (at in self.roads or at in self.at_place):
                terrain = 'plains'
            # Generated land never shuts a place in: every way out of it is walkable for a step.
            elif terrain == 'water' and at not in self.authored and any(
                    other in self.at_place for other in neighbours(*at)):
                terrain = self.generate.get('swap', {}).get('plains', 'plains')
            river = self.rivers.get(at) if terrain != 'water' else None
            self.cache[at] = {'q': at[0], 'r': at[1], 'terrain': terrain, 'region': region,
                              'road': self.roads.get(at), 'place': self.at_place.get(at), 'river': river}
        return self.cache[at]

    def nearest_authored(self, at: tuple[int, int]) -> tuple[int, bool, str | None] | None:
        """How far the nearest authored hexes are, whether most of them are land, and a region they carry."""
        for radius in range(1, REACH + 1):
            found = [self.authored[other] for other in ring(at, radius)
                     if other in self.authored and distance(at, other) == radius]
            if found:
                land = [region for terrain, region in found if terrain != 'water']
                return radius, len(land) * 2 > len(found), next((region for region in land if region), None)
        return None

    def generated(self, at: tuple[int, int]) -> tuple[str, str]:
        """A hex no one authored, decided by the seed and where it is, carrying on the authored land near it."""
        x, y = point(*at)
        settings = self.generate
        land = noise(self.seed, 'land', x, y, 9) * 0.7 + noise(self.seed, 'land2', x, y, 3) * 0.3
        threshold = settings.get('water', 0.42 if self.authored else 0.3)
        near = self.nearest_authored(at) if self.authored else None
        if near:
            radius, landward, _ = near
            pull = 0.3 * (1 - radius / (REACH + 1))
            threshold += -pull if landward else pull
        if land < threshold:
            return 'water', None
        height, wet = noise(self.seed, 'height', x, y, 7), noise(self.seed, 'wet', x, y, 5)
        if height > 0.72:
            terrain = 'mountains'
        elif height > 0.6:
            terrain = 'hills'
        elif wet > 0.78 and height < 0.35:
            terrain = 'marsh'
        elif wet > 0.58:
            terrain = 'forest'
        elif wet < 0.22:
            terrain = 'waste'
        else:
            terrain = 'plains'
        # A map's own land: Havenbrooke's woods have no waste or mountains, and its open ground is mostly trees.
        terrain = settings.get('swap', {}).get(terrain, terrain)
        if near and near[2]:
            return terrain, near[2]
        frontier = settings.get('frontier', FRONTIER)
        return terrain, frontier[int(noise(self.seed, 'region', x, y, 20) * len(frontier)) % len(frontier)]

    def on_road(self, here: tuple[int, int], there: tuple[int, int]) -> bool:
        return frozenset((here, there)) in self.road_steps

    def danger(self, cell: dict, road: bool) -> str:
        if road:
            return cell['road']['danger']
        return (self.map['regions'].get(cell['region']) or {}).get('danger', 'high')

    def hours(self, cell: dict, road: bool) -> float | None:
        """Hours to cross a hex, for its size: the terrain table is for six-mile hexes."""
        hours = ROAD_HOURS if road else TERRAINS[cell['terrain']]['hours']
        return None if hours is None else round(hours * self.miles / 6, 2)

    def crossing(self, here: tuple[int, int], there: tuple[int, int], road: bool) -> dict | None:
        """Crossing a river stepping into a hex: by the road's bridge or ford, or fording it off the road (which takes
        FORD_HOURS more); none walking along the bank of the river one is already beside, or where there is none."""
        river = self.cell(there)['river']
        if not river:
            return None
        if road:
            return {'river': river['name'], 'by': 'bridge' if river['flow'] >= BRIDGE_FLOW else 'ford', 'hours': 0}
        beside = self.cell(here)['river']
        if beside and beside['id'] == river['id'] and (beside['down'] == list(there) or river['down'] == list(here)):
            return None
        return {'river': river['name'], 'by': 'wading', 'hours': round(FORD_HOURS * self.miles / 6, 2)}

    def step_hours(self, here: tuple[int, int], there: tuple[int, int]) -> float | None:
        """Hours for one step, a river's crossing included."""
        road = self.on_road(here, there)
        hours = self.hours(self.cell(there), road)
        if hours is None:
            return None
        crossing = self.crossing(here, there, road)
        return hours + (crossing['hours'] if crossing else 0)

    def text(self, cell: dict, road: bool) -> str:
        return cell['road']['name'] if road else self.terrain_text(cell['terrain'])

    def terrain_text(self, terrain: str) -> str:
        return self.names.get(terrain) or TERRAINS[terrain]['text']

    def way(self, start: tuple[int, int], goal: tuple[int, int], weather_: str = 'clear') -> list[dict] | None:
        """The quickest way from one hex to another, each step as {from, to, hours, terrain, danger, region}."""
        low_q, high_q = min(start[0], goal[0]) - MARGIN, max(start[0], goal[0]) + MARGIN
        low_r, high_r = min(start[1], goal[1]) - MARGIN, max(start[1], goal[1]) + MARGIN
        queue, best, came = [(0.0, 0.0, start)], {start: 0.0}, {}
        while queue:
            _, spent, at = heapq.heappop(queue)
            if at == goal:
                break
            if spent > best.get(at, math.inf):
                continue
            for other in neighbours(*at):
                if not (low_q <= other[0] <= high_q and low_r <= other[1] <= high_r):
                    continue
                hours = self.step_hours(at, other)
                if hours is None:
                    continue
                total = spent + hours
                if total < best.get(other, math.inf):
                    best[other], came[other] = total, at
                    heapq.heappush(queue, (total + distance(other, goal) * ROAD_HOURS, total, other))
        if goal not in best:
            return None
        cells = [goal]
        while cells[-1] != start:
            cells.append(came[cells[-1]])
        cells.reverse()
        return [self.step(here, there, weather_) for here, there in zip(cells, cells[1:])]

    def step(self, here: tuple[int, int], there: tuple[int, int], weather_: str = 'clear') -> dict:
        cell, road = self.cell(there), self.on_road(here, there)
        hours = self.hours(cell, road)
        crossing = self.crossing(here, there, road) if hours is not None else None
        if hours is not None and not road:
            hours = (hours + (crossing['hours'] if crossing else 0)) * SLOW.get(weather_, 1)
        leg = {'from': list(here), 'to': list(there), 'hours': hours, 'terrain': self.text(cell, road),
               'danger': self.danger(cell, road), 'region': cell['region']}
        return (leg | ({'place': cell['place']} if cell['place'] else {}) | ({'road': True} if road else {})
                | ({'crossing': crossing} if crossing else {}))

    def sight(self, at: tuple[int, int]) -> list[tuple[int, int]]:
        cell = self.cell(at)
        return ring(at, TERRAINS[cell['terrain']]['sight'] if not cell['road'] else max(
            1, TERRAINS[cell['terrain']]['sight']))


    def heading(self, start: tuple[int, int], direction: str, budget: float, weather: str,
                about: bool = False) -> tuple[list[dict], str]:
        """A day's walk in one direction from a hex: the steps, and why it stopped ('day', 'place' or 'water'). `about`:
        the budget is a rough length ("for an hour or so"), so the step that comes closest to it is taken too."""
        turns = ZIGZAG.get(direction, (direction,))
        legs, at, spent = [], start, 0.0
        while True:
            dq, dr = DIRECTIONS[turns[len(legs) % len(turns)]]
            there = (at[0] + dq, at[1] + dr)
            leg = self.step(at, there, weather)
            if leg['hours'] is None:
                return legs, 'water'
            if legs and spent + leg['hours'] > budget and (not about or spent + leg['hours'] - budget > budget - spent):
                return legs, 'day'
            legs.append(leg)
            spent += leg['hours']
            at = there
            if leg.get('place'):
                return legs, 'place'

    def site(self, at: tuple[int, int], levels: dict[str, int] | None = None) -> dict | None:
        """The site in a hex, if it has one, decided by the seed: never on water, a road or a place, and only what the
        intensity levels allow (none given: everything)."""
        table = self.map.get('sites')
        cell = self.cell(at)
        if not table or cell['terrain'] == 'water' or cell['road'] or cell['place']:
            return None
        if unit(self.seed, 'site', *at) * 100 >= table.get('odds', 4):
            return None
        entries = [entry for entry in [*table.get(cell['region'], []), *table.get('any', [])]
                   if allowed(entry, levels)]
        if not entries:
            return None
        roll, running = unit(self.seed, 'site-kind', *at) * sum(entry['weight'] for entry in entries), 0
        entry = entries[-1]
        for candidate in entries:
            running += candidate['weight']
            if roll <= running:
                entry = candidate
                break
        owners = table.get('owners') or ['Hob']
        template = entry['names'][int(unit(self.seed, 'site-name', *at) * len(entry['names']))]
        name = template.format(owner=owners[int(unit(self.seed, 'site-owner', *at) * len(owners))])
        return {'q': at[0], 'r': at[1], 'kind': entry['kind'], 'name': name, 'text': entry['text'],
                'visible': entry['visible']}

    def came_upon(self, legs: list[dict], found: set, levels: dict[str, int] | None = None) -> tuple[list[dict],
                                                                                                    dict | None]:
        """The legs up to the first hex with a site the character did not know of, that they would notice walking in
        (a hidden one is only found by searching), and the site."""
        for index, leg in enumerate(legs):
            site = self.site(tuple(leg['to']), levels)
            if site and site['visible'] and (site['q'], site['r']) not in found:
                return legs[:index + 1], site
        return legs, None

    def lost_odds(self, leg: dict, weather: str) -> str | None:
        """How hard keeping one's bearings is in a step's hex, or None where it can't be lost."""
        if leg.get('road'):
            return None
        difficulty = TERRAINS[self.cell(tuple(leg['to']))['terrain']]['lost']
        return HARDER[difficulty] if weather in MURK else difficulty


# The weather -------------------------------------------------------------------------------------------

def allowed(entry: dict, levels: dict[str, int] | None) -> bool:
    """Whether the intensity levels let a table entry happen: each category it names at least at its level."""
    return levels is None or all(levels.get(category, 3) >= level
                                 for category, level in (entry.get('intensity') or {}).items())


def hamlet_id(at: tuple[int, int]) -> str:
    return f'hamlet-{at[0]}-{at[1]}'


def weather(seed_: str, day: str, region: str | None, month: int) -> str:
    """The day's weather in a region, the same for the whole day and decided by the seed alone."""
    roll, at = unit(seed_, 'weather', day, region) * sum(weight for _, weight in WEATHER), 0
    for kind, weight in WEATHER:
        at += weight
        if roll <= at:
            return 'snow' if kind in ('rain', 'storm') and month in (12, 1, 2) else kind
    return 'clear'


# The campaign's seed and what the character has seen -----------------------------------------------

def seed(connection) -> str:
    """The campaign's world seed, chosen the first time the land past the authored map is needed."""
    row = optional(connection, 'SELECT seed FROM story_campaign WHERE id=1')
    if row and row['seed']:
        return row['seed']
    chosen = secrets.token_hex(8)
    connection.execute('INSERT INTO story_campaign (id, seed) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET seed=?',
                       (chosen, chosen))
    return chosen


def grid(connection, travel_map: dict) -> Grid:
    return _grid(key(travel_map), seed(connection), world_data.version())


@functools.lru_cache(maxsize=4)
def _grid(map_key: str, seed_: str, _version) -> Grid:
    from dungeon import travel
    # A world's roads map shares its key with nothing that crawls: only a hex crawl has a grid.
    travel_map = next(found for found in travel.maps() if key(found) == map_key and is_hex(found))
    return Grid(travel_map, seed_)


def levels(connection) -> dict[str, int]:
    """The intensity levels in play (dungeon/tone.py), which sites may be."""
    from dungeon import tone
    return tone.now(connection)['levels']


def site(connection, board: Grid, at: tuple[int, int]) -> dict | None:
    """The site in a hex: the one found there, else what the seed puts there at the levels in play."""
    return found_sites(connection, board).get(at) or board.site(at, levels(connection))


def reveal(connection, board: Grid, cells: list[tuple[int, int]], walked: bool = True):
    """The character walks into these hexes: each is visited, and seen with what can be seen from it, sites that
    show from a distance among it."""
    name = key(board.map)
    allowed_ = levels(connection)
    for at in cells:
        for other in board.sight(at):
            connection.execute('INSERT OR IGNORE INTO story_hexes (map, q, r, visited) VALUES (?, ?, ?, 0)',
                               (name, *other))
            if (found := board.site(other, allowed_)) and found['visible']:
                find_site(connection, board, other, found)
        if walked:
            connection.execute('INSERT INTO story_hexes (map, q, r, visited) VALUES (?, ?, ?, 1) '
                               'ON CONFLICT(map, q, r) DO UPDATE SET visited=1', (name, *at))


def find_site(connection, board: Grid, at: tuple[int, int], found: dict):
    """The character has found this site: it is kept as found, whatever the levels are later."""
    connection.execute('INSERT OR IGNORE INTO story_sites (map, q, r, site) VALUES (?, ?, ?, ?)',
                       (key(board.map), *at, json.dumps(found)))


def found_sites(connection, board: Grid) -> dict[tuple[int, int], dict]:
    """The sites the character has found on this map, by hex (one found before sites were kept: the seed's, again)."""
    found = {}
    for row in many(connection, 'SELECT q, r, site FROM story_sites WHERE map=?', (key(board.map),)):
        at = (row['q'], row['r'])
        if kept := json.loads(row['site']) if row['site'] else board.site(at):
            found[at] = kept
    return found


def hamlets(connection, travel_map: dict) -> list[dict]:
    """The hamlets found on a hex crawl, as places in the wild's city: each one a copy of the wild place, named and
    described as found, with people of its own (dungeon/world/townsfolk.py) because it is a place of its own."""
    wild = travel_map.get('wild')
    if not wild or not is_hex(travel_map):
        return []
    board = grid(connection, travel_map)
    return [{'id': hamlet_id(at), 'name': found['name'], 'kind': 'hamlet', 'summary': found['text'],
             'tags': ['travel', 'hamlet'], 'q': at[0], 'r': at[1]}
            for at, found in sorted(found_sites(connection, board).items()) if found['kind'] == 'hamlet']


def seen(connection, board: Grid, here: tuple[int, int] | None = None) -> dict[tuple[int, int], bool]:
    """Every hex the character has seen, and whether they have walked it; where they are, and what they see from
    there, count too."""
    rows = {(row['q'], row['r']): bool(row['visited']) for row in many(
        connection, 'SELECT q, r, visited FROM story_hexes WHERE map=?', (key(board.map),))}
    if here is not None:
        for other in board.sight(here):
            rows.setdefault(other, False)
        rows[here] = True
    return rows


def view(connection, board: Grid, here: tuple[int, int]) -> list[dict]:
    """The hexes the character knows, for the map on screen, with the sites found in them."""
    sites = found_sites(connection, board)
    return [board.cell(at) | {'visited': visited, 'site': sites[at]['name'] if at in sites else None}
            for at, visited in sorted(seen(connection, board, here).items())]


# Out in the wild --------------------------------------------------------------------------------------

def position(connection, board: Grid) -> dict | None:
    """Where the character is when out in the wild on this map: the hex, and the hex they believe they are in."""
    row = optional(connection, 'SELECT * FROM story_position WHERE id=1 AND map=?', (key(board.map),))
    if row is None:
        return None
    return {'at': (row['q'], row['r']), 'believed': (row['believed_q'], row['believed_r'])}


def place_at(connection, board: Grid, at: tuple[int, int], believed: tuple[int, int] | None = None):
    """The character stops out in the wild in this hex (believing they are in another, when lost); at a place
    there is no position kept, the place is where they are."""
    connection.execute('DELETE FROM story_position')
    if at in board.at_place and (believed is None or believed == at):
        return
    believed = believed or at
    connection.execute('INSERT INTO story_position (id, map, q, r, believed_q, believed_r) VALUES (1, ?, ?, ?, ?, ?)',
                       (key(board.map), *at, *believed))


def bearing(start: tuple[int, int], end: tuple[int, int]) -> str:
    """Which way one hex lies from another, as a compass word."""
    (x1, y1), (x2, y2) = point(*start), point(*end)
    angle = math.degrees(math.atan2(x2 - x1, y1 - y2)) % 360
    return ('north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west')[
        round(angle / 45) % 8]
