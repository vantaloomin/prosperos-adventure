"""Town maps (requirements "### Town maps"): a street map of a town, laid out by code from the town's data and the
campaign's seed, never drawn by hand or by an image model.

- **From the data.** A town file already says where its neighborhoods are (lat and lon), which places are in which
  neighborhood, and where its rivers run. That is all the map needs: the town is cut into patches (a Voronoi diagram
  of points spread from the middle out), each patch near enough the middle belongs to the nearest neighborhood, the
  patch edges are its streets, and its main roads run along them from the square out to the edge. A neighborhood far
  out of town (Kingswood's cutting line, Hollin's Reachwall) is not drawn: a road leaves the map toward it.
- **The seed decides the rest.** The same town and seed always give the same map, so it never has to be stored.
  Another campaign's Kingswood has the same neighborhoods in the same places, with other streets.
- **Lots, filled as they are needed.** Each patch is split into lots, the town's buildings. The town's own places,
  employers and colleges are given lots in their own neighborhood when the map is laid out (an open place, a park or
  a square, takes a whole patch). Every other lot is blank: what is in it is decided when the character first looks
  (`look`), from the town's names and its look's table (world/data/town_lots.json) at the intensity levels in
  play, then kept as found.
- **Found, not known.** A town's own places are on the map only once the character knows of them (`known`):
  where they have been, what they passed on the street, a building they looked at, or a place named to them in the
  story. A stranger knows the landmarks anyone could find (the square, the temple, the market, the big employers);
  a character whose home is the town knows all of it but what is hidden. The rest are blank lots until found.
- **Style.** The era picks the look unless the town's `town_map` says otherwise: 'ink' (a hand-inked old town, for
  fantasy and the past), 'street' (a modern grid) or 'floor' (a town on one floor of BABEL's tower, walled by it).
"""
import functools
import hashlib
import heapq
import json
import math
import re
from collections import Counter

from dungeon import hexes, packages, story
from dungeon.database import many
from dungeon.errors import require
from dungeon.hexes import unit

# How far out the map runs, in its own units: the town fills the middle 100 and the country runs on to 160.
TOWN = 100.0
EDGE = 160.0
# A neighborhood further from the middle than this many times the typical distance is out of town.
OUT_OF_TOWN = 2.5
# Place kinds that are open ground, given a whole patch rather than a lot.
OPEN = {'park', 'garden', 'stadium', 'beach', 'square', 'trail'}
# Place kinds that want a big lot: the largest one left in their neighborhood.
GRAND = {'landmark', 'temple', 'guildhall', 'museum', 'library', 'venue', 'market', 'stadium'}
SIDES = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}
STYLES = {'modern': 'street', 'future': 'street'}
STREET = 1.6       # half the width of a street between patches
ROAD = 2.6         # and of a main road
MIN_LOT = 6.0      # a piece smaller than this is a yard, not a lot


# Plane geometry -----------------------------------------------------------------------------------

def area(polygon: list[tuple[float, float]]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def centroid(polygon: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(polygon)
    return sum(x for x, _ in polygon) / n, sum(y for _, y in polygon) / n


def clip(polygon: list[tuple[float, float]], a: tuple[float, float], b: tuple[float, float]):
    """The part of a convex polygon on point a's side of the line halfway between a and b."""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    nx, ny = b[0] - a[0], b[1] - a[1]
    return cut(polygon, (mx, my), (nx, ny))


def cut(polygon: list[tuple[float, float]], point: tuple[float, float], normal: tuple[float, float]):
    """The part of a convex polygon behind the line through `point` facing `normal`."""
    side = [(x - point[0]) * normal[0] + (y - point[1]) * normal[1] for x, y in polygon]
    kept = []
    for i, (here, there) in enumerate(zip(polygon, polygon[1:] + polygon[:1])):
        s1, s2 = side[i], side[(i + 1) % len(polygon)]
        if s1 <= 0:
            kept.append(here)
        if (s1 < 0 < s2) or (s2 < 0 < s1):
            t = s1 / (s1 - s2)
            kept.append((here[0] + (there[0] - here[0]) * t, here[1] + (there[1] - here[1]) * t))
    return kept


def inset(polygon: list[tuple[float, float]], widths: list[float]) -> list[tuple[float, float]]:
    """A convex polygon with each edge moved in by its own width (an edge's width is widths[i], edge i running from
    vertex i to the next), or [] when nothing is left."""
    result = polygon
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(polygon, polygon[1:] + polygon[:1])):
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 1e-9 or widths[i] <= 0:
            continue
        # Counter-clockwise polygons have their inside on the left of each edge.
        inward = (-(y2 - y1) / length, (x2 - x1) / length)
        point = (x1 + inward[0] * widths[i], y1 + inward[1] * widths[i])
        result = cut(result, point, (-inward[0], -inward[1]))
        if len(result) < 3:
            return []
    return result


def counter_clockwise(polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
    signed = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]))
    return polygon if signed > 0 else polygon[::-1]


def to_segment(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = 0 if length == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def to_line(p: tuple[float, float], points: list[tuple[float, float]]) -> float:
    return min(to_segment(p, a, b) for a, b in zip(points, points[1:]))


def rounded(point: tuple[float, float]) -> tuple[float, float]:
    return round(point[0], 1), round(point[1], 1)


# Laying a town out --------------------------------------------------------------------------------

def style(data: dict) -> str:
    return (data.get('town_map') or {}).get('style') or STYLES.get(data.get('era', 'modern'), 'ink')


def has_map(data: dict) -> bool:
    """A town gets a map; a world's road or wilds (vallarith-road, havenbrooke-road, babel-floors), whose
    neighborhoods are whole regions, says `town_map: {"style": "none"}`."""
    return (data.get('town_map') or {}).get('style') != 'none'


def project(data: dict, points: list | None = None) -> list[tuple[float, float]] | dict[str, tuple[float, float]]:
    """Each neighborhood's position on the map (or, given [lat, lon] points, theirs), the town's middle at (0, 0),
    north up and scaled so the typical neighborhood sits about halfway out of the town."""
    lat0, lon0 = data['lat'], data['lon']
    scale = math.cos(math.radians(lat0))

    def metres(lat, lon):
        return (lon - lon0) * 111320 * scale, -(lat - lat0) * 110540

    hoods = {hood['id']: metres(hood['lat'], hood['lon']) for hood in data['neighborhoods']}
    spread = sorted(math.hypot(*at) for at in hoods.values() if math.hypot(*at) > 1)
    factor = TOWN * 0.45 / (spread[len(spread) // 2] if spread else 1.0)
    if points is not None:
        return [(x * factor, y * factor) for x, y in (metres(lat, lon) for lat, lon in points)]
    return {hood: (x * factor, y * factor) for hood, (x, y) in hoods.items()}


def seeds(look: str, count: int, seed: str, town_id: str) -> list[tuple[float, float]]:
    """Where the patches' middles are: a sunflower spread, denser in the middle, or for a modern town a grid."""
    if look == 'street':
        step = EDGE * 2 / math.sqrt(count * 1.25)
        tilt = (unit(seed, town_id, 'tilt') - 0.5) * 0.5
        points = []
        rows = int(EDGE * 2 / step) + 2
        for row in range(-rows // 2, rows // 2 + 1):
            for column in range(-rows // 2, rows // 2 + 1):
                # Blocks run longer one way than the other, as a real grid's do.
                x = column * step * 1.35 + (unit(seed, town_id, 'jx', row, column) - 0.5) * step * 0.12
                y = row * step * 0.8 + (unit(seed, town_id, 'jy', row, column) - 0.5) * step * 0.12
                x, y = x * math.cos(tilt) - y * math.sin(tilt), x * math.sin(tilt) + y * math.cos(tilt)
                if math.hypot(x, y) < EDGE:
                    points.append((x, y))
        return points
    golden = math.pi * (3 - math.sqrt(5))
    turn = unit(seed, town_id, 'turn') * math.tau
    points = [(0.0, 0.0)]
    for i in range(1, count):
        radius = EDGE * (i / count) ** 0.72 * (0.92 + unit(seed, town_id, 'r', i) * 0.16)
        angle = turn + i * golden + (unit(seed, town_id, 'a', i) - 0.5) * 0.5
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return points


def cells(points: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
    """Each point's Voronoi cell, clipped to a circle a little past the edge."""
    bound = EDGE * 1.12
    circle = [(bound * math.cos(math.tau * i / 40), bound * math.sin(math.tau * i / 40)) for i in range(40)]
    found = []
    for i, a in enumerate(points):
        others = sorted((j for j in range(len(points)) if j != i),
                        key=lambda j: (points[j][0] - a[0]) ** 2 + (points[j][1] - a[1]) ** 2)
        polygon = circle
        for j in others:
            b = points[j]
            # No point further than twice the cell's furthest corner can cut it.
            reach = max(math.hypot(x - a[0], y - a[1]) for x, y in polygon)
            if math.hypot(b[0] - a[0], b[1] - a[1]) > reach * 2:
                break
            polygon = clip(polygon, a, b)
        found.append(counter_clockwise(polygon))
    return found


def split(polygon: list[tuple[float, float]], seed: str, key: str, size: float) -> list[tuple[str, list]]:
    """A block cut into lots: halved across its longest side, again and again, until each piece is about `size`."""
    if area(polygon) <= size * (0.7 + unit(seed, key, 'stop') * 0.8) or len(polygon) < 3:
        return [(key, polygon)]
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    (x1, y1), (x2, y2) = max(edges, key=lambda edge: math.dist(*edge))
    t = 0.35 + unit(seed, key, 'at') * 0.3
    point = (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
    normal = (x2 - x1, y2 - y1)
    halves = cut(polygon, point, normal), cut(polygon, point, (-normal[0], -normal[1]))
    if any(len(half) < 3 or area(half) < size * 0.2 for half in halves):
        return [(key, polygon)]
    return [*split(halves[0], seed, key + 'a', size), *split(halves[1], seed, key + 'b', size)]


@functools.lru_cache(maxsize=16)
def _layout(town_id: str, seed: str, digest: str, data_json: str) -> dict:
    return build(json.loads(data_json), seed)


def layout(data: dict, seed: str) -> dict:
    """The town's map for this seed, worked out once and kept while the town's data is unchanged."""
    kept = {key: data.get(key) for key in ('id', 'era', 'lat', 'lon', 'neighborhoods', 'employers', 'colleges', 'water',
                                           'transit', 'town_map')}
    kept['places'] = [place for place in data.get('places', []) if 'lot' not in place.get('tags', [])]
    text = json.dumps(kept, sort_keys=True, default=str)
    return _layout(data['id'], seed, hashlib.blake2b(text.encode(), digest_size=8).hexdigest(), text)


def build(data: dict, seed: str) -> dict:
    return Town(data, seed).lay_out()


class Town:
    """One town laid out for one seed, a step at a time."""

    def __init__(self, data: dict, seed: str):
        self.data, self.seed, self.id, self.look = data, seed, data['id'], style(data)
        self.names = {hood['id']: hood['name'] for hood in data['neighborhoods']}
        self.anchors = project(data)
        spread = sorted(math.hypot(*at) for at in self.anchors.values() if math.hypot(*at) > 1)
        typical = spread[len(spread) // 2] if spread else TOWN * 0.45
        self.away = {hood for hood, at in self.anchors.items() if math.hypot(*at) > typical * OUT_OF_TOWN}
        self.near = self.spaced({hood: at for hood, at in self.anchors.items() if hood not in self.away}
                                or self.anchors)
        self.middle = min(self.near, key=lambda hood: math.hypot(*self.near[hood]))
        self.rivers = [(project(data, water['points']), water) for water in data.get('water', [])
                       if water['kind'] == 'river']
        # The town's own places, employers and colleges, each to be given a lot or a patch in its neighborhood.
        # A lot looked at is a place of the town (lot_places), but it already has its lot.
        things = [(place, 'place') for place in data.get('places', [])
                  if not {'hamlet', 'lot'} & set(place.get('tags', []))]
        # An employer that is also a place (Varro's Mill the workplace and the place) is the one building.
        named = {place['name'].casefold() for place, _ in things}
        things += [(employer, 'employer') for employer in data.get('employers', [])
                   if employer['name'].casefold() not in named]
        things += [(college, 'college') for college in data.get('colleges', [])]
        self.things = sorted(things, key=lambda pair: (pair[1], pair[0]['id']))
        self.wanted = Counter(thing.get('neighborhood') for thing, what in self.things
                              if not (what == 'place' and thing['kind'] in OPEN))

    def spaced(self, near: dict) -> dict:
        """Neighborhoods past the town's edge pulled in so their patches still fall in town, and two given the same
        spot nudged apart."""
        reach = max(math.hypot(*at) for at in near.values()) or 1
        if reach > TOWN * 0.8:
            near = {hood: (x * TOWN * 0.8 / reach, y * TOWN * 0.8 / reach) for hood, (x, y) in near.items()}
        placed: dict[str, tuple[float, float]] = {}
        for hood, (x, y) in near.items():
            while any(math.dist((x, y), other) < 8 for other in placed.values()):
                angle = unit(self.seed, self.id, 'nudge', hood, x) * math.tau
                x, y = x + 18 * math.cos(angle), y + 18 * math.sin(angle)
            placed[hood] = (x, y)
        return placed

    def under_water(self, point: tuple[float, float]) -> bool:
        """Whether a point is out to sea (past a coast just beyond the town's last neighborhood on the sea's side)
        or in a lake."""
        for water in self.data.get('water', []):
            if water['kind'] == 'sea':
                dx, dy = SIDES[water['side']]
                coast = max(x * dx + y * dy for x, y in self.near.values()) + 16
                wobble = (hexes.noise(self.seed, 'coast', point[0] * dy, point[1] * dx, 30) - 0.5) * 24
                if point[0] * dx + point[1] * dy > coast + wobble:
                    return True
            elif water['kind'] == 'lake':
                at = project(self.data, water['points'])[0]
                if math.dist(point, at) < max(8.0, min(30.0, water['width_km'] * 1000 / 40)):
                    return True
        return False

    def near_water(self, point: tuple[float, float]) -> bool:
        return any(to_line(point, line) < width(water) / 2 + 1.5 for line, water in self.rivers)

    def lay_out(self) -> dict:
        self.lay_patches()
        self.share_patches()
        self.lay_streets()
        self.lay_roads()
        self.open_places()
        self.cut_lots()
        self.give_lots()
        return self.result()

    def lay_patches(self):
        """Each patch: in town or out in the country, and whose neighborhood. A neighborhood with more places claims
        more of the town. The patch nearest the middle neighborhood is the town's square."""
        count = max(60, min(150, 40 + 14 * len(self.near)))
        points = seeds(self.look, count, self.seed, self.id)
        pull = {hood: math.sqrt(2 + self.wanted[hood]) for hood in self.near}
        self.patches = []
        for i, (point, polygon) in enumerate(zip(points, cells(points))):
            distance = math.hypot(*point) * (0.9 + unit(self.seed, self.id, 'rim', i) * 0.2)
            hood = min(self.near, key=lambda h: math.dist(point, self.near[h]) / pull[h])
            kind = 'water' if self.under_water(point) else 'town' if distance < TOWN else 'country'
            self.patches.append({'id': i, 'polygon': polygon, 'middle': point, 'kind': kind,
                                 'neighborhood': hood if kind == 'town' else None})
        if not any(patch['kind'] == 'town' for patch in self.patches):
            raise ValueError(f'{self.id} is all water.')
        self.square = min((patch for patch in self.patches if patch['kind'] == 'town'
                           and not self.near_water(patch['middle'])),
                          key=lambda patch: math.dist(patch['middle'], self.near[self.middle]))
        self.square['kind'], self.square['neighborhood'] = 'square', self.middle

    def share_patches(self):
        """Every neighborhood gets patches enough for its places, taken from the nearest neighbors that can spare
        them."""
        need = {hood: max(1, math.ceil(self.wanted[hood] / 3)) for hood in self.near}
        town = [patch for patch in self.patches if patch['kind'] == 'town']
        for hood in sorted(self.near, key=lambda h: (-need[h], h)):
            held = Counter(patch['neighborhood'] for patch in town)
            while held[hood] < need[hood]:
                spare = [patch for patch in town if patch['neighborhood'] != hood
                         and held[patch['neighborhood']] > need[patch['neighborhood']]]
                if not spare:
                    break
                taken = min(spare, key=lambda patch: math.dist(patch['middle'], self.near[hood]))
                held[taken['neighborhood']] -= 1
                held[hood] += 1
                taken['neighborhood'] = hood

    def lay_streets(self):
        """The street network: the patches' edges, keyed by their rounded ends."""
        self.edges: dict[tuple, set[int]] = {}
        for patch in self.patches:
            polygon = patch['polygon']
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                if math.dist(a, b) >= 0.5:
                    self.edges.setdefault(tuple(sorted((rounded(a), rounded(b)))), set()).add(patch['id'])
        self.in_town = {patch['id'] for patch in self.patches if patch['kind'] in ('town', 'square')}
        # Roads keep to land: an edge with water on both sides is no way to go.
        dry = {patch['id'] for patch in self.patches if patch['kind'] != 'water'}
        self.graph: dict[tuple, list[tuple]] = {}
        for (a, b), owners in self.edges.items():
            if not owners & dry:
                continue
            self.graph.setdefault(a, []).append(b)
            self.graph.setdefault(b, []).append(a)

    def lay_roads(self):
        """Main roads from the square out to the map's edge: toward each neighborhood out of town and a few more."""
        def heading(hood):
            return math.atan2(self.anchors[hood][1], self.anchors[hood][0])

        def apart(a, b):
            return abs((a - b + math.pi) % math.tau - math.pi)

        ways = [heading(hood) for hood in sorted(self.away)]
        extra = 4 if self.look == 'floor' else 3
        start = unit(self.seed, self.id, 'gates') * math.tau
        ways += [angle for angle in (start + math.tau * i / extra for i in range(extra))
                 if all(apart(angle, way) > 0.6 for way in ways)]
        corners = [rounded(point) for point in self.square['polygon']]
        rim = [vertex for vertex in self.graph if math.hypot(*vertex) > EDGE]
        self.roads, self.toward = [], {}
        for angle in ways:
            if not rim:
                break
            target = max(rim, key=lambda v: math.cos(math.atan2(v[1], v[0]) - angle) * math.hypot(*v))
            if path := route(self.graph, corners, target):
                self.roads.append(path)
                self.toward |= {hood: path[-1] for hood in self.away if apart(heading(hood), angle) < 0.01}
        self.road_edges = {tuple(sorted(pair)) for path in self.roads for pair in zip(path, path[1:])}

    def open_places(self):
        """Open places (a park, a square, a trail) take whole patches in their neighborhood: the first square of the
        middle neighborhood is the town's square; a park or trail likes the town's edge, a square the middle."""
        self.open_ground: dict[int, dict] = {}
        for thing, what in self.things:
            if what != 'place' or thing['kind'] not in OPEN or thing.get('neighborhood') in self.away:
                continue
            if thing['kind'] == 'square' and self.square['id'] not in self.open_ground \
                    and thing.get('neighborhood') == self.middle:
                self.open_ground[self.square['id']] = thing
                continue
            choices = [patch for patch in self.patches if patch['kind'] == 'town'
                       and patch['neighborhood'] == thing.get('neighborhood')]
            outward = 1 if thing['kind'] in ('park', 'trail', 'beach', 'stadium') else -1
            choices.sort(key=lambda patch: (-outward * math.hypot(*patch['middle']),
                                            unit(self.seed, thing['id'], patch['id'])))
            # A neighborhood keeps at least one patch for its buildings.
            if len(choices) > 1:
                self.open_ground[choices[0]['id']] = thing
                choices[0]['kind'] = 'open'

    def blocks(self) -> dict[int, list]:
        """Each town patch's block, inside its streets and roads."""
        found = {}
        for patch in self.patches:
            if patch['kind'] != 'town':
                continue
            polygon = patch['polygon']
            widths = [ROAD if tuple(sorted((rounded(a), rounded(b)))) in self.road_edges else STREET
                      for a, b in zip(polygon, polygon[1:] + polygon[:1])]
            if block := inset(polygon, widths):
                found[patch['id']] = block
        return found

    def cut_lots(self):
        """The blocks cut into lots, smaller in the middle; a neighborhood with many places of its own is cut finer,
        so there are always a few times as many lots as places. No lot stands in a river, and some in an old town's
        outskirts stay yards and gardens."""
        blocks = self.blocks()
        ground = Counter()
        for patch in self.patches:
            if patch['id'] in blocks:
                ground[patch['neighborhood']] += area(blocks[patch['id']])
        self.lots = []
        for patch in self.patches:
            if patch['id'] not in blocks:
                continue
            hood, dense = patch['neighborhood'], math.hypot(*patch['middle']) / TOWN
            size = min((55 if self.look == 'street' else 30) * (1 + dense * 2.2),
                       ground[hood] / max(1, self.wanted[hood] * 4))
            for key, piece in split(blocks[patch['id']], self.seed, f'{self.id}:{patch["id"]}:', max(size, MIN_LOT * 2.5)):
                piece = inset(piece, [0.35] * len(piece))
                if not piece or area(piece) < MIN_LOT or any(map(self.near_water, [*piece, centroid(piece)])):
                    continue
                if self.look == 'ink' and dense > 0.6 and unit(self.seed, key, 'yard') < dense * 0.35:
                    continue
                fronts = any(to_segment(point, *edge) < ROAD + 0.8 for point in piece for edge in self.road_edges
                             if math.dist(point, edge[0]) < 60)
                self.lots.append({'id': key.split(':', 1)[1], 'neighborhood': hood, 'polygon': piece,
                                  'front': fronts, 'area': area(piece), 'place': None})

    def give_lots(self):
        """Each of the town's own places and employers gets a lot in its own neighborhood: a grand one (a temple, a
        hall) the biggest left there, the rest one on a main road if one is free."""
        by_hood: dict[str, list[dict]] = {}
        for lot in self.lots:
            by_hood.setdefault(lot['neighborhood'], []).append(lot)
        for thing, what in self.things:
            if (what == 'place' and thing['kind'] in OPEN) or thing.get('neighborhood') in self.away:
                continue
            free = [lot for lot in by_hood.get(thing.get('neighborhood'), []) if not lot['place']] or \
                [lot for lot in self.lots if not lot['place']]
            if not free:
                break
            kind = thing.get('kind', what)
            if kind in GRAND or what == 'college':
                best = max(free, key=lambda lot: lot['area'])
            else:
                best = min(free, key=lambda lot: (not lot['front'], unit(self.seed, thing['id'], lot['id'])))
            best['place'] = {'id': thing['id'], 'name': thing['name'], 'kind': kind, 'what': what,
                             'summary': thing.get('summary', '')}

    def result(self) -> dict:
        def shape(polygon):
            return [rounded(point) for point in polygon]

        def ground(patch):
            thing = self.open_ground.get(patch['id'])
            return thing and {'id': thing['id'], 'name': thing['name'], 'kind': thing['kind'],
                              'summary': thing.get('summary', '')}

        districts = []
        for hood in self.near:
            own = [patch for patch in self.patches if patch['neighborhood'] == hood]
            if own:
                districts.append({'id': hood, 'name': self.names[hood],
                                  'label': rounded(centroid([patch['middle'] for patch in own])),
                                  'patches': [patch['id'] for patch in own]})
        return {
            'town': self.id, 'style': self.look, 'size': EDGE,
            'walls': bool((self.data.get('town_map') or {}).get('walls', self.look == 'floor')),
            'patches': [{'id': patch['id'], 'kind': patch['kind'], 'neighborhood': patch['neighborhood'],
                         'polygon': shape(patch['polygon']), 'place': ground(patch)} for patch in self.patches],
            'streets': [list(edge) for edge, owners in self.edges.items() if owners & self.in_town and len(owners) == 2],
            'roads': [[list(point) for point in path] for path in self.roads],
            'water': [{'name': water.get('name', ''), 'width': round(width(water), 1), 'points': shape(line)}
                      for line, water in self.rivers],
            'lots': [{key: lot[key] for key in ('id', 'neighborhood', 'front', 'place')} | {'polygon': shape(lot['polygon'])}
                     for lot in self.lots],
            'districts': districts, 'square': self.square['id'],
            'exits': [{'id': hood, 'name': self.names[hood], 'at': self.toward.get(hood)} for hood in sorted(self.away)],
            # Where the town meets the country: a walled town's wall.
            'border': [list(edge) for edge, owners in self.edges.items()
                       if len(owners) == 2 and len(owners & self.in_town) == 1],
        }


def width(water: dict) -> float:
    """A river's width on the map: wide enough to see, never so wide it swallows the town."""
    return max(4.0, min(14.0, water.get('width_km', 0.05) * 1000 / 12))


def route(graph: dict, starts: list[tuple], goal: tuple) -> list[tuple] | None:
    """The shortest way along the patch edges from any of `starts` to `goal`."""
    best = {start: 0.0 for start in starts if start in graph}
    came: dict[tuple, tuple] = {}
    queue = [(0.0, start) for start in best]
    heapq.heapify(queue)
    while queue:
        cost, here = heapq.heappop(queue)
        if here == goal:
            path = [here]
            while path[-1] in came:
                path.append(came[path[-1]])
            return path[::-1]
        if cost > best.get(here, math.inf):
            continue
        for there in graph[here]:
            step = cost + math.dist(here, there)
            if step < best.get(there, math.inf):
                best[there], came[there] = step, here
                heapq.heappush(queue, (step, there))
    return None


# In play ------------------------------------------------------------------------------------------

def view(connection) -> dict | None:
    """The map of the town the story is in, the lots looked at so far, and where in it the character is; None in a
    place with no map (the road between towns, the wilds). A place the character does not know of is a blank lot,
    or open ground marked `hidden`, until they find it."""
    where = story.scene_row(connection)
    data = story.city_data(connection, where['city_id'])
    if not has_map(data):
        return None
    board = layout(data, hexes.seed(connection))
    found, knows = looked(connection, data['id']), known(connection, data)
    here = where['place_id']
    place = next((item for item in data['places'] if item['id'] == here), None)
    lots = [lot | {'found': found.get(lot['id'])} | ({} if not lot['place'] or lot['place']['id'] in knows
                                                     else {'place': None}) for lot in board['lots']]
    patches = [patch | ({} if not patch['place'] or patch['place']['id'] in knows else {'place': None, 'hidden': True})
               for patch in board['patches']]
    return board | {'lots': lots, 'patches': patches, 'name': data['name'],
                    'here': {'place': here, 'neighborhood': place and place.get('neighborhood')}}


def looked(connection, town: str) -> dict[str, dict]:
    return {row['lot']: json.loads(row['found'])
            for row in many(connection, 'SELECT lot, found FROM story_lots WHERE town=?', (town,))}


def look(connection, lot_id: str) -> dict:
    """The character looks at a blank lot in the town they are in: what stands there is decided now and kept. One of
    the town's own places they did not know of is found ('open-<patch>' for open ground)."""
    where = story.scene_row(connection)
    data = story.city_data(connection, where['city_id'])
    require(has_map(data), 'There is no street map here.')
    seed = hexes.seed(connection)
    board = layout(data, seed)
    if lot_id.startswith('open-'):
        patch = next((found for found in board['patches'] if f'open-{found["id"]}' == lot_id), None)
        require(patch is not None and patch['place'] is not None, f'Nothing to find at {lot_id!r} in {data["name"]}.', 404)
        lot = patch
    else:
        lot = next((found for found in board['lots'] if found['id'] == lot_id), None)
        require(lot is not None, f'No lot {lot_id!r} in {data["name"]}.', 404)
    if lot['place'] is not None:
        require(lot['place']['id'] not in known(connection, data), f'{lot["place"]["name"]} is already on the map.')
        learn(connection, data['id'], lot['place']['id'], 'looked')
        return lot['place']
    if found := looked(connection, data['id']).get(lot_id):
        return found
    found = contents(data, seed, lot, hexes.levels(connection))
    connection.execute('INSERT INTO story_lots (town, lot, found) VALUES (?, ?, ?)',
                       (data['id'], lot_id, json.dumps(found)))
    return found


# Opening hours and the like for a lot's place, by its kind; a home is someone's, so it is open whenever they are in.
LOT_PLACES = {
    'home': {'cost': 'free', 'setting': 'indoor', 'good_for': ['solo'], 'day_parts': ['morning', 'afternoon', 'evening', 'late']},
    'shop': {'cost': '$', 'setting': 'indoor', 'good_for': ['solo', 'friends'], 'day_parts': ['morning', 'afternoon']},
    'workshop': {'cost': '$', 'setting': 'indoor', 'good_for': ['solo'], 'day_parts': ['morning', 'afternoon']},
    'nightlife': {'cost': '$$', 'setting': 'indoor', 'good_for': ['solo', 'friends'], 'day_parts': ['evening', 'late']},
    'bar': {'cost': '$', 'setting': 'indoor', 'good_for': ['solo', 'friends'], 'day_parts': ['afternoon', 'evening', 'late']},
    'tavern': {'cost': '$', 'setting': 'indoor', 'good_for': ['solo', 'friends'], 'day_parts': ['afternoon', 'evening', 'late']},
}
OTHER_PLACE = {'cost': '$', 'setting': 'indoor', 'good_for': ['solo', 'friends'], 'day_parts': ['morning', 'afternoon', 'evening']}


def lot_places(connection, data: dict) -> dict:
    """The lots looked at in this town, as places of it (story.city_for): the referee can take the character there
    and the narrator knows what they are."""
    if not has_map(data):
        return {}
    source = next(iter(data.get('sources') or {}), 'curated')
    found = [{'id': lot['id'], 'name': lot['name'], 'kind': lot['kind'], 'neighborhood': lot['neighborhood'],
              'summary': lot['summary'], 'tags': ['lot', lot['entry']], 'seasons': [], 'cuisine': '', 'spots': [],
              'source': source} | LOT_PLACES.get(lot['kind'], OTHER_PLACE)
             for lot in looked(connection, data['id']).values()]
    return {'places': [*data['places'], *found]} if found else {}


# The street outside ---------------------------------------------------------------------------------

STREET_LOTS = 5     # how many buildings nearby the narrator is told of
STREET_REACH = 30   # and how far off they may be, in map units


def neighbours(board: dict, place_id: str, neighborhood: str | None) -> list[dict]:
    """The lots nearest where the character is: their own place's lot or open ground, else the middle of their
    neighborhood. Their own lot is left out."""
    at = next((lot for lot in board['lots'] if (lot['place'] or {}).get('id') == place_id), None)
    if at is None and place_id.startswith('lot-'):
        at = next((lot for lot in board['lots'] if f'lot-{lot["id"]}' == place_id), None)
    if at is not None:
        middle_ = centroid(at['polygon'])
    elif ground := next((patch for patch in board['patches'] if (patch['place'] or {}).get('id') == place_id), None):
        middle_ = centroid(ground['polygon'])
    elif district := next((found for found in board['districts'] if found['id'] == neighborhood), None):
        middle_ = tuple(district['label'])
    else:
        return []
    near = sorted((math.dist(middle_, centroid(lot['polygon'])), lot['id'], lot) for lot in board['lots']
                  if lot is not at)
    return [lot for distance, _, lot in near[:STREET_LOTS] if distance < STREET_REACH]


def street(connection, data: dict, place_id: str) -> list[dict]:
    """What the character can see of the street outside: the buildings nearest them, each the town's own place,
    one looked at, or what the seed puts there (the same as looking at it would find, and kept once they pass by)."""
    if not has_map(data):
        return []
    seed = hexes.seed(connection)
    board = layout(data, seed)
    place = next((item for item in data['places'] if item['id'] == place_id), None)
    # Out and about in a neighborhood, not in any one place: '~' and its id.
    hood = place['neighborhood'] if place else place_id.removeprefix('~') if place_id.startswith('~') else None
    known, levels = looked(connection, data['id']), None
    found = []
    for lot in neighbours(board, place_id, hood):
        if lot['place']:
            found.append(lot['place'])
            continue
        if lot['id'] not in known:
            levels = levels if levels is not None else hexes.levels(connection)
            known[lot['id']] = contents(data, seed, lot, levels)
        found.append(known[lot['id']])
    return found


def pass_by(connection, data: dict, place_id: str):
    """The character arrives somewhere in town: it is known now, and the buildings on the street outside are kept
    as seen, so the map shows them and the player can walk into one by name."""
    learn(connection, data['id'], place_id, 'visited')
    if not has_map(data):
        return
    for found in street(connection, data, place_id):
        if found['id'].startswith('lot-'):
            connection.execute('INSERT OR IGNORE INTO story_lots (town, lot, found) VALUES (?, ?, ?)',
                               (data['id'], found['id'].removeprefix('lot-'), json.dumps(found)))
        else:
            learn(connection, data['id'], found['id'], 'passed')


def street_text(found: list[dict]) -> str:
    """The street outside as one line for the narrator."""
    if not found:
        return ''
    return ('Along the street outside, for detail only (the player may go into any of them): '
            + '; '.join(f"{item['name']} ({item['kind']})" for item in found) + '.')


# What the character knows of the town ---------------------------------------------------------------

# What anyone in town could find without being told: the square, the temple, the market, the way in and out.
LANDMARK_KINDS = {'square', 'park', 'market', 'temple', 'stadium', 'library', 'docks'}
LANDMARK_TAGS = {'central', 'arrival', 'waystone', 'gate', 'transit', 'meeting-point'}
# What even someone from the town may not know of.
HIDDEN_TAGS = {'hidden', 'secret'}
# A name shorter than this ("Inn") is too common a word to count as the place being named.
SHORTEST_NAME = 4


def own_places(data: dict) -> list[dict]:
    """The town's own places, employers and colleges: the ones it ships with, not lots looked at or hamlets found."""
    return [*(place for place in data.get('places', []) if not {'hamlet', 'lot'} & set(place.get('tags', []))),
            *data.get('employers', []), *data.get('colleges', [])]


def landmark(thing: dict) -> bool:
    return thing.get('kind') in LANDMARK_KINDS or bool(LANDMARK_TAGS & set(thing.get('tags', []))) \
        or thing.get('size') == 'large'


def home_town(connection, data: dict) -> bool:
    """Whether the character lives here (the persona's home, dungeon/world/where.py)."""
    from dungeon.world import where
    found = where.your_home(connection)
    return bool(found) and found[0]['id'] == data['id']


def known(connection, data: dict) -> dict[str, str]:
    """The town's own places the character knows of, each with how: 'visited', 'passed', 'looked', 'told', or
    'home' and 'landmark' for what they knew without finding it. Where they are now is visited."""
    found = {row['place']: row['how'] for row in
             many(connection, 'SELECT place, how FROM story_places WHERE town=?', (data['id'],))}
    home = home_town(connection, data)
    for thing in own_places(data):
        if thing['id'] in found or HIDDEN_TAGS & set(thing.get('tags', [])):
            continue
        if home or landmark(thing):
            found[thing['id']] = 'home' if home else 'landmark'
    where = story.scene_row(connection)
    if where['city_id'] == data['id']:
        found[where['place_id']] = 'visited'
    return found


def learn(connection, town: str, place_id: str, how: str):
    """The character knows of a place now; having been there outranks any other way of knowing it."""
    if not place_id or place_id.startswith(('~', 'lot-')):
        return
    connection.execute('INSERT INTO story_places (town, place, how) VALUES (?, ?, ?) ON CONFLICT(town, place) '
                       "DO UPDATE SET how=excluded.how WHERE excluded.how='visited'", (town, place_id, how))


def named_in(name: str, text: str) -> bool:
    """Whether a place's name is in the text: "the Felled Oak" as "Felled Oak", with its capitals as written (so "the
    Green" is not any green thing); a name with none ("the charcoal kilns") in any case."""
    core = re.sub(r'^(?:the|a|an)\s+', '', name.strip(), flags=re.I)
    flags = 0 if core[:1].isupper() else re.I
    return len(core) >= SHORTEST_NAME and re.search(rf'(?<!\w){re.escape(core)}(?!\w)', text, flags) is not None


def heard(connection, data: dict, text: str) -> list[str]:
    """Places of the town named in the story (the narration, an NPC giving directions) are known now; their ids."""
    if not text:
        return []
    knows = known(connection, data)
    told = [thing['id'] for thing in own_places(data) if thing['id'] not in knows and named_in(thing['name'], text)]
    for place_id in told:
        learn(connection, data['id'], place_id, 'told')
    return told


# What stands on a blank lot -----------------------------------------------------------------------

@functools.cache
def tables() -> dict:
    return json.loads((packages.DATA / 'town_lots.json').read_text(encoding='utf-8'))


def contents(data: dict, seed: str, lot: dict, levels: dict[str, int] | None) -> dict:
    """What stands on a lot, decided by the seed alone from the look's table: on a main road a shop is likelier
    than a house. An entry the intensity levels do not allow is passed over."""
    entries = [entry for entry in tables()['street' if style(data) == 'street' else 'ink']
               if hexes.allowed(entry, levels)]
    weights = [entry.get('front', entry['weight']) if lot['front'] else entry['weight'] for entry in entries]
    key = (data['id'], lot['id'])
    roll, running = unit(seed, 'lot', *key) * sum(weights), 0.0
    entry = entries[-1]
    for candidate, weight in zip(entries, weights):
        running += weight
        if roll < running:
            entry = candidate
            break
    given, families = names(data)
    template = entry['names'][int(unit(seed, 'lot-name', *key) * len(entry['names']))]
    name = template.format(family=families[int(unit(seed, 'lot-family', *key) * len(families))],
                           given=given[int(unit(seed, 'lot-given', *key) * len(given))])
    return {'id': f'lot-{lot["id"]}', 'name': name, 'kind': entry['kind'], 'entry': entry['id'],
            'summary': entry['summary'], 'neighborhood': lot['neighborhood']}


def names(data: dict) -> tuple[list[str], list[str]]:
    """Given and family names for a town's signs: its own name groups, else its era's commonest bank."""
    groups = list(((data.get('names') or {}).get('groups') or {}).values())
    given = [name for group in groups for gender in ('feminine', 'masculine') for name in group.get(gender, [])]
    families = [name for group in groups for name in group.get('family', [])]
    if given and families:
        return given, families
    shipped = json.loads((packages.DATA / 'names.json').read_text(encoding='utf-8'))
    era = shipped['eras'].get(data.get('era', 'modern')) or shipped['eras']['modern']
    bank = shipped['banks'][era['bank']]
    culture = bank[max(era['mix'], key=era['mix'].get) if era['mix'] else next(iter(bank))]
    return culture['feminine'] + culture['masculine'], culture['family']
