"""Lies are rolled when heard (docs/spec.md "The turn loop" step 4; Batch 3: "Lies between agents are rolled, as in
Dungeon").

Every lie is declared as one (adventure/rounds/contract.py Deception), so code knows what was claimed, what the liar
believes and whom it was aimed at. Right after Declare, and again for any lie told later in the turn (a reaction,
Converse), code rolls each listener's insight against the liar (adventure/lies.py `insight`, `practised`) and stages
what that listener makes of it in their in-turn knowledge:

- **Believed:** the claim, as a belief, with no mark that it is false. The listener can't be suspicious of a lie it
  failed to catch, because nothing in its context says there was one.
- **Uneasy** (a near miss): only that something in it didn't sit right.
- **Caught:** a tell, that the liar was lying about that claim (never what the truth is), and the listener's trust in
  the liar drops.

Who hears a lie: whoever it is aimed at and everyone present, since lines are said aloud, unless it was whispered,
when only the whisper's audience hears it. The liar keeps, as a private thought, that they lied and what they hold
true. Each roll's outcome is staged in `draft.extra['agents']['lies']` as {liar, listener, claim, band, read,
caught}; Resolve puts them in the brief as they stand and never rolls a declared lie again.
"""
import re

from adventure import lies
from adventure.rounds import agents
from adventure.rounds.contract import Deception, Declaration
from adventure.rounds.engine import Turn

WORD = re.compile(r"[a-z][a-z'-]{2,}", re.I)
# A whisper shares this much of a lie's words when the lie was told in it.
OVERLAP = 0.5
CAUGHT = {'trust': -2, 'respect': -1}


def words(text: str) -> set[str]:
    return {word.lower() for word in WORD.findall(text or '')}


def whispered(declaration: Declaration, deception: Deception):
    """The whisper a lie was told in, if any."""
    claim = words(deception.claim)
    for whisper in declaration.whispers:
        if claim and len(claim & words(whisper.text)) >= OVERLAP * len(claim):
            return whisper
    return None


def listeners(turn: Turn, speaker: str, declaration: Declaration, deception: Deception) -> list[str]:
    """Who hears the lie: a whisper's audience, else everyone present but the liar."""
    here = [key for key in agents.present(turn.snapshot) if key != speaker]
    whisper = whispered(declaration, deception)
    return [key for key in here if key in whisper.to] if whisper else here


def rolled(turn: Turn, connection, liar: str, listener: str, claim: str) -> dict:
    """One listener's insight against one lie; the human's character rolls in the campaign's ruleset."""
    snapshot = turn.snapshot
    names = {seat.key: seat.name for seat in snapshot.seats}
    human = snapshot.human()
    persona = human is not None and listener == human.key
    difficulty = lies.practised(connection, liar, persona=human is not None and liar == human.key)
    result = lies.insight(connection, listener, difficulty, f"see through {names.get(liar, liar)}",
                          getattr(turn.app, 'dice', None), persona)
    return {'liar': liar, 'listener': listener, 'claim': claim, 'band': result['band'], 'read': lies.read(result['band']),
            'caught': lies.read(result['band']) == 'caught'}


def staged(turn: Turn, outcome: dict):
    """What the listener makes of it, in their in-turn knowledge, and what being caught does to their trust."""
    draft, names = turn.draft, {seat.key: seat.name for seat in turn.snapshot.seats}
    liar, listener, claim = outcome['liar'], outcome['listener'], outcome['claim']
    name = names.get(liar, liar)
    if outcome['read'] == 'caught':
        draft.learn(listener, 'tell', f'{name} was lying when they said: {claim}', source=liar, about=liar, importance=2)
        draft.feel(listener, liar, scaled(CAUGHT, agents.held(turn.snapshot)['loyalty']), f'Caught {name} in a lie.')
    elif outcome['read'] == 'uneasy':
        draft.learn(listener, 'tell', f"Something didn't sit right when {name} said: {claim}", source=liar, about=liar)
    else:
        draft.learn(listener, 'belief', f'{name} said: {claim}', source=liar, about=liar)


def scaled(changes: dict, loyalty: str) -> dict:
    """Feelings moved faster or slower by the loyalty dial: slow halves (down), fast adds half (up)."""
    from adventure import feelings
    return feelings.scaled(changes, agents.LOYALTY[loyalty])


def heard(turn: Turn, speaker: str, declaration: Declaration, hearing: list[str] | None = None) -> list[dict]:
    """Roll every lie in `declaration` for each listener (`hearing`, plus whoever it is aimed at who is present; by
    default those who heard it) and stage what each makes of it. The outcomes, also kept in the draft."""
    if not declaration.deceptions:
        return []
    names = {seat.key: seat.name for seat in turn.snapshot.seats}
    here = set(agents.present(turn.snapshot))
    outcomes = []
    with turn.database.connect() as connection:
        for deception in declaration.deceptions:
            reached = listeners(turn, speaker, declaration, deception) if hearing is None else \
                list(dict.fromkeys([*hearing, *(key for key in deception.aimed_at if key in here)]))
            reached = [key for key in reached if key != speaker]
            for listener in reached:
                outcome = rolled(turn, connection, speaker, listener, deception.claim)
                staged(turn, outcome)
                outcomes.append(outcome)
            if reached:
                told = ', '.join(names.get(key, key) for key in reached)
                believed = f' What you hold true: {deception.believed}' if deception.believed else ''
                turn.draft.learn(speaker, 'motive', f'You lied to {told}, claiming: {deception.claim}.{believed}',
                                 source=speaker, importance=2)
        # A ruleset's own bookkeeping from the roll (momentum, an experience check) is not kept: nothing outside the
        # draft changes before Commit.
        connection.rollback()
    turn.draft.extra.setdefault('agents', {}).setdefault('lies', []).extend(outcomes)
    return outcomes


async def step(turn: Turn):
    """After Declare: every declared lie, rolled for everyone who heard it, in seat order."""
    if not turn.snapshot.agents():
        return
    for key in agents.present(turn.snapshot):
        if (declaration := turn.draft.declarations.get(key)) is not None:
            heard(turn, key, declaration)
