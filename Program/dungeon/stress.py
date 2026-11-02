"""Stress: mental harm (requirements "Injuries and recovery": a stress track; docs/story.md "Stress").

Code keeps a stress track for the character, 0 to 12. Traumatic events add to it: the first kill, something
dreadful to fight (a foe marked horror), being beaten nearly to death, robbed and left, or taken prisoner, a lasting
injury. Each time, the character resists with a Resolve roll: a critical success shrugs it off, a success takes
half, a failure all of it, a critical failure one more.

Past each threshold (4, 8, 12), and every time more lands at the top, code rolls a lasting condition of the mind
from the table (rules/injuries.json `conditions`): nightmares, a fear of the dark, numbness, a temper. They work
like lasting injuries (dungeon/injuries.py), under the same Injury persistence setting, and the narrator plays them.
Each good night of rest eases the track by one (dungeon/rest.py).

The track is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import random

from dungeon import injuries, sheet, sworn
from dungeon.database import optional

TOP = 12
THRESHOLDS = (4, 8, 12)
# What each event costs the character, before Resolve.
COST = {'kill_first': 2, 'horror': 2, 'captured': 3, 'robbed': 2, 'rescued': 2, 'thrown_out': 1, 'maimed': 1}
CAUSE = {'kill_first': 'the first life they have taken', 'horror': 'facing {who}', 'captured': 'being beaten and taken by {who}',
         'robbed': 'being beaten, robbed and left for dead by {who}', 'rescued': 'being beaten nearly to death by '
         '{who}', 'thrown_out': 'being beaten senseless by {who}', 'maimed': 'being maimed by {who}'}
# The share of the stress taken, by how the Resolve roll landed: (multiplier, extra).
RESISTED = {'critical_success': (0, 0), 'success': (0.5, 0), 'success_cost': (0.5, 0), 'failure_upside': (1, 0),
            'failure': (1, 0), 'critical_failure': (1, 1)}
WORDS = ((0, 'steady'), (3, 'shaken'), (7, 'strained'), (11, 'frayed'), (TOP, 'breaking'))


def points(connection) -> int:
    row = optional(connection, 'SELECT points FROM story_stress WHERE id=1')
    return row['points'] if row else 0


def kills(connection) -> int:
    row = optional(connection, 'SELECT kills FROM story_stress WHERE id=1')
    return row['kills'] if row else 0


def save(connection, value: int, killed: int | None = None):
    connection.execute('INSERT INTO story_stress (id, points, kills) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET '
                       'points=excluded.points, kills=excluded.kills',
                       (max(0, min(TOP, value)), kills(connection) if killed is None else killed))
    # Under Ironsworn, spirit follows the track.
    sworn.follow_stress(connection, max(0, min(TOP, value)), TOP)


def word(value: int) -> str:
    return next(name for ceiling, name in WORDS if value <= ceiling)


def add(connection, event: str, who: str, now, rng=None, logged: str = '', amount: int | None = None,
        cause: str = '') -> list[str]:
    """The stress an event costs (or `amount`, for `cause`), after the character's Resolve; and the conditions it
    leaves past a threshold."""
    rng = rng or random.SystemRandom()
    band = sheet.check(connection, 'Resolve', 'normal', rng=rng, save=True)['band']
    share, extra = RESISTED[band]
    taken = int((COST[event] if amount is None else amount) * share) + extra
    cause = cause or CAUSE[event].format(who=who)
    before = points(connection)
    after = min(TOP, before + taken)
    save(connection, after)
    if not taken:
        return [f"The character shrugs off {cause} (Resolve: {band.replace('_', ' ')})."]
    lines = [f"{cause[0].upper()}{cause[1:]} weighs on the character (Resolve: {band.replace('_', ' ')}): now "
             f"{word(after)}, {after} of {TOP}."]
    crossed = sum(1 for mark in THRESHOLDS if before < mark <= after) or int(before >= TOP)
    for _ in range(crossed):
        if left := injuries.roll(connection, now, cause, rng, logged, kind='condition'):
            lines.append(left)
    return lines


def aftermath(connection, now, events: list[tuple[str, str]], rng=None, logged: str = '') -> list[str]:
    """What a fight round's events leave on the character (dungeon/combat.py turn): lasting injuries and stress."""
    lines = []
    for event, who in events:
        if event == 'maimed':
            if left := injuries.roll(connection, now, who, rng, logged):
                lines.append(left)
            lines += add(connection, 'maimed', who, now, rng, logged)
        elif event == 'kill':
            first = kills(connection) == 0
            save(connection, points(connection), kills(connection) + 1)
            if first:
                lines += add(connection, 'kill_first', who, now, rng, logged)
        elif event in COST:
            lines += add(connection, event, who, now, rng, logged)
    return lines


def ease(connection, nights: int) -> list[str]:
    """Each good night of rest eases the track by one."""
    before = points(connection)
    if nights <= 0 or not before:
        return []
    after = max(0, before - nights)
    save(connection, after)
    return [f"Rest eases the strain: the character is {word(after)}, {after} of {TOP}."]


def prompt_text(connection) -> str:
    value = points(connection)
    if not value:
        return ''
    return f"The player's character is {word(value)} (stress {value} of {TOP}, kept by the game; write it as it is)."


def view(connection, shown: bool) -> str:
    """The track for the screen: the word, with the number when the dice are shown; '' while steady."""
    value = points(connection)
    if not value:
        return ''
    return f'{word(value)}, {value} of {TOP}' if shown else word(value)
