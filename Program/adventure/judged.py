"""What the fact extraction model judged after a turn, each with an undo (docs/spec.md, code and model boundary
follow-ups: "The fact extraction model still judges quest endings, oaths, feelings and dark acts, and the user can
undo each one").

After a player's line the Continuity model may say a quest ended, an oath was sworn, someone's feelings shifted or
the character did something dark (adventure/story.py afterwards). Code applies each one within its own limits, as
before, but now inside `judging`, which keeps what that one change did to the game state:

- **Kept as a diff of the saved game state.** The game state is every table in adventure/timeline.py SAVED. Before and
  after each change the tables are read, and what differs (rows added, rows removed, columns changed) is kept in
  `judged_changes`, keyed to the narrator's reply it followed, with a line in plain words for the turn report. So a
  quest's ending is undone whole: its status, the pay or standing it settled, a milestone it gave, the lines it left
  in the record.
- **Undo puts back only that change** (`undo`). Rows it added are taken out and rows it removed put back. A number it
  moved is moved back by the same amount, so what later turns did to it stays (a feeling moved again since keeps
  that move); any other value it changed goes back only if nothing has changed it since. An undone change is marked,
  never deleted, and can't be undone twice.
- **Only on the branch being played.** A change belongs to its reply; once the story has gone back past that reply,
  the change is not in play and can't be undone from here.
"""
import json
from contextlib import contextmanager

from adventure import timeline
from adventure.database import decode, encode, identifier, many, optional
from adventure.errors import require

KINDS = ('quest', 'oath', 'feeling', 'dark')


# The game state, read and compared ----------------------------------------------------------------------------------

def keys_of(connection, table: str) -> list[str]:
    """The table's primary key columns, in key order; [] for a table without one."""
    columns = [dict(row) for row in connection.execute(f'PRAGMA table_info({table})')]
    return [column['name'] for column in sorted(columns, key=lambda column: column['pk']) if column['pk']]


def snapshot(connection) -> dict[str, list[dict]]:
    return {table: many(connection, f'SELECT * FROM {table}') for table in timeline.SAVED}


def identity(row: dict, keys: list[str]):
    return tuple(row[key] for key in keys) if keys else json.dumps(row, sort_keys=True, default=str)


def diff(connection, before: dict, after: dict) -> dict:
    """What changed between two snapshots, by table: {added: [row], removed: [row], changed: [{key, columns:
    {column: [old, new]}}]}; tables with no change are left out."""
    changes = {}
    for table in timeline.SAVED:
        keys = keys_of(connection, table)
        old = {identity(row, keys): row for row in before.get(table, [])}
        new = {identity(row, keys): row for row in after.get(table, [])}
        added = [row for key, row in new.items() if key not in old]
        removed = [row for key, row in old.items() if key not in new]
        changed = [{'key': dict(zip(keys, key)),
                    'columns': {column: [old[key][column], value] for column, value in row.items()
                                if old[key].get(column) != value}}
                   for key, row in new.items() if key in old and old[key] != row]
        if added or removed or changed:
            changes[table] = {'added': added, 'removed': removed, 'changed': changed}
    return changes


# Keeping a judged change ----------------------------------------------------------------------------------------------

class Judging:
    """The state as the next change starts, carried from one change to the next so each is read only once."""

    def __init__(self, connection, message_id: str, now: str):
        self.connection, self.message_id, self.now = connection, message_id, now
        self.state = snapshot(connection)

    @contextmanager
    def change(self, kind: str, label: str):
        """Apply one judged change inside the block; what it did is kept, unless it did nothing."""
        assert kind in KINDS, kind
        yield
        after = snapshot(self.connection)
        changes = diff(self.connection, self.state, after)
        self.state = after
        if changes:
            self.connection.execute(
                'INSERT INTO judged_changes (id, message_id, kind, label, changes, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (identifier(), self.message_id, kind, label[:300], encode(changes), self.now))


def of_reply(connection, message_id: str | None) -> list[dict]:
    """A reply's judged changes, for the turn report."""
    if not message_id:
        return []
    return [{'id': row['id'], 'kind': row['kind'], 'label': row['label'], 'undone': bool(row['undone_at'])}
            for row in many(connection, 'SELECT id, kind, label, undone_at FROM judged_changes WHERE message_id=? '
                                        'ORDER BY created_at, rowid', (message_id,))]


# Undoing one ----------------------------------------------------------------------------------------------------------

def where(keys: list[str], row: dict) -> tuple[str, tuple]:
    """A WHERE clause for one row: by its key, or by every column for a table without one."""
    columns = keys or list(row)
    return ' AND '.join(f'{column} IS ?' for column in columns), tuple(row[column] for column in columns)


def number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def put_back(current: dict, columns: dict) -> dict:
    """The values to write back into a row a change moved: a number by the same amount, anything else only if it is
    still what the change left."""
    put = {}
    for column, (old, new) in columns.items():
        if column not in current:
            continue
        if number(old) and number(new) and number(current[column]):
            put[column] = current[column] - (new - old)
        elif current[column] == new:
            put[column] = old
    return put


def reverse_table(connection, table: str, change: dict):
    keys = keys_of(connection, table)
    for row in change['added']:
        clause, values = where(keys, row)
        connection.execute(f'DELETE FROM {table} WHERE rowid = (SELECT rowid FROM {table} WHERE {clause} LIMIT 1)',
                           values)
    for row in change['removed']:
        connection.execute(f"INSERT OR IGNORE INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                           tuple(row.values()))
    for item in change['changed']:
        clause, values = where(keys, item['key'])
        current = optional(connection, f'SELECT * FROM {table} WHERE {clause}', values)
        put = put_back(current, item['columns']) if current is not None else {}
        if put:
            connection.execute(f"UPDATE {table} SET {', '.join(f'{column}=?' for column in put)} WHERE {clause}",
                               (*put.values(), *values))


def reverse(connection, changes: dict):
    for table, change in changes.items():
        require(table in timeline.SAVED, 'That change touched something the game no longer keeps.', 409)
        reverse_table(connection, table, change)


def undo(connection, message_id: str, change_id: str, now: str) -> dict:
    """Undo one judged change of a reply on the branch being played."""
    row = optional(connection, 'SELECT * FROM judged_changes WHERE id=? AND message_id=?', (change_id, message_id))
    require(row is not None, 'That change is not in this turn.', 404)
    require(not row['undone_at'], 'That change was already undone.', 409)
    clause, values = timeline.visible(connection)
    require(optional(connection, f'SELECT 1 FROM story_messages WHERE id=? AND {clause}', (message_id, *values))
            is not None, 'That turn is not on the story you are playing now.', 409)
    reverse(connection, decode(row['changes']))
    connection.execute('UPDATE judged_changes SET undone_at=? WHERE id=?', (now, change_id))
    return {'id': change_id, 'kind': row['kind'], 'label': row['label'], 'undone': True}


def clear(connection):
    connection.execute('DELETE FROM judged_changes')
