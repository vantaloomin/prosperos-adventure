"""Built-in cities the app no longer ships (dungeon/world/data/retired). A world already set in one keeps it: it
becomes one of that world's own cities, under Custom, so the story still opens and the user can delete it when done.
New worlds never see it."""
import json

from dungeon.database import encode
from dungeon.world import catalog, custom

FOLDER = catalog.DATA / 'retired'


def keep(connection, timestamp: str):
    """Copies each retired city a table of this world still names into its own cities, once."""
    tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    columns = [(table, column) for table in tables for column in
               (row[1] for row in connection.execute(f'PRAGMA table_info({table})')) if column.endswith('city_id')]
    for path in sorted(FOLDER.glob('*.json')):
        city_id = path.stem
        if city_id in catalog.cities() or connection.execute('SELECT 1 FROM world_cities WHERE id=?',
                                                             (city_id,)).fetchone():
            continue
        if any(connection.execute(f'SELECT 1 FROM {table} WHERE {column}=? LIMIT 1', (city_id,)).fetchone()
               for table, column in columns):
            data = custom.check(json.loads(path.read_text(encoding='utf-8')))
            connection.execute('INSERT INTO world_cities (id, definition, created_at, updated_at) VALUES (?, ?, ?, ?)',
                               (city_id, encode(custom._definition(data)), timestamp, timestamp))
