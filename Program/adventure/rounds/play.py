"""Playing rounds: opening a turn, answering the reply card, re-asking an agent, and picking up after a restart
(docs/spec.md "The turn loop", "Turn state and persistence", Batch 4: "Branching is Dungeon's, plus re-asking an
agent").

Every turn opens on a user line in the story (`story_messages`, role 'user'): the player's line in Play, and in
Author and Watch a line in that mode holding the Author's nudge (or nothing, in Watch). So every turn is a save point
exactly as a player's line is in Dungeon (adventure/timeline.py `save`): going back to it, a re-ask, and memory read
through the branch's ancestry all work the same in every mode. Steps tell a mode's lines apart by
`story_messages.mode`.

- **Next** (`next_turn`) opens and runs a turn in the campaign's mode.
- **The reply card** (`reply`): the turn waiting on a human seat runs on with the answer.
- **Re-asking** (`reask`) goes back to before a committed turn, on a new branch, and plays it again from Declare:
  everyone else keeps the declaration they made, the re-asked character decides again, and everything from the lies
  heard onward is redone for everyone, with new dice, from the turn's own snapshot.
- **After a restart** (`recover`): a turn waiting on the reply card stays waiting. Any other open turn is thrown away;
  a round turn is then played again from its snapshot, while a solo turn waits for the player's Retry as in Dungeon.
"""
from adventure import story, timeline
from adventure.database import decode, one
from adventure.errors import require
from adventure.rounds import engine, seats, solo, turns
from adventure.rounds.contract import Mind, Point, Snapshot, State, plain
from adventure.rounds.draft import Draft


def opening_line(connection, now: str, mode: str, text: str) -> dict:
    """The user line a turn opens on, kept as a save point."""
    line = story.add(connection, now, 'user', text.strip(), story.scene_row(connection))
    connection.execute('UPDATE story_messages SET mode=? WHERE id=?', (mode, line['id']))
    timeline.save(connection, line['id'])
    return line | {'mode': mode}


async def next_turn(app, nudge: str = '', emit=None, on_text=None) -> dict:
    """A turn in the campaign's mode: in Author with the nudge, in Watch with none. Returns the turn's row."""
    database = app.database
    await story.settled(app)
    with database.connect(write=True) as connection:
        mode = seats.settings(connection)['mode']
        line = opening_line(connection, database.now(), mode, nudge if mode == 'author' else '')
    turn = await engine.begin(app, line['branch_id'], line['seq'], anchor_id=line['id'], emit=emit, mode=mode,
                              on_text=on_text)
    await engine.run(turn)
    return turn.row


async def reply(app, turn_id: str, seat: str, answer: dict, emit=None, on_text=None) -> dict:
    """The human at `seat` answered the reply card of the turn waiting on them."""
    turn = engine.resumed(app, turn_id, emit, on_text)
    waiting = turn.draft.awaiting
    require(turn.row['state'] == State.AWAITING_USER and waiting and waiting['seat'] == seat,
            'That turn is not waiting for this answer.', 409, 'stale')
    await engine.answer(turn, seat, answer)
    return turn.row


async def reask(app, turn_id: str, seat: str, emit=None, on_text=None) -> dict:
    """Play a committed turn again on a new branch, with `seat`'s choice asked again and everyone else's kept."""
    database = app.database
    await story.settled(app)
    with database.connect(write=True) as connection:
        original = turns.get(connection, turn_id)
        require(original['state'] == State.COMMITTED, 'Only a turn already played can be asked again.', 409)
        snapshot = Snapshot.of(decode(original['snapshot']))
        chosen = snapshot.seat(seat)
        require(chosen is not None and chosen.mind == Mind.AGENT, 'Only an agent can be asked to decide again.', 409)
        first = Draft.of(decode(original['draft']))
        anchor = one(connection, 'SELECT * FROM story_messages WHERE id=?', (original['anchor_id'],))
        timeline.back(connection, anchor['id'], database.now())
        line = opening_line(connection, database.now(), original['mode'], anchor['text'])
    turn = await engine.begin(app, line['branch_id'], line['seq'], anchor_id=line['id'], emit=emit,
                              mode=original['mode'], reask_of=turn_id, reask_seat=seat, on_text=on_text)
    # The same snapshot, read at the new branch's place: it sees exactly what the original turn saw.
    turn.snapshot = Snapshot.of(plain(snapshot) | {'turn_id': turn.id, 'point': plain(Point(line['branch_id'],
                                                                                            line['seq']))})
    turn.snapshot.settings['message_id'] = line['id']
    for key, declaration in first.declared.items():
        if key != seat:
            turn.draft.declare(declaration)
    engine.kept(turn, snapshot=True)
    await engine.run(turn, State.DECLARING)
    return turn.row


def recover(app) -> str | None:
    """After a restart: the open turn that should be played again from its snapshot, if there is one."""
    with app.database.connect(write=True) as connection:
        row = turns.under_way(connection)
        if row is None or row['state'] == State.AWAITING_USER:
            return None
        turns.discard(connection, row['id'], 'The app stopped during this turn.')
        solo_turn = solo.SOLO in (decode(row['draft']) or {}).get('extra', {})
        return None if solo_turn or row['anchor_id'] is None else row['id']


async def replay(app, turn_id: str, emit=None, on_text=None) -> dict:
    """Play a thrown-away turn again from its snapshot, at the same place, with a fresh draft."""
    with app.database.connect() as connection:
        original = turns.get(connection, turn_id)
    snapshot = Snapshot.of(decode(original['snapshot']))
    turn = await engine.begin(app, original['branch_id'], original['seq'], anchor_id=original['anchor_id'], emit=emit,
                              mode=original['mode'], on_text=on_text)
    turn.snapshot = Snapshot.of(plain(snapshot) | {'turn_id': turn.id})
    engine.kept(turn, snapshot=True)
    gathered = bool(snapshot.seats)
    await engine.run(turn, State.DECLARING if gathered else State.GATHERING)
    return turn.row
