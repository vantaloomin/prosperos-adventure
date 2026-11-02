"""The 5E battle map (requirements "Combat": "Positioning: zones, grid optional"; docs/story.md "The battle map").

Under 5E the fight card can show the fight on a grid of five-foot squares. The range bands stay what code decides
(dungeon/ranges.py); the map only draws them:
- The character stands in the middle square. Each foe stands in a direction of its own, in order (ahead first,
  then the flanks, then behind), at its band's distance: engaged 1 square (5 ft), near 4 (20 ft, one move away),
  far 9 (45 ft). More foes than directions stand a square further out.
- Companions fighting beside the character (dungeon/allies.py) stand behind them.
- Distances are counted as 5E's grid counts them: every square, diagonals too, is five feet.
Nothing here is saved: the same fight always draws the same map.
"""
from dungeon import sheet
from dungeon.rules import srd52

FEET = 5
DISTANCE = {'engaged': 1, 'near': 4, 'far': 9}
AHEAD = ((0, -1), (1, -1), (-1, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (0, 1))
BEHIND = ((0, 1), (-1, 1), (1, 1), (-1, 0), (1, 0))


def square(index: int, zone: str | None) -> tuple[int, int]:
    """Where the index-th foe stands, by its range band."""
    dx, dy = AHEAD[index % len(AHEAD)]
    out = DISTANCE.get(zone or 'engaged', 1) + index // len(AHEAD)
    return dx * out, dy * out


def feet(x: int, y: int) -> int:
    return max(abs(x), abs(y)) * FEET


def drawn(state: dict, standing: list[dict], allied: list[dict]) -> dict:
    """The map of a fight: the character, each foe (down or not), each companion; squares relative to the character."""
    up = {id(foe) for foe in standing}
    foes = []
    for index, foe in enumerate(state['foes']):
        x, y = square(index, foe.get('zone'))
        foes.append({'name': foe['name'], 'x': x, 'y': y, 'feet': feet(x, y), 'down': id(foe) not in up})
    allies = []
    for index, ally in enumerate(allied):
        (dx, dy), out = BEHIND[index % len(BEHIND)], 1 + index // len(BEHIND)
        allies.append({'name': ally['name'], 'x': dx * out, 'y': dy * out, 'down': ally['state'] == 'down'})
    return {'square_feet': FEET, 'area': state.get('area'), 'foes': foes, 'allies': allies}


def view(connection, state: dict | None, standing, allied: list[dict]) -> dict | None:
    """The map, for a fight under 5E; None otherwise."""
    if state is None or sheet.ruleset(connection) != srd52.ID:
        return None
    return drawn(state, standing(state), allied)


def positions(connection, state: dict, standing: list[dict]) -> str:
    """Under 5E, how far off each foe stands, in feet, for the narrator; '' otherwise."""
    if sheet.ruleset(connection) != srd52.ID:
        return ''
    up = {id(foe) for foe in standing}
    far = [f"{foe['name']} {feet(*square(index, foe.get('zone')))} ft"
           for index, foe in enumerate(state['foes']) if id(foe) in up]
    return f"On the grid: {'; '.join(far)}." if far else ''
