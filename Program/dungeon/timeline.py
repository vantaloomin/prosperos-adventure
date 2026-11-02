"""Every turn is a save point (docs/story.md "Going back"; requirements "Campaign management").

The story's messages belong to branches. The first branch is ROOT; going back to one of the player's lines starts a
new branch that shares everything before that line, and the game state is put back to how it was when the line was
sent. The branch left behind is kept, with its game state, and can be played again. Nothing is rolled again until
the player sends a line, so going back always brings new dice.

The game state is every table in SAVED, kept as rows. A system that keeps state for the story adds its tables here.
"""
import json

from dungeon.database import RENAMED_TABLES, identifier, many, one, optional
from dungeon.errors import require

SAVED = ('story_scene', 'story_people', 'character_stats', 'record_entries', 'story_summary',
         'story_clock', 'story_quests', 'story_inventory', 'story_purse', 'story_stock', 'story_shops', 'story_markets', 'story_services', 'story_appearance', 'story_trades',
         'story_wounds', 'story_fight', 'story_haggles', 'story_finds', 'story_map', 'story_hexes', 'story_sites', 'story_lots', 'story_places', 'story_position',
         'story_interior', 'story_interior_rooms', 'story_interior_ways',
         'story_injuries', 'story_stress', 'story_cards',
         'story_clocks', 'story_reputation', 'story_fates', 'story_bonds', 'story_party', 'story_beats', 'story_word', 'story_offpage',
         'story_tier', 'story_marks', 'story_dark',
         'story_director', 'story_arcs', 'story_threads', 'story_nemeses', 'story_chapter_break',
         'story_seeds', 'story_arc_beats', 'story_sheet', 'story_enrollment', 'story_attendance', 'story_grades',
         'lore_timers')
ROOT = 'first'
OLD_NAMES = {new: old for old, new in RENAMED_TABLES}


# The game state ----------------------------------------------------------------------------------

def state(connection) -> str:
    return json.dumps({table: many(connection, f'SELECT * FROM {table}') for table in SAVED})


def restore(connection, saved: str, tables: tuple[str, ...] = SAVED):
    rows = json.loads(saved)
    for table in tables:
        connection.execute(f'DELETE FROM {table}')
        # A save from before a table was renamed keeps its rows under the old name.
        for row in rows.get(table, rows.get(OLD_NAMES.get(table, ''), [])):
            columns = ', '.join(row)
            connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({', '.join('?' * len(row))})",
                               tuple(row.values()))


def restore_at(connection, message_id: str, tables: tuple[str, ...]):
    """Some tables put back to how they were as one of the player's lines arrived."""
    row = optional(connection, 'SELECT state FROM story_saves WHERE message_id=?', (message_id,))
    if row:
        restore(connection, row['state'], tables)


def save(connection, message_id: str):
    """The state as the player's line arrives, before its rolls or anything the narrator changes."""
    connection.execute('INSERT OR IGNORE INTO story_saves (message_id, state) VALUES (?, ?)',
                       (message_id, state(connection)))


# Branches ----------------------------------------------------------------------------------------

def active(connection) -> str:
    row = optional(connection, 'SELECT branch_id FROM story_timeline WHERE id=1')
    return row['branch_id'] if row else ROOT


def set_active(connection, branch_id: str):
    connection.execute('INSERT INTO story_timeline (id, branch_id) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET '
                       'branch_id=excluded.branch_id', (branch_id,))


def chain(connection, branch_id: str) -> list[tuple[str, int | None]]:
    """The branch and its ancestors, each with the seq its messages stop before (None: all of them)."""
    result, limit = [], None
    while True:
        result.append((branch_id, limit))
        row = optional(connection, 'SELECT parent_id, fork_seq FROM story_branches WHERE id=?', (branch_id,))
        if row is None or row['parent_id'] is None:
            return result
        branch_id = row['parent_id']
        limit = row['fork_seq'] if limit is None else min(limit, row['fork_seq'])


def visible(connection, branch_id: str | None = None) -> tuple[str, tuple]:
    """A WHERE clause for the messages of a branch (the one being played by default)."""
    parts, values = [], []
    for branch, limit in chain(connection, active(connection) if branch_id is None else branch_id):
        if limit is None:
            parts.append('(branch_id=?)')
            values.append(branch)
        else:
            parts.append('(branch_id=? AND seq<?)')
            values += [branch, limit]
    return '(' + ' OR '.join(parts) + ')', tuple(values)


def leave(connection, now: str, ending: str = ''):
    """Keep the game state of the branch being left, so it can be played on later; `ending` is how it ended, when the
    character died ('death') or was lost ('lost') there."""
    branch = active(connection)
    connection.execute('INSERT INTO story_branches (id, parent_id, fork_seq, tip, created_at, ending) VALUES (?, NULL, '
                       'NULL, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET tip=excluded.tip, ending=excluded.ending',
                       (branch, state(connection), now, ending))


def back(connection, message_id: str, now: str, ending: str = '') -> dict:
    """Go back to before one of the player's lines: a new branch from there, with the state the line found."""
    where, values = visible(connection)
    line = optional(connection, f"SELECT * FROM story_messages WHERE id=? AND role='user' AND {where}",
                    (message_id, *values))
    require(line is not None, 'That line is not in the story you are playing.', 404)
    saved = optional(connection, 'SELECT state FROM story_saves WHERE message_id=?', (message_id,))
    require(saved is not None, 'That line was sent before the story kept save points.', 409)
    leave(connection, now, ending)
    branch = identifier()
    connection.execute('INSERT INTO story_branches (id, parent_id, fork_seq, tip, created_at) VALUES (?, ?, ?, NULL, ?)',
                       (branch, active(connection), line['seq'], now))
    set_active(connection, branch)
    restore(connection, saved['state'])
    return line


def switch(connection, branch_id: str, now: str, ending: str = ''):
    """Play on in another branch, where the player left it."""
    if branch_id == active(connection):
        return
    row = optional(connection, 'SELECT tip FROM story_branches WHERE id=?', (branch_id,))
    require(row is not None and row['tip'] is not None, 'That branch is not in this story.', 404)
    leave(connection, now, ending)
    restore(connection, row['tip'])
    connection.execute('UPDATE story_branches SET tip=NULL WHERE id=?', (branch_id,))
    set_active(connection, branch_id)


def branches(connection) -> list[dict]:
    """Every branch with its last line, the one being played first, then the newest."""
    playing = active(connection)
    rows = many(connection, 'SELECT id, parent_id, fork_seq, created_at FROM story_branches')
    if not any(row['id'] == playing for row in rows):
        rows.append({'id': playing, 'parent_id': None, 'fork_seq': None, 'created_at': ''})
    result = []
    for row in rows:
        where, values = visible(connection, row['id'])
        last = optional(connection, f"SELECT text, created_at FROM story_messages WHERE role='user' AND {where} "
                                    'ORDER BY seq DESC LIMIT 1', values)
        turns = one(connection, f"SELECT COUNT(*) AS n FROM story_messages WHERE role='user' AND {where}", values)['n']
        result.append({'id': row['id'], 'playing': row['id'] == playing, 'turns': turns,
                       'last_line': last['text'] if last else '', 'last_at': last['created_at'] if last else '',
                       'started_at': row['created_at']})
    result.sort(key=lambda item: item['last_at'], reverse=True)
    return sorted(result, key=lambda item: not item['playing'])


def clear(connection):
    connection.execute('DELETE FROM story_branches')
    connection.execute('DELETE FROM story_timeline')
