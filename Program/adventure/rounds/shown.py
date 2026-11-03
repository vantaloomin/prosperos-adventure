"""Character sheets refreshed from the page (docs/spec.md "Keeping records readable": "Character sheets are refreshed
from the page").

At each chapter close (adventure/chapters.py `arrive`), code drafts a "shown so far" update for each character at
the table (adventure/rounds/seats.py) from what the chapter put on the page, with no model call:

- **injuries**: the record's wounds about them from the chapter's lines;
- **revealed**: what the chapter showed about them that the player's character saw (record secrets, facts and
  relationships with truth 'both'; hidden truth stays off the sheet);
- **habits**: what they kept doing, an intent they declared in more than one of the chapter's turns.

A draft applies when the user reviews it in the GM view (they may edit or drop items first), or at once in Watch,
where nobody is there to review. An applied update is keyed to the chapter's end on its branch, so it is read
through the branch's ancestry like the story (`sheet`, `text`) and going back before the chapter's end drops it.
A campaign with nobody seated drafts nothing.
"""
import re
from collections import Counter

from adventure import timeline
from adventure.database import decode, encode, identifier, many, one, optional
from adventure.errors import require
from adventure.rounds import seats as table
from adventure.rounds.contract import Mode

KINDS = ('injury', 'revealed', 'habit')
REVEALED = ('secret', 'fact', 'relationship')
MOST = 8
LONGEST = 300
# A habit is an intent declared in at least this many of the chapter's turns.
HABIT = 2
LEAD = re.compile(r"^(?:i|i'll|i will|she|he|they|you)\s+", re.I)


def named(name: str, text: str) -> bool:
    """The seat's name, or its first word (a first name), in the text as a whole word."""
    words = {name.strip(), name.strip().split(' ')[0]} - {''}
    return any(re.search(rf'(?<!\w){re.escape(word)}(?!\w)', text, re.I) for word in words)


def span(connection, branch_id: str, start: int, end: int) -> tuple[list[str], list[dict]]:
    """The chapter's message ids and its committed round turns, as the branch tells them."""
    where, values = timeline.visible(connection, branch_id)
    messages = [row['id'] for row in many(
        connection, f'SELECT id FROM story_messages WHERE {where} AND seq >= ? AND seq < ?', (*values, start, end))]
    turns = many(connection, f"SELECT draft FROM round_turns WHERE {where} AND seq >= ? AND seq <= ? AND "
                             "state='committed' ORDER BY seq, number", (*values, start, end))
    return messages, turns


def from_record(connection, messages: list[str], name: str) -> list[dict]:
    if not messages:
        return []
    marks = ', '.join('?' for _ in messages)
    rows = many(connection, f'SELECT kind, subject, text, truth FROM record_entries WHERE removed=0 AND '
                            f'message_id IN ({marks}) ORDER BY created_at, rowid', tuple(messages))
    found = []
    for row in rows:
        if not named(name, row['subject']):
            continue
        if row['kind'] == 'wound':
            found.append({'kind': 'injury', 'text': row['text']})
        elif row['kind'] in REVEALED and row['truth'] == 'both':
            found.append({'kind': 'revealed', 'text': row['text']})
    return found


def plain_intent(text: str, name: str) -> str:
    text = ' '.join(text.split()).strip().rstrip('.')
    for word in {name.strip(), name.strip().split(' ')[0]} - {''}:
        if text.casefold().startswith(word.casefold() + ' '):
            text = text[len(word) + 1:]
            break
    return LEAD.sub('', text)


def stem(verb: str) -> str:
    """A verb as "I" says it, so "watches" and "watch" are the same act."""
    if verb.endswith('es') and verb[:-2].endswith(('ch', 'sh', 'x', 'ss', 'z')):
        return verb[:-2]
    return verb[:-1] if verb.endswith('s') and not verb.endswith('ss') else verb


def habits(turns: list[dict], key: str, name: str) -> list[dict]:
    """An intent the character declared in more than one turn: the same first words, the latest as said."""
    seen, latest = Counter(), {}
    for turn in turns:
        declared = ((decode(turn['draft']) or {}).get('declarations') or {}).get(key) or {}
        intent = plain_intent(str(declared.get('intent') or ''), name)
        if intent:
            first, *rest = intent.casefold().split()[:2]
            lead = ' '.join([stem(first), *rest])
            seen[lead] += 1
            latest[lead] = intent
    return [{'kind': 'habit', 'text': f'Often: {latest[lead]}.'} for lead, count in seen.most_common() if count >= HABIT]


def drafted(connection, branch_id: str, start: int, end: int, key: str, name: str) -> list[dict]:
    messages, turns = span(connection, branch_id, start, end)
    items = from_record(connection, messages, name) + habits(turns, key, name)
    unique = list({(item['kind'], item['text'].casefold()): item for item in items}.values())
    return [{'kind': item['kind'], 'text': item['text'][:LONGEST]} for item in unique[:MOST]]


def close(connection, chapter_id: str, branch_id: str, start: int, end: int, now: str) -> list[dict]:
    """The chapter from `start` to before `end` closed: a draft per seated character it showed anything of, applied
    at once in Watch."""
    watching = table.settings(connection)['mode'] == Mode.WATCH.value
    made = []
    for seat in table.seats(connection):
        items = drafted(connection, branch_id, start, end, seat.key, seat.name)
        if not items:
            continue
        update_id = identifier()
        connection.execute(
            'INSERT INTO round_shown (id, seat_key, name, chapter_id, branch_id, seq, items, status, created_at, '
            'decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (update_id, seat.key, seat.name, chapter_id, branch_id, end, encode(items),
             'applied' if watching else 'drafted', now, now if watching else None))
        made.append(of(connection, update_id))
    return made


def shape(row: dict) -> dict:
    return {'id': row['id'], 'seat': row['seat_key'], 'name': row['name'], 'chapter_id': row['chapter_id'],
            'items': decode(row['items']) or [], 'status': row['status'], 'created_at': row['created_at']}


def of(connection, update_id: str) -> dict:
    return shape(one(connection, 'SELECT * FROM round_shown WHERE id=?', (update_id,)))


def visible(connection, status: str | None = None, branch_id: str | None = None) -> list[dict]:
    where, values = timeline.visible(connection, branch_id)
    chosen = 'AND status=?' if status else ''
    return [shape(row) for row in many(connection, f'SELECT * FROM round_shown WHERE {where} {chosen} '
                                                   'ORDER BY seq, created_at, rowid',
                                       (*values, *((status,) if status else ())))]


def checked_items(items: list) -> list[dict]:
    require(isinstance(items, list) and len(items) <= MOST, f'At most {MOST} items.', 422)
    result = []
    for item in items:
        require(isinstance(item, dict) and item.get('kind') in KINDS, f'Each item is one of: {", ".join(KINDS)}.',
                422)
        text = ' '.join(str(item.get('text') or '').split())
        require(0 < len(text) <= LONGEST, f'Each item has a text of at most {LONGEST} characters.', 422)
        result.append({'kind': item['kind'], 'text': text})
    return result


def decide(connection, update_id: str, apply: bool, now: str, items: list | None = None) -> dict:
    """The user's review: apply the draft (as edited, when items are given) or dismiss it."""
    row = optional(connection, 'SELECT * FROM round_shown WHERE id=?', (update_id,))
    require(row is not None, 'That sheet update is not there.', 404)
    require(row['status'] == 'drafted', 'That sheet update was already reviewed.', 409)
    chosen = checked_items(items) if items is not None else decode(row['items']) or []
    connection.execute('UPDATE round_shown SET items=?, status=?, decided_at=? WHERE id=?',
                       (encode(chosen), 'applied' if apply and chosen else 'dismissed', now, update_id))
    return of(connection, update_id)


def sheet(connection, key: str, branch_id: str | None = None) -> list[dict]:
    """A character's "shown so far": every applied item for them on this branch, oldest first, a later repeat
    dropped."""
    items = [item for update in visible(connection, 'applied', branch_id) if update['seat'] == key
             for item in update['items']]
    return list({(item['kind'], item['text'].casefold()): item for item in items}.values())


def text(connection, key: str, branch_id: str | None = None) -> str:
    """The "shown so far" lines for a character's sheet in a prompt; empty when nothing was shown yet."""
    items = sheet(connection, key, branch_id)
    labels = {'injury': 'Hurt', 'revealed': 'Shown', 'habit': 'Habit'}
    return '\n'.join(f"- {labels[item['kind']]}: {item['text']}" for item in items)


def clear(connection):
    connection.execute('DELETE FROM round_shown')
