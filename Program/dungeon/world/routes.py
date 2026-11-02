"""World data API: the built-in and user cities, the generators built on them, and the city builder."""
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import Field

from dungeon import travel, world_select
from dungeon.clock import zone
from dungeon.errors import require
from dungeon.models import Input
from dungeon.world import catalog, changes, custom, generators, marinara, townsfolk
from dungeon.world.schema import PlaceKind
from dungeon.world.source import CatalogWorld

router = APIRouter(prefix='/api/world')
Company = Literal['solo', 'friends', 'date', 'family', 'coworkers']
DayPart = Literal['morning', 'afternoon', 'evening', 'late']
Cost = Literal['free', '$', '$$', '$$$', '$$$$']


class CityRevision(Input):
    definition: dict
    expected_revision: int = Field(ge=1)


class CityCopy(Input):
    id: str = Field(pattern=r'^[a-z0-9]+(-[a-z0-9]+)*$', max_length=80)
    name: str = Field(min_length=1, max_length=400)


class CityChange(Input):
    kind: Literal['opening', 'closing', 'renovation', 'roadworks']
    starts_on: date
    ends_on: date | None = None
    place_id: str | None = Field(None, max_length=80)
    neighborhood: str | None = Field(None, max_length=80)
    name: str | None = Field(None, min_length=1, max_length=120)
    place_kind: PlaceKind | None = None
    summary: str = Field('', max_length=300)
    delay: int | None = Field(None, ge=1, le=60)


def user_cities(request: Request) -> dict[str, dict]:
    return custom.read(request.app.state.database)


def city(request: Request, city_id: str, day: date | None = None) -> dict:
    """A city; with `day`, as it stands that day after its changes (closures, openings, road works)."""
    data = catalog.city(city_id, user_cities(request))
    return CatalogWorld(request.app.state.database).find(city_id, day) if day else data


@router.get('/cities')
def list_cities(request: Request):
    """Every city, each with the world package it belongs to (the travel map it is on), or none for a city on its
    own, so the Worlds page can show only the open world's cities."""
    homes = {node['city']: travel_map['world'] for travel_map in travel.maps() if travel_map.get('world')
             for node in travel_map['nodes'] if node.get('city')}
    names = {world: world_select.settings(request.app.state.database.root, world).get('name') or world.title()
             for world in set(homes.values())}
    return [catalog.summary(data) | {'world': homes.get(data['id']), 'world_name': names.get(homes.get(data['id']))}
            for data in [*catalog.cities().values(), *user_cities(request).values()]]


@router.get('/featured')
def read_featured(request: Request):
    return catalog.featured(user_cities(request))


@router.get('/broken-cities')
def list_broken_cities(request: Request):
    """The user's cities that no longer load, so Settings can offer to save or delete them."""
    return custom.broken(request.app.state.database)


@router.get('/careers')
def list_careers():
    return list(catalog.careers().values())


@router.get('/resolve')
def resolve(request: Request, text: str = Query(max_length=200)):
    return {'match': catalog.resolve(text, user_cities(request))}


@router.get('/packs')
def read_packs():
    return catalog.packs()


@router.post('/packs/reload')
def reload_packs():
    return catalog.reload()


@router.get('/template')
def read_template(request: Request):
    return custom.template(request.app.state.database.now()[:10])


@router.post('/validate')
def validate(definition: dict):
    data = custom.check(definition)
    return {'valid': True, 'data_version': data['data_version'], 'summary': catalog.summary(data)}


@router.post('/cities')
def create_city(request: Request, definition: dict):
    return custom.create(request.app.state.database, definition)


@router.post('/import/marinara')
def import_marinara(request: Request, value: dict):
    """A Marinara world map, its pictures already left out by the page, becomes a city and world lore at once."""
    return marinara.bring(request.app.state.database, value)


@router.get('/cities/{city_id}')
def read_city(request: Request, city_id: str):
    return city(request, city_id)


@router.put('/cities/{city_id}')
def update_city(request: Request, city_id: str, body: CityRevision):
    return custom.update(request.app.state.database, city_id, body.definition, body.expected_revision)


@router.delete('/cities/{city_id}')
def delete_city(request: Request, city_id: str):
    custom.delete(request.app.state.database, city_id)
    return {'deleted': city_id}


@router.post('/cities/{city_id}/copy')
def copy_city(request: Request, city_id: str, body: CityCopy):
    return custom.copy(request.app.state.database, city_id, body.id, body.name)


@router.get('/cities/{city_id}/careers')
def list_city_careers(request: Request, city_id: str):
    return list(catalog.careers_for(city(request, city_id)).values())


@router.get('/cities/{city_id}/sources')
def read_sources(request: Request, city_id: str):
    return catalog.sources(city(request, city_id))


@router.get('/cities/{city_id}/places')
def list_places(request: Request, city_id: str, kind: str | None = None, neighborhood: str | None = None,
                tag: str | None = None, good_for: Company | None = None):
    return catalog.places(city(request, city_id), kind=kind, neighborhood=neighborhood, tag=tag, good_for=good_for)


def town(request: Request, data: dict) -> dict:
    """The city as this world's townsfolk live in it: each world seeds its own town."""
    from dungeon import story
    with request.app.state.database.connect() as connection:
        seed = story.town_seed(connection)
        return data | {'kin': [], 'town': seed, 'you': story.you(connection, seed), 'kept': ()}


@router.get('/cities/{city_id}/places/{place_id}/people')
def place_people(request: Request, city_id: str, place_id: str, on: date | None = None,
                 at: str = Query('12:00', pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')):
    """The townsfolk seeded at a place (dungeon/world/townsfolk.py): everything about them, how their goal
    stands on `on` (default today) and where their rules put them at `at` that day. The companion only
    learns this a little at a time; this is the city's own view."""
    data = town(request, city(request, city_id))
    day = on or request.app.state.database.clock.now().date()
    moment = datetime.combine(day, time.fromisoformat(at))
    result = []
    for sheet in townsfolk.at_place(data, place_id, day):
        result.append({**sheet, 'flaw_text': townsfolk.FLAWS[sheet['flaw']][0],
                       'desire_text': townsfolk.DESIRES[sheet['desire']], 'routine': townsfolk.routine_text(sheet),
                       'story': townsfolk.story(sheet, data, day), 'now': townsfolk.whereabouts(sheet, data, moment)})
    require(result or catalog.find(data, place_id) is not None, 'No such place in this city.', 404)
    return result


@router.get('/cities/{city_id}/neighborhoods/{hood_id}/people')
def neighborhood_people(request: Request, city_id: str, hood_id: str, on: date | None = None,
                        at: str = Query('12:00', pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')):
    """A neighborhood's ordinary residents (dungeon/world/townsfolk.py), with where their rules put them at
    `at` on `on` (default today)."""
    data = town(request, city(request, city_id))
    require(any(hood['id'] == hood_id for hood in data['neighborhoods']), 'No such neighborhood in this city.', 404)
    day = on or request.app.state.database.clock.now().date()
    moment = datetime.combine(day, time.fromisoformat(at))
    return [{**sheet, 'flaw_text': townsfolk.FLAWS[sheet['flaw']][0], 'desire_text': townsfolk.DESIRES[sheet['desire']],
             'routine': townsfolk.routine_text(sheet), 'story': townsfolk.story(sheet, data, day),
             'now': townsfolk.whereabouts(sheet, data, moment)} for sheet in townsfolk.residents(data, hood_id, day=day)]


@router.get('/cities/{city_id}/conditions')
def read_conditions(request: Request, city_id: str, day: date, seed: str = ''):
    data = city(request, city_id)
    return {'conditions': generators.conditions(data, day, seed), 'annual_events': generators.annual_events(data, day),
            'holidays': generators.holidays(data, day)}


@router.get('/cities/{city_id}/holidays')
def list_holidays(request: Request, city_id: str, start: date, end: date | None = None):
    return {'calendar': catalog.calendar_id(city(request, city_id)),
            'holidays': generators.holidays(city(request, city_id), start, end)}


@router.get('/cities/{city_id}/commute')
def read_commute(request: Request, city_id: str, origin: str = Query(alias='from'),
                 destination: str = Query(alias='to'), mode: str | None = None, day: date | None = None):
    return generators.commute(city(request, city_id, day), origin, destination, mode)


@router.get('/cities/{city_id}/generate/outing')
def generate_outing(request: Request, city_id: str, seed: str, day: date | None = None,
                    day_part: DayPart = 'afternoon', company: Company = 'solo', neighborhood: str | None = None,
                    home: str | None = None, budget: Cost | None = None, kind: list[str] | None = Query(default=None),
                    exclude: list[str] = Query(default=[])):
    return {'outing': generators.outing(city(request, city_id, day), seed=seed, day=day, day_part=day_part,
                                        company=company, neighborhood=neighborhood, home=home, budget=budget,
                                        kinds=kind, exclude=exclude)}


@router.get('/cities/{city_id}/generate/meal')
def generate_meal(request: Request, city_id: str, seed: str, meal: str = 'dinner', day: date | None = None,
                  company: Company = 'solo', neighborhood: str | None = None, home: str | None = None,
                  budget: Cost | None = None, exclude: list[str] = Query(default=[])):
    return {'outing': generators.meal(city(request, city_id, day), seed=seed, meal=meal, day=day, company=company,
                                      neighborhood=neighborhood, home=home, budget=budget, exclude=exclude)}


@router.get('/cities/{city_id}/generate/job')
def generate_job(request: Request, city_id: str, career: str, seed: str, home: str | None = None):
    return generators.job(city(request, city_id), career, seed=seed, home=home)


@router.get('/cities/{city_id}/generate/home')
def generate_home(request: Request, city_id: str, seed: str, bedrooms: str = 'one_bedroom',
                  budget: int | None = Query(None, gt=0), vibe: str | None = None, near: str | None = None):
    return generators.home(city(request, city_id), seed=seed, bedrooms=bedrooms, budget=budget, vibe=vibe,
                           near=near)


Role = Literal['close-friend', 'friend', 'coworker', 'neighbor', 'old-classmate', 'mentor', 'sibling', 'parent',
               'cousin']


@router.get('/cities/{city_id}/generate/resident')
def generate_resident(request: Request, city_id: str, seed: str, role: Role = 'friend', career: str | None = None,
                      age: int | None = Query(None, ge=16, le=100), near: str | None = None,
                      employer: str | None = None, family: str | None = None, group: str | None = None,
                      local: bool = True):
    return generators.resident(city(request, city_id), seed=seed, role=role, career=career, age=age, near=near,
                               employer=employer, family=family, group=group, local=local)


@router.get('/cities/{city_id}/generate/circle')
def generate_circle(request: Request, city_id: str, seed: str, size: int = Query(6, ge=1, le=12),
                    home: str | None = None, age: int | None = Query(None, ge=16, le=100),
                    career: str | None = None, employer: str | None = None, family: str | None = None,
                    group: str | None = None):
    return generators.circle(city(request, city_id), seed=seed, size=size, home=home, age=age, career=career,
                             employer=employer, family=family, group=group)


@router.get('/names')
def read_names():
    return catalog.names()


@router.get('/cities/{city_id}/local-color')
def list_local_color(request: Request, city_id: str, seed: str | None = None, day: date | None = None,
                     kind: list[str] | None = Query(default=None), count: int = Query(3, ge=1, le=100)):
    data = city(request, city_id)
    if seed is None:
        return data['local_color']
    return generators.local_color(data, seed=seed, kinds=kind, day=day, count=count)


@router.get('/cities/{city_id}/prices')
def list_prices(request: Request, city_id: str, item: str | None = None, seed: str | None = None):
    data = city(request, city_id)
    if item and seed is not None:
        return generators.price(data, item, seed=seed)
    return {'currency': data['currency'], 'prices': data['prices']}


def city_today(request: Request, data: dict) -> date:
    return request.app.state.database.clock.now().astimezone(zone(data['timezone'])).date()


@router.get('/cities/{city_id}/changes')
def list_changes(request: Request, city_id: str, day: date | None = None, days: int = Query(60, ge=1, le=730)):
    """Changes heard of by `day` (the city's today by default) that start, run or end within `days` of it."""
    database = request.app.state.database
    with database.connect() as connection:
        data = catalog.city(city_id, custom.all_cities(connection))
        saved = changes.stored(connection, city_id)
    day = day or city_today(request, data)
    since = (day - timedelta(days=days)).isoformat()
    found = [change for change in changes.known(data, day, saved)
             if change['starts'] >= since or change['ends'] is None or change['ends'] >= since]
    return {'day': day.isoformat(), 'changes': [change | {'active': changes.active(change, day)} for change in found]}


@router.post('/cities/{city_id}/changes')
def add_change(request: Request, city_id: str, body: CityChange):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        data = catalog.city(city_id, custom.all_cities(connection))
        change = body.model_dump(mode='json')
        return changes.add(connection, data, change, database.now())


@router.delete('/cities/{city_id}/changes/{change_id}')
def remove_change(request: Request, city_id: str, change_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        data = catalog.city(city_id, custom.all_cities(connection))
        return changes.remove(connection, data, change_id, database.now())
