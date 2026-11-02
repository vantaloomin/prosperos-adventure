"""Vallarith's authored hexes (requirements "### Hex crawl"; dungeon/hexes.py), painted from the world map
(dungeon/world/packages/vallarith/assets/maps/vallarith.jpg): each hex's terrain read from the map's colours, its
region from the nearest region or town on the map, the roads drawn between the travel map's places
(world/data/travel/vallarith.json), and each place's own hex. Hexes past the map are generated in play.

Run `python scripts/world/vallarith_hexes.py` to rewrite world/data/hexes/vallarith.json; it needs Pillow, which
the app itself does not.
"""
import colorsys
import json
import math
import statistics
from collections import Counter, deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'dungeon' / 'world' / 'packages' / 'vallarith'
MAP = PACKAGE / 'assets' / 'maps' / 'vallarith.jpg'
TRAVEL = ROOT / 'dungeon' / 'world' / 'data' / 'travel' / 'vallarith.json'
OUT = ROOT / 'dungeon' / 'world' / 'data' / 'hexes' / 'vallarith.json'

# Pixels between hex centres across the flats: six miles, so the Cyrel road from Kingswood to Eriane is about
# twelve hexes, as the travel map's twelve hours on the road say.
ACROSS = 8.0
SIDE = ACROSS / math.sqrt(3)
# Land enclosed by sea smaller than this is a map label or a stray mark, not an island; water smaller than this
# inside the land is a castle's white walls, not a lake.
SPECK = 12
POND = 6
# Terrain a region turns open ground into, and what a forest or hill reads as there.
DRY = {'badlands': 'w'}
WET = {'bashrat-island': 's'}
LEGEND = {'~': 'water', '.': 'plains', 'f': 'forest', 'h': 'hills', 'm': 'mountains', 'w': 'waste', 's': 'marsh'}


def centre(column: int, row: int) -> tuple[float, float]:
    return SIDE + 1.5 * SIDE * column, ACROSS / 2 + ACROSS * row + (ACROSS / 2 if column % 2 else 0)


def cell_at(x: float, y: float) -> tuple[int, int]:
    column = round((x - SIDE) / (1.5 * SIDE))
    return column, round((y - ACROSS / 2 - (ACROSS / 2 if column % 2 else 0)) / ACROSS)


def around(column: int, row: int) -> list[tuple[int, int]]:
    steps = ((0, -1), (0, 1), (-1, 0), (-1, 1), (1, 0), (1, 1)) if column % 2 else \
        ((0, -1), (0, 1), (-1, -1), (-1, 0), (1, -1), (1, 0))
    return [(column + dc, row + dr) for dc, dr in steps]


def pixels(image, x: float, y: float, reach: int) -> list[tuple[int, int, int]]:
    width, height = image.size
    return [image.getpixel((min(width - 1, max(0, int(x + i))), min(height - 1, max(0, int(y + j)))))
            for i in range(-reach, reach + 1) for j in range(-reach, reach + 1)]


def hsv(pixel) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(*(value / 255 for value in pixel))


def read_terrain(image, column: int, row: int) -> str:
    """Sea is the grey paper, land is tan; dark ink on land is trees (greenish) or mountain shading (brown)."""
    x, y = centre(column, row)
    wide = [hsv(pixel) for pixel in pixels(image, x, y, 6)]
    light = [h for h in wide if h[2] > 0.55]
    snowy = sum(1 for h in wide if h[1] < 0.06 and h[2] > 0.85) / len(wide)
    if not ((light and statistics.mean(h[1] for h in light) > 0.17) or
            (snowy > 0.35 and statistics.mean(h[1] for h in wide) > 0.04)):
        return '~'
    near = pixels(image, x, y, 4)
    inked = [pixel for pixel in near if hsv(pixel)[2] < 0.5]
    if sum(1 for pixel in near if hsv(pixel)[1] < 0.06 and hsv(pixel)[2] > 0.85) / len(near) > 0.3:
        return 'm'
    share = len(inked) / len(near)
    if share < 0.1:
        return '.'
    if sum(1 for pixel in inked if pixel[1] >= pixel[0] - 4) / len(inked) > 0.5:
        return 'f'
    return 'm' if share > 0.3 else 'h'


def components(grid: dict, inside) -> list[set]:
    seen, found = set(), []
    for start in grid:
        if start in seen or not inside(grid[start]):
            continue
        group, queue = set(), deque([start])
        seen.add(start)
        while queue:
            at = queue.popleft()
            group.add(at)
            for other in around(*at):
                if other in grid and other not in seen and inside(grid[other]):
                    seen.add(other)
                    queue.append(other)
        found.append(group)
    return found


def smooth(grid: dict) -> dict:
    """Two passes of a majority filter: a land hex most of whose neighbours agree takes their terrain."""
    for _ in range(2):
        changed = dict(grid)
        for at, terrain in grid.items():
            counts = Counter(grid.get(other, '~') for other in around(*at))
            top, count = counts.most_common(1)[0]
            if counts['~'] == 6:
                changed[at] = '~'
            elif terrain != '~' and top != '~' and count >= 4:
                changed[at] = top
        grid = changed
    return grid


def tidy(grid: dict, columns: int, rows: int) -> dict:
    for group in components(grid, lambda terrain: terrain != '~'):
        if len(group) < SPECK:
            grid.update({at: '~' for at in group})
    for group in components(grid, lambda terrain: terrain == '~'):
        edge = any(c in (0, columns - 1) or r in (0, rows - 1) for c, r in group)
        if not edge and len(group) < POND:
            for at in group:
                fill(grid, at)
    return grid


def axial(column: int, row: int) -> tuple[int, int]:
    return column, row - (column - (column & 1)) // 2


def offset(q: int, r: int) -> tuple[int, int]:
    return q, r + (q - (q & 1)) // 2


def line(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """The hexes on a straight line between two, as offset cells."""
    (q1, r1), (q2, r2) = axial(*start), axial(*end)
    steps = max(abs(q1 - q2), abs(r1 - r2), abs((-q1 - r1) - (-q2 - r2)))
    cells = []
    for step in range(steps + 1):
        t = step / steps if steps else 0
        q, r = q1 + (q2 - q1) * t + 1e-6, r1 + (r2 - r1) * t + 1e-6
        s = -q - r
        rq, rr, rs = round(q), round(r), round(s)
        if abs(rq - q) > abs(rr - r) and abs(rq - q) > abs(rs - s):
            rq = -rr - rs
        elif abs(rr - r) > abs(rs - s):
            rr = -rq - rs
        cell = offset(rq, rr)
        if not cells or cells[-1] != cell:
            cells.append(cell)
    return cells


def written(data: dict) -> str:
    """The file with one map row, place or road to a line, so a change to the map reads as a change to its rows."""
    def block(value) -> str:
        if isinstance(value, list):
            return '[\n' + ',\n'.join(f'  {json.dumps(item, ensure_ascii=False)}' for item in value) + '\n ]'
        if isinstance(value, dict) and value and isinstance(next(iter(value.values())), list):
            return '{\n' + ',\n'.join(f'  {json.dumps(name)}: {json.dumps(item)}' for name, item in value.items()) + '\n }'
        return json.dumps(value, ensure_ascii=False)
    return '{\n' + ',\n'.join(f' {json.dumps(name)}: {block(value)}' for name, value in data.items()) + '\n}\n'


def fill(grid: dict, at: tuple[int, int]):
    land = [grid[other] for other in around(*at) if grid.get(other, '~') != '~']
    grid[at] = Counter(land).most_common(1)[0][0] if land else '.'


def touch_up(grid: dict, places: dict):
    """A town's own picture on the map is grey like the sea, so the hexes about a place are land; and the blue glow
    along the coast reads as trees, so a forest hex on the shore needs forest inland beside it."""
    for place in places.values():
        for at in {place, *around(*place), *(far for near in around(*place) for far in around(*near))}:
            if grid.get(at) == '~':
                fill(grid, at)
    shore = {at for at, terrain in grid.items() if terrain != '~' and any(grid.get(o, '~') == '~' for o in around(*at))}
    for at in shore:
        if grid[at] == 'f' and sum(1 for o in around(*at) if grid.get(o) == 'f' and o not in shore) < 2:
            grid[at] = '.'


def nearest(seeds: list, at: tuple[int, int]) -> str:
    return min(seeds, key=lambda seed: math.dist(centre(*at), centre(*seed[0])))[1]


def owners(grid: dict, seeds: list) -> dict:
    """Each land hex's region: each landmass takes it from the seeds on it, so an island's stays on the island."""
    owner = {}
    for group in components(grid, lambda terrain: terrain != '~'):
        local = [seed for seed in seeds if seed[0] in group] or seeds
        owner.update({at: nearest(local, at) for at in group})
    return owner


def draw_roads(grid: dict, owner: dict, seeds: list, places: dict, routes: list[dict]) -> list[dict]:
    """Each route as a road of hexes in a straight line between its places; where it crosses water, a causeway."""
    roads = []
    for route in routes:
        cells = line(places[route['from']], places[route['to']])
        for at in cells:
            if grid[at] == '~':
                grid[at] = '.'
            owner.setdefault(at, nearest(seeds, at))
        roads.append({'name': route['terrain'], 'danger': route['danger'],
                      'cells': [list(axial(*at)) for at in cells]})
    return roads


def main():
    image = Image.open(MAP).convert('RGB')
    width, height = image.size
    columns, rows = int((width - SIDE) / (1.5 * SIDE)), int(height / ACROSS) - 1
    grid = tidy(smooth({(c, r): read_terrain(image, c, r) for c in range(columns) for r in range(rows)}),
                columns, rows)
    travel = json.loads(TRAVEL.read_text(encoding='utf-8'))
    regions = json.loads((PACKAGE / 'regions.json').read_text(encoding='utf-8'))['regions']
    places = {node['id']: cell_at(node['map']['x'] * width, node['map']['y'] * height) for node in travel['nodes']}
    seeds = [(cell_at(region['map']['x'] * width, region['map']['y'] * height), region['id']) for region in regions
             if region.get('map') and region['kind'] in ('land', 'island')]
    seeds += [(places[node['id']], node['region']) for node in travel['nodes']]
    letters = {region: chr(ord('a') + index) for index, region in enumerate(dict.fromkeys(r for _, r in seeds))}
    touch_up(grid, places)
    owner = owners(grid, seeds)
    roads = draw_roads(grid, owner, seeds, places, travel['routes'])
    for at, region in owner.items():
        if grid[at] == '.' and region in DRY:
            grid[at] = DRY[region]
        elif grid[at] in '.f' and region in WET:
            grid[at] = WET[region]
    data = {
        'about': __doc__.split('\n\n')[0].replace('\n', ' '),
        'miles': 6,
        'layout': 'Offset rows, flat-topped, odd columns shifted down half a hex; column c and row r are the axial '
                  'hex q = c, r = r - (c - (c & 1)) / 2.',
        'legend': LEGEND,
        'terrain': [''.join(grid[c, r] for c in range(columns)) for r in range(rows)],
        'region_legend': {letter: region for region, letter in letters.items()},
        'regions': [''.join(letters[owner[c, r]] if (c, r) in owner else ' ' for c in range(columns))
                    for r in range(rows)],
        'places': {node: list(axial(*at)) for node, at in places.items()},
        'roads': roads,
        # Past the map: mostly sea, as round the continent, with land now and then, in the wilds.
        'generate': {'water': 0.55, 'frontier': ['wilds']},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(written(data), encoding='utf-8')
    print(f'{OUT}: {columns} x {rows} hexes, {sum(1 for t in grid.values() if t != "~")} on land')


if __name__ == '__main__':
    main()
