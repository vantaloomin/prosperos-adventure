"""Asking a thinking character along (docs/spec.md, code and model boundary follow-ups: "Agents choose whether to leave
the party; feelings still limit who joins").

In Play, when the player's line asks someone along ("come with us, Hesk") and that someone runs on an agent this
round, the agent decides whether their character comes, as a Program character's bond, warmth and Allure roll decide
for them in Dungeon (adventure/party.py):

- **Feelings limit first, in code.** A full party, or a character wary of the user's character, refuses before anyone
  is asked (`party.askable`), so no call is spent on an answer that could not stand.
- **Then the agent is asked**, after React ('joining'), in one call of its own ('invite', adventure/rounds/agents.py),
  from inside its own knowledge with the line that asked. It answers yes or no and says so aloud. Its answer stands
  in Resolve, in place of the roll: yes, they join; no, they turn the character down.
- **What they say is heard.** Their answer's lines join their declaration and everyone present hears them
  (adventure/rounds/react.py `share`); their reason is their own motive, which nobody else learns.
- **Failures fall back.** An agent that fails, refuses or gives no clear yes or no leaves the asking to Dungeon's
  rule, as any failed agent falls back to its Program mind.

The answer is kept in the draft (`draft.extra['joining']`, {key: bool}), so a turn picked up again does not ask twice;
adventure/rounds/telling.py hands it to the party's asking.
"""
from dataclasses import replace

from adventure import combat, party, story, story_clock
from adventure.rounds import agents, react, telling
from adventure.rounds.contract import Mind, State
from adventure.rounds.engine import Turn, register

KEY = 'joining'


def asked_whom(turn: Turn) -> tuple[str, str] | None:
    """The agent the player's line asks along, when the feelings leave it to them, and the line that asked."""
    line = telling.line_of(turn)
    if line is None or not turn.snapshot.agents():
        return None
    database = turn.database
    with database.connect() as connection:
        if combat.fight(connection):
            return None
        view = story.scene(connection, story_clock.now(connection, database.clock))
        person = party.askable(connection, view, line['text'])
    seat = turn.snapshot.seat(person['sheet']['key']) if person else None
    return (seat.key, line['text']) if seat is not None and seat.mind == Mind.AGENT else None


def heard(turn: Turn, key: str, said):
    """The agent's answer, said aloud: added to its declaration and shared; its reason kept as its own motive."""
    draft = turn.draft
    before = draft.declarations.get(key)
    if before is not None and said.lines:
        after = replace(before, lines=[*before.lines, *said.lines])
        draft.declarations[key] = after
        react.share(turn, after, before)
    if said.motive:
        draft.learn(key, 'motive', said.motive, source=key, importance=2)


async def joining(turn: Turn):
    """Reacting, after the agents' one reaction: the agent asked along answers for themselves."""
    draft = turn.draft
    if KEY in draft.extra:
        return
    draft.extra[KEY] = {}
    found = asked_whom(turn)
    if found is None:
        return
    key, line = found
    human = turn.snapshot.human()
    try:
        answer = await agents.ask(turn, key, 'invite', {'kind': 'invite', 'speaker': human.key if human else '',
                                                        'line': line})
    except agents.Failed:
        return
    joins = answer['answer'].get('joins')
    if not isinstance(joins, bool):
        return
    draft.extra[KEY][key] = joins
    heard(turn, key, answer['declaration'])


register(State.REACTING, 'joining', joining, after='signs_first')
