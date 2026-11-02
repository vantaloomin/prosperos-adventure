"""The agents' settings API (adventure/rounds/agents.py): the preset with its estimate, the scheming and loyalty
dials, and the session's spend against its cap."""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import Field

from adventure import pace
from adventure.models import Input
from adventure.rounds import agents, seats
from adventure.rounds.contract import Mind

router = APIRouter(prefix='/api/agents')


class AgentSettingsUpdate(Input):
    preset: Literal['quick', 'balanced', 'rich'] | None = None
    scheming: int | None = Field(None, ge=0, le=3)
    loyalty: Literal['slow', 'steady', 'fast'] | None = None
    session_cap: int | None = Field(None, ge=0)


def shown(database, connection) -> dict:
    """The settings, each preset's estimate for the agents at the table (up to the cap), and the session's spend."""
    held = seats.settings(connection)
    sitting = sum(1 for seat in seats.seats(connection) if seat.mind == Mind.AGENT)
    found = agents.view(connection, min(sitting, held['agent_cap']), held['converse_cap'])
    return found | {'spend': pace.spend_for(database).view(found['session_cap']),
                    'capped': pace.capped(database, found['session_cap'])}


@router.get('')
def read(request: Request):
    database = request.app.state.database
    with database.connect() as connection:
        return shown(database, connection)


@router.put('')
def change(request: Request, body: AgentSettingsUpdate):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        agents.change(connection, body.model_dump(exclude_none=True), database.now())
        return shown(database, connection)
