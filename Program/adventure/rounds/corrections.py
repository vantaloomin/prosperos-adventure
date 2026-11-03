"""Corrections and struck inventions (docs/spec.md "Corrections", "Inventions").

**A correction is a turn-keyed patch.** From the GM view the user corrects a committed turn: a character knew
something they couldn't, a feeling moved that shouldn't have, a fact or a number was wrong. `correct` writes every
change in one transaction (the caller's write connection), each with a row in `round_corrections` keyed to the
corrected turn's place on the timeline (its branch and seq), so every later read through the branch's ancestry sees
it:

- **memory**: struck, or reworded. Recall reads through `amended` (registered with adventure/rounds/memory.py
  `amend`), which drops the memories a visible correction struck and swaps in the corrected wording, before fading,
  so a reworded memory keeps its importance.
- **feeling**: a compensating change, written with memory.feel at the corrected turn's place.
- **record**: changed or removed through adventure/record.py `correct`, which logs it in the journal's corrections too.
- **stat**: set through adventure/sheet.py `set_stats`, with the value before kept in the correction.

Later turns already played on that branch are not re-run: `later` lists the committed turns after it whose post
names what was corrected, so the user can go back if it matters.

**Inventions are kept unless the user strikes them.** The Writer lists each new name it made up with the sentence
that brought it in (`draft.extra['w4']['inventions']`). `strike` takes one out, after commit, as a correction: the
memories that turn wrote naming it are struck, the facts the post's extraction took from it go, and the passage is
handed back to be rewritten without it (adventure/story.py `rewritten`, which also takes the facts again).
"""
import re

from adventure import record, sheet, timeline
from adventure.database import decode, encode, identifier, many, optional
from adventure.errors import require
from adventure.feelings import AXES
from adventure.rounds import memory, turns
from adventure.rounds.contract import Point, State

KINDS = ('memory', 'feeling', 'record', 'stat', 'invention')
MOST_WHY = 500
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]{2,}")


def committed_turn(connection, turn_id: str) -> dict:
    row = turns.get(connection, turn_id)
    require(row['state'] == State.COMMITTED, 'Only a turn already played can be corrected.', 409)
    return row


def log(connection, turn: dict, kind: str, target: str, before, after, why: str, now: str) -> str:
    correction_id = identifier()
    connection.execute(
        'INSERT INTO round_corrections (id, turn_id, branch_id, seq, kind, target, before, after, why, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (correction_id, turn['id'], turn['branch_id'], turn['seq'], kind, target, encode(before),
         None if after is None else encode(after), why[:MOST_WHY], now))
    return correction_id


# Each kind of change -------------------------------------------------------------------------------------------------

def memory_change(connection, turn: dict, change: dict, why: str, now: str) -> str:
    row = optional(connection, 'SELECT * FROM character_memories WHERE id=?', (str(change.get('memory_id')),))
    require(row is not None, 'That memory is not in this story.', 404)
    text = change.get('text')
    text = ' '.join(str(text).split())[:500] if text is not None else None
    require(text is None or bool(text), 'Write what they remember, or strike it.', 422)
    return log(connection, turn, 'memory', row['id'], row['text'], text, why, now)


def feeling_change(connection, turn: dict, change: dict, why: str, now: str) -> str:
    moved = {axis: int(value) for axis, value in (change.get('changes') or {}).items() if axis in AXES}
    require(bool(moved) and change.get('from') and change.get('to'), 'Say who feels what toward whom.', 422)
    memory.feel(connection, turn, str(change['from']), str(change['to']), moved, why or 'a correction', now)
    return log(connection, turn, 'feeling', f"{change['from']}>{change['to']}", None, moved, why, now)


def record_change(connection, turn: dict, change: dict, why: str, now: str) -> str:
    entry = record.entry(connection, str(change.get('entry_id')))
    record.correct(connection, entry['id'], now, change.get('text'))
    return log(connection, turn, 'record', entry['id'], entry['text'], change.get('text'), why, now)


def stat_change(connection, turn: dict, change: dict, why: str, now: str) -> str:
    actor, stat = str(change.get('actor') or sheet.PERSONA), str(change.get('stat'))
    before = sheet.stats(connection, actor).get(stat)
    sheet.set_stats(connection, {stat: change.get('value')}, now, actor)
    return log(connection, turn, 'stat', f'{actor}:{stat}', before, change.get('value'), why, now)


CHANGES = {'memory': memory_change, 'feeling': feeling_change, 'record': record_change, 'stat': stat_change}


def correct(connection, turn_id: str, changes: list[dict], why: str, now: str) -> dict:
    """Every change to a committed turn, in the caller's one transaction; with the later turns that named it."""
    turn = committed_turn(connection, turn_id)
    require(0 < len(changes) <= 40, 'Make between one and forty changes at a time.', 422)
    made = []
    for change in changes:
        kind = change.get('kind')
        require(kind in CHANGES, f'A correction changes a {", ".join(CHANGES)}.', 422)
        made.append(CHANGES[kind](connection, turn, change, ' '.join((why or '').split()), now))
    rows = many(connection, f"SELECT before, after FROM round_corrections WHERE id IN ({', '.join('?' * len(made))})",
                made)
    named = ' '.join(str(decode(value) or '') for row in rows for value in (row['before'], row['after']) if value)
    return {'corrections': made, 'later': later(connection, turn, named)}


# Reading through corrections ------------------------------------------------------------------------------------------

def visible(connection, point: Point, kind: str) -> list[dict]:
    """The corrections of a kind seen from `point`: those keyed to turns on its branch's ancestry, oldest first."""
    clause, values = memory.where(connection, point)
    return many(connection, f'SELECT * FROM round_corrections WHERE kind=? AND {clause} ORDER BY created_at, rowid',
                (kind, *values))


def amended(connection, point: Point, rows: list[dict]) -> list[dict]:
    """Memories as corrected from `point`: struck ones gone, reworded ones in their new words (the last one wins)."""
    if not rows:
        return rows
    after = {row['target']: decode(row['after']) for row in visible(connection, point, 'memory')}
    if not after:
        return rows
    kept = []
    for row in rows:
        if row['id'] not in after:
            kept.append(row)
        elif after[row['id']] is not None:
            kept.append(row | {'text': after[row['id']], 'corrected': True})
    return kept


memory.amend('corrections', amended)


def of_turn(connection, turn_id: str) -> list[dict]:
    """A turn's corrections as the turn report lists them."""
    return [{'id': row['id'], 'kind': row['kind'], 'target': row['target'], 'before': decode(row['before']),
             'after': decode(row['after']), 'why': row['why'], 'created_at': row['created_at']}
            for row in many(connection, 'SELECT * FROM round_corrections WHERE turn_id=? ORDER BY created_at, rowid',
                            (turn_id,))]


def later(connection, turn: dict, named: str) -> list[dict]:
    """The committed turns after `turn` on the branch being played whose post names something in `named`."""
    names = {word.casefold() for word in WORD.findall(named or '') if word[0].isupper() or len(word) > 5}
    if not names:
        return []
    clause, values = memory.where(connection, Point(timeline.active(connection), 10 ** 12))
    rows = many(connection, f"SELECT id, number, seq, draft FROM round_turns WHERE state='committed' AND seq > ? AND "
                            f'{clause} ORDER BY seq', (turn['seq'], *values))
    found = []
    for row in rows:
        post = (decode(row['draft']) or {}).get('post') or ''
        if names & {word.casefold() for word in WORD.findall(post)}:
            found.append({'turn_id': row['id'], 'number': row['number'] + 1})
    return found


# Striking an invention --------------------------------------------------------------------------------------------------

def strike(connection, turn_id: str, name: str, now: str) -> dict:
    """Take one of the Writer's inventions out of a committed turn: its memories and facts go, and the passage that
    used it comes back to be rewritten. Returns the narration's id and the passage, and the later turns naming it."""
    turn = committed_turn(connection, turn_id)
    draft = decode(turn['draft']) or {}
    inventions = (draft.get('extra', {}).get('w4') or {}).get('inventions') or []
    found = next((item for item in inventions if (item.get('name') or '').casefold() == name.casefold()), None)
    require(found is not None, 'That is not one of the inventions of this turn.', 404)
    pattern = re.compile(rf'(?<!\w){re.escape(found["name"])}(?!\w)', re.IGNORECASE)
    for row in many(connection, 'SELECT id, text FROM character_memories WHERE turn_id=?', (turn['id'],)):
        if pattern.search(row['text']):
            log(connection, turn, 'memory', row['id'], row['text'], None, f'Struck invention: {found["name"]}', now)
    reply_id = reply_of(draft)
    if reply_id:
        for row in many(connection, "SELECT id, text, subject FROM record_entries WHERE message_id=? AND removed=0",
                        (reply_id,)):
            if pattern.search(row['text']) or pattern.search(row['subject']):
                connection.execute('UPDATE record_entries SET removed=1 WHERE id=?', (row['id'],))
    struck = log(connection, turn, 'invention', found['name'], found, None, 'Struck by the user', now)
    return {'correction': struck, 'message_id': reply_id, 'passage': found.get('text') or '',
            'later': later(connection, turn, found['name'])}


def reply_of(draft: dict) -> str | None:
    """The committed narrator message's id: saved by today's telling on a player's line (adventure/rounds/telling.py),
    or by the round Writer's 'writer' hook in a round with no player's line (W4, `draft.extra['w4']['reply']`)."""
    extra = draft.get('extra', {})
    for key in ('telling', 'w4'):
        found = ((extra.get(key) or {}).get('reply') or {}).get('id')
        if found:
            return found
    return None


def clear(connection):
    """A new story."""
    connection.execute('DELETE FROM round_corrections')


def struck(connection, turn_id: str) -> set[str]:
    """The names of a turn's inventions the user struck."""
    return {row['target'].casefold() for row in many(
        connection, "SELECT target FROM round_corrections WHERE turn_id=? AND kind='invention'", (turn_id,))}
