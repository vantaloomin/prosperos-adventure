"""The GM view (requirements "Memory and context": "a settings toggle opens a full GM view that shows and edits
everything, secrets included"; docs/story.md "The GM view").

With the GM view on (the Table's `gm_view`, adventure/table.py), the player sees what the game keeps behind the story: every quest with
its hidden truth, how everyone met feels and why, the director's arcs at their stages with their truths, its threads
and nemeses, the factions' standing, the dark tracks' points, and the log of every correction made to the record.
They can set a person's feelings and a faction's standing by hand, and plan with the director (adventure/plotting.py):
the Chekhov list of seeds, to cash one in or retire it, and each arc's planned beats, to cut and reorder. The record itself is edited from the journal
(adventure/record.py), which shows hidden truth too while the GM view is on.

**In round play** (docs/spec.md "Waiting and pauses": "The GM view asks first in Play"), `open_round` shows the turn
being played, or the last one committed on this branch, with everything in it (adventure/rounds/context.py: the GM
view gets everything): every character's declaration, motive and whispers, what each learned and remembers, how each
feels toward the others, the turn result and every package fact with its tag. In Play it asks first, unless the
user said to remember their answer for this campaign (`gm_view_consent`), and each turn it was open on is marked
(`gm_view` on round_turns, adventure/rounds/turns.py `mark`): the turn it opened on, and every turn played while
the GM view toggle stays on (`mark_if_open`, run at Gather). `marked` lists them, so the user knows which surprises
they spoiled. Author and Watch have no gate and mark nothing.
"""
from adventure import director, feelings, growth, plotting, quests, record, timeline, world_data
from adventure.database import decode, many, optional
from adventure.errors import DomainError, require
from adventure.rounds import context, memory, modes, seats, shown, turns
from adventure.rounds.contract import Mode, Point, Snapshot, plain
from adventure.rounds.draft import Draft

FACTION_RANGE = (-5, 5)
ASKS_FIRST = 'This shows every secret and motive. Open anyway?'
MARK = 'gm_view'
# A place past every turn on a branch, for reading all of it.
END = 2 ** 62


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


# The GM view in round play ------------------------------------------------------------------------------------------

def remembered(connection) -> bool:
    row = optional(connection, 'SELECT remembered FROM gm_view_consent WHERE id=1')
    return bool(row and row['remembered'])


def forget_consent(connection):
    """A new story asks again."""
    connection.execute('DELETE FROM gm_view_consent')


def watched_turn(connection) -> dict | None:
    """The turn the GM view shows: the one being played, else the last committed on this branch."""
    found = turns.committed(connection, Point(timeline.active(connection), END), 1)
    return turns.under_way(connection) or (found[0] if found else None)


def open_round(connection, now: str, confirmed: bool = False, remember: bool = False) -> dict:
    """The GM view of the turn: in Play only once the user has said yes (now or, remembered, before), and the turn
    is marked as one they saw behind."""
    play = seats.settings(connection)['mode'] == Mode.PLAY
    if play and not remembered(connection):
        if not confirmed:
            raise DomainError(ASKS_FIRST, 409, 'gm_view_asks_first')
        if remember:
            connection.execute('INSERT INTO gm_view_consent (id, remembered, created_at) VALUES (1, 1, ?) '
                               'ON CONFLICT(id) DO UPDATE SET remembered=1', (now,))
    turn = watched_turn(connection)
    if play and turn is not None:
        turns.mark(connection, turn['id'], MARK)
    return round_view(connection, turn)


def mark_if_open(connection, turn: dict, mode: str):
    """At Gather: a turn played in Play while the GM view toggle is on is marked too."""
    if mode == Mode.PLAY and record.gm_view(connection):
        turns.mark(connection, turn['id'], MARK)


def marked(connection) -> list[str]:
    """The turns on this branch the GM view was open on, oldest first."""
    clause, values = memory.where(connection, Point(timeline.active(connection), END))
    rows = many(connection, f'SELECT id, marks FROM round_turns WHERE {clause} ORDER BY seq, created_at', values)
    return [row['id'] for row in rows if MARK in (decode(row['marks']) or [])]


def minds_panel(connection) -> dict:
    """The minds panel, not the GM view: who is deciding on the watched turn, and in Author and Watch (or for the
    user's own character) what each means and why; in Play the others show only whether they have decided. A turn
    played in Play stays that way unless a later switch out of Play was answered Show (adventure/rounds/modes.py
    `revealed`)."""
    turn = watched_turn(connection)
    if turn is None:
        return {'turn': None, 'mode': seats.settings(connection)['mode'], 'minds': [], 'revealed': False}
    snapshot, revealed = Snapshot.of(decode(turn['snapshot'])), modes.revealed(connection, turn)
    return {'turn': turn['id'], 'mode': turn['mode'], 'revealed': revealed,
            'minds': context.minds(snapshot, Draft.of(decode(turn['draft'])), reveal=revealed)}


def round_view(connection, turn: dict | None) -> dict:
    """Everything about one turn, for the GM view (adventure/rounds/context.py `gm` is the same as model text)."""
    if turn is None:
        return {'turn': None, 'marked': marked(connection)}
    snapshot, draft = Snapshot.of(decode(turn['snapshot'])), Draft.of(decode(turn['draft']))
    world = snapshot.settings.get('world')
    # A committed turn is shown with what it left behind: memory and feelings as of just after it.
    after = Point(snapshot.point.branch, snapshot.point.seq + 1) if turn['state'] == 'committed' else snapshot.point
    return {'turn': {'id': turn['id'], 'state': turn['state'], 'mode': turn['mode'], 'marks': turns.marks(
                connection, turn['id'])},
            'minds': context.minds(snapshot, draft, reveal=True),
            'knowledge': [plain(item) for item in draft.knowledge], 'exchanges': draft.exchanges,
            'result': plain(draft.result) if draft.result else None,
            'feelings': {seat.key: memory.feelings(connection, seat.key, after) for seat in snapshot.seats},
            'memories': {seat.key: [{key: row[key] for key in ('kind', 'text', 'about', 'source', 'importance', 'faded')}
                                    for row in memory.recall(connection, seat.key, after)]
                         for seat in snapshot.seats},
            'shown': {seat.key: shown.sheet(connection, seat.key, snapshot.point.branch) for seat in snapshot.seats},
            # Sheet updates waiting for the user's review: only here, never in a character's own context.
            'drafted': [update for update in shown.visible(connection, 'drafted', snapshot.point.branch)
                        if update['seat'] in {seat.key for seat in snapshot.seats}],
            'facts': world_data.facts(world) if world else [], 'marked': marked(connection)}
