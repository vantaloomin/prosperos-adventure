"""Factions, their clocks and the character's standing (requirements "Quests and factions"; docs/story.md
"Factions").

Each world's factions in play (world/data/factions/<world>.json) are the powers with a hand on its travel map: a
realm, a guild, the elves past the border stones. Each has goals, holds some places, has rivals and allies, and runs
progress clocks.

- **Clocks move on the world clock.** Each story day, each open clock may move a segment (the file's `pace`, in
  100). When one fills, what it meant happens: the record keeps it as the world's truth, and the news reaches the
  character on their next day in a town, whether or not they had a hand in it.
- **Standing is a Reputation track**, -5 to 5, shown in words ("trusted", "distrusted") or, with the dice shown,
  the number. Life Cards move it now; jobs for factions will too.
- **The narrator is told the powers that hold the place**: who they are, what they want, how far their clocks have
  run and how they stand with the character. It acts through their people and never announces a clock.

Clocks and standing are game state, branched with the story (dungeon/timeline.py SAVED).
"""
import random
from datetime import datetime
from pathlib import Path

from dungeon import record, world_data
from dungeon.database import many, optional

FACTIONS = Path(__file__).parent / 'world' / 'data' / 'factions'
LOWEST, HIGHEST, ENEMY = -5, 5, -4
STANDING = ((ENEMY, 'an enemy'), (-2, 'distrusted'), (-1, 'frowned on'), (0, 'unknown'), (1, 'noticed'),
            (3, 'trusted'), (HIGHEST, 'honoured'))
# Off only for tests that are about something else (tests/conftest.py).
ACTIVE = True


@world_data.memo
def data(world: str) -> dict:
    return world_data.read('factions', world) or {'pace': 0, 'factions': []}


def factions(world: str) -> list[dict]:
    return data(world)['factions']


def find(world: str, faction_id: str) -> dict | None:
    return next((item for item in factions(world) if item['id'] == faction_id), None)


def anywhere(faction_id: str) -> dict | None:
    """A faction by its id, in whichever world has it."""
    return next((found for path in world_data.keys('factions') if (found := find(path, faction_id))), None)


def local(world: str, node_id: str) -> list[dict]:
    """The factions with a hand in a place on the travel map."""
    return [item for item in factions(world) if node_id in item['holds']]


# Standing ----------------------------------------------------------------------------------------

def standing(connection, faction_id: str) -> int:
    row = optional(connection, 'SELECT value FROM story_reputation WHERE faction_id=?', (faction_id,))
    return row['value'] if row else 0


def standing_word(value: int) -> str:
    return next(word for ceiling, word in STANDING if value <= ceiling)


def shift(connection, faction: dict, amount: int) -> str:
    value = max(LOWEST, min(HIGHEST, standing(connection, faction['id']) + amount))
    connection.execute('INSERT INTO story_reputation (faction_id, value) VALUES (?, ?) ON CONFLICT(faction_id) DO '
                       'UPDATE SET value=excluded.value', (faction['id'], value))
    return f"The character's standing with {faction['name']}: now {standing_word(value)}."


# Clocks ------------------------------------------------------------------------------------------

def clocks(connection) -> dict[tuple[str, str], dict]:
    return {(row['faction_id'], row['clock_id']): row for row in many(connection, 'SELECT * FROM story_clocks')}


def filled(connection, faction_id: str, clock_id: str) -> int:
    row = optional(connection, 'SELECT filled FROM story_clocks WHERE faction_id=? AND clock_id=?',
                   (faction_id, clock_id))
    return row['filled'] if row else 0


def tick(connection, world: str, faction: dict, clock: dict, steps: int, now: datetime, logged: str):
    """A clock moves; when it fills, what it meant happens."""
    before = filled(connection, faction['id'], clock['id'])
    if before >= clock['segments']:
        return
    after = max(0, min(clock['segments'], before + steps))
    done = after >= clock['segments']
    connection.execute('INSERT INTO story_clocks (faction_id, clock_id, filled, done_at, told) VALUES (?, ?, ?, ?, 0) '
                       'ON CONFLICT(faction_id, clock_id) DO UPDATE SET filled=excluded.filled, '
                       'done_at=excluded.done_at', (faction['id'], clock['id'], after,
                                                    now.isoformat() if done else None))
    if done:
        record.add(connection, 'fact', faction['name'], clock['done'], logged, truth='world')


def advance(connection, world: str, before: datetime, after: datetime, logged: str, rng=None):
    """Each story day passed, each open clock may move a segment."""
    if not ACTIVE:
        return
    rng = rng or random.SystemRandom()
    for _ in range(max(0, (after.date() - before.date()).days)):
        for faction in factions(world):
            for clock in faction['clocks']:
                if rng.randint(1, 100) <= data(world)['pace']:
                    tick(connection, world, faction, clock, 1, after, logged)


def first_open(connection, faction: dict) -> dict | None:
    return next((clock for clock in faction['clocks']
                 if filled(connection, faction['id'], clock['id']) < clock['segments']), None)


def news(connection, world: str, logged: str) -> list[str]:
    """What has happened among the powers since the character last heard, as it reaches a town."""
    lines = []
    for row in many(connection, 'SELECT * FROM story_clocks WHERE done_at IS NOT NULL AND told=0 ORDER BY done_at'):
        faction = find(world, row['faction_id'])
        clock = next((item for item in (faction or {}).get('clocks', []) if item['id'] == row['clock_id']), None)
        if clock is None:
            continue
        connection.execute('UPDATE story_clocks SET told=1 WHERE faction_id=? AND clock_id=?',
                           (row['faction_id'], row['clock_id']))
        record.add(connection, 'fact', faction['name'], clock['done'], logged)
        lines.append(f"News reaches town: {clock['done']}")
    return lines


# For the narrator and the screen -------------------------------------------------------------------

def prompt_text(connection, world: str, node_id: str) -> str:
    here = local(world, node_id)
    if not here:
        return ''
    lines = []
    for faction in here:
        runs = '; '.join(f"{clock['name']} {filled(connection, faction['id'], clock['id'])} of {clock['segments']}"
                         for clock in faction['clocks'])
        lines.append(f"- {faction['name']} ({faction['kind']}): {faction['summary']} Wants: "
                     f"{'; '.join(faction['goals'])}. Clocks: {runs}. The character is "
                     f"{standing_word(standing(connection, faction['id']))} to them.")
    return ('## The powers here (kept by the game; act through their people, never announce a clock)\n'
            + '\n'.join(lines))


def view(connection, world: str, visited: set[str], shown: bool) -> list[dict]:
    """The factions the character knows of: those holding a place they have been, or that know them."""
    known = []
    for faction in factions(world):
        value = standing(connection, faction['id'])
        if value or visited & set(faction['holds']):
            known.append({'id': faction['id'], 'name': faction['name'], 'summary': faction['summary'],
                          'standing': f'{standing_word(value)} ({value:+d})' if shown else standing_word(value)})
    return known
