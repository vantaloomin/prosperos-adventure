"""Worlds and personas (dungeon/worlds.py): /api/worlds."""
from fastapi import APIRouter, Request

from dungeon import legacy, worlds
from dungeon.models import HomeChange, NewPersona, NewWorld, PersonaInput, WorldChange

router = APIRouter(prefix='/api/worlds')


def db(request: Request):
    return request.app.state.database


@router.get('')
def listing(request: Request):
    """Every persona with their worlds, and which world the user is in."""
    return worlds.view(db(request))


@router.post('')
def create_world(request: Request, body: NewWorld):
    """A new world, ready at once. It does not switch to it."""
    return worlds.create_world(db(request), body.persona_id, body.name, body.city_id)


@router.patch('/{world_id}')
def change_world(request: Request, world_id: str, body: WorldChange):
    return worlds.update_world(db(request), world_id, body)


@router.get('/{world_id}/home')
def home(request: Request, world_id: str, city_id: str | None = None):
    """Where the persona lives in this world, the cities they can live in and the neighbourhoods of `city_id`."""
    return worlds.home_choices(db(request), world_id, city_id)


@router.put('/{world_id}/home')
def change_home(request: Request, world_id: str, body: HomeChange):
    return worlds.change_home(db(request), world_id, body)


@router.delete('/{world_id}')
def delete_world(request: Request, world_id: str):
    """The world and everything in it, after a backup kept in Settings > Data."""
    return worlds.delete_world(db(request), world_id)


@router.post('/{world_id}/switch')
async def switch_world(request: Request, world_id: str):
    """Runs on the event loop, so nothing else the app does starts halfway through the switch."""
    return worlds.switch(request.app.state, world_id)


@router.post('/personas')
def create_persona(request: Request, body: NewPersona):
    """A new persona with a world of their own, in the city they picked. It does not switch to them."""
    return worlds.create_persona(db(request), body)


@router.patch('/personas/{persona_id}')
def change_persona(request: Request, persona_id: str, body: PersonaInput):
    return worlds.update_persona(db(request), persona_id, body)


@router.delete('/personas/{persona_id}')
def delete_persona(request: Request, persona_id: str):
    return worlds.delete_persona(db(request), persona_id)


@router.post('/personas/{persona_id}/switch')
async def switch_persona(request: Request, persona_id: str):
    """Into the world the persona was last in."""
    return worlds.switch_persona(request.app.state, persona_id)


@router.post('/import')
async def import_campaign(request: Request):
    """A campaign file (dungeon/legacy.py), sent as the request's body, as a new world."""
    return legacy.import_campaign(db(request), await request.body())
