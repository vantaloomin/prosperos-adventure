"""Today's single-player turn, played as a turn of the round loop (docs/spec.md "Turn state and persistence").

A player's line opens a turn in Play; Dungeon's pieces run as its steps (adventure/rounds/telling.py: Gather,
Resolve, Write and Commit), beside whatever the agents do in the same turn. What the round loop adds around them is
the turn row, the one-writer queue (adventure/rounds/queue.py) and the round timeline's events. A campaign with no
agents plays exactly as before.

The player's line is the turn's anchor: its id is `snapshot.settings['message_id']` and its text
`snapshot.settings['said']` (adventure/rounds/engine.py `opening`). `draft.extra['solo']` marks a turn opened on a
player's line, which a restart leaves for the player's Retry (adventure/rounds/play.py `recover`).

A line told again (Retry) replaces the turn that told it: that turn is retired and everything it wrote to anyone's
memory goes with it.
"""
from adventure import story
from adventure.rounds import engine, memory, telling, turns
from adventure.rounds.contract import Mode

SOLO = telling.PLAYERS_LINE


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
    turn.draft.extra[SOLO] = {'message_id': user['id']}
    await engine.run(turn)
    return telling.reply_of(turn)


async def send(app, text: str, client_id: str, on_text=None, on_event=None) -> dict:
    """As adventure/story.py `send`: the line saved once whatever retries come, then its reply."""
    user, reply = story.received(app.database, text, client_id, getattr(app, 'dice', None))
    return {'message': user, 'reply': reply or await answered(app, user, on_text, on_event)}


async def retry(app, on_text=None, on_event=None) -> dict:
    """As adventure/story.py `retry`: the last line told again."""
    user = await story.retelling(app)
    return {'message': user, 'reply': await answered(app, user, on_text, on_event)}
