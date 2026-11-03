"""The GM view in round play (adventure/gm.py `open_round`): the turn behind the story, asking first in Play, and
the turns it was open on; and the minds panel, which shows by mode (adventure/gm.py `minds_panel`)."""
from fastapi import APIRouter, Request

from adventure import gm
from adventure.models import Input
from adventure.rounds import context

router = APIRouter()


class Missed(Input):
    # The answer to "Show the motives you missed?" on leaving Play: Show (true) or Keep hidden (false).
    reveal: bool


class Opening(Input):
    # Yes to "This shows every secret and motive. Open anyway?", and whether to remember it for this campaign.
    confirmed: bool = False
    remember: bool = False


@router.post('/api/gm/round')
def open_round(request: Request, body: Opening):
    """409 with code gm_view_asks_first while Play still needs the user's yes."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        return gm.open_round(connection, database.now(), body.confirmed, body.remember)


@router.get('/api/gm/round/marks')
def marks(request: Request):
    with request.app.state.database.connect() as connection:
        return {'marked': gm.marked(connection)}


@router.get('/api/minds')
def minds(request: Request):
    """Each character's mind and status on the watched turn; intents and motives only where the mode shows them."""
    with request.app.state.database.connect() as connection:
        return gm.minds_panel(connection)


@router.put('/api/minds/reveal_missed')
def reveal_missed(request: Request, body: Missed):
    """Kept for the campaign: GET /api/minds then shows `reveal_missed` as this, not null, so it is asked only once."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        context.set_reveal_missed(connection, body.reveal, database.now())
        return gm.minds_panel(connection)
