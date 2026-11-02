"""Where the persona lives: their home in each of their worlds (from Companion's Where you are, Hit List #59).

Every persona has a home in each of their worlds: a city and a neighbourhood, kept on the world in worlds.json
(dungeon/worlds.py) and copied into the world's persona row. The app picks it and the user can change it on the
persona form: a world's home starts in the world's city, in a neighbourhood with ordinary rents picked by a seed, and
a city the user picks must be one a traveller from the world's city could reach (`fits`: same era, same world).
"""
import random

from dungeon.database import optional
from dungeon.errors import require
from dungeon.world import catalog, changes, custom

# A neighbourhood's rent tiers that count as ordinary rents: the app's pick for a home.
ORDINARY_RENTS = ('mid', 'low')

# Who picked the home: the app (it follows the world's city while the user has not changed it) or the user.
PICKED, YOURS = 'app', 'you'
# A city of another era this close to the user's is the same place (London and London, 1895 are 1 km apart).
SAME_PLACE_KM = 30


def known_cities(connection) -> dict[str, dict]:
    """Every city by id, a built-in one winning over a user's city with the same id (as catalog.city has it)."""
    return {**custom.all_cities(connection), **catalog.cities()}


def neighbourhood_for(city: dict, seed: str) -> str:
    """The app's pick: a neighbourhood with ordinary rents, seeded by the world; any neighbourhood in a city without
    rents, and none in a city that has no neighbourhoods."""
    hoods = city.get('neighborhoods') or []
    priced = [hood for hood in hoods if hood.get('rent')]
    fitting = [hood for hood in priced if hood.get('rent_tier') in ORDINARY_RENTS] or priced or hoods
    return random.Random(f'{seed}:your-hood').choice(sorted(fitting, key=lambda hood: hood['id']))['id'] if fitting else ''


def picked(city: dict, seed: str) -> dict:
    return {'city_id': city['id'], 'neighbourhood': neighbourhood_for(city, seed), 'set_by': PICKED}


def hood_named(city: dict, hood_id: str) -> dict | None:
    return next((hood for hood in city.get('neighborhoods') or [] if hood['id'] == hood_id), None)


def allowed(world_city: dict, city: dict) -> bool:
    """A home in the world's own city, or in one a trip from it could reach (same era and the same world)."""
    return city['id'] == world_city['id'] or fits(world_city, city)


def fits(home: dict, other: dict) -> bool:
    """Same era and the same world: real cities and towns invented in our world (Pellmouth)
    mix, as do the cities of a made-up world; a user's own city visits real ones."""
    if other['id'] == home['id'] or other.get('era', 'modern') != home.get('era', 'modern'):
        return False
    if 'lat' not in other or 'lat' not in home or other.get('distribution', 'public') != 'public':
        return False
    mine, theirs = catalog.category(home), catalog.category(other)
    if theirs == 'custom':
        return False
    if mine == 'custom':
        return theirs == 'real'
    return ours(home) == ours(other)


def ours(city: dict) -> bool:
    """A real city, or one invented in our world ('original'), rather than a city of a made-up world."""
    return city.get('setting') in ('real', 'original')


def choices(world_city: dict, cities: dict[str, dict]) -> list[dict]:
    """The cities the persona can live in, the world's own first; never a road between towns (`home` false)."""
    others = sorted((city for city in cities.values()
                     if city['id'] != world_city['id'] and city.get('home', True) and allowed(world_city, city)),
                    key=lambda city: city['name'])
    return [world_city, *others]


def settle(world: dict, world_city: dict, cities: dict[str, dict]) -> bool:
    """Gives `world` its home when it has none (a new world), and moves an app-picked home along with the world's city.
    A home whose city has gone, or that the world's city can no longer reach, goes back to the world's city. True when
    the home changed."""
    home = world.get('home') or {}
    city = cities.get(home.get('city_id', ''))
    if home and city and (city['id'] == world_city['id'] or (home.get('set_by') == YOURS and allowed(world_city, city))):
        if home.get('neighbourhood') and not hood_named(city, home['neighbourhood']):
            home['neighbourhood'] = neighbourhood_for(city, world['id'])
            return True
        return False
    world['home'] = picked(world_city, world['id'])
    return True


def change(world: dict, world_city: dict, city: dict, neighbourhood: str):
    """The user's own pick. A blank neighbourhood, or one from another city, lets the app pick one there."""
    require(allowed(world_city, city), f"You can't live in {city['name']} in this world.", 422)
    hood = neighbourhood if hood_named(city, neighbourhood) else neighbourhood_for(city, world['id'])
    world['home'] = {'city_id': city['id'], 'neighbourhood': hood, 'set_by': YOURS}


def view(home: dict | None, cities: dict[str, dict]) -> dict | None:
    """The home as the persona form shows it."""
    city = home and cities.get(home.get('city_id', ''))
    if not city:
        return None
    hood = hood_named(city, home.get('neighbourhood', ''))
    return {'city_id': city['id'], 'city': city['name'], 'region': city.get('region', ''),
            'neighbourhood': hood['id'] if hood else '', 'neighbourhood_name': hood['name'] if hood else '',
            'set_by': home.get('set_by', PICKED)}


# In a world ---------------------------------------------------------------------------------------------------

def your_home(connection) -> tuple[dict, dict | None] | None:
    """The user's city in this world and their neighbourhood in it, from the persona row; None before there is one."""
    row = optional(connection, 'SELECT home_city_id, home_neighbourhood FROM persona WHERE id=1')
    city = row and row['home_city_id'] and changes.resolve(row['home_city_id'], custom.all_cities(connection))
    if not city:
        return None
    return city, hood_named(city, row['home_neighbourhood'])


def home_text(connection) -> str:
    """"Canton, Baltimore", or just the city when there is no neighbourhood; '' before there is a home."""
    found = your_home(connection)
    if not found:
        return ''
    city, hood = found
    return f"{hood['name']}, {city['name']}" if hood else city['name']
