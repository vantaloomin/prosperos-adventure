"""Today's single-player turn, played as a turn of the round loop (docs/spec.md "Turn state and persistence").

Until its pieces are registered as steps of their own, Dungeon's whole turn (adventure/story.py `answer`: the
Referee, the rolls, the code systems and the narrator) runs as one Resolving step, 'solo'. It still writes the
story as it always has; what the round loop adds around it is the turn row, the one-writer queue
(adventure/rounds/queue.py) and the round timeline's events. A campaign with no agents plays exactly as before.

The player's line is the turn's anchor: its id is `snapshot.settings['message_id']` and its text
`snapshot.settings['said']` (adventure/rounds/engine.py `opening`); this step keeps the whole row in
`draft.extra['solo']['user']`, as story.answer wants it.

A line told again (Retry) replaces the turn that told it: that turn is retired and everything it wrote to anyone's
memory goes with it.
"""
from adventure import story
from adventure.rounds import engine, memory, turns
from adventure.rounds.contract import Mode, State

SOLO = 'solo'


async def told(turn: engine.Turn):
    """Resolving: the whole of today's turn for the player's line, its reply kept in the draft."""
    held = turn.draft.extra.get(SOLO)
    if not held or 'reply' in held:
        return
    reply = await story.answer(turn.app, held['user'], turn.on_text, turn.emit)
    held['reply'] = reply


engine.register(State.RESOLVING, SOLO, told)


def retire(connection, anchor_id: str):
    """The turns already played for this line, and what they wrote to memory, give way to a new telling."""
    for row in connection.execute("SELECT id FROM round_turns WHERE anchor_id=? AND state != 'discarded'",
                                  (anchor_id,)).fetchall():
        memory.forget_turn(connection, row['id'])
        turns.discard(connection, row['id'], 'told again')


def todays_events(on_event):
    """The story's stream as it always was: the round timeline's events stay out of a solo turn's stream."""
    async def emit(event: dict):
        if on_event is not None and not {'round', 'seat', 'awaiting'} & event.keys():
            await on_event(event)
    return emit


async def answered(app, user: dict, on_text=None, on_event=None) -> dict:
    """The narrator's reply to the player's line, as one turn of the round loop."""
    with app.database.connect(write=True) as connection:
        retire(connection, user['id'])
    turn = await engine.begin(app, user['branch_id'], user['seq'], anchor_id=user['id'],
                              emit=todays_events(on_event), mode=Mode.PLAY, on_text=on_text)
    turn.draft.extra[SOLO] = {'user': user}
    await engine.run(turn)
    return turn.draft.extra[SOLO]['reply']


async def send(app, text: str, client_id: str, on_text=None, on_event=None) -> dict:
    """As adventure/story.py `send`: the line saved once whatever retries come, then its reply."""
    user, reply = story.received(app.database, text, client_id, getattr(app, 'dice', None))
    return {'message': user, 'reply': reply or await answered(app, user, on_text, on_event)}


async def retry(app, on_text=None, on_event=None) -> dict:
    """As adventure/story.py `retry`: the last line told again."""
    user = await story.retelling(app)
    return {'message': user, 'reply': await answered(app, user, on_text, on_event)}
