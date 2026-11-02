"""The Author's hand (docs/spec.md Batch 3: "The Author gives nudges and edits story beats"; "Waiting and pauses":
"Author nudges get feedback"; "The turn brief and the stop point": "Beats beyond the user's own character in Play").

Characters still choose for themselves: a nudge is a hidden note to the director and the Writer, never an order to
anyone, and no agent ever reads one (adventure/rounds/context.py gives it to the Writer in Author only).

- **Nudges.** In Author the nudge comes with Next and is in the snapshot from the start (`settings['nudge']`,
  adventure/rounds/engine.py `opening`). In Play the user can write beats they would like to see beside their line
  (a storm, a stranger arriving) in the nudge box (`nudge_box`); the next Play turn takes them at Gather
  (`taken`) as the user-set beats Resolve puts in the brief (`settings['beats']`, adventure/rounds/resolve.py),
  and they leave the box when that turn is committed, so a cancelled turn leaves them waiting.
- **The beat board** is the director's plan (adventure/plotting.py, `story_arc_beats`): each arc's beats for its
  stage. The Author adds beats, cuts them and reorders them, with no GM view gate. A nudge that names a planned beat
  moves that beat to the front of its arc's plan when the turn is committed. A beat given to the director's note
  that reaches the page is marked landed.
- **Feedback.** At Commit code checks whether each nudge took, in this order: a character set out to do it or said
  it (its words in their declared intent or lines), it reached the page (its words in the turn's post), or the
  director moved a beat it named up the plan. Then "Used: ..."; otherwise "Not yet: no one took it up this turn."
  Kept by turn (`author_feedback`), so the line under the nudge box is the newest turn's, and going back shows the
  feedback of the turn now newest.
"""
from adventure import director, plotting
from adventure.database import identifier, many, optional
from adventure.errors import require
from adventure.rounds import engine, queue
from adventure.rounds.contract import Mode, State
from adventure.rounds.solo import SOLO

MOST_BOX = 6
MOST_BEAT_CHARS = 300


# The nudge box ------------------------------------------------------------------------------------------------------

def box(connection) -> list[dict]:
    return many(connection, 'SELECT id, text, created_at FROM nudge_box ORDER BY created_at, rowid')


def add_to_box(connection, text: str, now: str) -> list[dict]:
    text = ' '.join(str(text or '').split())[:MOST_BEAT_CHARS]
    require(text, 'Write the beat you would like to see.', 422)
    require(len(box(connection)) < MOST_BOX, f'The nudge box holds {MOST_BOX} beats at a time.', 409)
    connection.execute('INSERT INTO nudge_box (id, text, created_at) VALUES (?, ?, ?)', (identifier(), text, now))
    return box(connection)


def take_from_box(connection, beat_id: str) -> list[dict]:
    connection.execute('DELETE FROM nudge_box WHERE id=?', (beat_id,))
    return box(connection)


# The beat board -----------------------------------------------------------------------------------------------------

def board(connection) -> list[dict]:
    """Each arc's planned beats for its stage, the spine first, with what has been used and what has landed."""
    row = director.state(connection)
    world = row['world']
    arcs = director.arcs(connection)
    listed = []
    for arc_id in sorted(arcs, key=lambda key: (key != row['spine_id'], key)):
        found = director.arc(world, arc_id) if world else None
        listed.append({'arc_id': arc_id, 'name': found['name'] if found else arc_id, 'stage': arcs[arc_id]['stage'],
                       'spine': arc_id == row['spine_id'],
                       'beats': [{'id': item['id'], 'text': item['text'], 'cut': bool(item['cut']),
                                  'used': bool(item['used']), 'landed': bool(item['landed']),
                                  'source': item['source']}
                                 for item in plotting.beats(connection, arc_id, arcs[arc_id]['stage'])]})
    return listed


def upcoming(connection) -> list[dict]:
    """The planned beats still to come (not cut, not yet given to the note), spine first."""
    return [{'id': beat['id'], 'arc_id': arc['arc_id'], 'text': beat['text']}
            for arc in board(connection) for beat in arc['beats'] if not beat['cut'] and not beat['used']]


def editable(connection) -> bool:
    """The Author edits the plan freely; in other modes it takes the GM view, as in Dungeon."""
    from adventure.rounds.modes import coming
    return coming(connection) == Mode.AUTHOR


# Gather -------------------------------------------------------------------------------------------------------------

def named_beat(nudge: str, beats: list[dict]) -> dict | None:
    """The first planned beat a nudge points at, by their words."""
    words = plotting.words_of(nudge)
    return next((beat for beat in beats if words and plotting.landed(sorted(words), beat['text'])), None)


async def taken(turn: engine.Turn):
    """Gathering: the turn's nudges, frozen with the snapshot: the Author's, or in Play the beats in the box (as the
    user-set beats of the brief); and the planned beats they name."""
    snapshot = turn.snapshot
    if snapshot.mode == Mode.WATCH:
        return
    with turn.database.connect() as connection:
        waiting = box(connection) if snapshot.mode == Mode.PLAY else []
        planned = upcoming(connection)
    nudges = [str(snapshot.settings.get('nudge') or '').strip()] if snapshot.mode == Mode.AUTHOR else []
    nudges = [nudge for nudge in nudges if nudge] + [item['text'] for item in waiting]
    if waiting:
        snapshot.settings['beats'] = [*snapshot.settings.get('beats', []), *(item['text'] for item in waiting)]
    named = [named_beat(nudge, planned) for nudge in nudges]
    if nudges:
        snapshot.settings['author'] = {'nudges': nudges, 'box': [item['id'] for item in waiting],
                                       'named': [beat and {'id': beat['id'], 'text': beat['text']} for beat in named]}


# Commit -------------------------------------------------------------------------------------------------------------

def posted(turn: engine.Turn) -> str:
    """The turn's post: the round Writer's, or today's narrator's for a solo turn."""
    reply = (turn.draft.extra.get(SOLO) or {}).get('reply') or {}
    return turn.draft.post or str(reply.get('text') or '')


def hit(words: set[str], text: str) -> bool:
    return bool(words) and plotting.landed(sorted(words), text)


def feedback(turn: engine.Turn, nudge: str, named: dict | None, post: str) -> tuple[str, str]:
    """Whether one nudge took this turn, and the line that says so."""
    words = plotting.words_of(nudge)
    for seat in turn.snapshot.seats:
        declared = turn.draft.declarations.get(seat.key)
        if declared and hit(words, ' '.join([declared.intent, *(line.text for line in declared.lines)])):
            return 'used', f'Used: {seat.name} took it up.'
    if hit(words, post):
        return 'used', 'Used: it reached the page.'
    if named:
        return 'used', f"Used: the director moved “{named['text']}” up its plan."
    return 'not_yet', 'Not yet: no one took it up this turn.'


def committed(connection, turn: engine.Turn):
    """The nudges' feedback, the beats they named moved up, the box emptied of what was taken, and the planned beats
    that reached the page marked landed."""
    held = turn.snapshot.settings.get('author') or {}
    post = posted(turn)
    now = turn.database.now()
    for position, (nudge, named) in enumerate(zip(held.get('nudges', []), held.get('named', []), strict=False)):
        status, why = feedback(turn, nudge, named, post)
        connection.execute('INSERT INTO author_feedback (id, turn_id, position, nudge, status, why, created_at) '
                           'VALUES (?, ?, ?, ?, ?, ?, ?)', (identifier(), turn.id, position, nudge, status, why, now))
        if named and optional(connection, 'SELECT 1 FROM story_arc_beats WHERE id=? AND used=0', (named['id'],)):
            plotting.change_beat(connection, named['id'], position=0, gated=False)
    for beat_id in held.get('box', []):
        connection.execute('DELETE FROM nudge_box WHERE id=?', (beat_id,))
    if post:
        plotting.landed_beats(connection, post)


def feedback_of(connection, turn_id: str | None) -> list[dict]:
    if turn_id is None:
        return []
    return [{'nudge': row['nudge'], 'status': row['status'], 'why': row['why']}
            for row in many(connection, 'SELECT * FROM author_feedback WHERE turn_id=? ORDER BY position',
                            (turn_id,))]


def view(connection) -> dict:
    """What the Author's screen shows: the beat board, the box, and the newest turn's feedback."""
    return {'board': board(connection), 'box': box(connection), 'editable': editable(connection),
            'feedback': feedback_of(connection, queue.head(connection))}


engine.register(State.GATHERING, 'author', taken, after='pick')
engine.on_commit('author', committed)
