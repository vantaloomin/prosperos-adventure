"""The modes' API (adventure/rounds/modes.py, author.py, watch.py; docs/spec.md Batch 3, "Waiting and pauses").

- `/api/rounds/mode`: switch modes (at the next Idle when a turn is under way), with who plays the user's character
  outside Play and, on leaving Play, whether to see the motives missed.
- `/api/rounds/author`: the beat board, the nudge box and the newest turn's feedback.
- `/api/rounds/watch`: the timer, why it is paused, Continue, and the timer's own Next.

Next by hand in Author and Watch, the reply card and re-asking stay where they are (adventure/round_routes.py).
"""
from fastapi import APIRouter, Request
from pydantic import Field

from adventure import plotting
from adventure.errors import require
from adventure.models import Input
from adventure.round_routes import AGAINST, done
from adventure.round_routes import view as table_view
from adventure.rounds import author, modes, play, queue, turns, watch
from adventure.rounds.contract import Mind, Mode
from adventure.story_routes import streamed

router = APIRouter(prefix='/api/rounds')


def modes_view(connection) -> dict:
    return {'settings': modes.settings(connection), 'coming': modes.coming(connection),
            'switches': modes.asked(connection)}


@router.get('/mode')
def read_mode(request: Request):
    with request.app.state.database.connect() as connection:
        return modes_view(connection) | {'table': table_view(connection)}


class ModeSwitch(Input):
    mode: Mode
    stand_in: Mind | None = None
    reveal: bool = False


@router.put('/mode')
def switch(request: Request, body: ModeSwitch):
    """Switch modes. Leaving Play, `reveal` says whether to see the motives missed (hidden unless asked)."""
    database = request.app.state.database
    require(body.stand_in in (None, Mind.AGENT, Mind.PROGRAM), 'Outside Play your character runs on an agent or '
            'its Program mind.', 422)
    with database.connect(write=True) as connection:
        modes.switch(connection, body.mode, database.now(), turns.under_way(connection) is not None,
                     body.stand_in, body.reveal)
        return modes_view(connection) | {'table': table_view(connection)}


class ModeSettings(Input):
    stand_in: Mind | None = None
    watch_seconds: int | None = Field(None, ge=0, le=3600)


@router.put('/mode/settings')
def change_settings(request: Request, body: ModeSettings):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        modes.change(connection, body.model_dump(), database.now())
        return modes_view(connection)


# Author -------------------------------------------------------------------------------------------------------------

@router.get('/author')
def read_author(request: Request):
    with request.app.state.database.connect() as connection:
        return author.view(connection)


class Beat(Input):
    text: str = Field(min_length=1, max_length=300)


@router.post('/author/box')
def add_to_box(request: Request, body: Beat):
    """A beat the user would like to see, beside their line in Play."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        require(modes.coming(connection) == Mode.PLAY, 'In Author, nudge the story with Next.', 409)
        author.add_to_box(connection, body.text, database.now())
        return author.view(connection)


@router.delete('/author/box/{beat_id}')
def take_from_box(request: Request, beat_id: str):
    with request.app.state.database.connect(write=True) as connection:
        author.take_from_box(connection, beat_id)
        return author.view(connection)


class PlannedBeat(Input):
    arc_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=300)


@router.post('/author/beats')
def add_beat(request: Request, body: PlannedBeat):
    with request.app.state.database.connect(write=True) as connection:
        require(author.editable(connection), 'Switch to Author to add beats to the plan.', 409)
        plotting.add_beat(connection, body.arc_id, body.text)
        return author.view(connection)


class BeatChange(Input):
    cut: bool | None = None
    position: int | None = Field(None, ge=0, le=20)


@router.patch('/author/beats/{beat_id}')
def change_beat(request: Request, beat_id: str, body: BeatChange):
    """Cut a planned beat, bring it back, or move it in its arc's order."""
    with request.app.state.database.connect(write=True) as connection:
        plotting.change_beat(connection, beat_id, body.cut, body.position, gated=not author.editable(connection))
        return author.view(connection)


# Watch --------------------------------------------------------------------------------------------------------------

@router.get('/watch')
def read_watch(request: Request):
    state = request.app.state
    with state.database.connect() as connection:
        return watch.view(state, connection)


class Against(Input):
    against: str | None = AGAINST


@router.post('/watch/continue')
def go_on(request: Request, body: Against):
    """Go on from a pause: the timer runs again from the newest turn."""
    state = request.app.state
    with state.database.connect(write=True) as connection:
        head = queue.head(connection)
        require(head is not None and head == body.against, 'The story moved on since this was sent. Reload to see '
                'where it is.', 409, 'stale')
        watch.go_on(connection, head, state.database.now())
        return watch.view(state, connection)


@router.post('/watch/next/stream')
async def timer_next(request: Request, body: Against):
    """The timer's Next: a Watch turn, unless a big moment or the session cap paused it."""
    state = request.app.state

    async def turn(on_text, on_event):
        async def checked():
            watch.check_timer(state)
            return await done(state, play.next_turn(state, '', on_event, on_text))
        return await queue.play(state, checked, body.against)
    return streamed(state, turn)
