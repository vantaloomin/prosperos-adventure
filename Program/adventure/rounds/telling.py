"""Today's turn as steps of the round loop (docs/spec.md "The turn loop"; adventure/story.py `Telling`).

The player's line in Play is told by Dungeon's own pieces, each run as a step, so a campaign with no agents plays
exactly as before and a round with agents rolls, fights and narrates the player's part the same way:

- **Gathering** ('line', after 'pick'): the line the turn opens on (`snapshot.settings['message_id']`, read from
  story_messages) and, for a player's line, `story.gathered`: there is a model, the last turn's after-work is done,
  the time budget is set.
- **Resolving** ('line', after 'ambiguity'): `story.resolved` on the line as the player meant it (their answer to the
  one question, adventure/rounds/resolve.py `meant`), with each agent ally's declared move for a fight, and who the
  round's agents are, so code never lies or walks off for them (adventure/lies.py, adventure/party.py). Its rolls
  are staged for the party's Resolve ('resolve', next), labelled as the player's. In a round with agents the lives
  off the page are left to Writing (W4's 'offpage' step).
- **Writing** ('write'): `story.written`, the narrator's packet and telling; the text is the draft's post. The
  round Writer (adventure/rounds/writer.py) replaces this step by name and calls `write` here for a turn with no
  agents.
- **Committing** (hook 'story'): `story.saved_reply` in Commit's one transaction, with the draft's post as the
  reply's text; then the after-work is left for the next turn, as today.

The Telling holds live things (the app, the stream, the time budget), so it is kept in memory for the turn
(`TELLINGS`). A turn picked up again after a pause, in this process or after a restart, gathers it again from the
line; every piece of today's turn keeps what it decided with the line, so nothing is rolled or drawn twice.
"""
from adventure import story
from adventure.database import optional
from adventure.rounds import engine, resolve
from adventure.rounds.contract import Mind, State

TELLINGS: dict[str, story.Telling] = {}
KEY = 'telling'
# The mark of a turn opened on a player's line (adventure/rounds/solo.py `answered`).
PLAYERS_LINE = 'solo'


def line_of(turn) -> dict | None:
    """The player's line the turn opens on, when it was opened on one (Author and Watch lines are their own)."""
    message_id = turn.snapshot.settings.get('message_id')
    if not message_id or PLAYERS_LINE not in turn.draft.extra:
        return None
    with turn.database.connect() as connection:
        row = optional(connection, "SELECT * FROM story_messages WHERE id=? AND role='user'", (message_id,))
    return row if row and (row.get('mode') or 'play') == 'play' else None


async def telling_of(turn) -> story.Telling | None:
    """The turn's Telling: kept since Gather, or gathered again for a turn picked up after a pause or re-run from
    Declare (a re-ask)."""
    if turn.id not in TELLINGS:
        user = line_of(turn)
        if user is None:
            return None
        turn.draft.extra[KEY] = {'message_id': user['id']}
        TELLINGS[turn.id] = await story.gathered(turn.app, user, turn.on_text, turn.emit)
    return TELLINGS[turn.id]


async def gather(turn):
    await telling_of(turn)


def labelled(rolls: list[dict], actor: str) -> list[dict]:
    """The line's rolls as the round's result carries them: the player's, at nobody in particular."""
    return [dict(roll) | {'actor': actor, 'target': '', 'kind': resolve.LINE, 'stake': roll['action'],
                          'opposed': None} for roll in rolls]


async def line(turn):
    telling = await telling_of(turn)
    if telling is None or 'line_rolls' in turn.draft.extra.get('resolve', {}):
        return
    telling.user = telling.user | {'text': resolve.meant(telling.user['text'], turn)}
    telling.moves = resolve.ally_moves(turn)
    telling.agents = {seat.key for seat in turn.snapshot.agents()}
    telling.offpage = not turn.snapshot.agents()
    await story.resolved(telling)
    human = turn.snapshot.human()
    turn.draft.extra.setdefault('resolve', {})['line_rolls'] = labelled(
        telling.rolls, human.key if human is not None and human.mind == Mind.HUMAN else 'persona')


async def write(turn):
    telling = await telling_of(turn)
    if telling is None:
        return
    if turn.snapshot.agents():
        # The lives off the page were drawn in this turn's own Resolving (W4's 'offpage'), with the agents' lines.
        telling.meanwhile = (turn.draft.extra.get('offpage') or {}).get('cutaways', [])
    await story.written(telling)
    turn.draft.post = telling.text


def committed(connection, turn):
    telling = TELLINGS.get(turn.id)
    if telling is None:
        return
    telling.text = turn.draft.post or telling.text
    reply = story.saved_reply(connection, telling)
    turn.draft.extra[KEY]['reply'] = reply
    story.after_telling(telling, reply)
    TELLINGS.pop(turn.id, None)


def reply_of(turn) -> dict | None:
    """The narrator's reply the turn kept, for the caller of today's send and retry."""
    return (turn.draft.extra.get(KEY) or {}).get('reply')


engine.register(State.GATHERING, 'line', gather, after='pick')
engine.register(State.RESOLVING, 'line', line, after='ambiguity')
engine.register(State.RESOLVING, 'resolve', resolve.resolve, after='line')
engine.register(State.WRITING, 'write', write)
engine.on_commit('story', committed)
