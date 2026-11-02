"""What each character saw and heard of the others' moves, the one reaction each agent may make, and how the round
moved their feelings (docs/spec.md "The turn loop" step 5; Batch 1: "declare at once, then one reaction"; Batch 2:
"Agents can talk privately to each other", "Siding ... comes from feelings plus the character's own goals").

- **Seeing and hearing is decided by code** (`share`). Everyone present sees what the others try, unless it is done
  covertly (slipping, palming, sneaking: whether anyone notices is Resolve's roll), and hears every line, since lines
  are said aloud: those it was said to as told, the rest as heard. A whisper reaches only its audience. Motives
  reach nobody. Each becomes the listener's in-turn knowledge, which the agent context builder reads, so an agent's
  reaction is built only from what it could see and hear, with lie outcomes already in it (adventure/rounds/
  lies_heard.py).
- **React** (`react`): each agent may react once, in parallel: step in, object, change course, or let its move
  stand. A changed move replaces its declaration (the first is kept for the minds panel and re-asking); what is new
  in it is shared and its new lies rolled as heard. In "Quick and cheap" only agents someone spoke to, whispered
  to, lied to or named get to react. An agent whose call fails keeps its move.
- **Feelings** (`felt`, after Resolve): every roll one character aimed at another moves the target's feelings toward
  the one who acted (adventure/feelings.py `between`), slower or faster by the loyalty dial. The user's own
  character's feelings are the user's.
"""
import asyncio
import re

from adventure import feelings
from adventure.rounds import agents, lies_heard
from adventure.rounds.contract import Declaration, Mind, Mode, seat_event
from adventure.rounds.engine import Turn

COVERT = re.compile(r"\b(secretly|quietly|covertly|unseen|unnoticed|slips?|slipping|palms?|pockets?|sneak\w*|hid(e|es|ing)|"
                    r"conceal\w*|behind (his|her|their) back|without (anyone|being) (noticing|seeing|seen))\b", re.I)


def names(turn: Turn) -> dict[str, str]:
    return {seat.key: seat.name for seat in turn.snapshot.seats}


def share(turn: Turn, declaration: Declaration, before: Declaration | None = None):
    """Stage what everyone present could see and hear of one declaration (only what is new since `before`)."""
    called, draft = names(turn), turn.draft
    speaker = declaration.seat
    name = called.get(speaker, speaker)
    others = [key for key in agents.present(turn.snapshot) if key != speaker]
    if declaration.intent and not COVERT.search(declaration.intent) and \
            (before is None or before.intent != declaration.intent):
        for key in others:
            draft.learn(key, 'witnessed', f'{name}: {declaration.intent}', source=speaker, about=speaker)
    said_before = {line.text for line in before.lines} if before else set()
    for line in declaration.lines:
        if line.text in said_before:
            continue
        to = f" to {', '.join(called.get(key, key) for key in line.to)}" if line.to else ''
        for key in others:
            draft.learn(key, 'told' if key in line.to else 'heard', f'{name} said{to}: "{line.text}"', source=speaker,
                        about=speaker)
    whispered_before = {whisper.text for whisper in before.whispers} if before else set()
    for whisper in declaration.whispers:
        if whisper.text not in whispered_before:
            for key in whisper.to:
                draft.learn(key, 'whisper', f'{name} whispered to you: "{whisper.text}"', source=speaker,
                            about=speaker, importance=2)


def addressed(turn: Turn, key: str) -> bool:
    """Whether anyone spoke to, whispered to, lied to or named this character in their declaration."""
    name = names(turn).get(key, key)
    for other, declaration in turn.draft.declarations.items():
        if other == key:
            continue
        if any(key in line.to for line in declaration.lines) or any(key in whisper.to for whisper in
                                                                    declaration.whispers):
            return True
        if any(key in deception.aimed_at for deception in declaration.deceptions) or \
                re.search(rf'\b{re.escape(name.split(" ")[0])}\b', declaration.intent, re.I):
            return True
    return False


def reacting(turn: Turn) -> list[str]:
    """The agents who may react: every agent whose move came from its agent, or in Quick only those addressed."""
    every = agents.PRESETS[agents.held(turn.snapshot)['preset']]['react'] == 'all'
    return [key for key in agents.present(turn.snapshot)
            if turn.snapshot.seat(key).mind == Mind.AGENT and key in turn.draft.declarations
            and not turn.draft.declarations[key].fallback and (every or addressed(turn, key))]


async def reaction(turn: Turn, key: str) -> dict | None:
    try:
        return await agents.ask(turn, key, 'react')
    except agents.Failed as failure:
        turn.draft.extra.setdefault('agents', {}).setdefault('reaction_failures', {})[key] = failure.why
        return None


def changed(turn: Turn, key: str, made: Declaration):
    """A reaction that changes course: its new move replaces the old, and what is new is shared and rolled."""
    before = turn.draft.declarations[key]
    made.intent = made.intent or before.intent
    turn.draft.declare(made)
    if made.motive and made.motive != before.motive:
        turn.draft.learn(key, 'motive', made.motive, source=key, importance=2)
    share(turn, made, before)
    told = {deception.claim for deception in before.deceptions}
    new = [deception for deception in made.deceptions if deception.claim not in told]
    if new:
        lies_heard.heard(turn, key, Declaration(seat=key, lines=made.lines, deceptions=new, whispers=made.whispers))


async def react(turn: Turn):
    if not turn.snapshot.agents():
        return
    shared = turn.draft.extra.setdefault('agents', {}).setdefault('shared', [])
    for key in agents.present(turn.snapshot):
        if key in turn.draft.declarations and key not in shared:
            share(turn, turn.draft.declarations[key])
            shared.append(key)
    keys = reacting(turn)
    for key in keys:
        await turn.emit(seat_event(key, 'reacting'))
    answers = await asyncio.gather(*(reaction(turn, key) for key in keys))
    for key, answer in zip(keys, answers):
        if answer and answer['change']:
            changed(turn, key, answer['declaration'])
        declaration = turn.draft.declarations[key]
        await turn.emit(seat_event(key, 'done', declaration.intent if turn.snapshot.mode != Mode.PLAY else None))


async def felt(turn: Turn):
    """After Resolve: the feelings the round's rolls moved, staged for Commit."""
    if turn.draft.result is None:
        return
    human = turn.snapshot.human()
    factor = agents.LOYALTY[agents.held(turn.snapshot)['loyalty']]
    for change in feelings.between(turn.draft.result.rolls, factor, {human.key} if human else set()):
        turn.draft.feel(change['from'], change['to'], change['changes'], change['why'])
