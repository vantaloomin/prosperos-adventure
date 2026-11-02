"""The round loop's API (adventure/rounds/; docs/spec.md "Turn state and persistence", "Waiting and pauses").

Everything that starts or continues a turn goes through the one-writer queue (adventure/rounds/queue.py) and may
say which turn it was issued against (`against`), so a second tab or a late click is refused as stale instead of
acting on a turn that has moved on. Turns stream as today's story turn does (adventure/story_routes.py `streamed`),
with the round timeline's events among the rest. Settings and seats can change at any time: while a turn is under
way, mode and cap changes wait for the next Idle.
"""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import Field

from adventure.database import decode
from adventure.errors import require
from adventure.models import Input
from adventure.rounds import overrides, play, queue, seats, turns
from adventure.rounds.contract import Mind, Mode, plain
from adventure.story_routes import streamed

router = APIRouter(prefix='/api/rounds')
AGAINST = Field(None, max_length=64)


def view(connection) -> dict:
    """The table as it stands: settings (with what waits for Idle), seats, the turn under way and the newest turn."""
    open_turn = turns.under_way(connection)
    return {'settings': seats.settings(connection), 'seats': [plain(seat) for seat in seats.seats(connection)],
            'under_way': turn_view(open_turn) if open_turn else None, 'head': queue.head(connection)}


def turn_view(row: dict) -> dict:
    """A turn's state and marks; what it holds is shown through the readers' own views, never raw here."""
    draft = decode(row['draft']) or {}
    waiting = draft.get('awaiting')
    return {'id': row['id'], 'state': row['state'], 'mode': row['mode'], 'marks': decode(row['marks']) or [],
            'reask_of': row['reask_of'], 'reask_seat': row['reask_seat'], 'error': row['error'],
            'awaiting': {key: waiting[key] for key in ('seat', 'speaker', 'line', 'context')} if waiting else None}


@router.get('')
def read(request: Request):
    with request.app.state.database.connect() as connection:
        return view(connection)


class SettingsChange(Input):
    mode: Mode | None = None
    agent_cap: int | None = Field(None, ge=1, le=6)
    converse_cap: int | None = Field(None, ge=1, le=12)


@router.put('/settings')
def change_settings(request: Request, body: SettingsChange):
    with request.app.state.database.connect(write=True) as connection:
        changes = {key: value for key, value in body.model_dump().items() if value is not None}
        seats.change(connection, changes, under_way=turns.under_way(connection) is not None)
        return view(connection)


class SeatChange(Input):
    name: str = Field(min_length=1, max_length=120)
    mind: Mind | None = None
    order: int | None = Field(None, ge=0, le=999)
    model_profile_id: str | None = Field(None, max_length=64)
    notes: str | None = Field(None, max_length=600)
    promoted: bool | None = None


@router.put('/seats/{key}')
def change_seat(request: Request, key: str, body: SeatChange):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        changes = {name: value for name, value in body.model_dump().items() if value is not None and name != 'name'}
        seats.set_seat(connection, key, body.name, database.now(), **changes)
        return view(connection)


@router.delete('/seats/{key}')
def remove_seat(request: Request, key: str):
    with request.app.state.database.connect(write=True) as connection:
        seats.remove_seat(connection, key)
        return view(connection)


@router.get('/turns/{turn_id}')
def read_turn(request: Request, turn_id: str):
    with request.app.state.database.connect() as connection:
        return turn_view(turns.get(connection, turn_id))


class NextTurn(Input):
    against: str | None = AGAINST
    nudge: str = Field('', max_length=4000)


@router.post('/turns/stream')
async def next_turn(request: Request, body: NextTurn):
    """Next: a turn in Author (with the nudge) or Watch. Play turns are the player's lines (/api/story/messages)."""
    state = request.app.state
    with state.database.connect() as connection:
        require(seats.settings(connection)['mode'] != Mode.PLAY, 'In Play, a turn starts with your line.', 409)
    return streamed(state, lambda on_text, on_event: queue.play(
        state, lambda: done(state, play.next_turn(state, body.nudge, on_event, on_text)), body.against))


class Reply(Input):
    against: str | None = AGAINST
    seat: str = Field(min_length=1, max_length=200)
    kind: Literal['reply', 'silent', 'let_answer']
    text: str = Field('', max_length=4000)


@router.post('/turns/{turn_id}/reply/stream')
async def reply(request: Request, turn_id: str, body: Reply):
    """The reply card's answer: Reply, Say nothing, or Let my character answer (for this one line)."""
    state = request.app.state
    require(body.kind != 'reply' or body.text.strip(), 'Write a reply, or pick Say nothing.', 422)
    answer = {'kind': body.kind, 'text': body.text.strip()}
    return streamed(state, lambda on_text, on_event: queue.play(
        state, lambda: done(state, play.reply(state, turn_id, body.seat, answer, on_event, on_text)), body.against))


class Reask(Input):
    against: str | None = AGAINST
    seat: str = Field(min_length=1, max_length=200)


@router.post('/turns/{turn_id}/reask/stream')
async def reask(request: Request, turn_id: str, body: Reask):
    """Ask one agent to decide again: the turn is played again on a new branch."""
    state = request.app.state
    return streamed(state, lambda on_text, on_event: queue.play(
        state, lambda: done(state, play.reask(state, turn_id, body.seat, on_event, on_text)), body.against))


class Override(Input):
    band: Literal['critical_failure', 'failure', 'failure_upside', 'success_cost', 'success', 'critical_success']
    reason: str = Field(min_length=1, max_length=300)


@router.post('/turns/{turn_id}/rolls/{position}/override')
async def override_roll(request: Request, turn_id: str, position: int, body: Override):
    """From the GM view: one roll of a turn lands on another band, logged with why (adventure/rounds/overrides.py)."""
    state = request.app.state

    async def work():
        with state.database.connect(write=True) as connection:
            return overrides.override(connection, turn_id, position, body.band, body.reason, state.database.now())
    logged = await queue.play(state, work)
    with state.database.connect() as connection:
        return {'override': logged, 'turn': turn_view(turns.get(connection, turn_id))}


@router.post('/turns/{turn_id}/cancel')
def cancel(request: Request, turn_id: str):
    """Cancel the turn under way at once: its draft is thrown away and nothing it made is kept."""
    state = request.app.state
    require(queue.cancel(state, turn_id), 'That turn is not being played.', 409, 'stale')
    with state.database.connect() as connection:
        return view(connection)


async def done(state, playing) -> dict:
    """What a stream ends with: the turn's row as it stands, and the table."""
    row = await playing
    with state.database.connect() as connection:
        return {'turn': turn_view(turns.get(connection, row['id']))} | view(connection)
