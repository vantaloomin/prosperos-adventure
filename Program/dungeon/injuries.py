"""Lasting injuries and treatment (requirements "Injuries and recovery"; docs/story.md "Lasting injuries" and
"Treatment").

Everything here follows one setting, **Injury persistence**: Permanent (the default), Temporary or None.

- **Lasting injuries are rolled.** A hit that leaves the character Maimed, a foe's critical hit, or a beating that
  nearly killed them rolls on the lasting-injury table (rules/injuries.json): a lost eye, a limp, a ruined hand, a
  scar. Each makes the actions it touches a step harder and has a look people react to; the narrator is told both.
  Under Permanent it stays (rare magic or a master healer may mend it later); under Temporary it fades after its
  days; under None nothing is rolled and nothing old shows.
- **Treatment takes a healer or supplies, and a roll, and can go wrong.** "I bandage the wound" with bandages or a
  poultice in the pack is a Mind roll of the character's, harder the worse the wound (a poultice makes it a step
  easier). A healer in the scene treats instead, for a fee, rolling their own skill. A success mends a level now (a
  critical two); a critical failure turns the wound bad, a level worse. A wound is treated once; a new one can be
  treated again.

All of it is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import functools
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from dungeon import combat, combat5e, inventory, record, sheet
from dungeon import table as campaign_table
from dungeon.database import many, optional
from dungeon.rules import brp, marvel

TABLE = Path(__file__).parent / 'rules' / 'injuries.json'
PERSISTENCE = ('permanent', 'temporary', 'none')
TREAT = re.compile(r'\b(treat|tend|bandag|bind up|binds up|binds? (?:my|the|his|her|their) wound|dress|stitch|sew up|sews up|splint|patch(es)? (me |myself '
                   r'|it |the wound |up)|clean (the|my) (wound|cut)|poultice|see to (the|my) wound|set (the|my) bone)\w*',
                   re.I)
HEALER = re.compile(r'\b(healer|physician|surgeon|bonesetter|apothecary|herb ?woman|herbalist|midwife|leech)\b', re.I)
SUPPLIES = ('poultice', 'bandages')
HEALER_FEE = 200
HEALER_SKILL = 15
STAT = 'Mind'
# The difficulty of treating each wound level: Grazed, Hurt, Wounded, Maimed.
DIFFICULTY = {1: 'easy', 2: 'normal', 3: 'hard', 4: 'very_hard'}
EASIER = {'normal': 'easy', 'hard': 'normal', 'very_hard': 'hard', 'extreme': 'very_hard', 'easy': 'easy'}
MENDED = {'critical_success': 2, 'success': 1, 'success_cost': 1, 'failure_upside': 0, 'failure': 0,
          'critical_failure': -1}


# What each kind of lasting harm is called: the body's injuries and the mind's conditions (dungeon/stress.py).
KINDS = {'injury': ('injuries', 'It leaves a lasting injury', 'lasting injuries'),
         'condition': ('conditions', 'It leaves a lasting mark on the mind', 'lasting conditions of the mind')}


@functools.cache
def table() -> tuple[dict, ...]:
    """Every lasting injury and condition, each with its kind."""
    data = json.loads(TABLE.read_text(encoding='utf-8'))
    return tuple(entry | {'kind': kind} for kind, (key, _, _) in KINDS.items() for entry in data[key])


def persistence(connection) -> str:
    return campaign_table.rule(connection, 'injury_persistence')


# Lasting injuries --------------------------------------------------------------------------------

def active(connection, now: datetime) -> list[dict]:
    """The lasting injuries that show now: none under None, the unfaded ones under Temporary."""
    kept = persistence(connection)
    if kept == 'none':
        return []
    rows = many(connection, 'SELECT * FROM story_injuries ORDER BY rowid')
    entries = {entry['id']: entry for entry in table()}
    return [entries[row['injury_id']] | {'since': row['since']} for row in rows if row['injury_id'] in entries
            and (kept == 'permanent' or datetime.fromisoformat(row['since'])
                 + timedelta(days=entries[row['injury_id']]['fade_days']) > now)]


def roll(connection, now: datetime, cause: str, rng=None, logged: str = '', kind: str = 'injury') -> str | None:
    """A lasting injury (or condition) from the table, one the character does not already have; the line that says
    so."""
    if persistence(connection) == 'none':
        return None
    have = {row['injury_id'] for row in many(connection, 'SELECT injury_id FROM story_injuries')}
    # Lower intensity leaves out the worst of the table (an entry's `intensity`: the level each category needs).
    from dungeon import tone
    levels = tone.now(connection)['levels']
    left = [entry for entry in table() if entry['id'] not in have and entry['kind'] == kind
            and all(levels.get(category, 3) >= level for category, level in (entry.get('intensity') or {}).items())]
    if not left:
        return None
    rng = rng or random.SystemRandom()
    pick, total = rng.randint(1, sum(entry['weight'] for entry in left)), 0
    entry = left[-1]
    for candidate in left:
        total += candidate['weight']
        if pick <= total:
            entry = candidate
            break
    connection.execute('INSERT INTO story_injuries (injury_id, since) VALUES (?, ?)', (entry['id'], now.isoformat()))
    record.add(connection, 'wound' if kind == 'injury' else 'fact', "the player's character",
               f"Left with {entry['name']} by {cause}.", logged or now.isoformat())
    return f"{KINDS[kind][1]}: {entry['name']}."


def adjust(connection, actions: list[dict], now: datetime) -> list[dict]:
    """Each lasting injury makes the actions it touches a step harder."""
    shown = active(connection, now)
    adjusted = []
    for action in actions:
        steps = sum(1 for entry in shown if re.search(rf"\b({entry['harder']})\w*", action['action'], re.I))
        difficulty = action['difficulty']
        for _ in range(steps):
            difficulty = combat.HARDER[difficulty]
        adjusted.append(action | {'difficulty': difficulty})
    return adjusted


def prompt_text(connection, now: datetime) -> str:
    shown = active(connection, now)
    parts = []
    for kind, (_, _, called) in KINDS.items():
        if mine := [entry for entry in shown if entry['kind'] == kind]:
            parts.append(f"The player's character's {called} (kept by the game; play them, and let people react): "
                         + ' '.join(f"{entry['name'][0].upper()}{entry['name'][1:]}: {entry['seen']}"
                                    for entry in mine))
    return '\n'.join(parts)


def treatment_text(lines: list[str]) -> str:
    return '## The treatment (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''


def view(connection, now: datetime) -> list[str]:
    return [entry['name'] for entry in active(connection, now)]


# Treatment ---------------------------------------------------------------------------------------

def healer_in(people: list[dict]) -> dict | None:
    return next((person for person in people if HEALER.search(
        ' '.join(str(person['sheet'].get(key) or '') for key in ('role', 'occupation', 'about')))), None)


def supply(connection) -> dict | None:
    return next((row for item_id in SUPPLIES if (row := optional(
        connection, 'SELECT id, item_id FROM story_inventory WHERE item_id=? AND qty > 0 LIMIT 1', (item_id,)))), None)


def level(connection) -> int:
    """The character's wound level; under a ruleset that keeps hit points, the worse of it and what they read as
    (a Percentile fight lowers the hit points alone: playtest m5)."""
    now, points = combat.condition(connection), combat.points_of(connection)
    return max(now['level'], combat5e.level_for(*points)) if points else now['level']


def wanted(connection, text: str) -> bool:
    return bool(TREAT.search(text)) and 0 < level(connection) < combat.DYING and not combat.condition(connection)['dead']


def unhurt(connection, text: str) -> bool:
    """A line that treats a wound the character does not have: nothing to roll, and the narrator is told so."""
    return bool(TREAT.search(text)) and level(connection) == 0 and not combat.condition(connection)['dead'] and \
        not combat.fight(connection)


def first_aid(connection, text: str, actions: list[dict]) -> dict | None:
    """Under Percentile, a hurt character who binds their own wound rolls First Aid, though the Referee saw nothing
    uncertain in it (dungeon/combat_brp.py heals on a success, once a wound)."""
    found = sheet.native(connection) if sheet.ruleset(connection) == brp.ID else None
    if not found or found['hp'] >= found['max_hp'] or found['hp'] <= 0 or found.get('aided') or \
            brp.skill_for(text) != 'first_aid' or combat.fight(connection) or \
            any(brp.skill_for(action['action']) == 'first_aid' for action in actions):
        return None
    return {'action': 'first aid on the wound', 'stat': STAT, 'difficulty': 'normal'}


def untreated(actions: list[dict]) -> list[dict]:
    """The actions with no treatment among them, for a character with no wound."""
    return [action for action in actions if not TREAT.search(action['action'])]


def decide(connection, text: str, people: list[dict]) -> dict | None:
    """The character's own roll to treat a wound with supplies from the pack, when no healer is there to do it."""
    if not wanted(connection, text) or healer_in(people) or combat.fight(connection) or treated(connection):
        return None
    found = supply(connection)
    if found is None:
        return None
    difficulty = DIFFICULTY[level(connection)]
    return {'action': 'treat the wound', 'stat': STAT, 'difficulty': EASIER[difficulty] if found['item_id'] ==
            'poultice' else difficulty}


def treated(connection) -> bool:
    row = optional(connection, 'SELECT treated FROM story_wounds WHERE id=1')
    return bool(row and row['treated'])


def outcome(connection, band: str, by: str) -> list[str]:
    now = combat.condition(connection)
    change = MENDED[band]
    level = max(0, min(combat.DOWN, now['level'] - change))
    combat.set_condition(connection, level)
    connection.execute('UPDATE story_wounds SET treated=1 WHERE id=1')
    if change > 0:
        return [f"{by} treats the wound well: the character goes from {combat.word(connection, now['level'])} to "
                f'{combat.word(connection, level)}.']
    if change < 0:
        return [f'{by} makes it worse: the wound goes bad, and the character is now {combat.word(connection, level)}.']
    return [f"{by} does what can be done, and it is not enough: the character is still {combat.word(connection, level)}."]


def treat(connection, text: str, people: list[dict], rolls: list[dict], currency: dict, rng=None) -> list[str]:
    """The treatment a line asks for: by a healer there, for a fee, or by the character with supplies."""
    if unhurt(connection, text):
        return ["The character has no wound to treat."]
    if not wanted(connection, text) or combat.fight(connection):
        return []
    if treated(connection):
        return ["The wound has been treated already; now it needs rest."]
    healer = healer_in(people)
    if healer:
        name = healer['sheet']['name']
        if inventory.purse(connection) < HEALER_FEE:
            return [f"{name} will treat the wound for {inventory.money_text(HEALER_FEE, currency)}, and the "
                    "character cannot pay it."]
        inventory.set_purse(connection, inventory.purse(connection) - HEALER_FEE)
        level = combat.condition(connection)['level']
        band = marvel.roll(HEALER_SKILL, EASIER[DIFFICULTY[level]], rng or random.SystemRandom())['band']
        return [f"{name} is paid {inventory.money_text(HEALER_FEE, currency)} to treat the wound."] + outcome(
            connection, band, name)
    mine = next((roll for roll in rolls if roll.get('action') == 'treat the wound'), None)
    found = supply(connection)
    if mine is None or found is None:
        return ["There is nothing in the pack to treat the wound with: bandages or a poultice would do."]
    connection.execute('UPDATE story_inventory SET qty=qty-1 WHERE id=?', (found['id'],))
    return outcome(connection, mine['band'], "The player's character")
