"""What each character remembers and feels, and how it follows branches (docs/spec.md "Turn state and persistence":
"Memory follows branches"; Batch 3: "Each character has Companion's memory, with Dungeon's fading").

Every row is written by a turn's commit and keyed by that turn's place on the timeline: its branch and the seq of its
anchor message. Reading goes through the branch's ancestry the way the story's messages do (adventure/timeline.py
`chain`), so going back to an earlier line hides what came after it and each branch reads only its own past. Rows
are never rewritten or deleted by play:

- **Fading is worked out as it is read.** A memory's age is the number of committed turns since it was made (or last
  brought back to mind, which is a row of its own in `character_memory_refreshes`). Small things fade soon, notable
  ones later, important ones (deaths, betrayals, debts, oaths: importance 3) never. A memory about someone the
  holder feels strongly toward stays sharp whatever its age. A faded memory is still returned, marked `faded`; the
  context builder words it vaguely.
- **Feelings are changes.** Each row moves one character's five tracks toward another, by at most MOST_CHANGE each,
  and they are added up in timeline order within the tracks' ranges (adventure/feelings.py AXES, LOW, HIGH).
  Rows at seq 0 on the first branch are a campaign's starting feelings, seen from every branch.

Nothing here decides who learns what: the turn's steps name every holder (adventure/rounds/contract.py Knowledge)
and Commit writes them through `remember` and `feel`.
"""
import re

from adventure import timeline
from adventure.database import identifier, many, one
from adventure.feelings import AXES, HIGH, LOW, MOST_CHANGE
from adventure.rounds.contract import KNOWLEDGE_KINDS, Point

# Turns before a memory of each importance fades; the most important never do (as adventure/remembering.py FADE).
FADE = {1: 25, 2: 100, 3: None}
# A feeling this strong (either way) keeps every memory about its subject sharp.
SHARP = 3
BIG = re.compile(r'\b(betray\w*|murder\w*|kill\w*|debt|owe[sd]?|sworn|swore|oath|vow\w*|revenge|died|dead)\b', re.I)
WORD = re.compile(r"[a-z][a-z'-]{2,}", re.I)
SMALL = {'the', 'and', 'her', 'his', 'their', 'with', 'from', 'that', 'this', 'you', 'your'}
START = Point(timeline.ROOT, 0)


def importance(text: str, given: int = 1) -> int:
    """At least 3 for a death, betrayal, debt or oath, whatever the step that found it said."""
    return 3 if BIG.search(text or '') else max(1, min(3, given))


def where(connection, point: Point) -> tuple[str, tuple]:
    """A WHERE clause for rows committed before `point` on its branch and the branches it came from."""
    parts, values = [], []
    for branch, limit in timeline.chain(connection, point.branch):
        parts.append('(branch_id=? AND seq<?)')
        values += [branch, point.seq if limit is None else min(limit, point.seq)]
    # The starting rows (seq 0 on the first branch) are seen from everywhere, even a branch tree cleared and begun again.
    parts.append('(branch_id=? AND seq=0)')
    values.append(timeline.ROOT)
    return '(' + ' OR '.join(parts) + ')', tuple(values)


def turns_before(connection, point: Point) -> int:
    """The committed turns before `point`: what memory ages by."""
    clause, values = where(connection, point)
    return one(connection, f"SELECT COUNT(*) AS n FROM round_turns WHERE state='committed' AND {clause}", values)['n']


# Writing (only from a turn's commit) ---------------------------------------------------------------------------------

def remember(connection, turn: dict, key: str, kind: str, text: str, *, about: str = '', source: str = '',
             weight: int = 1, now: str = '') -> str:
    """One memory for `key`, from the turn `turn` (a round_turns row, or START's place for a campaign's start)."""
    assert kind in KNOWLEDGE_KINDS, kind
    memory_id = identifier()
    connection.execute(
        'INSERT INTO character_memories (id, turn_id, branch_id, seq, number, character_key, kind, text, about, source, '
        'importance, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (memory_id, turn.get('id'), turn['branch_id'], turn['seq'], turn.get('number', 0), key, kind, text.strip(),
         about, source, importance(text, weight), now))
    return memory_id


def brought_back(connection, turn: dict, memory_id: str):
    """A memory mentioned again in this turn is fresh again from here, on this branch."""
    connection.execute('INSERT INTO character_memory_refreshes (memory_id, turn_id, branch_id, seq, number) '
                       'VALUES (?, ?, ?, ?, ?)', (memory_id, turn.get('id'), turn['branch_id'], turn['seq'],
                                                  turn.get('number', 0)))


def feel(connection, turn: dict, from_key: str, to_key: str, changes: dict[str, int], why: str = '', now: str = ''):
    """How `from_key`'s feelings toward `to_key` moved in this turn; each track by at most MOST_CHANGE."""
    steps = {axis: max(-MOST_CHANGE, min(MOST_CHANGE, int(changes.get(axis) or 0))) for axis in AXES}
    if not any(steps.values()) and not why.strip():
        return
    connection.execute(
        f"INSERT INTO character_feelings (id, turn_id, branch_id, seq, from_key, to_key, {', '.join(AXES)}, why, "
        f"created_at) VALUES (?, ?, ?, ?, ?, ?, {', '.join('?' * len(AXES))}, ?, ?)",
        (identifier(), turn.get('id'), turn['branch_id'], turn['seq'], from_key, to_key, *steps.values(),
         why.strip()[:160], now))


def forget_turn(connection, turn_id: str):
    """Everything a turn wrote, for a turn told again from the start (a retry of the same line)."""
    for table in ('character_memories', 'character_memory_refreshes', 'character_feelings'):
        connection.execute(f'DELETE FROM {table} WHERE turn_id=?', (turn_id,))


def clear(connection):
    """A new story."""
    for table in ('character_memories', 'character_memory_refreshes', 'character_feelings'):
        connection.execute(f'DELETE FROM {table}')


# Reading ------------------------------------------------------------------------------------------------------------

def feelings(connection, from_key: str, point: Point) -> dict[str, dict]:
    """`from_key`'s feelings toward everyone they have any toward, as of `point`: {to_key: {tracks, 'impressions'}}."""
    clause, values = where(connection, point)
    rows = many(connection, f'SELECT * FROM character_feelings WHERE from_key=? AND {clause} ORDER BY seq, rowid',
                (from_key, *values))
    result: dict[str, dict] = {}
    for row in rows:
        held = result.setdefault(row['to_key'], {axis: 0 for axis in AXES} | {'impressions': []})
        for axis in AXES:
            held[axis] = max(LOW[axis], min(HIGH, held[axis] + row[axis]))
        if row['why'] and row['why'] not in held['impressions']:
            held['impressions'] = [*held['impressions'], row['why']][-4:]
    return result


def toward(connection, from_key: str, to_key: str, point: Point) -> dict:
    return feelings(connection, from_key, point).get(to_key) or ({axis: 0 for axis in AXES} | {'impressions': []})


def words(text: str) -> set[str]:
    return {word.lower() for word in WORD.findall(text or '')} - SMALL


def freshest(connection, point: Point, ids: list[str]) -> dict[str, int]:
    """The latest turn number each memory was brought back to mind in, on this branch."""
    if not ids:
        return {}
    clause, values = where(connection, point)
    marks = ', '.join('?' * len(ids))
    rows = many(connection, f'SELECT memory_id, MAX(number) AS number FROM character_memory_refreshes WHERE memory_id '
                            f'IN ({marks}) AND {clause} GROUP BY memory_id', (*ids, *values))
    return {row['memory_id']: row['number'] for row in rows}


def faded(row: dict, now: int, sharp: set[str]) -> bool:
    limit = FADE.get(row['importance'])
    if limit is None or (row['about'] and row['about'] in sharp):
        return False
    return now - row['number'] > limit


def recall(connection, key: str, point: Point, focus: str = '', limit: int = 60) -> list[dict]:
    """What `key` remembers as of `point`, most important first, then what `focus` is about, then the newest; each
    with `faded` set by age, importance and strong feelings."""
    clause, values = where(connection, point)
    rows = many(connection, f'SELECT * FROM character_memories WHERE character_key=? AND {clause} '
                            'ORDER BY seq DESC, rowid DESC', (key, *values))
    fresh = freshest(connection, point, [row['id'] for row in rows])
    now = turns_before(connection, point)
    sharp = {other for other, held in feelings(connection, key, point).items()
             if any(abs(held[axis]) >= SHARP for axis in AXES)}
    mentioned = words(focus)
    for row in rows:
        row['number'] = max(row['number'], fresh.get(row['id'], 0))
        row['faded'] = faded(row, now, sharp)
    first = [row for row in rows if row['importance'] == 3]
    relevant = [row for row in rows if row['importance'] < 3 and mentioned & words(f"{row['text']} {row['about']}")]
    rest = [row for row in rows if row not in first and row not in relevant]
    return (first + relevant + rest)[:limit]
