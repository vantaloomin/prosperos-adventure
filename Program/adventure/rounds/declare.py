"""Who decides this turn, and how each one declares (docs/spec.md "The turn loop" steps 1 and 3; Batch 1: "Agents:
party members plus key NPCs, up to 6 at once"; Batch 3: "Program characters run on Dungeon's code minds as they are").

- **Gather** (`pick`, replacing the foundation's default under the same name): the agents this turn are the seats
  the user made agents who are present, up to the cap, picked party first, then nemeses and characters promoted by
  hand, then those the turn's line names, ties by seat order. Anyone past the cap runs on their Program mind for the
  turn, and is listed in `snapshot.settings['dropped']`. The human sits only in Play. The agents' settings and the
  story's intensity are frozen into the snapshot (adventure/rounds/agents.py `frozen`).
- **Declare** (`declare`): every agent at once, each from its own context, merged in seat order, not in the order the
  answers arrive. Program characters' moves come from code (`program`), with no model call. The human, in Play,
  declares the line they typed (`human`). A seat that already has a declaration keeps it: a re-ask arrives with
  everyone else's. An agent that fails runs on its Program mind for the turn and its seat event says `fallback`.
- Each declared motive goes into its owner's in-turn knowledge only, and nowhere else.

Then the declared lies are rolled as heard (adventure/rounds/lies_heard.py), each agent may react once, and after
Resolve the round's rolls move feelings (adventure/rounds/react.py). The steps are registered here, in that order.
"""
import asyncio
import re

from adventure import combat, party, story_people
from adventure.database import many
from adventure.rounds import agents, lies_heard, react
from adventure.rounds.contract import Declaration, Line, Mind, Mode, State, seat_event
from adventure.rounds.engine import Turn, register
from adventure.rounds.engine import pick as engine_pick

QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')
# Party members this warm (trust and affection added up) stay close; colder, they hang back (adventure/party.py).
HANG_BACK = 0
PARTY, NEMESIS, NAMED, REST = range(4)


# Gather -------------------------------------------------------------------------------------------------------------

def named_in(name: str, text: str) -> bool:
    return any(len(part) > 2 and re.search(rf'(?<![\w-]){re.escape(part)}(?![\w-])', text, re.I)
               for part in {name, name.split(' ')[0]})


def rank(seat, in_party: set[str], nemeses: set[str], said: str) -> tuple[int, int]:
    """Where a seat comes in the queue for the agent cap."""
    if seat.key in in_party:
        group = PARTY
    elif seat.promoted or seat.name.lower() in nemeses:
        group = NEMESIS
    else:
        group = NAMED if named_in(seat.name, said) else REST
    return group, seat.order


async def pick(turn: Turn):
    """The agents this turn, within the cap (see the module docstring)."""
    snapshot = turn.snapshot
    if not snapshot.agents():
        await engine_pick(turn)
        return
    with turn.database.connect() as connection:
        snapshot.settings['agents'] = agents.frozen(connection)
        in_party = party.keys(connection)
        nemeses = {row['name'].lower() for row in many(connection, "SELECT name FROM story_nemeses WHERE "
                                                                   "status='alive'")}
    here = set(agents.present(snapshot))
    for seat in snapshot.seats:
        if seat.mind == Mind.HUMAN and snapshot.mode != Mode.PLAY:
            seat.mind = Mind.PROGRAM
    said = str(snapshot.settings.get('said') or snapshot.settings.get('nudge') or '')
    wanting = sorted((seat for seat in snapshot.seats if seat.mind == Mind.AGENT and seat.key in here),
                     key=lambda seat: rank(seat, in_party, nemeses, said))
    for seat in wanting[snapshot.agent_cap:]:
        seat.mind = Mind.PROGRAM
    snapshot.settings['dropped'] = [seat.key for seat in wanting[snapshot.agent_cap:]]


# Program minds and the human ----------------------------------------------------------------------------------------

def program(connection, snapshot, key: str) -> Declaration:
    """A Program character's move, from Dungeon's code minds: a party member keeps close to the user's character,
    or hangs back when their feelings have cooled, and fights beside them when a fight is on; anyone else goes about
    their own business. The Writer voices them."""
    human = snapshot.human()
    lead = human.name if human else 'the others'
    if key in party.keys(connection):
        if combat.fight(connection):
            intent = f'fights beside {lead}, going for the foe worst hurt'
        elif party.warmth(story_people.known(connection), key) < HANG_BACK:
            intent = f'hangs back from {lead}, keeping their own counsel'
        else:
            intent = f'keeps close to {lead} and watches their back'
    else:
        intent = 'goes about their own business'
    return Declaration(seat=key, intent=intent)


def human(snapshot, key: str) -> Declaration:
    """The user's line in Play as a declaration: quoted speech becomes lines, the rest is the attempt."""
    said = ' '.join(str(snapshot.settings.get('said') or '').split())
    lines = [Line(first or second) for first, second in QUOTED.findall(said) if (first or second).strip()]
    intent = agents.attempt(QUOTED.sub(' ', said).strip(' ,.'))
    return Declaration(seat=key, intent=intent or ('speaks' if lines else ''), lines=lines)


# Declare ------------------------------------------------------------------------------------------------------------

async def decided(turn: Turn, key: str) -> Declaration:
    """An agent's declaration, or its Program mind's when the agent fails or refuses."""
    try:
        return (await agents.ask(turn, key, 'declare'))['declaration']
    except agents.Failed as failure:
        turn.draft.extra.setdefault('agents', {}).setdefault('fallbacks', {})[key] = failure.why
        with turn.database.connect() as connection:
            made = program(connection, turn.snapshot, key)
        made.fallback = True
        return made


def shown(turn: Turn, declaration: Declaration) -> str | None:
    """A seat's intent on the round timeline: only outside Play ("Hesk has decided" in Play)."""
    return declaration.intent if turn.snapshot.mode != Mode.PLAY else None


def motives(turn: Turn):
    """Every declared motive into its owner's in-turn knowledge, once."""
    known = {item.holder for item in turn.draft.knowledge if item.kind == 'motive' and item.source == item.holder}
    for key, declaration in turn.draft.declarations.items():
        if declaration.motive and key not in known:
            turn.draft.learn(key, 'motive', declaration.motive, source=key, importance=2)


async def declare(turn: Turn):
    """Everyone present who has no declaration yet declares; a turn with no agents is left to today's turn."""
    snapshot, draft = turn.snapshot, turn.draft
    if not snapshot.agents():
        return
    here = [snapshot.seat(key) for key in agents.present(snapshot) if key not in draft.declarations]
    thinking = [seat for seat in here if seat.mind == Mind.AGENT]
    for seat in thinking:
        await turn.emit(seat_event(seat.key, 'thinking'))
    made = dict(zip([seat.key for seat in thinking], await asyncio.gather(*(decided(turn, seat.key)
                                                                            for seat in thinking))))
    with turn.database.connect() as connection:
        for seat in here:
            if seat.mind == Mind.HUMAN:
                draft.declare(human(snapshot, seat.key))
            else:
                draft.declare(made.get(seat.key) or program(connection, snapshot, seat.key))
    motives(turn)
    for seat in thinking:
        declaration = draft.declarations[seat.key]
        await turn.emit(seat_event(seat.key, 'fallback' if declaration.fallback else 'declared',
                                   shown(turn, declaration)))


# The agents' steps, in the order they run (registering a name again replaces it in place).
register(State.GATHERING, 'pick', pick)
register(State.DECLARING, 'declare', declare)
register(State.DECLARING, 'lies', lies_heard.step)
register(State.REACTING, 'react', react.react)
register(State.WRITING, 'feelings', react.felt)
