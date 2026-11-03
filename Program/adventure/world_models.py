"""Which text model profile does each job in this world (Vanta, 2026-10-28: as with image backends, a world may have
models of its own).

Profiles and the usual job assignments belong to the user and follow them from world to world (adventure/worlds.py).
A world uses those until the user gives it its own in Settings > Models; it then starts from a copy of them, and
choosing a profile for a job there (or switching models in chat) changes this world's alone. A profile removed since
is passed over: its job uses the conversation's, and a conversation with none left uses the usual one. The Mix in
chat belongs to the usual setup, so a world with models of its own answers with its own Conversation profile.
"""
from adventure.database import decode, encode, many, optional


def own(connection) -> dict | None:
    """This world's job assignments, or None when it uses the usual ones."""
    row = optional(connection, 'SELECT routes FROM world_model_routes WHERE id=1')
    return decode(row['routes']) if row else None


def usual(connection) -> dict[str, str]:
    return {row['job']: row['profile_id'] for row in many(connection, 'SELECT job, profile_id FROM model_routes')}


def routes(connection) -> dict[str, str]:
    """The assignments that apply here, with every profile in them still there."""
    shared = usual(connection)
    picked = own(connection)
    if picked is None:
        return shared
    known = {row['id'] for row in many(connection, 'SELECT id FROM model_profiles')}
    kept = {job: profile_id for job, profile_id in picked.items() if profile_id in known}
    if 'chat' not in kept and 'chat' in shared:
        kept['chat'] = shared['chat']
    return kept


def choose(connection, separate: bool, timestamp: str):
    """Give this world assignments of its own, starting from the usual ones, or go back to those."""
    if not separate:
        connection.execute('DELETE FROM world_model_routes')
    elif own(connection) is None:
        connection.execute('INSERT INTO world_model_routes (id, routes, updated_at) VALUES (1, ?, ?)',
                           (encode(usual(connection)), timestamp))


def assign(connection, job: str, profile_id: str | None, timestamp: str) -> bool:
    """Set a job here when this world has its own assignments; False when it uses the usual ones."""
    picked = own(connection)
    if picked is None:
        return False
    if profile_id is None:
        picked.pop(job, None)
    else:
        picked[job] = profile_id
    connection.execute('UPDATE world_model_routes SET routes=?, updated_at=? WHERE id=1', (encode(picked), timestamp))
    return True
