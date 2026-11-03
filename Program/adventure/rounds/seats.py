"""Who sits at the table, and how rounds play in this campaign (docs/spec.md Batch 1: "Agents: party members plus key
NPCs, up to 6 at once"; Batch 3: "Modes can be switched any time"; "Turn state and persistence": "One command queue").

- **Seats** (`round_seats`) hold the user's choices per character: an agent, a Program mind (Dungeon's code minds),
  or the human; seat order, which breaks ties when agents are picked; a model for that character alone; the user's
  short notes; and whether the user promoted them by hand. They are choices, not story, so going back keeps them.
  Who is an agent in a given turn is decided at Gather, within the cap (adventure/rounds/engine.py).
- **Settings** (`round_settings`) hold the mode (Play, Author, Watch), the agent cap (1 to 6, default 6) and the
  conversation cap (1 to 12, default 4). A change asked for while a turn is under way waits in `queued` and takes
  effect at the next Idle (`apply_queued`), so a turn always finishes as it started.
"""
from adventure.database import decode, encode, many, optional
from adventure.errors import require
from adventure.rounds.contract import Mind, Mode, Seat

AGENT_CAP = (1, 6)
CONVERSE_CAP = (1, 12)
DEFAULTS = {'mode': Mode.PLAY.value, 'agent_cap': 6, 'converse_cap': 4}


def seat_of(row: dict) -> Seat:
    return Seat(key=row['key'], name=row['name'], mind=row['mind'], order=row['seat_order'],
                model_profile_id=row['model_profile_id'], notes=row['notes'], promoted=bool(row['promoted']))


def seats(connection) -> list[Seat]:
    return [seat_of(row) for row in many(connection, 'SELECT * FROM round_seats ORDER BY seat_order, rowid')]


def seat(connection, key: str) -> Seat | None:
    row = optional(connection, 'SELECT * FROM round_seats WHERE key=?', (key,))
    return seat_of(row) if row else None


def set_seat(connection, key: str, name: str, now: str, **changes) -> Seat:
    """Add a seat or change one: `mind`, `order`, `model_profile_id`, `notes`, `promoted`. Only one human sits."""
    current = seat(connection, key)
    mind = changes.get('mind', current.mind if current else Mind.PROGRAM)
    require(mind in tuple(Mind), 'A seat is an agent, a Program mind or the human.', 422)
    if mind == Mind.HUMAN:
        connection.execute("UPDATE round_seats SET mind='program' WHERE mind='human' AND key != ?", (key,))
    order = changes.get('order', current.order if current else next_order(connection))
    connection.execute(
        'INSERT INTO round_seats (key, name, mind, seat_order, model_profile_id, notes, promoted, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET name=excluded.name, mind=excluded.mind, '
        'seat_order=excluded.seat_order, model_profile_id=excluded.model_profile_id, notes=excluded.notes, '
        'promoted=excluded.promoted',
        (key, name, str(mind), order, changes.get('model_profile_id', current.model_profile_id if current else None),
         str(changes.get('notes', current.notes if current else ''))[:600],
         int(bool(changes.get('promoted', current.promoted if current else False))), now))
    return seat(connection, key)


def next_order(connection) -> int:
    row = optional(connection, 'SELECT MAX(seat_order) AS n FROM round_seats')
    return (row['n'] if row and row['n'] is not None else -1) + 1


def remove_seat(connection, key: str):
    connection.execute('DELETE FROM round_seats WHERE key=?', (key,))


# Settings -----------------------------------------------------------------------------------------------------------

def settings(connection) -> dict:
    row = optional(connection, 'SELECT * FROM round_settings WHERE id=1')
    if row is None:
        return DEFAULTS | {'queued': {}}
    return {'mode': row['mode'], 'agent_cap': row['agent_cap'], 'converse_cap': row['converse_cap'],
            'queued': decode(row['queued']) or {}}


def checked(changes: dict) -> dict:
    """Only known settings, within their ranges."""
    result = {}
    if 'mode' in changes:
        require(changes['mode'] in tuple(Mode), 'The modes are Play, Author and Watch.', 422)
        result['mode'] = str(changes['mode'])
    for name, (low, high) in (('agent_cap', AGENT_CAP), ('converse_cap', CONVERSE_CAP)):
        if name in changes:
            value = changes[name]
            require(isinstance(value, int) and low <= value <= high, f'{name} runs from {low} to {high}.', 422)
            result[name] = value
    return result


def write(connection, values: dict, queued: dict):
    connection.execute(
        'INSERT INTO round_settings (id, mode, agent_cap, converse_cap, queued) VALUES (1, ?, ?, ?, ?) '
        'ON CONFLICT(id) DO UPDATE SET mode=excluded.mode, agent_cap=excluded.agent_cap, '
        'converse_cap=excluded.converse_cap, queued=excluded.queued',
        (values['mode'], values['agent_cap'], values['converse_cap'], encode(queued)))


def change(connection, changes: dict, under_way: bool) -> dict:
    """Change the settings now, or, with a turn under way, at the next Idle."""
    changes, current = checked(changes), settings(connection)
    if under_way:
        write(connection, current, current['queued'] | changes)
    else:
        write(connection, current | changes, current['queued'])
    return settings(connection)


def apply_queued(connection) -> dict:
    """At Idle: the changes asked for during the turn take effect."""
    current = settings(connection)
    if current['queued']:
        write(connection, current | current['queued'], {})
    return settings(connection)
