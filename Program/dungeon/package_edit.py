"""The built-in world editor's store (requirements "World packages": "Worlds are edited in a built-in DB editor";
docs/packages.md "The editor"): a world package's entries read, searched, changed and undone in place.

- **Entries** are the rows of the package's sections (cast, lore, settlements...). Each keeps whether it holds a
  hidden truth (packages.hidden), so the editor can mark it; that is worked out again on every save.
- **Validation on save.** An entry needs a kebab-case id unique in its section, and every field that names an entry
  of another section (packages.REFERENCES: a settlement's region, a person's faction) must name one that exists.
  Renaming an entry's id is refused while other entries still name it.
- **Linked records.** Each entry's view lists what it names and what names it, so the screen can open them.
- **Undo history.** Every change keeps the entry as it was (`history`), newest last; undo puts the last one back,
  and the history lists them.
- **Built-in worlds** are edited in their package in the data folder. An edited one is marked (`meta.edited`) and is
  no longer rebuilt from the shipped files (packages.installed), until it is reset to them.
"""
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from dungeon import packages
from dungeon.errors import require

HISTORY = """
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, section TEXT NOT NULL, entry_id TEXT NOT NULL,
  before TEXT, after TEXT);
"""
MOST_HISTORY = 500
MOST_FOUND = 500


def opened(path: Path) -> sqlite3.Connection:
    connection = packages.connect(path)
    connection.executescript(HISTORY)
    return connection


def section_of(section: str) -> str:
    require(section in packages.SECTIONS, 'That is not a section of a world package.', 404)
    return section


def listing(path: Path, section: str | None = None, query: str = '', hidden: bool | None = None) -> dict:
    """The package's entries, newest order kept: each section's count, and the entries matching a section, words in
    their text, and whether they hold a hidden truth."""
    with closing(opened(path)) as connection:
        counts = {row['section']: {'entries': row['n'], 'hidden': row['h']} for row in connection.execute(
            'SELECT section, COUNT(*) AS n, SUM(hidden) AS h FROM entries GROUP BY section')}
        where, values = ['1=1'], []
        if section:
            where.append('section=?')
            values.append(section_of(section))
        if query.strip():
            where.append('(data LIKE ? OR id LIKE ?)')
            values += [f'%{query.strip()}%'] * 2
        if hidden is not None:
            where.append('hidden=?')
            values.append(int(hidden))
        rows = connection.execute(f"SELECT section, id, name, hidden FROM entries WHERE {' AND '.join(where)} "
                                  'ORDER BY section, position LIMIT ?', (*values, MOST_FOUND)).fetchall()
    return {'sections': [{'id': name, 'name': name} | counts.get(name, {'entries': 0, 'hidden': 0})
                         for name in packages.SECTIONS],
            'entries': [{'section': row['section'], 'id': row['id'], 'name': row['name'] or row['id'],
                         'hidden': bool(row['hidden'])} for row in rows]}


def ids(connection, section: str) -> set[str]:
    return {row['id'] for row in connection.execute('SELECT id FROM entries WHERE section=?', (section,))}


def named(entry: dict, field: str) -> list[str]:
    value = entry.get(field)
    return [item for item in (value if isinstance(value, list) else [value]) if isinstance(item, str) and item]


def links(connection, section: str, entry: dict) -> dict:
    """What an entry names (by the reference fields) and which entries name it."""
    out = [{'section': target, 'id': value, 'field': field} for source, field, target in packages.REFERENCES
           if source == section for value in named(entry, field)]
    into = []
    for source, field, target in packages.REFERENCES:
        if target != section:
            continue
        for row in connection.execute('SELECT id, data FROM entries WHERE section=?', (source,)):
            if entry['id'] in named(json.loads(row['data']), field):
                into.append({'section': source, 'id': row['id'], 'field': field})
    return {'names': out, 'named_by': into}


def entry(path: Path, section: str, entry_id: str) -> dict:
    with closing(opened(path)) as connection:
        row = connection.execute('SELECT data, hidden FROM entries WHERE section=? AND id=?',
                                 (section_of(section), entry_id)).fetchone()
        require(row is not None, 'That entry is not in this world.', 404)
        data = json.loads(row['data'])
        return {'section': section, 'entry': data, 'hidden': bool(row['hidden']),
                'hidden_fields': [field for field in packages.HIDDEN_FIELDS if data.get(field)]} | \
            links(connection, section, data)


def problems(connection, section: str, data: dict, old_id: str | None) -> list[str]:
    """What stops an entry being saved: its id, a reference to nothing, or a rename others still point at."""
    found: list[str] = []
    taken = ids(connection, section) - {old_id}
    packages.section_ids(section, [*({'id': other} for other in taken), data], found)
    for source, field, target in packages.REFERENCES:
        if source == section:
            known = ids(connection, target)
            found += [f'{field} {value} is not in {target}' for value in named(data, field) if value not in known]
    if old_id and data.get('id') != old_id:
        if users := links(connection, section, {'id': old_id})['named_by']:
            found.append(f"{old_id} is still named by {', '.join(user['id'] for user in users[:5])}; change those first")
    return found


def remember(connection, section: str, entry_id: str, before: str | None, after: str | None):
    connection.execute('INSERT INTO history (at, section, entry_id, before, after) VALUES (?, ?, ?, ?, ?)',
                       (datetime.now().isoformat(timespec='seconds'), section, entry_id, before, after))
    connection.execute('DELETE FROM history WHERE id <= (SELECT MAX(id) FROM history) - ?', (MOST_HISTORY,))
    connection.execute("INSERT INTO meta (key, value) VALUES ('edited', 'true') ON CONFLICT(key) DO UPDATE SET "
                       "value='true'")


def place(connection, section: str, data: dict, position: int | None):
    """An entry written into its section (the section's header made when it is the first entry)."""
    meta = json.loads(connection.execute("SELECT value FROM meta WHERE key='sections'").fetchone()['value'])
    if section not in meta:
        meta[section] = {'schema_version': 1}
        connection.execute("UPDATE meta SET value=? WHERE key='sections'", (json.dumps(meta, ensure_ascii=False),))
    if position is None:
        position = connection.execute('SELECT COALESCE(MAX(position) + 1, 0) FROM entries WHERE section=?',
                                      (section,)).fetchone()[0]
    connection.execute('INSERT INTO entries (section, id, position, name, hidden, data) VALUES (?, ?, ?, ?, ?, ?)',
                       (section, data['id'], position, str(data.get('name') or data.get('title') or ''),
                        int(packages.hidden(section, data)), json.dumps(data, ensure_ascii=False)))


def save(path: Path, section: str, data: dict, old_id: str | None = None) -> dict:
    """An entry saved (new, or `old_id` changed), once it validates; its old self kept for undo."""
    section_of(section)
    require(isinstance(data, dict), 'An entry is an object.', 422)
    with closing(opened(path)) as connection, connection:
        before = connection.execute('SELECT data, position FROM entries WHERE section=? AND id=?',
                                    (section, old_id)).fetchone() if old_id else None
        require(old_id is None or before is not None, 'That entry is not in this world.', 404)
        found = problems(connection, section, data, old_id)
        require(not found, 'This entry has problems: ' + '; '.join(found[:6]), 422)
        if before is not None:
            connection.execute('DELETE FROM entries WHERE section=? AND id=?', (section, old_id))
        place(connection, section, data, before['position'] if before is not None else None)
        remember(connection, section, data['id'], before['data'] if before is not None else None,
                 json.dumps(data, ensure_ascii=False))
    return entry(path, section, data['id'])


def delete(path: Path, section: str, entry_id: str):
    with closing(opened(path)) as connection, connection:
        before = connection.execute('SELECT data FROM entries WHERE section=? AND id=?',
                                    (section_of(section), entry_id)).fetchone()
        require(before is not None, 'That entry is not in this world.', 404)
        users = links(connection, section, {'id': entry_id})['named_by']
        require(not users, f"{entry_id} is still named by {', '.join(user['id'] for user in users[:5])}; change "
                'those first.', 409)
        connection.execute('DELETE FROM entries WHERE section=? AND id=?', (section, entry_id))
        remember(connection, section, entry_id, before['data'], None)


def history(path: Path) -> list[dict]:
    with closing(opened(path)) as connection:
        rows = connection.execute('SELECT id, at, section, entry_id, before, after FROM history ORDER BY id DESC '
                                  'LIMIT 50').fetchall()
    return [{'id': row['id'], 'at': row['at'], 'section': row['section'], 'entry_id': row['entry_id'],
             'change': 'added' if row['before'] is None else 'deleted' if row['after'] is None else 'changed'}
            for row in rows]


def undo(path: Path) -> dict | None:
    """The last change taken back: the entry as it was before it (gone again when it was new)."""
    with closing(opened(path)) as connection, connection:
        row = connection.execute('SELECT * FROM history ORDER BY id DESC LIMIT 1').fetchone()
        require(row is not None, 'There is nothing to undo.', 409)
        after = json.loads(row['after']) if row['after'] else None
        position = None
        if after is not None:
            kept = connection.execute('SELECT position FROM entries WHERE section=? AND id=?',
                                      (row['section'], after['id'])).fetchone()
            position = kept['position'] if kept else None
            connection.execute('DELETE FROM entries WHERE section=? AND id=?', (row['section'], after['id']))
        if row['before'] is not None:
            place(connection, row['section'], json.loads(row['before']), position)
        connection.execute('DELETE FROM history WHERE id=?', (row['id'],))
        return {'section': row['section'], 'entry_id': json.loads(row['before'])['id'] if row['before'] else None}


def edited(path: Path) -> bool:
    with closing(packages.connect(path)) as connection:
        row = connection.execute("SELECT value FROM meta WHERE key='edited'").fetchone()
    return bool(row and json.loads(row['value']))
