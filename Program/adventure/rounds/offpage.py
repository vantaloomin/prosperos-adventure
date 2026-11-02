"""Off-page threads in a round (docs/spec.md "Off-page threads"; Batch 2 follow-ups: "Offscreen agents: code rolls
the outcome, the character's agent writes their lines").

The people the scene has left behind keep living while a round is played, as Dungeon's off-page beats
(adventure/beats.py). In a round with agents:

- **Code decides each beat** (`beats.draw`): who it happens to and what happens, by the same clock and cards as
  today's turn, without writing anything yet.
- **An offscreen agent says its own lines.** For a beat that lands on an agent's character, that character's own
  agent writes the few lines it said, from its own knowledge and the outcome code drew, in one cheap call
  (adventure/rounds/agents.py `speak`, cue 'offpage'). A Program character's beat is code only, and an agent that
  fails or refuses says nothing.
- **It is staged, then committed with the turn.** The beats, their lines and the cutaways go in
  `draft.extra['offpage']` (the Writer's prompt reads the cutaways from there); each person who lived a beat
  remembers it, and an agent its own lines. Commit writes the beats through `beats.apply` in the turn's one
  transaction, so the outcome is in the record before the next turn's snapshot.

A turn with no agents leaves off-page beats to today's telling (adventure/rounds/telling.py, adventure/story.py
`beats_turn`), unchanged; a turn with agents has its telling skip them.
"""
import asyncio
from datetime import datetime

from adventure import beats, story, story_clock, table
from adventure.rounds import engine
from adventure.rounds.contract import Mind, State
from adventure.rounds.writer import one_line

KEY = 'offpage'
MOST_LINES = 4


def anchor(turn) -> str:
    return turn.row.get('anchor_id') or turn.id


async def said(turn, key: str, outcome: str) -> list[str]:
    """What `key`'s own agent says it said in its beat; nothing when it failed or refused."""
    from adventure.rounds import agents  # the agent call, its validation and its fallback
    declaration = await agents.speak(turn, key, {'kind': 'offpage', 'outcome': outcome, 'with': []})
    if declaration.fallback:
        return []
    return [text for text in (one_line(line.text) for line in declaration.lines) if text][:MOST_LINES]


def agent(turn, key: str) -> bool:
    seat = turn.snapshot.seat(key)
    return seat is not None and seat.mind == Mind.AGENT and key not in turn.snapshot.present


async def offpage(turn):
    """Draw this round's off-page beats, have each offscreen agent write its lines, and stage it all."""
    if not turn.snapshot.agents() or KEY in turn.draft.extra:
        return
    database = turn.database
    with database.connect() as connection:
        now = story_clock.now(connection, database.clock)
        view = story.scene(connection, now)
        drawn = beats.draw(connection, anchor(turn), view, story.intensity(connection, view['data']), now,
                           getattr(turn.app, 'dice', None))
        town = view['city']['name']
        truths = [beats.told(connection, beat['person'], beat['drawn'], town)[0] for beat in drawn['beats']]
        cutaways = table.rule(connection, 'cutaways')
    voiced = [said(turn, beat['person']['key'], truth) if agent(turn, beat['person']['key']) else none()
              for beat, truth in zip(drawn['beats'], truths)]
    for beat, truth, lines in zip(drawn['beats'], truths, await asyncio.gather(*voiced)):
        beat['lines'] = lines
        key, name = beat['person']['key'], beat['person']['name']
        turn.draft.learn(key, 'witnessed', truth[:1].upper() + truth[1:], about=key, importance=2)
        for line in lines:
            turn.draft.learn(key, 'told', f'{name}, off the page: "{line}"', source=key)
    turn.draft.extra[KEY] = {'message_id': anchor(turn), 'town': town, 'now': now.isoformat(), 'drawn': drawn,
                             'cutaways': [truth[:1].upper() + truth[1:] for truth in truths] if cutaways else []}


async def none() -> list[str]:
    return []


def committed(connection, turn):
    """The staged beats written in the turn's transaction."""
    staged = turn.draft.extra.get(KEY)
    if staged:
        beats.apply(connection, staged['message_id'], staged['drawn'], staged['town'],
                    datetime.fromisoformat(staged['now']), turn.database.now())


# Code draws while Resolve runs, so the Writer has the cutaways to place and the beats are in before Commit.
engine.register(State.RESOLVING, 'offpage', offpage)
engine.on_commit('offpage', committed)
