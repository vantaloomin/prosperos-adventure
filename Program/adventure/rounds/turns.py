"""The turns of the round loop as rows (`round_turns`; docs/spec.md "Turn state and persistence": "A turn is a
transaction").

A turn is opened at a place on the timeline (its branch and the seq of the story message it opens with), moves
through the states in adventure/rounds/contract.py, and ends committed or discarded. Its snapshot and draft are kept
with it as JSON after every step, so the turn can be picked up again where it waits for the user, and a re-ask can
read exactly what the original turn read. At most one turn is open at a time (`under_way`); the command queue keeps
it that way (adventure/rounds/queue.py).
"""
from adventure.database import decode, encode, identifier, many, one, optional
from adventure.errors import require
from adventure.rounds import memory
from adventure.rounds.contract import Point, State

OPEN = tuple(str(state) for state in State if state not in (State.IDLE, State.COMMITTED, State.DISCARDED))


def get(connection, turn_id: str) -> dict:
    row = optional(connection, 'SELECT * FROM round_turns WHERE id=?', (turn_id,))
    require(row is not None, 'That turn is not in this story.', 404)
    return row


def under_way(connection) -> dict | None:
    """The turn being played, if any: opened and not yet committed or discarded."""
    marks = ', '.join('?' * len(OPEN))
    return optional(connection, f'SELECT * FROM round_turns WHERE state IN ({marks}) ORDER BY created_at DESC LIMIT 1',
                    OPEN)


def open_turn(connection, branch_id: str, seq: int, mode: str, now: str, anchor_id: str | None = None,
              reask_of: str | None = None, reask_seat: str | None = None) -> dict:
    """A new turn at (branch, seq), counted after the committed turns before it there."""
    require(under_way(connection) is None, 'A turn is already being played.', 409)
    turn_id = identifier()
    number = memory.turns_before(connection, Point(branch_id, seq))
    connection.execute(
        'INSERT INTO round_turns (id, anchor_id, branch_id, seq, number, state, mode, reask_of, reask_seat, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (turn_id, anchor_id, branch_id, seq, number, str(State.GATHERING), str(mode), reask_of, reask_seat, now))
    return get(connection, turn_id)


def view(row: dict) -> dict:
    """A turn's state and marks, and the reply card it waits on; what it holds is shown through the readers' own
    views, never raw here."""
    draft = decode(row['draft']) or {}
    waiting = draft.get('awaiting')
    return {'id': row['id'], 'state': row['state'], 'mode': row['mode'], 'marks': decode(row['marks']) or [],
            'reask_of': row['reask_of'], 'reask_seat': row['reask_seat'], 'error': row['error'],
            'awaiting': {key: waiting[key] for key in ('seat', 'speaker', 'line', 'context')} if waiting else None}


def set_state(connection, turn_id: str, state: State, now: str = ''):
    connection.execute('UPDATE round_turns SET state=?, committed_at=CASE WHEN ?=? THEN ? ELSE committed_at END '
                       'WHERE id=?', (str(state), str(state), str(State.COMMITTED), now, turn_id))


def keep(connection, turn_id: str, snapshot: dict | None = None, draft: dict | None = None):
    """Save the turn's snapshot and draft as they stand: the checkpoint a restart reads."""
    if snapshot is not None:
        connection.execute('UPDATE round_turns SET snapshot=? WHERE id=?', (encode(snapshot), turn_id))
    if draft is not None:
        connection.execute('UPDATE round_turns SET draft=? WHERE id=?', (encode(draft), turn_id))


def discard(connection, turn_id: str, error: str | None = None):
    connection.execute('UPDATE round_turns SET state=?, error=? WHERE id=?', (str(State.DISCARDED), error, turn_id))


def mark(connection, turn_id: str, what: str):
    """Note something about a turn the user should see later: the GM view was open, a roll was overridden."""
    marks = decode(get(connection, turn_id)['marks']) or []
    if what not in marks:
        connection.execute('UPDATE round_turns SET marks=? WHERE id=?', (encode([*marks, what]), turn_id))


def marks(connection, turn_id: str) -> list[str]:
    return decode(get(connection, turn_id)['marks']) or []


def committed(connection, point: Point, limit: int = 50) -> list[dict]:
    """The newest committed turns before `point`, newest first."""
    clause, values = memory.where(connection, point)
    return many(connection, f"SELECT * FROM round_turns WHERE state='committed' AND {clause} ORDER BY seq DESC "
                            'LIMIT ?', (*values, limit))


def count(connection) -> int:
    return one(connection, 'SELECT COUNT(*) AS n FROM round_turns')['n']


def clear(connection):
    """A new story."""
    connection.execute('DELETE FROM round_turns')
