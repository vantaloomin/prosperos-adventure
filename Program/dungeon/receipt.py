"""The turn receipt (requirements "Play screen and widgets": a turn receipt of chips): what a turn changed, in short
chips under the narration, so the player sees the purse, the pack, a wound or a new quest move without reading for it.

Nothing new is kept for it. Every player line saves the game state as it arrives (dungeon/timeline.py), so a turn's
receipt is the difference between its line's save and the next line's (or the game as it stands, for the latest
turn). It reads only what the player could already see: the purse, the pack, their condition and lasting injuries,
the quests they know of, and facts their character knows. Hidden truth, feelings and standings stay out.
"""
import json

from dungeon import combat, injuries, inventory, quests, timeline
from dungeon.database import optional

# Receipts for this many of the latest turns; older ones are rarely looked at and each costs two saves read.
RECENT = 40
# The character, as the code writes them into the record; their own changes have chips of their own.
CHARACTER = {"the player's character", 'the character'}
MOST_LEARNED = 3


def saved(connection, message_id: str) -> dict | None:
    row = optional(connection, 'SELECT state FROM story_saves WHERE message_id=?', (message_id,))
    return json.loads(row['state']) if row else None


def coins(state: dict) -> int:
    return sum(row['coins'] for row in state.get('story_purse', []))


def pack(state: dict) -> dict[tuple[str, str], int]:
    counted: dict[tuple[str, str], int] = {}
    for row in state.get('story_inventory', []):
        key = (row['city_id'], row['item_id'])
        counted[key] = counted.get(key, 0) + row['qty']
    return counted


def level(state: dict) -> tuple[int, bool]:
    row = next(iter(state.get('story_wounds', [])), None)
    return (row['level'], bool(row['dead'])) if row else (0, False)


def money(before: dict, after: dict, currency: dict) -> list[dict]:
    moved = coins(after) - coins(before)
    if not moved:
        return []
    sign = '+' if moved > 0 else '−'
    return [{'kind': 'coins', 'tone': 'gain' if moved > 0 else 'loss',
             'text': f'{sign}{inventory.money_text(abs(moved), currency)}'}]


def items(before: dict, after: dict) -> list[dict]:
    had, has = pack(before), pack(after)
    chips = []
    for key in sorted(set(had) | set(has)):
        moved = has.get(key, 0) - had.get(key, 0)
        entry = inventory.item(*key)
        if not moved or entry is None:
            continue
        count = f' ×{abs(moved)}' if abs(moved) > 1 else ''
        chips.append({'kind': 'item', 'tone': 'gain' if moved > 0 else 'loss',
                      'text': f"{'Gained' if moved > 0 else 'Lost'} {entry['name']}{count}"})
    return chips


def hurt(connection, before: dict, after: dict) -> list[dict]:
    (was, was_dead), (now, dead) = level(before), level(after)
    if dead and not was_dead:
        return [{'kind': 'hurt', 'tone': 'loss', 'text': 'Dead'}]
    if now == was:
        return []
    return [{'kind': 'hurt', 'tone': 'loss' if now > was else 'gain',
             'text': f"{'Hurt' if now > was else 'Mending'}: {combat.word(connection, now)}"}]


def lasting(before: dict, after: dict) -> list[dict]:
    had = {row['injury_id'] for row in before.get('story_injuries', [])}
    names = {entry['id']: entry['name'] for entry in injuries.table()}
    return [{'kind': 'injury', 'tone': 'loss', 'text': f"Lasting: {names[row['injury_id']]}"}
            for row in after.get('story_injuries', []) if row['injury_id'] not in had and row['injury_id'] in names]


QUEST_ENDS = {'done': 'Quest done', 'failed': 'Quest failed', 'missed': 'Quest missed'}


def quest_chips(before: dict, after: dict) -> list[dict]:
    had = {row['id']: row for row in before.get('story_quests', [])}
    chips = []
    for row in after.get('story_quests', []):
        title = quests.with_text(row).get('title')
        old = had.get(row['id'])
        if not title or not row['known']:
            continue
        if old is None or not old['known']:
            chips.append({'kind': 'quest', 'tone': 'neutral', 'text': f'New quest: {title}'})
        elif row['status'] != old['status'] and row['status'] in QUEST_ENDS:
            chips.append({'kind': 'quest', 'tone': 'gain' if row['status'] == 'done' else 'loss',
                          'text': f"{QUEST_ENDS[row['status']]}: {title}"})
    return chips


def learned(before: dict, after: dict) -> list[dict]:
    """New facts the character knows, by what they are about; the player's own notes are not news to them."""
    had = {row['id'] for row in before.get('record_entries', [])}
    subjects = []
    for row in after.get('record_entries', []):
        if row['id'] in had or row['removed'] or row['truth'] == 'world' or row['source'] == 'player':
            continue
        if row['subject'].lower() not in CHARACTER and row['subject'] not in subjects:
            subjects.append(row['subject'])
    if not subjects:
        return []
    more = f' and {len(subjects) - MOST_LEARNED} more' if len(subjects) > MOST_LEARNED else ''
    return [{'kind': 'learned', 'tone': 'neutral', 'text': f"Learned about {', '.join(subjects[:MOST_LEARNED])}{more}"}]


def chips(connection, before: dict, after: dict, currency: dict) -> list[dict]:
    return (hurt(connection, before, after) + lasting(before, after) + money(before, after, currency)
            + items(before, after) + quest_chips(before, after) + learned(before, after))


def receipts(connection, rows: list[dict], currency: dict) -> dict[str, list[dict]]:
    """Each recent player line's receipt, by the line's id: its save against the next line's, or the game now."""
    lines = [row['id'] for row in rows if row['role'] == 'user'][-RECENT - 1:]
    states = [saved(connection, line) for line in lines] + [json.loads(timeline.state(connection))]
    return {line: chips(connection, before, after, currency)
            for line, before, after in zip(lines, states, states[1:]) if before and after}
