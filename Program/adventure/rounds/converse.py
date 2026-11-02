"""Converse: the talk inside one turn (docs/spec.md "The turn loop" step 6; Batch 2: "In Converse, the asking
character's own agent writes the question"; "In-turn conversations have a user-set cap").

After React, characters may ask each other things and get answers in the same turn, up to the conversation cap.

- **A line said to the user's character is answered first.** In Play, a declared line addressed to the human's seat
  puts the reply card up (adventure/rounds/reply.py) before anything else is asked.
- **The Writer picks who asks whom, and only that.** One call, from the Writer's view of the turn, returns pairs; it
  never says what to ask, so it can't slip a secret into a question. Code keeps a pair only when the asker is an
  agent this turn and present, the one asked is present and someone else, and the cap is not reached.
- **The asker's own agent writes the question** from its own knowledge (adventure/rounds/agents.py `speak`), and an
  agent asked answers through its own agent. The user's character answers on the reply card. A Program character, or
  an agent that failed, is voiced by the Writer in the post, as Program characters always are: no call here.
- **Everyone present hears it.** Each line goes into every present character's in-turn knowledge (as told, for the
  one who said it), and any lie in it is rolled for each listener (adventure/rounds/lies_heard.py `heard`).
- **It resumes.** The step runs again after the reply card: the pairs and each exchange so far are in the draft, so
  nothing is asked twice and nobody is billed twice.

Exchanges are kept in `draft.exchanges` as {asker, to, question, answer, status, answered_by, declared}; the lie rolls
stay in `draft.extra['converse']`, out of the exchanges every Writer reads.
"""
import json
import logging
import re

from adventure.rounds import engine, reply, writer
from adventure.rounds.contract import Declaration, Mind, State, seat_event

log = logging.getLogger(__name__)

# Where an exchange has got to. Settled ones are never touched again.
OPEN, WAITING = 'open', 'waiting'
SETTLED = ('answered', 'silent', 'voiced', 'dropped')
JSON = re.compile(r'\{.*\}', re.DOTALL)


# Who is in it ------------------------------------------------------------------------------------------------------

def present(turn) -> list[str]:
    return list(dict.fromkeys(turn.snapshot.present))


def mind_of(turn, key: str) -> str:
    seat = turn.snapshot.seat(key)
    return seat.mind if seat else Mind.PROGRAM


def askers(turn) -> list[str]:
    """The agents present this turn: only they can ask, since only an agent writes its own question."""
    here = set(present(turn))
    return [seat.key for seat in turn.snapshot.agents() if seat.key in here]


def listeners(turn, speaker: str) -> list[str]:
    return [key for key in present(turn) if key != speaker]


# The exchanges -----------------------------------------------------------------------------------------------------

def exchange(asker: str, to: str, question: str | None = None, declared: bool = False) -> dict:
    return {'asker': asker, 'to': to, 'question': question, 'answer': None, 'status': OPEN, 'answered_by': None,
            'declared': declared}


def addressed(turn) -> list[dict]:
    """In Play, the first declared line each agent said to the user's character: each one waits on the reply card."""
    human = turn.snapshot.human()
    if human is None or human.key not in present(turn):
        return []
    agents, found = set(askers(turn)), []
    for seat in turn.snapshot.seats:
        declaration = turn.draft.declarations.get(seat.key)
        if seat.key not in agents or declaration is None:
            continue
        line = next((line for line in declaration.lines if human.key in line.to), None)
        if line is not None:
            found.append(exchange(seat.key, human.key, line.text, declared=True))
    return found


def kept_pairs(turn, picked: list, room: int) -> list[tuple[str, str]]:
    """The Writer's pairs that code allows, in its order, up to `room`."""
    can_ask, here, kept = set(askers(turn)), set(present(turn)), []
    for pair in picked:
        if len(kept) >= room:
            break
        asker, to = (pair.get('asks'), pair.get('to')) if isinstance(pair, dict) else (None, None)
        if asker in can_ask and to in here and to != asker:
            kept.append((asker, to))
    return kept


def said(turn, before: dict | None = None) -> list[str]:
    """Every line said aloud this turn so far, as "Name: line", up to the exchange `before`."""
    lines = []
    for seat in turn.snapshot.seats:
        declaration = turn.draft.declarations.get(seat.key)
        lines += [f'{seat.name}: {line.text}' for line in (declaration.lines if declaration else [])]
    for item in turn.draft.exchanges:
        if item is before:
            break
        if item['question'] and not item['declared']:
            lines.append(f"{writer.name_of(turn, item['asker'])}: {item['question']}")
        if item['answer']:
            lines.append(f"{writer.name_of(turn, item['to'])}: {item['answer']}")
    return lines


# Who asks whom: the Writer's one call ------------------------------------------------------------------------------

PICK = """You are the Writer of a roleplaying game for adults, setting up the talk inside one round. Choose who asks \
whom, in order, where a question would move the scene: someone pressing a doubt, chasing a lie, wanting something \
from another, or answering back. Choose fewer, or none, if nobody would speak up. You choose only the pairs; each \
asker writes their own words. Reply with JSON only, using the keys given: \
{"exchanges": [{"asks": "<key>", "to": "<key>"}]}"""


def roster(turn, keys: list[str]) -> str:
    return '\n'.join(f'- {key}: {writer.fence("name", writer.name_of(turn, key))}' for key in keys)


def picked(text: str) -> list:
    """The pairs in the Writer's reply; none when it gave no readable JSON."""
    found = JSON.search(text or '')
    try:
        data = json.loads(found[0]) if found else {}
    except ValueError:
        return []
    pairs = data.get('exchanges') if isinstance(data, dict) else None
    return pairs if isinstance(pairs, list) else []


async def pick(turn, room: int) -> list[tuple[str, str]]:
    if room <= 0 or not askers(turn) or len(present(turn)) < 2:
        return []
    with turn.database.connect() as connection:
        known = writer.view(connection, turn)
    system = '\n\n'.join((PICK, writer.fence_rule(), known))
    asked = (f'Up to {room} exchanges.\n\nWho can ask:\n{roster(turn, askers(turn))}\n\n'
             f'Who can be asked:\n{roster(turn, present(turn))}')
    return kept_pairs(turn, picked(await writer.complete(turn, system, [{'role': 'user', 'content': asked}])), room)


# Speaking and hearing -----------------------------------------------------------------------------------------------

async def spoken(turn, key: str, cue: dict) -> Declaration | None:
    """What `key`'s own agent says for `cue`; None when it failed or refused (its Program mind takes over, which in
    Converse means the Writer voices it)."""
    from adventure.rounds import agents  # the agent call, its validation and its fallback
    await turn.emit(seat_event(key, 'thinking'))
    declaration = await agents.speak(turn, key, cue)
    if declaration.fallback or not any(line.text.strip() for line in declaration.lines):
        await turn.emit(seat_event(key, 'fallback'))
        return None
    await turn.emit(seat_event(key, 'done'))
    return declaration


def heard(turn, speaker: str, to: str, text: str, kind: str = 'heard'):
    """`speaker`'s line to `to`, in the in-turn knowledge of everyone present."""
    line = f'{writer.name_of(turn, speaker)}, to {writer.name_of(turn, to)}: "{text}"'
    turn.draft.learn(speaker, 'told', line, source=speaker, about=to)
    for key in listeners(turn, speaker):
        turn.draft.learn(key, kind, line, source=speaker, about=to)


def silence(turn, item: dict):
    line = f"{writer.name_of(turn, item['to'])} said nothing to {writer.name_of(turn, item['asker'])}."
    for key in present(turn):
        turn.draft.learn(key, 'witnessed', line, source=item['to'], about=item['asker'])


def lies(turn, speaker: str, declaration: Declaration):
    """Each lie in what was said, rolled for everyone who heard it; the rolls stay in Converse's own staged data."""
    if not declaration.deceptions:
        return
    from adventure.rounds import lies_heard  # code rolls insight against deception; the listener never judges
    rolled = lies_heard.heard(turn, speaker, declaration, listeners(turn, speaker))
    turn.draft.extra.setdefault('converse', {}).setdefault('lies', []).extend(rolled or [])


def line_of(declaration: Declaration) -> str:
    return ' '.join(line.text.strip() for line in declaration.lines if line.text.strip())


async def asked(turn, item: dict) -> bool:
    """The question, written by the asker's own agent; False when it had nothing to say."""
    if item['question'] is not None:
        return True
    declaration = await spoken(turn, item['asker'], {'kind': 'ask', 'to': item['to']})
    if declaration is None:
        item['status'] = 'dropped'
        return False
    item['question'] = writer.one_line(line_of(declaration))
    heard(turn, item['asker'], item['to'], item['question'])
    lies(turn, item['asker'], declaration)
    return True


async def by_user(turn, item: dict):
    """The user's character answers on the reply card: put it up, or take the answer it came back with."""
    answer = reply.taken(turn, item['to'])
    if answer is None:
        context = said(turn, before=item)
        reply.ask(turn, item['to'], item['asker'], item['question'], context)
        item['status'] = WAITING
        return
    text = answer['text'] if answer['kind'] == 'reply' else ''
    if answer['kind'] == 'let_answer':
        text = await writer.answer_for(turn, item['to'], item['asker'], item['question'])
    item['answered_by'] = 'writer' if answer['kind'] == 'let_answer' else 'user'
    if not text:
        item['status'] = 'silent'
        silence(turn, item)
        return
    item['answer'], item['status'] = text, 'answered'
    heard(turn, item['to'], item['asker'], text)


async def by_agent(turn, item: dict):
    declaration = await spoken(turn, item['to'], {'kind': 'answer', 'speaker': item['asker'],
                                                  'line': item['question']})
    if declaration is None:
        item['status'], item['answered_by'] = 'voiced', 'writer'
        return
    item['answer'], item['status'], item['answered_by'] = writer.one_line(line_of(declaration)), 'answered', 'agent'
    heard(turn, item['to'], item['asker'], item['answer'])
    lies(turn, item['to'], declaration)


async def advance(turn, item: dict):
    """Take one exchange as far as it can go now: asked, then answered, or waiting on the reply card."""
    if not await asked(turn, item):
        return
    mind = mind_of(turn, item['to'])
    if mind == Mind.HUMAN:
        await by_user(turn, item)
    elif mind == Mind.AGENT:
        await by_agent(turn, item)
    else:
        item['status'], item['answered_by'] = 'voiced', 'writer'


# The step ----------------------------------------------------------------------------------------------------------

async def converse(turn):
    """Conversing: the exchanges of this turn, up to the cap; pauses on the reply card and picks up after it."""
    if not askers(turn):
        return
    staged = turn.draft.extra.setdefault('converse', {})
    if not staged.get('started'):
        turn.draft.exchanges.extend(addressed(turn)[:turn.snapshot.converse_cap])
        staged['started'] = True
    # What was said to the user's character is answered before the Writer picks, so its pairs can follow it up.
    if not await settled(turn):
        return
    if not staged.get('picked'):
        room = turn.snapshot.converse_cap - len(turn.draft.exchanges)
        turn.draft.exchanges.extend(exchange(asker, to) for asker, to in await pick(turn, room))
        staged['picked'] = True
    await settled(turn)


async def settled(turn) -> bool:
    """Every open exchange taken as far as it goes, in order; False when one is waiting on the reply card."""
    for item in turn.draft.exchanges:
        if item['status'] in SETTLED:
            continue
        await advance(turn, item)
        if turn.draft.awaiting is not None:
            return False
    return True


engine.register(State.CONVERSING, 'converse', converse)
