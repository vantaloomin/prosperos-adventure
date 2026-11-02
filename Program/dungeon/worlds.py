"""Worlds and personas: more than one life for the user, each in its own world.

A persona is the user as someone in particular: a name, a gender, an age, a birthday and a few lines about them.
A world is everything that happened to one persona there: their story and its town. Each persona has one or more
worlds, and two worlds may share a city.

Each world is a workspace of its own, one database in its own folder (the first world keeps the data folder's
own database, `Database.root`), so nothing in one world can reach another. Which worlds and personas there are
lives in `worlds.json` beside the first world. Switching points the app's one Database at the other world's file
(`Database.use`); what belongs to the user rather than to a world (model connections, image backends, voices,
settings, their own cities) is carried over from the world they leave, so it follows them.

"The world exists outside of User" (Vanta, 2026-10-08): nobody sets anything up. The first run makes the first
world with a blank persona; a new persona or world arrives ready in the city the user picked (the form starts on a
featured one the app picks).
"""
import json
import os
import shutil
import sqlite3
from pathlib import Path

from dungeon import backup, lore, restore, story, tiers
from dungeon.clock import AppClock
from dungeon.database import Database, identifier, optional
from dungeon.errors import require
from dungeon.models import PERSONA_AGES
from dungeon.world import catalog, generators, lifespans, mix, where

REGISTRY = 'worlds.json'
FOLDER = 'worlds'
DATABASE = 'dungeon.sqlite3'
GENDERS = ('woman', 'man', 'nonbinary')
# What belongs to the user rather than to a world: carried from the world they leave into the one they enter, as a
# restore keeps them (dungeon/restore.py). Debug time stays with its world; their own cities follow them.
SHARED = tuple(table for table in restore.KEPT_SETTINGS if table != 'debug_time') + ('world_cities',)
# The city picker's "Somewhere new (picked for you)": a featured city other than the one the user is in.
SOMEWHERE_NEW = 'somewhere-new'
# The world of the cities outside the world packages, in `somewhere-new:custom`.
CUSTOM = 'custom'


# The registry -------------------------------------------------------------------------------------------

def registry_path(root: Path) -> Path:
    return Path(root) / REGISTRY


def load(root: Path) -> dict | None:
    try:
        data = json.loads(registry_path(root).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get('worlds') or not data.get('personas'):
        return None
    return data


def save(root: Path, data: dict):
    """Written whole and swapped in, so a crash never leaves half a registry."""
    path = registry_path(root)
    partial = path.with_name(path.name + '.partial')
    partial.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(partial, path)


def world_path(home: Path, world: dict) -> Path:
    """The first world keeps the database the app was opened with; every other world has its own folder."""
    return Path(home).parent / world['folder'] / DATABASE if world['folder'] else Path(home)


def active_path(home: Path) -> Path:
    """The active world's database, read without opening anything (the launcher applies a restore there)."""
    data = load(Path(home).parent)
    world = data and find(data['worlds'], data.get('active'))
    path = world_path(home, world) if world else Path(home)
    return path if path.exists() else Path(home)


def find(items: list[dict], item_id: str | None) -> dict | None:
    return next((item for item in items if item['id'] == item_id), None)


def found(items: list[dict], item_id: str, what: str) -> dict:
    item = find(items, item_id)
    require(item is not None, f'That {what} is no longer here.', 404)
    return item


def registry(database: Database) -> dict:
    data = load(database.root)
    require(data is not None, 'The list of worlds could not be read. Restart the Dungeon.', 409)
    return data


# The first world ----------------------------------------------------------------------------------------

def persona_from(timestamp: str) -> dict:
    """The first persona: blank, for the user to fill in."""
    return {'id': identifier(), 'name': '', 'gender': '', 'age': None, 'about': '', 'birthday': '',
            'created_at': timestamp}


def city_of(connection) -> dict:
    """The city a world takes place in when it names none: the default one."""
    return story.city_data(connection, story.DEFAULT_CITY)


def first_registry(database: Database) -> dict:
    """Everything already here becomes the first world, with a persona made from what the app knows."""
    timestamp = database.now()
    persona = persona_from(timestamp)
    with database.connect() as connection:
        city = city_of(connection)
    world = {'id': identifier(), 'name': city['name'], 'persona_id': persona['id'], 'folder': '',
             'city_id': city['id'], 'created_at': timestamp, 'used_at': timestamp}
    world['home'] = where.picked(city, world['id'])
    return {'version': 1, 'active': world['id'], 'personas': [persona], 'worlds': [world]}


def start(database: Database):
    """At startup: the registry (made on the first run of this version) and the world the user was last in."""
    data = load(database.root)
    if data is None:
        data = first_registry(database)
        save(database.root, data)
    world = find(data['worlds'], data.get('active')) or next(item for item in data['worlds'] if not item['folder'])
    path = world_path(database.home, world)
    if not path.exists():  # A world folder removed by hand: back to the first world.
        world = next(item for item in data['worlds'] if not item['folder'])
        path = database.home
    data['active'] = database.world = world['id']
    save(database.root, data)
    if path != database.path:
        database.use(path)
    mix.load(database)
    with database.connect(write=True) as connection:
        if restored_home(connection, world) | settle_home(connection, world):
            save(database.root, data)
        write_persona(connection, found(data['personas'], world['persona_id'], 'persona'), database.now(),
                      world['home'])


# Personas in a world ------------------------------------------------------------------------------------

def write_persona(connection, persona: dict, timestamp: str, home: dict | None = None):
    """Who the user is in this world, and where they live in it (`home`, the world's: dungeon/world/where.py). The
    world's town seed is its own, set once by `build`, so it is never overwritten here."""
    home = home or {}
    connection.execute('INSERT INTO persona (id, persona_id, name, gender, age, about, birthday, updated_at, '
                       'townsfolk_key, home_city_id, home_neighbourhood, kind, lifespan) '
                       'VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET '
                       'persona_id=excluded.persona_id, name=excluded.name, gender=excluded.gender, age=excluded.age, '
                       'about=excluded.about, birthday=excluded.birthday, updated_at=excluded.updated_at, '
                       'townsfolk_key=excluded.townsfolk_key, home_city_id=excluded.home_city_id, '
                       'home_neighbourhood=excluded.home_neighbourhood, kind=excluded.kind, lifespan=excluded.lifespan',
                       (persona['id'], persona['name'], persona['gender'], persona['age'], persona['about'],
                        persona.get('birthday') or '', timestamp, persona.get('townsfolk_key', ''),
                        home.get('city_id', ''), home.get('neighbourhood', ''),
                        persona.get('kind') or '', persona.get('lifespan')))


def world_city(connection, world: dict, cities: dict[str, dict]) -> dict:
    """The city the world is in: the one it was made in, else (a city since deleted) the default one."""
    return cities.get(world.get('city_id') or '') or city_of(connection)


def restored_home(connection, world: dict) -> bool:
    """A world restored from a backup (or brought from another install) remembers where the user lived in it; a home
    the app picked in this registry gives way to it. True when the home changed."""
    row = optional(connection, 'SELECT home_city_id, home_neighbourhood FROM persona WHERE id=1')
    home = world.get('home') or {}
    if not row or not row['home_city_id'] or home.get('set_by') == where.YOURS or \
            (row['home_city_id'], row['home_neighbourhood']) == (home.get('city_id'), home.get('neighbourhood')):
        return False
    world['home'] = {'city_id': row['home_city_id'], 'neighbourhood': row['home_neighbourhood'], 'set_by': where.YOURS}
    return True


def settle_home(connection, world: dict) -> bool:
    """The world's home for its persona, picked when it has none (dungeon/world/where.py). True when it changed."""
    cities = where.known_cities(connection)
    return where.settle(world, world_city(connection, world, cities), cities)


# Views ----------------------------------------------------------------------------------------------------

def world_view(database: Database, data: dict, world: dict, cities: dict[str, dict] | None = None) -> dict:
    if cities is None:
        with database.connect() as connection:
            cities = where.known_cities(connection)
    return {**world, 'active': world['id'] == data['active'], 'first': not world['folder'],
            'home': where.view(world.get('home'), cities)}


def view(database: Database) -> dict:
    data = registry(database)
    active = found(data['worlds'], data['active'], 'world')
    with database.connect() as connection:
        cities = where.known_cities(connection)
        here = city_of(connection)
    personas = [{**persona, 'active': persona['id'] == active['persona_id'], 'kind_shown': kind_shown(persona, here),
                 'worlds': [world_view(database, data, world, cities) for world in
                            sorted(data['worlds'], key=lambda item: item['used_at'], reverse=True)
                            if world['persona_id'] == persona['id']]}
                for persona in data['personas']]
    return {'active_world_id': active['id'], 'active_persona_id': active['persona_id'],
            'world': world_view(database, data, active, cities),
            'persona': find(personas, active['persona_id']), 'personas': personas, 'genders': list(GENDERS)}


# Switching ------------------------------------------------------------------------------------------------

def busy(state) -> str | None:
    """Why the app cannot leave its world right now, if it cannot."""
    with state.database.connect() as connection:
        if optional(connection, 'SELECT id FROM debug_time WHERE id=1'):
            return 'Debug time is on in this world. Return to real time in Settings > Developer first.'
    return None


def carry_settings(target: Path, source: Path, timestamp: str):
    """What follows the user, from the world they leave into `target`."""
    restore.copy_settings(target, source, SHARED, timestamp)
    connection = sqlite3.connect(target, isolation_level=None)
    try:
        # Lore of a city deleted in another world goes with it (dungeon/lore.py).
        lore.drop_orphaned(connection)
    finally:
        connection.close()


def switch(state, world_id: str) -> dict:
    database = state.database
    data = registry(database)
    world = found(data['worlds'], world_id, 'world')
    if world['id'] == data['active']:
        return view(database)
    reason = busy(state)
    require(reason is None, reason or '', 409)
    target = world_path(database.home, world)
    require(target.exists(), "That world's folder is missing from the data folder.", 404)
    previous = database.path
    restore.settle(previous)
    database.use(target)
    mix.load(database)
    carry_settings(target, previous, database.now())
    data['active'], world['used_at'] = world['id'], database.now()
    database.world = world['id']
    with database.connect(write=True) as connection:
        settle_home(connection, world)
        write_persona(connection, found(data['personas'], world['persona_id'], 'persona'), database.now(),
                      world['home'])
    save(database.root, data)
    return view(database)


def switch_persona(state, persona_id: str) -> dict:
    """A persona's world is the one they were last in."""
    data = registry(state.database)
    found(data['personas'], persona_id, 'persona')
    theirs = [world for world in data['worlds'] if world['persona_id'] == persona_id]
    require(bool(theirs), 'That persona has no world yet.', 409)
    return switch(state, max(theirs, key=lambda item: item['used_at'])['id'])


# New worlds -----------------------------------------------------------------------------------------------

def build(database: Database, path: Path, persona: dict, city_id: str, seed: str, town_mix: dict | None = None,
          home: dict | None = None):
    """A new world's database: the user's settings and the persona. Its townsfolk mix (dungeon/world/mix.py) is
    `town_mix`, else the one of the world it was made from. Its town is seeded anew from `seed`."""
    restore.settle(database.path)
    if town_mix is None:
        with database.connect() as connection:
            town_mix = mix.read(connection)
    made = Database(path, AppClock(database.clock.base))
    carry_settings(path, database.path, made.now())
    with made.connect(write=True) as connection, mix.using(town_mix):
        if town_mix != mix.DEFAULTS:
            mix.write(connection, town_mix, made.now())
        write_persona(connection, persona, made.now(), home)
        connection.execute('UPDATE persona SET town_seed=? WHERE id=1', (seed[:16],))
        data = story.city_for(connection, city_id, seed[:16])
    lore.carry_city_lore(path, database.path, data)


def somewhere_new(connection, here: str, seed: str, world: str | None = None) -> str:
    """A town to live in of `world` (a world package, or 'custom' for the cities outside them; by default the world
    `here` is in), other than `here` when that world has another, the same one for the same seed. Never a road
    between towns (a city with `home` false)."""
    world = world or tiers.world_of(here) or CUSTOM
    towns = sorted(city['id'] for city in where.known_cities(connection).values()
                   if city.get('home', True) and (tiers.world_of(city['id']) or CUSTOM) == world)
    others = [city_id for city_id in towns if city_id != here] or towns
    return min(others, key=lambda city_id: generators.unit(city_id, 'somewhere-new', seed), default=here)


def unique_name(data: dict, wanted: str) -> str:
    taken = {world['name'] for world in data['worlds']}
    if wanted not in taken:
        return wanted
    return next(f'{wanted} {number}' for number in range(2, 1000) if f'{wanted} {number}' not in taken)


def create_world(database: Database, persona_id: str | None = None, name: str | None = None,
                 city_id: str | None = None, town_mix: dict | None = None) -> dict:
    """A new world for a persona (the active one by default), in the current city unless another is named.
    `SOMEWHERE_NEW` lets the app pick a town in this world, `somewhere-new:<world>` one in that world. `town_mix` is its townsfolk mix (Worlds > Townsfolk mix), else the current world's."""
    data = registry(database)
    active = found(data['worlds'], data['active'], 'world')
    persona = found(data['personas'], persona_id or active['persona_id'], 'persona')
    world_id = identifier()
    with database.connect() as connection:
        if city_id and city_id.split(':')[0] == SOMEWHERE_NEW:
            city_id = somewhere_new(connection, city_of(connection)['id'], world_id, city_id.partition(':')[2] or None)
        city = story.city_data(connection, city_id) if city_id else city_of(connection)
    folder = f'{FOLDER}/{world_id}'
    path = database.root / folder / DATABASE
    home = where.picked(city, world_id)
    try:
        build(database, path, persona, city['id'], world_id, town_mix, home)
    except BaseException:
        shutil.rmtree(path.parent, ignore_errors=True)
        raise
    timestamp = database.now()
    world = {'id': world_id, 'name': (name or '').strip()[:80] or unique_name(data, city['name']),
             'persona_id': persona['id'], 'folder': folder, 'city_id': city['id'], 'home': home,
             'created_at': timestamp, 'used_at': timestamp}
    data['worlds'].append(world)
    save(database.root, data)
    return world_view(database, data, world)


# Personas -------------------------------------------------------------------------------------------------

def kind_shown(persona: dict, data: dict | None) -> dict:
    """The Persona page's Kind and How long they live (dungeon/world/lifespans.py): what applies, the app's pick from
    their words, and what the pickers offer where they are."""
    found = lifespans.from_words(persona.get('about') or '', data)
    shown = lifespans.described(lifespans.persona_kind(persona, data), persona.get('lifespan'), persona.get('age'), data)
    return shown | {'found': found, 'found_label': lifespans.kinds(data)[found]['label'],
                    'picked': persona.get('kind') or '', **lifespans.choices(data)}


def check_kind(database: Database, persona: dict):
    """A kind picked must be one listed where they are; an age past 120 is only for a long-lived kind, picked or read
    from their words."""
    with database.connect() as connection:
        data = city_of(connection)
    require(not persona.get('kind') or persona['kind'] in lifespans.kinds(data), 'Pick one of the kinds listed.', 422)
    require((persona.get('age') or 0) <= PERSONA_AGES[0] or lifespans.long_lived(lifespans.persona_lifespan(persona, data)),
            f'An age past {PERSONA_AGES[0]} is only for a long-lived kind: pick one under Kind.', 422)


def create_persona(database: Database, body) -> dict:
    """A new persona with a world of their own. Who the user is stays theirs to say (Vanta, 2026-10-09): the name
    they typed, and nothing the app makes up; what they leave blank stays blank. Where they live is theirs to pick
    too (the form starts on somewhere new, picked for them); everyone in it is decided for them."""
    name = (body.name or '').strip()
    require(bool(name), 'Give the new persona a name.', 422)
    data = registry(database)
    persona_id = identifier()
    persona = {'id': persona_id, 'name': name, 'gender': body.gender or '', 'age': body.age,
               'about': (body.about or '').strip(), 'birthday': body.birthday or '', 'created_at': database.now(),
               'kind': body.kind or '', 'lifespan': body.lifespan}
    check_kind(database, persona)
    data['personas'].append(persona)
    save(database.root, data)
    try:
        world = create_world(database, persona_id, city_id=getattr(body, 'city_id', None))
    except BaseException:
        data = registry(database)
        data['personas'] = [item for item in data['personas'] if item['id'] != persona_id]
        save(database.root, data)
        raise
    return {**persona, 'worlds': [world]}


def update_persona(database: Database, persona_id: str, body) -> dict:
    data = registry(database)
    persona = found(data['personas'], persona_id, 'persona')
    changes = body.model_dump(exclude_unset=True)
    if 'name' in changes:
        changes['name'] = (changes['name'] or '').strip()
    persona.update({key: '' if value is None and key not in ('age', 'lifespan') else value
                    for key, value in changes.items()})
    check_kind(database, persona)
    save(database.root, data)
    active = found(data['worlds'], data['active'], 'world')
    if active['persona_id'] == persona_id:
        with database.connect(write=True) as connection:
            write_persona(connection, persona, database.now(), active.get('home'))
    return view(database)


def update_world(database: Database, world_id: str, body) -> dict:
    """Rename a world, or give it to another persona."""
    data = registry(database)
    world = found(data['worlds'], world_id, 'world')
    if body.name is not None:
        require(body.name.strip(), 'Give the world a name.', 422)
        world['name'] = body.name.strip()[:80]
    if body.persona_id is not None:
        persona = found(data['personas'], body.persona_id, 'persona')
        world['persona_id'] = persona['id']
        if world['id'] == data['active']:
            with database.connect(write=True) as connection:
                write_persona(connection, persona, database.now(), world.get('home'))
    save(database.root, data)
    return view(database)


def home_choices(database: Database, world_id: str, city_id: str | None = None) -> dict:
    """Where the persona can live in a world (dungeon/world/where.py): its home, the cities they can pick and the
    neighbourhoods of `city_id` (else of their home's city)."""
    data = registry(database)
    world = found(data['worlds'], world_id, 'world')
    with database.connect() as connection:
        cities = where.known_cities(connection)
        here = world_city(connection, world, cities)
    listed = where.choices(here, cities)
    shown = cities.get(city_id or (world.get('home') or {}).get('city_id') or '') or here
    return {'home': where.view(world.get('home'), cities),
            'cities': [{'id': city['id'], 'name': city['name'], 'region': city.get('region', ''),
                        'country': city.get('country', ''), 'category': catalog.category(city)} for city in listed],
            'city_id': shown['id'],
            'neighbourhoods': [{'id': hood['id'], 'name': hood['name']}
                               for hood in sorted(shown.get('neighborhoods') or [], key=lambda hood: hood['name'])]}


def change_home(database: Database, world_id: str, body) -> dict:
    """The user moves: a city they can live in from this world and a neighbourhood there (blank lets the app pick)."""
    data = registry(database)
    world = found(data['worlds'], world_id, 'world')
    with database.connect(write=True) as connection:
        cities = where.known_cities(connection)
        city = cities.get(body.city_id)
        require(city is not None, 'That city is no longer here.', 404)
        where.change(world, world_city(connection, world, cities), city, body.neighbourhood or '')
        if world['id'] == data['active']:
            write_persona(connection, found(data['personas'], world['persona_id'], 'persona'), database.now(),
                          world['home'])
    save(database.root, data)
    return view(database)


def set_aside(database: Database, world: dict) -> str:
    """A verified backup of a world about to be deleted, in the data folder's backups/deleted-worlds; it is not
    listed in Settings > Data, where restoring it would replace the world the user is in."""
    created_at = database.now()
    name = f"before-delete-world-{created_at[:19].replace(':', '').replace('-', '')}-{world['id'][:6]}.zip"
    path = world_path(database.home, world)
    backup.archive(path, database.root / 'backups' / 'deleted-worlds' / name, created_at)
    return name


def delete_world(database: Database, world_id: str) -> dict:
    """A world goes with everything in it, after a backup. Not the one the user is in, nor the first world, whose
    folder holds all the others."""
    data = registry(database)
    world = found(data['worlds'], world_id, 'world')
    require(world['id'] != data['active'], 'Switch to another world before deleting this one.', 409)
    require(bool(world['folder']), 'The first world holds the others, so it stays. Start a new story in it instead.',
            409)
    if world_path(database.home, world).exists():
        set_aside(database, world)
    shutil.rmtree(database.root / world['folder'], ignore_errors=True)
    data['worlds'].remove(world)
    save(database.root, data)
    return view(database)


def delete_persona(database: Database, persona_id: str) -> dict:
    data = registry(database)
    persona = found(data['personas'], persona_id, 'persona')
    theirs = [world for world in data['worlds'] if world['persona_id'] == persona_id]
    require(all(world['id'] != data['active'] for world in theirs),
            'Switch to another persona before deleting this one.', 409)
    require(all(world['folder'] for world in theirs), 'This persona lives in the first world, so they stay. '
            'Give that world to another persona first.', 409)
    for world in theirs:
        delete_world(database, world['id'])
    data = registry(database)
    data['personas'] = [item for item in data['personas'] if item['id'] != persona['id']]
    save(database.root, data)
    return view(database)
