"""Switching modes (docs/spec.md Batch 3: "Modes can be switched any time"; "Waiting and pauses": "Switching out of
Play doesn't spoil the past").

The mode itself is a round setting (adventure/rounds/seats.py), so a switch asked for during a turn waits for the
next Idle and the turn finishes in the mode it started in. This module adds what a switch decides besides the mode:

- **Who stands in for the user's character outside Play** (`mode_settings.stand_in`): an agent or its Program mind,
  the user's pick. The user's seat stays the human's (going back to Play needs nothing undone); at Gather, outside
  Play, the Gathering step `stand_in` gives the character the mind the user picked. As an agent it is a character
  promoted by hand, so it comes after the party and before characters picked by role for the agent cap, and the
  cap is applied again with it in (the 'pick' step, adventure/rounds/declare.py).
- **Motives missed in Play stay hidden unless the user chooses.** On a switch out of Play the user is asked once
  whether to see them, defaulting to hidden (`mode_switches`). A turn played in Play shows its motives only when a
  later switch said to (`revealed`); turns played in Author and Watch show them as those modes always do. The
  minds panel and anything else that shows a past turn's motives asks `revealed` (adventure/rounds/context.py
  `minds`, its `reveal`).
"""
from adventure.database import identifier, many, optional
from adventure.errors import require
from adventure.rounds import engine, seats
from adventure.rounds.contract import Mind, Mode, State

STAND_INS = (Mind.AGENT.value, Mind.PROGRAM.value)
WATCH_SECONDS = (0, 3600)
DEFAULTS = {'stand_in': Mind.PROGRAM.value, 'watch_seconds': 20}


def settings(connection) -> dict:
    row = optional(connection, 'SELECT stand_in, watch_seconds FROM mode_settings WHERE id=1')
    return dict(row) if row else dict(DEFAULTS)


def checked(changes: dict) -> dict:
    result = {}
    if changes.get('stand_in') is not None:
        require(changes['stand_in'] in STAND_INS, "Outside Play your character runs on an agent or its Program mind.",
                422)
        result['stand_in'] = str(changes['stand_in'])
    if changes.get('watch_seconds') is not None:
        low, high = WATCH_SECONDS
        seconds = changes['watch_seconds']
        require(isinstance(seconds, int) and low <= seconds <= high,
                f'The Watch timer runs from {low} (by hand) to {high} seconds.', 422)
        result['watch_seconds'] = seconds
    return result


def change(connection, changes: dict, now: str) -> dict:
    values = settings(connection) | checked(changes)
    connection.execute('INSERT INTO mode_settings (id, stand_in, watch_seconds, updated_at) VALUES (1, ?, ?, ?) '
                       'ON CONFLICT(id) DO UPDATE SET stand_in=excluded.stand_in, '
                       'watch_seconds=excluded.watch_seconds, updated_at=excluded.updated_at',
                       (values['stand_in'], values['watch_seconds'], now))
    return settings(connection)


# A switch -----------------------------------------------------------------------------------------------------------

def coming(connection) -> str:
    """The mode the next turn plays in: the one queued for Idle, else the one in force."""
    held = seats.settings(connection)
    return held['queued'].get('mode', held['mode'])


def switch(connection, mode: str, now: str, under_way: bool, stand_in: str | None = None,
           reveal: bool = False) -> dict:
    """Switch to `mode` (at the next Idle when a turn is under way). Leaving Play records whether the user chose to
    see the motives they missed; `stand_in` sets who plays their character outside Play."""
    require(mode in tuple(Mode), 'The modes are Play, Author and Watch.', 422)
    before = coming(connection)
    if stand_in is not None:
        change(connection, {'stand_in': stand_in}, now)
    if before == Mode.PLAY and mode != Mode.PLAY:
        newest = optional(connection, 'SELECT MAX(rowid) AS n FROM round_turns')['n'] or 0
        connection.execute('INSERT INTO mode_switches (id, from_mode, to_mode, reveal, through_turn, created_at) '
                           'VALUES (?, ?, ?, ?, ?, ?)', (identifier(), before, mode, int(bool(reveal)), newest, now))
    return seats.change(connection, {'mode': mode}, under_way)


def revealed(connection, row: dict) -> bool:
    """Whether a past turn's motives may be shown: always for Author and Watch turns; for a Play turn, only when the
    user chose to see what they missed on a switch made after it."""
    if row['mode'] != Mode.PLAY:
        return True
    return optional(connection, 'SELECT 1 FROM mode_switches s JOIN round_turns t ON t.id=? WHERE s.reveal=1 AND '
                                's.through_turn >= t.rowid LIMIT 1', (row['id'],)) is not None


def asked(connection) -> list[dict]:
    """Every switch out of Play and what the user chose, newest first."""
    return [{'from': row['from_mode'], 'to': row['to_mode'], 'reveal': bool(row['reveal']), 'at': row['created_at']}
            for row in many(connection, 'SELECT * FROM mode_switches ORDER BY created_at DESC, rowid DESC')]


# Gather: the user's character outside Play --------------------------------------------------------------------------

async def stand_in(turn: engine.Turn):
    """Outside Play, the user's character runs on the mind the user picked; as an agent it takes a slot within the
    cap like a character promoted by hand. 'pick' has already made it a Program character for the turn."""
    snapshot = turn.snapshot
    if snapshot.mode == Mode.PLAY:
        return
    with turn.database.connect() as connection:
        picked = settings(connection)['stand_in']
        human = next((seat.key for seat in seats.seats(connection) if seat.mind == Mind.HUMAN), None)
    seat = snapshot.seat(human) if human else None
    snapshot.settings['stand_in'] = {'key': human, 'mind': picked} if human else None
    if seat is None or picked != Mind.AGENT:
        return
    seat.mind, seat.promoted = Mind.AGENT, True
    dropped = list(snapshot.settings.get('dropped') or [])
    pick = dict(engine.STEPS[State.GATHERING]).get('pick')
    await pick(turn)
    snapshot.settings['dropped'] = list(dict.fromkeys([*dropped, *(snapshot.settings.get('dropped') or [])]))


engine.register(State.GATHERING, 'stand_in', stand_in, after='pick')
