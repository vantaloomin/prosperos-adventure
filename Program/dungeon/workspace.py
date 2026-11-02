"""Workspace settings."""
import json

from dungeon import local_zone, table
from dungeon.clock import zone
from dungeon.database import settings

FLAGS = ('auto_launch', 'show_odds', 'adult_side', 'show_adult_side', 'record_model_calls', 'cutaways',
         'roll_dice', 'gm_view', 'contradiction_check', 'passive_art')


def view(row: dict) -> dict:
    return {**row, **{flag: bool(row[flag]) for flag in FLAGS},
            'ai_notice_confirmed': row['ai_notice_at'] is not None,
            'custom_palette': json.loads(row['custom_palette']) if row['custom_palette'] else None,
            'system_timezone': local_zone.detect()}


def follows_pc(row: dict) -> bool:
    """A zone the user picked is never replaced; the untouched UTC default and a PC-set zone are."""
    return row['user_timezone_source'] == 'pc' or (row['user_timezone_source'] == 'default'
                                                    and row['user_timezone'] == 'UTC')


def timezone_change(row: dict, changes: dict):
    """Turns the requested zone and its source into columns. 'detected' is the interface reporting the PC's
    zone on its own, so it only applies while the workspace follows the PC; 'pc' is the user asking for it."""
    source = changes.pop('user_timezone_source', None)
    if 'user_timezone' not in changes:
        return
    zone(changes['user_timezone'])
    if source == 'detected' and not follows_pc(row):
        del changes['user_timezone']
        return
    changes['user_timezone_source'] = 'chosen' if source in (None, 'chosen') else 'pc'


def adopt_pc_timezone(database, detected: str | None):
    """At startup, a workspace still on the UTC default (or following the PC) takes this PC's zone."""
    if not detected:
        return
    with database.connect(write=True) as connection:
        row = settings(connection)
        if follows_pc(row) and (row['user_timezone'], row['user_timezone_source']) != (detected, 'pc'):
            connection.execute("UPDATE workspace_settings SET user_timezone=?, user_timezone_source='pc', "
                               'updated_at=? WHERE id=1', (detected, database.now()))


def read(database) -> dict:
    with database.connect() as connection:
        return view(settings(connection))


def update(database, body) -> dict:
    changes = body.model_dump(exclude_none=True)
    with database.connect(write=True) as connection:
        row = settings(connection)
        timezone_change(row, changes)
        if 'custom_palette' in changes:
            changes['custom_palette'] = json.dumps(changes['custom_palette'], sort_keys=True)
        # The first-run notice is confirmed once and stays confirmed.
        if changes.pop('ai_notice_confirmed', False) and row['ai_notice_at'] is None:
            changes['ai_notice_at'] = database.now()
        changed = {key: value for key, value in changes.items() if row[key] != value}
        assignments = {**{key: int(value) if isinstance(value, bool) else value for key, value in changed.items()},
                       'updated_at': database.now()}
        columns = ', '.join(f'{key}=?' for key in assignments)
        connection.execute(f'UPDATE workspace_settings SET {columns} WHERE id=1', tuple(assignments.values()))
        # A campaign rule set here is also the playing campaign's (dungeon/table.py).
        table.change(connection, changes)
        return view(settings(connection))
