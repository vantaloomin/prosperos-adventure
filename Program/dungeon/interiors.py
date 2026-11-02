"""Interiors (requirements "### Interiors"): the inside of a keep, cave, crypt or mine, as rooms joined by passages.

This is the format and where an interior is found: authored interiors are engine data (world/data/interiors, or a
world package's engine/interiors), checked against world/schema.py `Interior`, and entered from a town's place, a
travel-map stop or an authored hex site. Walking them in play, and seeded interiors for rolled sites, build on this.
"""
from dungeon import world_data
from dungeon.errors import require
from dungeon.world.schema import Interior


def validated(data: dict) -> dict:
    """An interior as the game uses it, or pydantic's ValidationError saying what is wrong."""
    return Interior.model_validate(data).model_dump(mode='json')


@world_data.memo
def everything() -> dict[str, dict]:
    """Every interior in the packages in use (and the shipped ones), by id. One that does not validate is left out."""
    found = {}
    for key in world_data.keys('interiors'):
        data = world_data.read('interiors', key)
        try:
            found[key] = validated(data) if isinstance(data, dict) else None
        except ValueError:
            continue
    return {key: value for key, value in found.items() if value}


def get(interior_id: str) -> dict:
    found = everything().get(interior_id)
    require(found is not None, f'There is no interior called {interior_id}.', 404)
    return found


def entered_from(*, world: str | None = None, city: str | None = None, place: str | None = None,
                 node: str | None = None, site: str | None = None) -> dict | None:
    """The interior whose way in is this place, travel-map stop or site, if any."""
    for interior in everything().values():
        at = interior['at']
        if world and interior['world'] != world:
            continue
        if (place and at.get('city') == city and at.get('place') == place) or (node and at.get('node') == node) \
                or (site and at.get('site') == site):
            return interior
    return None


def for_world(world: str) -> list[dict]:
    return [interior for interior in everything().values() if interior['world'] == world]


def room(interior: dict, room_id: str) -> dict:
    found = next((item for item in interior['rooms'] if item['id'] == room_id), None)
    require(found is not None, f'{interior["name"]} has no room called {room_id}.', 404)
    return found


def ways_out(interior: dict, room_id: str, known_hidden: frozenset[str] = frozenset()) -> list[dict]:
    """The passages leaving a room the character can see: hidden ones only once found (`known_hidden` holds the
    other end's room id), and one-way ones only from their first room."""
    found = []
    for passage in interior['passages']:
        a, b = passage['between']
        if room_id not in (a, b) or (passage['one_way'] and room_id != a):
            continue
        other = b if room_id == a else a
        if passage['hidden'] and other not in known_hidden:
            continue
        found.append({'to': other, 'passage': passage})
    return found
