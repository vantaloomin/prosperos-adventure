"""What the people met feel about the player's character, NPCs v0 (requirements "NPC minds").

Five separate tracks for each person met (story_people): trust, affection and respect from -5 to 5, fear and
desire from 0 to 5. Someone can fear and want the character while trusting them not at all. Code moves them:
- A roll aimed at someone by name moves them by its stat and how it landed (charm that works warms them, a threat
  that lands frightens them, a fight leaves fear and dislike).
- When a Continuity model is chosen, its question after each turn lists the people there, and it may say a turn
  moved one of them, with a short reason that is kept as their impression of the character.
The narrator is told each person's feelings in words, and they make asking them easier or harder: a warm person
is persuaded one step more easily, a hostile one a step less.

Feelings are game state, branched with the story (story_people is in dungeon/timeline.py SAVED).
"""
import json
import re

from dungeon import bonds, record
from dungeon.database import decode, encode, optional

AXES = ('trust', 'affection', 'respect', 'fear', 'desire')
LOW = {'trust': -5, 'affection': -5, 'respect': -5, 'fear': 0, 'desire': 0}
HIGH = 5
MOST_CHANGE = 2
IMPRESSIONS = 4
# Rolls that land on someone: (stat, landed) -> changes. `landed` is a success of any kind.
BY_ROLL = {
    ('Allure', True): {'affection': 1, 'trust': 1},
    ('Allure', False): {'trust': -1},
    ('Resolve', True): {'fear': 1, 'respect': 1},
    ('Resolve', False): {'respect': -1},
    ('Vitality', True): {'fear': 1, 'affection': -1},
    ('Vitality', False): {'respect': -1, 'affection': -1},
}
SUCCESS = ('success_cost', 'success', 'critical_success')
# Asking someone who likes and trusts the character is a step easier; asking someone hostile, a step harder.
WARM, COLD = 4, -4
EASIER = {'extreme': 'very_hard', 'very_hard': 'hard', 'hard': 'normal', 'normal': 'easy', 'easy': 'easy'}
HARDER = {value: key for key, value in EASIER.items() if key != value} | {'extreme': 'extreme'}
WORDS = {
    'trust': ((-5, -3, 'deeply distrusts them'), (-2, -1, 'is wary of them'), (1, 2, 'trusts them a little'),
              (3, 5, 'trusts them')),
    'affection': ((-5, -3, 'hates them'), (-2, -1, 'dislikes them'), (1, 2, 'likes them'), (3, 5, 'is fond of them')),
    'respect': ((-5, -3, 'holds them in contempt'), (-2, -1, 'looks down on them'), (1, 2, 'respects them'),
                (3, 5, 'admires them')),
    'fear': ((1, 2, 'is uneasy around them'), (3, 5, 'is afraid of them')),
    'desire': ((1, 2, 'is drawn to them'), (3, 5, 'wants them')),
}


def of(row: dict | None) -> dict:
    return {axis: (row or {}).get(axis) or 0 for axis in AXES}


def words(row: dict | None) -> list[str]:
    values = of(row)
    return [said for axis in AXES for low, high, said in WORDS[axis] if low <= values[axis] <= high]


def text(row: dict | None) -> str:
    """Their feelings toward the character in words, for the narrator; '' when they feel nothing in particular yet."""
    said = words(row)
    return 'Toward the player\'s character: ' + ', '.join(said) + '.' if said else ''


def shown(row: dict | None) -> str:
    """The same for the player, while the dice are shown: "Trusts you a little, is afraid of you"."""
    said = ', '.join(words(row)).replace(' them', ' you')
    return said[:1].upper() + said[1:]


def change(connection, key: str, changes: dict[str, int], why: str = ''):
    """Move someone's feelings, each by at most MOST_CHANGE and within its range; a reason is kept as an impression."""
    row = optional(connection, 'SELECT * FROM story_people WHERE key=?', (key,))
    if row is None:
        return
    values = of(row)
    for axis, amount in changes.items():
        if axis in AXES and isinstance(amount, int):
            step = max(-MOST_CHANGE, min(MOST_CHANGE, amount))
            values[axis] = max(LOW[axis], min(HIGH, values[axis] + step))
    kept = decode(row['impressions'] or '[]')
    if why.strip() and why.strip() not in kept:
        kept = [*kept, why.strip()[:160]][-IMPRESSIONS:]
    connection.execute(f"UPDATE story_people SET {', '.join(f'{axis}=?' for axis in AXES)}, impressions=? WHERE key=?",
                       (*values.values(), encode(kept), key))
    # Warm enough, they are bonded to the character (dungeon/bonds.py).
    bonds.earned(connection, key)


def aimed_at(row: dict, action: str) -> bool:
    """Whether an action names this person (their full or first name)."""
    names = {row['name'], row['name'].split(' ')[0]}
    return any(re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', action, re.I) for name in names if len(name) > 2)


def target(rows: list[dict], action: str) -> dict | None:
    return next((row for row in rows if aimed_at(row, action)), None)


def met(connection) -> list[dict]:
    return [dict(row) for row in connection.execute('SELECT * FROM story_people ORDER BY last_met_at DESC')]


def adjust(connection, actions: list[dict]) -> list[dict]:
    """A persuasion aimed at someone met is a step easier when they are warm to the character, harder when cold."""
    rows, adjusted = met(connection), []
    for action in actions:
        row = target(rows, action['action']) if action.get('stat') == 'Allure' else None
        warmth = of(row)['trust'] + of(row)['affection']
        if row and warmth >= WARM:
            action = action | {'difficulty': EASIER[action['difficulty']]}
        elif row and warmth <= COLD:
            action = action | {'difficulty': HARDER[action['difficulty']]}
        adjusted.append(action)
    return adjusted


def from_rolls(connection, rolls: list[dict]):
    """Rolls aimed at someone met move their feelings by the stat and how the roll landed."""
    rows = met(connection)
    for roll in rolls:
        row = target(rows, roll['action'])
        changes = BY_ROLL.get((roll['stat'], roll['band'] in SUCCESS)) if row else None
        if changes:
            if roll['band'] in ('critical_success', 'critical_failure'):
                changes = {axis: amount * 2 for axis, amount in changes.items()}
            change(connection, row['key'], changes)


# From the Continuity model ------------------------------------------------------------------------

def feelings_ask(people: list[dict]) -> str:
    """Added to the Continuity model's question: the named people there, by key."""
    if not people:
        return ''
    listed = '\n'.join(f"- {person['key']}: {person['name']}" for person in people)
    return (f'\n\nThese people were in the scene:\n{listed}\nIf this turn changed how one of them feels about the '
            f"player's character, add \"feelings\": [{{\"key\": \"...\", \"changes\": {{\"trust\": -1}}, \"why\": "
            f'"a few words, as they would put it"}}]. Axes: {", ".join(AXES)}; each change is -2 to 2.')


def feelings_schema(people: list[dict]) -> dict:
    """The part of the extraction schema (dungeon/record.py) that answers feelings_ask; an axis left alone is 0."""
    if not people:
        return {}
    return {'feelings': {'type': 'array', 'items': record.strict({
        'key': {'type': 'string', 'enum': [person['key'] for person in people]},
        'changes': record.strict({axis: {'type': 'integer'} for axis in AXES}), 'why': {'type': 'string'}})}}


def from_answer(connection, answer: str, keys: set[str]):
    match = re.search(r'\{.*\}', answer or '', re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        return
    for item in (data.get('feelings') if isinstance(data, dict) else None) or []:
        if isinstance(item, dict) and item.get('key') in keys and isinstance(item.get('changes'), dict):
            moved = {axis: amount for axis, amount in item['changes'].items()
                     if axis in AXES and isinstance(amount, int) and amount}
            if moved:
                change(connection, item['key'], moved, str(item.get('why') or ''))

