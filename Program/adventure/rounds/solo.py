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

With agents at the table, the round timeline's events go out in the story's stream too, and a turn can stop on the
reply card (Converse): the line's request then ends with no reply yet and the turn under way (`'awaiting'`, as
adventure/rounds/turns.py `view` shows it). The card is answered through /api/rounds/turns/{id}/reply/stream, where
the turn runs on and tells the line; that stream ends with the reply. While the card waits, a new line is refused:
the same line sent again (a retried request) is shown the card again.
"""
from adventure import story
from adventure.database import decode, optional
from adventure.errors import DomainError
from adventure.rounds import engine, memory, telling, turns
from adventure.rounds.contract import Mode, State

SOLO = telling.PLAYERS_LINE


def retire(connection, anchor_id: str):
    """The turns already played for this line, and what they wrote to memory, give way to a new telling."""
    for row in connection.execute("SELECT id FROM round_turns WHERE anchor_id=? AND state != 'discarded'",
                                  (anchor_id,)).fetchall():
        memory.forget_turn(connection, row['id'])
        turns.discard(connection, row['id'], 'told again')


def todays_events(on_event, turn: engine.Turn | None = None):
    """The story's stream as it always was: with no agents at the table, the round timeline's events stay out of it."""
    async def emit(event: dict):
        if on_event is None:
            return
        if turn is not None and turn.snapshot.agents() or not {'round', 'seat', 'awaiting'} & event.keys():
            await on_event(event)
    return emit


def told_reply(row: dict) -> dict | None:
    """The narrator's reply a committed turn told for a player's line, if it was one (adventure/rounds/telling.py)."""
    held = (decode(row['draft']) or {}).get('extra', {}).get(telling.KEY) or {}
    return held.get('reply') if row['state'] == State.COMMITTED else None


async def answered(app, user: dict, on_text=None, on_event=None) -> dict:
    """The narrator's reply to the player's line, as one turn of the round loop; or, when the turn stops on the reply
    card, no reply yet and the turn waiting on it."""
    with app.database.connect(write=True) as connection:
        retire(connection, user['id'])
    turn = await engine.begin(app, user['branch_id'], user['seq'], anchor_id=user['id'], mode=Mode.PLAY,
                              on_text=on_text)
    turn.emit = todays_events(on_event, turn)
    turn.draft.extra[SOLO] = {'message_id': user['id']}
    if await engine.run(turn) == State.AWAITING_USER:
        with app.database.connect() as connection:
            return {'reply': None, 'awaiting': turns.view(turns.get(connection, turn.id))}
    return {'reply': telling.reply_of(turn)}


def waiting(app, client_id: str) -> dict | None:
    """While a turn waits on the reply card: the card again for its own line, and a new line refused."""
    with app.database.connect() as connection:
        row = turns.under_way(connection)
        if row is None or row['state'] != State.AWAITING_USER:
            return None
        line = optional(connection, 'SELECT * FROM story_messages WHERE client_id=?', (client_id,))
    if line is None or line['id'] != row['anchor_id']:
        raise DomainError('Answer the reply card first.', 409, 'awaiting')
    return {'message': line, 'reply': None, 'awaiting': turns.view(row)}


async def send(app, text: str, client_id: str, on_text=None, on_event=None) -> dict:
    """As adventure/story.py `send`: the line saved once whatever retries come, then its reply."""
    if shown := waiting(app, client_id):
        return shown
    user, reply = story.received(app.database, text, client_id, getattr(app, 'dice', None))
    return {'message': user} | ({'reply': reply} if reply else await answered(app, user, on_text, on_event))


async def retry(app, on_text=None, on_event=None) -> dict:
    """As adventure/story.py `retry`: the last line told again."""
    user = await story.retelling(app)
    return {'message': user} | await answered(app, user, on_text, on_event)
