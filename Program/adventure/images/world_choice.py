"""Which image backends a world draws with (Vanta, 2026-10-28: anime pictures in Runeterra, photographs on Earth).

Backends belong to the user and follow them from world to world (adventure/worlds.py); which of them a world uses
is the world's own, kept in its database. A world uses every enabled backend in the user's order until the user
picks some for it in Settings > Images; then only those, still in that order. A backend added while in such a world
joins its picks. If none of its picks is enabled any more, the world uses the usual order again, so pictures still
come rather than stopping without a word.
"""
from adventure.database import decode, encode, optional
from adventure.errors import require


def picked(connection) -> list[str] | None:
    """This world's picks, or None when it uses every backend."""
    row = optional(connection, 'SELECT backend_ids FROM world_image_backends WHERE id=1')
    return decode(row['backend_ids']) if row else None


def narrowed(connection, enabled: list[dict]) -> list[dict]:
    ids = picked(connection)
    if ids is None:
        return enabled
    return [backend for backend in enabled if backend['id'] in ids] or enabled


def view(connection, rows: list[dict]) -> dict:
    ids = picked(connection)
    enabled = [row for row in rows if row['enabled']]
    used = {backend['id'] for backend in narrowed(connection, enabled)}
    return {'own': ids is not None, 'picked': [row['id'] for row in rows if ids is not None and row['id'] in ids],
            'falls_back': ids is not None and bool(enabled) and not any(row['id'] in ids for row in enabled),
            'used': [row['id'] for row in rows if row['id'] in used]}


def choose(connection, backend_ids: list[str] | None, timestamp: str):
    """None goes back to every backend; a list is this world's picks."""
    if backend_ids is None:
        connection.execute('DELETE FROM world_image_backends')
        return
    known = {row['id'] for row in connection.execute('SELECT id FROM image_backends')}
    kept = [backend_id for backend_id in dict.fromkeys(backend_ids) if backend_id in known]
    require(kept, 'Pick at least one backend for this world, or let it use all of them.', 422)
    connection.execute('INSERT INTO world_image_backends (id, backend_ids, updated_at) VALUES (1, ?, ?) '
                       'ON CONFLICT(id) DO UPDATE SET backend_ids=excluded.backend_ids, updated_at=excluded.updated_at',
                       (encode(kept), timestamp))


def joined(connection, backend_id: str, timestamp: str):
    """A backend added in a world with its own picks is one the user wants here."""
    ids = picked(connection)
    if ids is not None:
        choose(connection, [*ids, backend_id], timestamp)
