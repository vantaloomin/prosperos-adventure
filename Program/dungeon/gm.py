"""The GM view (requirements "Memory and context": "a settings toggle opens a full GM view that shows and edits
everything, secrets included"; docs/story.md "The GM view").

With the GM view on (the Table's `gm_view`, dungeon/table.py), the player sees what the game keeps behind the story: every quest with
its hidden truth, how everyone met feels and why, the director's arcs at their stages with their truths, its threads
and nemeses, the factions' standing, the dark tracks' points, and the log of every correction made to the record.
They can set a person's feelings and a faction's standing by hand, and plan with the director (dungeon/plotting.py):
the Chekhov list of seeds, to cash one in or retire it, and each arc's planned beats, to cut and reorder. The record itself is edited from the journal
(dungeon/record.py), which shows hidden truth too while the GM view is on.
"""
from dungeon import director, feelings, growth, plotting, quests, record
from dungeon.database import decode, many, optional
from dungeon.errors import require

FACTION_RANGE = (-5, 5)


def corrections(connection, limit: int = 30) -> list[dict]:
    return many(connection, 'SELECT record_corrections.before, record_corrections.after, record_corrections.created_at, '
                            'record_entries.subject FROM record_corrections LEFT JOIN record_entries ON '
                            'record_entries.id = record_corrections.entry_id ORDER BY record_corrections.created_at '
                            'DESC, record_corrections.rowid DESC LIMIT ?', (limit,))


def arcs(connection, world: str | None) -> list[dict]:
    result = []
    for arc_id, row in director.arcs(connection).items():
        found = world and director.arc(world, arc_id)
        stage = director.stage_of(world, row) if found else None
        result.append({'id': arc_id, 'title': found['name'] if found else arc_id, 'stage': row['stage'],
                       'stages': len(found['stages']) if found else 0, 'bite': row['bite'],
                       'truth': stage['truth'] if stage else '',
                       'antagonist': found.get('antagonist', {}).get('name', '') if found else ''})
    return result


def view(connection, world: str | None) -> dict:
    require(record.gm_view(connection), 'Turn on the GM view in the journal to see behind the story.', 409)
    return {
        'quests': [{'id': quest['id'], 'title': quest['title'], 'status': quest['status'], 'known': bool(quest['known']),
                    'truth': quest.get('truth') or '', 'kind': quest['kind']} for quest in quests.rows(connection)],
        'people': [{'key': row['key'], 'name': row['name'], 'feelings': feelings.of(row),
                    'impressions': decode(row['impressions'] or '[]')} for row in feelings.met(connection)],
        'arcs': arcs(connection, world),
        'threads': [{'id': row['id'], 'kind': row['kind'], 'title': row['title'], 'truth': row['truth'],
                     'known': bool(row['known']), 'heat': round(row['heat'], 1)} for row in director.threads(connection)],
        'nemeses': many(connection, 'SELECT name, grudge, remembers, status FROM story_nemeses ORDER BY since'),
        'factions': many(connection, 'SELECT faction_id, value FROM story_reputation ORDER BY faction_id'),
        'dark': growth.view(connection, True)['dark'],
        'corrections': corrections(connection),
    } | plotting.view(connection)


def set_feelings(connection, key: str, values: dict[str, int]):
    require(record.gm_view(connection), 'Turn on the GM view to change how someone feels.', 409)
    require(optional(connection, 'SELECT 1 FROM story_people WHERE key=?', (key,)) is not None,
            'That person has not been met.', 404)
    for axis, value in values.items():
        require(axis in feelings.AXES, f'{axis} is not a feeling.', 422)
        low, high = feelings.LOW[axis], feelings.HIGH
        connection.execute(f'UPDATE story_people SET {axis}=? WHERE key=?', (max(low, min(high, value)), key))


def set_standing(connection, faction_id: str, value: int):
    require(record.gm_view(connection), 'Turn on the GM view to change a faction\'s standing.', 409)
    low, high = FACTION_RANGE
    connection.execute('INSERT INTO story_reputation (faction_id, value) VALUES (?, ?) ON CONFLICT(faction_id) DO '
                       'UPDATE SET value=excluded.value', (faction_id, max(low, min(high, value))))
