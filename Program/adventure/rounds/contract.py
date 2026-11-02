"""What every part of the round loop agrees on (docs/spec.md "The turn loop", "Agent output", "Turn state and
persistence").

A round runs Idle → Gathering → Declaring → Reacting → Conversing ⇄ AwaitingUser → Resolving → Writing → Committing
→ Idle. These are the shapes passed between its steps, kept as plain dataclasses so a turn's snapshot and draft are
JSON in `round_turns` and a restart can pick them up again:

- `Seat`: who sits at the table and how they decide (an agent, a Program mind, or the human).
- `Declaration`: what one character gives back in Declare (and again, changed, in React): the attempt, the lines
  said aloud, the private motive, each lie as a field, and whispers. Code validates it; nobody's success is in it.
- `Knowledge`: one thing one character learned this turn, and how (saw, heard, believed, caught a tell, whispered
  to, their own motive). Code decides every holder; Commit turns each into that character's memory.
- `Snapshot`: what the turn was built from, frozen at Gather, so re-asking reads exactly what the turn read.
- `Brief` and `TurnResult`: Resolve's output, which the Writer renders. Who saw and heard what is not in it: every
  step adds that to the draft's knowledge (adventure/rounds/draft.py), which Commit writes.

Stream events (`round_event`, `seat_event`, `awaiting_event`) go out beside the ones today's turn already sends
(adventure/story_routes.py `streamed`).
"""
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum


class State(StrEnum):
    IDLE = 'idle'
    GATHERING = 'gathering'
    DECLARING = 'declaring'
    REACTING = 'reacting'
    CONVERSING = 'conversing'
    AWAITING_USER = 'awaiting_user'
    RESOLVING = 'resolving'
    WRITING = 'writing'
    COMMITTING = 'committing'
    # Where a turn ends up: written in one transaction, or thrown away (cancelled, or left open by a restart).
    COMMITTED = 'committed'
    DISCARDED = 'discarded'


# The steps a turn goes through, in order. AwaitingUser is entered from Conversing (or before Resolving, for the one
# question an ambiguous move gets) and goes back to the step that asked.
ORDER = (State.GATHERING, State.DECLARING, State.REACTING, State.CONVERSING, State.RESOLVING, State.WRITING,
         State.COMMITTING)


class Mode(StrEnum):
    PLAY = 'play'
    AUTHOR = 'author'
    WATCH = 'watch'


class Mind(StrEnum):
    AGENT = 'agent'
    PROGRAM = 'program'
    HUMAN = 'human'


KNOWLEDGE_KINDS = ('witnessed', 'heard', 'told', 'belief', 'tell', 'motive', 'whisper', 'fact')
SEAT_STATUSES = ('thinking', 'declared', 'reacting', 'done', 'fallback')


def built(kind, data: dict | None):
    """A dataclass from its JSON form, ignoring keys it doesn't have (a newer draft read by older code)."""
    data = data or {}
    names = {item.name for item in fields(kind)}
    return kind(**{key: value for key, value in data.items() if key in names})


@dataclass
class Seat:
    key: str
    name: str
    mind: str = Mind.PROGRAM
    order: int = 0
    # A model profile for this character alone, over the agents' role.
    model_profile_id: str | None = None
    notes: str = ''
    promoted: bool = False


@dataclass
class Line:
    """Something said aloud; `to` names who it is said to (empty: everyone present)."""
    text: str
    to: list[str] = field(default_factory=list)


@dataclass
class Deception:
    """A lie, declared as one: what is claimed, what the speaker believes is true, and who it is aimed at. Code rolls
    each listener's insight against it; a line with no deception is honest as far as the speaker knows."""
    claim: str
    believed: str
    aimed_at: list[str] = field(default_factory=list)


@dataclass
class Whisper:
    text: str
    to: list[str] = field(default_factory=list)


@dataclass
class Declaration:
    seat: str
    intent: str = ''
    lines: list[Line] = field(default_factory=list)
    motive: str = ''
    deceptions: list[Deception] = field(default_factory=list)
    whispers: list[Whisper] = field(default_factory=list)
    # Made by the character's Program mind because its agent failed, timed out or refused this turn.
    fallback: bool = False

    @classmethod
    def of(cls, data: dict) -> 'Declaration':
        made = built(cls, data)
        made.lines = [built(Line, item) for item in data.get('lines', [])]
        made.deceptions = [built(Deception, item) for item in data.get('deceptions', [])]
        made.whispers = [built(Whisper, item) for item in data.get('whispers', [])]
        return made


@dataclass
class Knowledge:
    """One thing `holder` learned this turn. `kind` is one of KNOWLEDGE_KINDS; `source` is whose line or act it came
    from, `about` whom it concerns; `importance` 1 to 3 decides how soon it fades (3 never does)."""
    holder: str
    kind: str
    text: str
    source: str = ''
    about: str = ''
    importance: int = 1


@dataclass
class Point:
    """A place on the timeline: what was committed before `seq` on `branch` and its ancestors."""
    branch: str
    seq: int


@dataclass
class Snapshot:
    turn_id: str
    mode: str
    point: Point
    # The number of committed turns before this one on its branch: memory's age is counted in these.
    number: int
    seats: list[Seat] = field(default_factory=list)
    present: list[str] = field(default_factory=list)
    agent_cap: int = 6
    converse_cap: int = 4
    # Settings in force for the turn (intensity, veils, dials, the Author's nudge): whatever the steps need frozen.
    settings: dict = field(default_factory=dict)

    @classmethod
    def of(cls, data: dict) -> 'Snapshot':
        made = built(cls, data)
        made.point = built(Point, data.get('point'))
        made.seats = [built(Seat, item) for item in data.get('seats', [])]
        return made

    def seat(self, key: str) -> Seat | None:
        return next((seat for seat in self.seats if seat.key == key), None)

    def agents(self) -> list[Seat]:
        return [seat for seat in self.seats if seat.mind == Mind.AGENT]

    def human(self) -> Seat | None:
        return next((seat for seat in self.seats if seat.mind == Mind.HUMAN), None)


@dataclass
class Brief:
    """What the Writer must render (spec "The turn brief and the stop point")."""
    when: str = ''
    where: str = ''
    beats: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    math: list[str] = field(default_factory=list)
    stop_point: str = ''


@dataclass
class TurnResult:
    """Resolve's immutable output: the declarations as they stood, the rolls (as adventure/turn.py keeps them), each
    outcome, and the brief. The Writer renders it; Commit writes the record from it."""
    declarations: list[Declaration] = field(default_factory=list)
    rolls: list[dict] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)
    brief: Brief = field(default_factory=Brief)

    @classmethod
    def of(cls, data: dict) -> 'TurnResult':
        made = built(cls, data)
        made.declarations = [Declaration.of(item) for item in data.get('declarations', [])]
        made.brief = built(Brief, data.get('brief'))
        return made


def plain(value) -> dict:
    """A contract dataclass as JSON-ready data."""
    return asdict(value)


# Stream events ------------------------------------------------------------------------------------------------------

def round_event(turn_id: str, state: str) -> dict:
    return {'round': {'turn_id': turn_id, 'state': str(state)}}


def seat_event(key: str, status: str, intent: str | None = None) -> dict:
    """A character's row on the round timeline. `intent` only where the mode shows it (never in Play)."""
    assert status in SEAT_STATUSES, status
    return {'seat': {'key': key, 'status': status} | ({'intent': intent} if intent is not None else {})}


def awaiting_event(seat: str, speaker: str, line: str, context: list[str]) -> dict:
    """The reply card: `speaker` addressed the human at `seat`; the last two lines of context come with it."""
    return {'awaiting': {'seat': seat, 'speaker': speaker, 'line': line, 'context': context[-2:]}}
