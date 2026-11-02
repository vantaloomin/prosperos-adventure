"""Scaling and tiers (requirements "Scaling and tiers"; docs/story.md "Scaling and tiers").

One tier ladder for every world and ruleset (LADDER), so code can compare the character, the work offered, the
regions and the foes. Each world names the track that sets the character's tier (world/data/tiers/<world>.json):
Vallarith's is renown, earned by work done.

- **The arc.** At campaign start the player picks how far the character can rise (ARCS: grounded stays low, classic
  runs from the street to the gods, epic starts high) and how fast (PACES); the world sets the defaults. The tier is
  the track's level, never below the arc's start or above its ceiling.
- **Work comes at the character's tier.** A job offered unasked is at their tier; now and then (STRETCH in 100) one
  a tier above, with a warning that it is beyond them. Nothing two tiers above ever comes to them; work below their
  tier comes only when they go looking for it (dungeon/jobs.py).
- **The world stays where it is.** Regions keep their tier (the travel map's `regions`). Walking into one above the
  character, the signs warn first, and the narrator is told. Foes a card brings are at the region's tier; a faction
  the character has made an enemy of, of a higher tier than the region, sends its own after them on the road.

The track is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import random
from datetime import datetime
from pathlib import Path

from dungeon import factions, travel, world_data
from dungeon.database import optional

TIERS = Path(__file__).parent / 'world' / 'data' / 'tiers'
LADDER = ('Local', 'Regional', 'Realm', 'World', 'Mythic')
ARCS = {'grounded': (1, 2), 'classic': (1, 5), 'epic': (3, 5)}
PACES = {'slow': 2.0, 'steady': 1.0, 'fast': 0.5}
# The track needed for each tier at a steady pace, and what work done earns, times its tier.
NEEDED = (0, 12, 36, 80, 160)
EARNED = 4
STRETCH = 10
# A foe a tier up: so much more Vitality and Resolve, and a better weapon every two tiers.
FOE_STEP = 2


@world_data.memo
def track(world: str) -> dict:
    found = world_data.read('tiers', world) or {}
    return {'track': 'renown', 'name': 'Renown', 'arc': 'classic', 'pace': 'steady',
            'words': [f'{name} renown' for name in LADDER]} | found


def start(world: str | None) -> datetime | None:
    """When a campaign in the world begins on the story clock (the tier file's `start`), or None for today."""
    found = track(world).get('start') if world else None
    return datetime.fromisoformat(found) if found else None


def clock(world: str | None) -> str:
    """How the world keeps time (the tier file's `clock`): 'story', or 'real_time' for a world that keeps moving
    while the app is closed."""
    return (track(world).get('clock') if world else None) or 'story'


def name(tier: int) -> str:
    return LADDER[tier - 1]


def world_of(city_id: str) -> str | None:
    """The world a city is on the travel map of."""
    return next((travel_map['world'] for travel_map in travel.maps() if travel_map.get('world')
                 and any(node['city'] == city_id for node in travel_map['nodes'])), None)


# The character's tier ---------------------------------------------------------------------------

def state(connection, world: str) -> dict:
    row = optional(connection, 'SELECT arc, pace, points FROM story_tier WHERE id=1')
    return row or {'arc': track(world)['arc'], 'pace': track(world)['pace'], 'points': 0}


def begin(connection, world: str, arc: str | None = None, pace: str | None = None):
    connection.execute('INSERT INTO story_tier (id, arc, pace, points) VALUES (1, ?, ?, 0) ON CONFLICT(id) DO UPDATE '
                       'SET arc=excluded.arc, pace=excluded.pace, points=0',
                       (arc or track(world)['arc'], pace or track(world)['pace']))


def level(points: int, pace: str) -> int:
    return max(n + 1 for n, needed in enumerate(NEEDED) if points >= needed * PACES[pace])


def tier(connection, world: str) -> int:
    row = state(connection, world)
    start, ceiling = ARCS[row['arc']]
    return max(start, min(ceiling, level(row['points'], row['pace'])))


def earn(connection, world: str, amount: int) -> str:
    """The track climbs; a line for the narrator when it lifts the character a tier."""
    before, row = tier(connection, world), state(connection, world)
    connection.execute('INSERT INTO story_tier (id, arc, pace, points) VALUES (1, ?, ?, ?) ON CONFLICT(id) DO UPDATE '
                       'SET points=excluded.points', (row['arc'], row['pace'], row['points'] + amount))
    after = tier(connection, world)
    if after <= before:
        return ''
    return (f"The character's {track(world)['name'].lower()} rises: {name(after)}, "
            f"{track(world)['words'][after - 1]}. Bigger work will come to them now.")


def for_work(quest_tier: int, character: int) -> int:
    """What work done earns: more for work above the character."""
    return EARNED * quest_tier * (2 if quest_tier > character else 1)


# Offers -----------------------------------------------------------------------------------------

def offer_tiers(character: int, seeking: bool, rng=None) -> tuple[set[int], bool]:
    """The tiers of work that may come to the character, and whether this is a stretch offer."""
    if seeking:
        return set(range(1, character + 1)), False
    rng = rng or random.SystemRandom()
    if character < len(LADDER) and rng.randint(1, 100) <= STRETCH:
        return {character + 1}, True
    return {character}, False


def stretch_text(work: int, character: int) -> str:
    return (f'Those who know say this one is beyond the character: {name(work)} work, and they are '
            f'{name(character)}. Have someone warn them before they take it.')


# The world's tiers ------------------------------------------------------------------------------

def hunted_by(connection, world: str, above: int) -> dict | None:
    """The most powerful faction that has made an enemy of the character, if it stands above `above`."""
    enemies = [item for item in factions.factions(world) if item.get('tier', 1) > above
               and factions.standing(connection, item['id']) <= factions.ENEMY]
    return max(enemies, key=lambda item: item['tier'], default=None)


def scaled(spec: dict, steps: int) -> dict:
    if steps <= 0:
        return spec
    return spec | {'vitality': spec.get('vitality', 10) + FOE_STEP * steps,
                   'resolve': spec.get('resolve', 10) + FOE_STEP * steps,
                   'weapon': spec.get('weapon', 0) + (steps + 1) // 2}


def foe(connection, found: dict, spec: dict, base: int) -> tuple[dict, str]:
    """A foe from a table at `base` tier, met where `found` is (happenings.where): at the region's tier, or sent by an
    enemy faction above it. Returns the foe and a line naming who sent them, if anyone did."""
    region = found['tier']
    hunter = hunted_by(connection, found['world'], region)
    target = hunter['tier'] if hunter else region
    line = f"They were sent by {hunter['name']}, who have not forgotten the character." if hunter else ''
    return scaled(spec, target - base), line


def warning(connection, found: dict) -> str:
    """Signs that the region is above the character, for a line that arrives there."""
    character = tier(connection, found['world'])
    if found['tier'] <= character:
        return ''
    return (f"Signs on the way warn the character: this is {name(found['tier'])} country, and they are "
            f"{name(character)}. People here are more than they can handle, and death is real.")


# For the narrator and the screen -----------------------------------------------------------------

def prompt_text(connection, found: dict) -> str:
    world = found['world']
    character = tier(connection, world)
    text = (f"## The character's standing (kept by the game)\n- {track(world)['name']}: {name(character)}, "
            f"{track(world)['words'][character - 1]}. Work that finds them unasked is at this tier.")
    if found['tier'] > character:
        text += f"\n- This place is {name(found['tier'])}: above them. Its people and dangers outmatch them."
    return text


def view(connection, world: str, shown: bool) -> dict:
    row, character = state(connection, world), tier(connection, world)
    ceiling = ARCS[row['arc']][1]
    result = {'tier': name(character), 'words': track(world)['words'][character - 1], 'track': track(world)['name'],
              'arc': row['arc'], 'pace': row['pace']}
    if shown:
        following = NEEDED[character] * PACES[row['pace']] if character < ceiling else None
        result |= {'points': row['points'], 'next': following and int(following)}
    return result
