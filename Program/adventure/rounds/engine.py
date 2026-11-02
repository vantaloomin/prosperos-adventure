"""The round loop's state machine (docs/spec.md "The turn loop", "Turn state and persistence").

A turn is opened (`begin`) at a place on the timeline, then `run` takes it through Gathering, Declaring, Reacting,
Conversing, Resolving, Writing and Committing. Each state runs the steps registered for it, in order; every step is
`async def step(turn: Turn) -> None` that reads `turn.snapshot` and writes only to `turn.draft`. The draft and the
state are saved after every step, and the round timeline hears each change (contract.round_event).

- **Steps are plugged in.** Each part of the loop registers its own (`register`): the agents' Declare and React,
  Converse, Resolve, the Writer. Registering a name again replaces that step, so a default can be swapped out. With
  nothing registered a state passes straight through.
- **Waiting.** A step that calls `turn.draft.wait_for(...)` pauses the turn in AwaitingUser after it returns: the
  reply card goes out (contract.awaiting_event) and `run` returns. `answer` takes the reply and runs the turn on from
  the step that asked, which runs again, finds the answer in `draft.replies` and carries on. Steps that pause must
  be written to run again that way.
- **Commit is one transaction.** Committing runs every commit hook (`on_commit`) in one write connection: the
  memory hook here writes each character's in-turn knowledge and feelings (adventure/rounds/memory.py); other parts
  add theirs (the record, the post). Then the turn is committed and changes queued for Idle take effect
  (adventure/rounds/seats.py). A step that fails discards the turn, so nothing half-made is kept.
- **The snapshot is frozen at Gather.** `begin` builds it from the seats and settings; the Gathering steps may add
  to it (who is present, the agents picked, the Author's nudge); after Gathering it is saved and read only.
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from adventure.database import decode
from adventure.rounds import memory, seats, turns
from adventure.rounds.contract import (
    ORDER,
    Mind,
    Mode,
    Point,
    Snapshot,
    State,
    awaiting_event,
    plain,
    round_event,
)
from adventure.rounds.draft import Draft


async def no_event(_event: dict):
    pass


@dataclass
class Turn:
    """A turn being played: `app` is the app's state (database, provider, dice), `row` its round_turns row."""
    app: Any
    row: dict
    snapshot: Snapshot
    draft: Draft
    emit: Callable[[dict], Awaitable[None]] = no_event

    @property
    def id(self) -> str:
        return self.row['id']

    @property
    def database(self):
        return self.app.database

    @property
    def point(self) -> Point:
        return self.snapshot.point


Step = Callable[[Turn], Awaitable[None]]
CommitHook = Callable[[Any, Turn], None]
STEPS: dict[State, list[tuple[str, Step]]] = {state: [] for state in ORDER if state != State.COMMITTING}
COMMITS: list[tuple[str, CommitHook]] = []


def register(state: State, name: str, step: Step):
    """Run `step` in `state`, after the steps already there; a name registered again replaces its step in place."""
    assert state in STEPS, state
    steps = STEPS[state]
    for index, (existing, _) in enumerate(steps):
        if existing == name:
            steps[index] = (name, step)
            return
    steps.append((name, step))


def unregister(state: State, name: str):
    STEPS[state][:] = [(existing, step) for existing, step in STEPS[state] if existing != name]


def on_commit(name: str, hook: CommitHook):
    """Run `hook(connection, turn)` inside Commit's one transaction; a name registered again replaces its hook."""
    for index, (existing, _) in enumerate(COMMITS):
        if existing == name:
            COMMITS[index] = (name, hook)
            return
    COMMITS.append((name, hook))


# Opening a turn -----------------------------------------------------------------------------------------------------

def snapshot_for(connection, row: dict) -> Snapshot:
    """The turn's snapshot as Gather starts it: every seat with its mind, the mode and caps in force."""
    held = seats.settings(connection)
    return Snapshot(turn_id=row['id'], mode=row['mode'], point=Point(row['branch_id'], row['seq']),
                    number=row['number'], seats=seats.seats(connection), agent_cap=held['agent_cap'],
                    converse_cap=held['converse_cap'])


async def begin(app, branch_id: str, seq: int, anchor_id: str | None = None, emit=None, mode: str | None = None,
                reask_of: str | None = None, reask_seat: str | None = None) -> Turn:
    """Open a turn at (branch, seq) in the campaign's mode (or `mode`), with its snapshot started and an empty draft."""
    database = app.database
    with database.connect(write=True) as connection:
        mode = mode or seats.settings(connection)['mode']
        row = turns.open_turn(connection, branch_id, seq, mode, database.now(), anchor_id, reask_of, reask_seat)
        snapshot = snapshot_for(connection, row)
        turns.keep(connection, row['id'], plain(snapshot), Draft().data())
    return Turn(app, row, snapshot, Draft(), emit or no_event)


def resumed(app, turn_id: str, emit=None) -> Turn:
    """A turn read back from its row: its snapshot and draft as last saved."""
    with app.database.connect() as connection:
        row = turns.get(connection, turn_id)
    return Turn(app, row, Snapshot.of(decode(row['snapshot'])), Draft.of(decode(row['draft'])), emit or no_event)


# Running it ---------------------------------------------------------------------------------------------------------

async def enter(turn: Turn, state: State):
    with turn.database.connect(write=True) as connection:
        turns.set_state(connection, turn.id, state, turn.database.now())
    turn.row = turn.row | {'state': str(state)}
    await turn.emit(round_event(turn.id, state))


def kept(turn: Turn, snapshot: bool = False):
    with turn.database.connect(write=True) as connection:
        turns.keep(connection, turn.id, plain(turn.snapshot) if snapshot else None, turn.draft.data())


async def pause(turn: Turn, state: State, step: str):
    """Stop on the reply card; `answer` runs the turn on from the step that asked."""
    turn.draft.awaiting = turn.draft.awaiting | {'state': str(state), 'step': step}
    kept(turn)
    await enter(turn, State.AWAITING_USER)
    waiting = turn.draft.awaiting
    await turn.emit(awaiting_event(waiting['seat'], waiting['speaker'], waiting['line'], waiting['context']))


async def steps_of(turn: Turn, state: State, from_step: str | None = None) -> bool:
    """Run a state's steps (from the one named `from_step`, when resuming); False when one paused the turn."""
    listed = list(STEPS[state])
    names = [name for name, _ in listed]
    for name, step in listed[names.index(from_step) if from_step in names else 0:]:
        await step(turn)
        kept(turn, snapshot=state == State.GATHERING)
        if turn.draft.awaiting is not None:
            await pause(turn, state, name)
            return False
    return True


async def run(turn: Turn, start: State = State.GATHERING, from_step: str | None = None) -> State:
    """Take the turn from `start` to Committed, or to AwaitingUser if a step pauses it. A failure discards it."""
    try:
        for state in ORDER[ORDER.index(start):]:
            await enter(turn, state)
            if state == State.COMMITTING:
                commit(turn)
                await turn.emit(round_event(turn.id, State.IDLE))
                return State.COMMITTED
            if not await steps_of(turn, state, from_step if state == start else None):
                return State.AWAITING_USER
    except BaseException as failure:
        discard(turn, str(failure) or type(failure).__name__)
        raise
    return State.COMMITTED


async def answer(turn: Turn, seat: str, reply: dict) -> State:
    """The human at `seat` answered the reply card: `reply` is {'kind': 'reply'|'silent'|'let_answer', 'text': ...}."""
    waiting = turn.draft.awaiting
    assert waiting is not None and waiting['seat'] == seat, 'The turn is not waiting on that seat.'
    turn.draft.replies[seat] = reply | {'line': waiting['line'], 'speaker': waiting['speaker']}
    turn.draft.awaiting = None
    return await run(turn, State(waiting['state']), waiting.get('step'))


def commit(turn: Turn):
    """Write the turn in one transaction: every commit hook, then the turn's state, then what waited for Idle."""
    database = turn.database
    with database.connect(write=True) as connection:
        for _, hook in list(COMMITS):
            hook(connection, turn)
        turns.keep(connection, turn.id, draft=turn.draft.data())
        turns.set_state(connection, turn.id, State.COMMITTED, database.now())
        seats.apply_queued(connection)
    turn.row = turn.row | {'state': str(State.COMMITTED)}


def discard(turn: Turn, error: str | None = None):
    with turn.database.connect(write=True) as connection:
        turns.discard(connection, turn.id, error)
        seats.apply_queued(connection)
    turn.row = turn.row | {'state': str(State.DISCARDED)}


# The steps the foundation itself provides ---------------------------------------------------------------------------

async def pick(turn: Turn):
    """Who decides how this turn, within the cap. The default: seats in order until the cap is reached; the human
    sits only in Play (in Author and Watch their character runs on its Program mind until the user picks otherwise).
    Agent selection by party, nemesis, promotion and role replaces this ('pick')."""
    agents = 0
    for seat in turn.snapshot.seats:
        if seat.mind == Mind.HUMAN and turn.snapshot.mode != Mode.PLAY:
            seat.mind = Mind.PROGRAM
        elif seat.mind == Mind.AGENT:
            agents += 1
            if agents > turn.snapshot.agent_cap:
                seat.mind = Mind.PROGRAM


def committed_memory(connection, turn: Turn):
    """Each character's in-turn knowledge becomes their memory; feelings moved and memories brought back are kept."""
    now = turn.database.now()
    for item in turn.draft.knowledge:
        memory.remember(connection, turn.row, item.holder, item.kind, item.text, about=item.about, source=item.source,
                        weight=item.importance, now=now)
    for change in turn.draft.feelings:
        memory.feel(connection, turn.row, change['from'], change['to'], change['changes'], change.get('why', ''), now)
    for item in turn.draft.refreshed:
        memory.brought_back(connection, turn.row, item['memory_id'])


register(State.GATHERING, 'pick', pick)
on_commit('memory', committed_memory)

# Who may read what: the context builders' own Gathering step (adventure/rounds/context.py `privacy`).
from adventure.rounds import context  # noqa: E402,F401
