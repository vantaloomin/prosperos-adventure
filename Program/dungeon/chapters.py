"""Chapters, bookmarks, Ironman and the player's notebook (requirements "Memory and context" round 2 and "Campaign
management"; docs/story.md "Chapters and the branch tree").

- **Chapters close at scene breaks.** A change of place, a journey or a rest, the end of a fight or of a quest, or
  the player closing one themselves (with a name, if they like) leaves a break pending; the player's next line opens
  the next chapter. The chapter that ends is summarized as the break is made by the Continuity model, when one is
  chosen, which also names it unless the player did and says what it leaves open; the next chapter opens with a
  short "previously" from that, once the story has run a while since the last one (RECAP_TURNS of the player's
  lines) or the player closed the chapter themselves. A line that goes somewhere opens the new chapter itself.
- **Chapters follow the branches.** A chapter starts at one of the player's lines and its end is recorded on the
  branch where it ended, so both are seen through dungeon/timeline.py `visible` like the messages: a branch shares
  its parent's chapters up to where it forked, and an end on another branch is not this branch's.
- **The tree** maps every branch and its own chapters; a branch left with the character dead or lost is marked by how
  it ended.
- **Bookmarks** name moments to find them fast; going to one plays on in its branch.
- **Ironman**, chosen at campaign start, turns off going back: no going back to a line, no other branches, no
  telling a line again with new dice, so death is final.
- **The notebook** is the player's own, spans every branch, and no model ever reads it.
"""
from dungeon import record, timeline
from dungeon.database import identifier, many, optional
from dungeon.errors import require
from dungeon.text_models import config_for, routes

REASONS = ('place', 'time', 'fight', 'quest', 'player')
BREAK_SAVED = 'story_chapter_break'
SUMMARIZE = """You keep the chapters of a tabletop roleplaying game's story. Read one chapter and give it a short \
title (two to six words, no quotation marks), a summary of what happened in it, in order, in past tense, in at most \
120 words, and the hook it leaves: the question still open at its end, in one sentence. Answer with JSON only: \
{"title": "...", "summary": "...", "hook": "..."}"""
SHAPE = record.strict({'title': {'type': 'string'}, 'summary': {'type': 'string'}, 'hook': {'type': 'string'}})
PREVIOUSLY = ('## Previously (a new chapter opens with this line: begin with a short "Previously" of two or three '
              'sentences drawn from this, then go on with the scene)')
IRONMAN = 'This is an Ironman campaign: there is no going back.'
# The player's lines since the last "previously" (or the story's start) before another is worth it.
RECAP_TURNS = 6


# Breaks and chapters -----------------------------------------------------------------------------

def pending(connection) -> dict | None:
    return optional(connection, 'SELECT reason, title FROM story_chapter_break WHERE id=1')


def held(connection) -> dict | None:
    """The break waiting, with the summary of the chapter it ends when that is ready."""
    return optional(connection, 'SELECT * FROM story_chapter_break WHERE id=1')


def mark(connection, reason: str, title: str = ''):
    """A scene break: the player's next line opens a new chapter. A name the player gave is kept over a later break."""
    require(reason in REASONS, f'{reason} is not a scene break.', 422)
    held = pending(connection)
    if held and held['title'] and not title:
        return
    connection.execute('INSERT INTO story_chapter_break (id, reason, title) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE '
                       'SET reason=excluded.reason, title=excluded.title', (reason, title.strip()[:80]))


def visible(connection, table: str, branch_id: str | None = None) -> list[dict]:
    where, values = timeline.visible(connection, branch_id)
    return many(connection, f'SELECT * FROM {table} WHERE {where} ORDER BY seq', values)


def ends(connection, branch_id: str | None = None) -> dict[str, dict]:
    return {row['chapter_id']: row for row in visible(connection, 'story_chapter_ends', branch_id)}


def arrive(connection, line: dict, now: str):
    """The player's line opens a chapter when it is the story's first or a break is pending."""
    opened = visible(connection, 'story_chapters')
    waiting = held(connection)
    if opened and waiting is None:
        return
    if opened:
        connection.execute('INSERT INTO story_chapter_ends (chapter_id, branch_id, seq, reason, title, summary, hook, '
                           'created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                           (opened[-1]['id'], line['branch_id'], line['seq'], waiting['reason'],
                            waiting['title'] or waiting['named'], waiting['summary'], waiting['hook'], now))
    connection.execute('INSERT INTO story_chapters (id, branch_id, seq, created_at) VALUES (?, ?, ?, ?)',
                       (identifier(), line['branch_id'], line['seq'], now))
    connection.execute('DELETE FROM story_chapter_break')


def lines_of(connection, start: int, end: int | None, branch_id: str | None = None) -> list[dict]:
    where, values = timeline.visible(connection, branch_id)
    upper = 'AND seq < ?' if end is not None else ''
    return many(connection, f"SELECT * FROM story_messages WHERE {where} AND seq >= ? {upper} AND "
                            "(role != 'narrator' OR status='complete') ORDER BY seq",
                (*values, start, *((end,) if end is not None else ())))


def read(connection, chapter_id: str, branch_id: str | None = None) -> list[dict]:
    """A chapter's lines as one branch tells it."""
    chapter = next((row for row in visible(connection, 'story_chapters', branch_id) if row['id'] == chapter_id), None)
    require(chapter is not None, 'That chapter is not in that branch.', 404)
    end = ends(connection, branch_id).get(chapter_id)
    return [{'id': line['id'], 'role': line['role'], 'text': line['text']}
            for line in lines_of(connection, chapter['seq'], end and end['seq'], branch_id)]


def listing(connection, branch_id: str | None = None) -> list[dict]:
    """The chapters of a branch (the one being played by default), like a table of contents."""
    closed = ends(connection, branch_id)
    result = []
    for number, row in enumerate(visible(connection, 'story_chapters', branch_id), 1):
        end = closed.get(row['id'])
        turns = sum(line['role'] == 'user' for line in lines_of(connection, row['seq'], end and end['seq'], branch_id))
        result.append({'id': row['id'], 'number': number, 'title': (end and end['title']) or f'Chapter {number}',
                       'summary': end['summary'] if end else '', 'hook': end['hook'] if end else '',
                       'open': end is None, 'turns': turns,
                       'ended_by': end['reason'] if end else None, 'branch_id': row['branch_id'], 'seq': row['seq']})
    return result


async def summed(state, config: dict, lines: list[dict]) -> dict:
    """A chapter's title, summary and the hook it leaves, from its lines."""
    answer = await record.schema_first(state, config, SUMMARIZE, record.transcript(lines), SHAPE,
                                       lambda answer: isinstance(record.read_json(answer), dict))
    data = record.read_json(answer) or {}
    return {'summary': str(data.get('summary') or '').strip()[:1200] or answer.strip()[:1200],
            'title': str(data.get('title') or '').strip().strip('"')[:80], 'hook': str(data.get('hook') or '').strip()[:300]}


async def summarize(state):
    """The chapter a pending break ends, summarized as the break is made, so the next chapter can open with
    "previously"; and any chapter that ended without a summary (no model then, or a failure), summarized now."""
    database = state.database
    with database.connect() as connection:
        config = config_for(connection, record.JOB) if routes(connection).get(record.JOB) else None
        waiting, opened = held(connection), visible(connection, 'story_chapters')
        late = [(chapter, end) for chapter in opened if (end := ends(connection).get(chapter['id'])) and not end['summary']]
        current = opened and waiting and not waiting['summary'] and lines_of(connection, opened[-1]['seq'], None)
    if config is None:
        return
    try:
        if current:
            done = await summed(state, config, current)
            with database.connect(write=True) as connection:
                connection.execute('UPDATE story_chapter_break SET summary=?, named=?, hook=? WHERE id=1',
                                   (done['summary'], done['title'], done['hook']))
        for chapter, end in late:
            with database.connect() as connection:
                lines = lines_of(connection, chapter['seq'], end['seq'])
            done = await summed(state, config, lines)
            with database.connect(write=True) as connection:
                connection.execute('UPDATE story_chapter_ends SET summary=?, title=?, hook=? WHERE chapter_id=? AND '
                                   'branch_id=?', (done['summary'], end['title'] or done['title'], done['hook'],
                                                   end['chapter_id'], end['branch_id']))
    except Exception:  # noqa: BLE001 - the chapter stays unsummarized until the next try.
        return


def opening(connection, line: dict) -> str:
    """When the line opens a chapter after another: the "previously" it begins with, from the chapter that ended, the
    hook it left and the hottest threads the character knows of."""
    chapters = listing(connection)
    if len(chapters) < 2 or chapters[-1]['seq'] != line['seq'] or not chapters[-2]['summary']:
        return ''
    ended = chapters[-2]
    if not recap_due(chapters[:-1]):
        return ''
    from dungeon import director  # the director reads the record; chapters need it only here.
    threads = [row['seen'] for row in director.threads(connection) if row['known'] and row['seen']][:2]
    parts = [ended['summary'], ended['hook'] and f"Still open: {ended['hook']}",
             threads and 'On the character\'s mind: ' + ' '.join(threads)]
    return PREVIOUSLY + '\n' + '\n'.join(part for part in parts if part)


def recap_due(closed: list[dict]) -> bool:
    """Whether the chapter that just closed (the last of `closed`) earns a "previously": the player closed it, or
    RECAP_TURNS of the player's lines have passed since the last chapter opening that had one."""
    since, due = 0, False
    for chapter in closed:
        since += chapter['turns']
        due = since >= RECAP_TURNS or chapter['ended_by'] == 'player'
        since = 0 if due else since
    return due


def opens(connection, line: dict) -> bool:
    """Whether the line opened a chapter."""
    return any(row['seq'] == line['seq'] and row['branch_id'] == line['branch_id']
               for row in visible(connection, 'story_chapters'))


# The tree ----------------------------------------------------------------------------------------

def tree(connection) -> list[dict]:
    """Every branch, where it forked from its parent, how it ended if the character died or was lost there, and the
    chapters it began itself."""
    playing = timeline.active(connection)
    rows = many(connection, 'SELECT id, parent_id, fork_seq, ending FROM story_branches')
    if not any(row['id'] == playing for row in rows):
        rows.append({'id': playing, 'parent_id': None, 'fork_seq': None, 'ending': ''})
    result = []
    for row in rows:
        own = [chapter for chapter in listing(connection, row['id']) if chapter['branch_id'] == row['id']]
        result.append({'id': row['id'], 'parent_id': row['parent_id'], 'fork_seq': row['fork_seq'],
                       'playing': row['id'] == playing, 'ending': row['ending'] or '', 'chapters': own})
    return result


# Ironman -----------------------------------------------------------------------------------------

def ironman(connection) -> bool:
    row = optional(connection, 'SELECT ironman FROM story_campaign WHERE id=1')
    return bool(row and row['ironman'])


def set_ironman(connection, on: bool):
    connection.execute('INSERT INTO story_campaign (id, ironman) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET '
                       'ironman=excluded.ironman', (int(on),))


def no_going_back(connection):
    require(not ironman(connection), IRONMAN, 409)


# Bookmarks ---------------------------------------------------------------------------------------

def bookmarks(connection) -> list[dict]:
    return many(connection, 'SELECT story_bookmarks.id, story_bookmarks.name, story_bookmarks.message_id, '
                            'story_messages.branch_id, story_messages.text, story_bookmarks.created_at FROM '
                            'story_bookmarks JOIN story_messages ON story_messages.id = story_bookmarks.message_id '
                            'ORDER BY story_bookmarks.created_at DESC, story_bookmarks.rowid DESC')


def bookmark(connection, message_id: str, name: str, now: str) -> None:
    where, values = timeline.visible(connection)
    require(optional(connection, f'SELECT 1 FROM story_messages WHERE id=? AND {where}', (message_id, *values))
            is not None, 'That line is not in the story you are playing.', 404)
    require(bool(name.strip()), 'Name the bookmark.', 422)
    connection.execute('INSERT INTO story_bookmarks (id, message_id, name, created_at) VALUES (?, ?, ?, ?)',
                       (identifier(), message_id, name.strip()[:80], now))


def unbookmark(connection, bookmark_id: str):
    require(connection.execute('DELETE FROM story_bookmarks WHERE id=?', (bookmark_id,)).rowcount == 1,
            'That bookmark is not there.', 404)


def marked_branch(connection, bookmark_id: str) -> dict:
    row = optional(connection, 'SELECT story_messages.branch_id, story_messages.id AS message_id FROM story_bookmarks '
                               'JOIN story_messages ON story_messages.id = story_bookmarks.message_id WHERE '
                               'story_bookmarks.id=?', (bookmark_id,))
    require(row is not None, 'That bookmark is not there.', 404)
    return row


# The notebook ------------------------------------------------------------------------------------

def notebook(connection) -> list[dict]:
    return many(connection, 'SELECT id, text, created_at, updated_at FROM story_notebook ORDER BY created_at, rowid')


def write_note(connection, text: str, now: str, note_id: str | None = None):
    require(bool(text.strip()), 'Write the note, or remove it.', 422)
    if note_id is None:
        connection.execute('INSERT INTO story_notebook (id, text, created_at, updated_at) VALUES (?, ?, ?, ?)',
                           (identifier(), text.strip()[:4000], now, now))
        return
    require(connection.execute('UPDATE story_notebook SET text=?, updated_at=? WHERE id=?',
                               (text.strip()[:4000], now, note_id)).rowcount == 1, 'That note is not there.', 404)


def remove_note(connection, note_id: str):
    require(connection.execute('DELETE FROM story_notebook WHERE id=?', (note_id,)).rowcount == 1,
            'That note is not there.', 404)


def view(connection) -> dict:
    return {'chapters': listing(connection), 'tree': tree(connection), 'bookmarks': bookmarks(connection),
            'ironman': ironman(connection), 'pending': pending(connection)}


def clear(connection):
    for table in ('story_chapters', 'story_chapter_ends', 'story_chapter_break', 'story_bookmarks', 'story_notebook',
                  'story_campaign'):
        connection.execute(f'DELETE FROM {table}')
