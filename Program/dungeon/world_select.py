"""The title screen's worlds (src/features/story/TitleScreen.tsx): every world with a travel map to play on, with its
pitch and key art, and going to one. Going to a world is going to the persona's own world there, the one they were in
last, else a new world for them in the town the world's campaign starts in (dungeon/worlds.py). The key art is the
package's assets/keyart.webp, made with scripts/art/keyart.py.
"""
import json
from contextlib import closing

from dungeon import package_lore, packages, story, tiers, travel, world_data, worlds
from dungeon.errors import require
from dungeon.world import catalog

# The order on the title screen: the first slice's world first. Worlds not named here follow by id.
ORDER = ('vallarith', 'havenbrooke', 'babel')
KEYART = 'keyart.webp'


def playable() -> list[str]:
    """The worlds a campaign can be played in: those with a travel map."""
    found = {travel_map['world'] for travel_map in travel.maps() if travel_map.get('world')}
    return sorted(found, key=lambda world: (ORDER.index(world) if world in ORDER else len(ORDER), world))


def settings(root, world_id: str) -> dict:
    """The world's own settings (world.json) as its package holds them, so an edited world reads as edited."""
    built = root / packages.FOLDER / f'{world_id}.sqlite'
    path = built if built.is_file() else package_lore.package_path(root, world_id)
    if not path:
        return {}
    with closing(packages.connect(path)) as connection:
        row = connection.execute("SELECT value FROM meta WHERE key='world'").fetchone()
    return json.loads(row['value']) if row else {}


def start_city(world_id: str, place: dict | None = None) -> str | None:
    """The town a new campaign in the world starts in: the package's starting settlement when it is a town on the
    world's travel map, else the map's first town."""
    towns = [node['city'] for travel_map in travel.maps() if travel_map.get('world') == world_id
             for node in travel_map['nodes'] if node.get('city')]
    settlement = (place or {}).get('settlement')
    return settlement if settlement in towns else next(iter(towns), None)


def theirs(database, world_id: str) -> dict | None:
    """The active persona's world in this one they were in last."""
    data = worlds.registry(database)
    persona = next(world['persona_id'] for world in data['worlds'] if world['id'] == data['active'])
    mine = [world for world in data['worlds']
            if world['persona_id'] == persona and tiers.world_of(world['city_id']) == world_id]
    return max(mine, key=lambda world: world['used_at']) if mine else None


def here(database) -> str | None:
    with database.connect() as connection:
        return tiers.world_of(story.scene_row(connection)['city_id'])


def choices(database) -> dict:
    """The worlds to pick from, the one the story is in marked `here`."""
    current = here(database)
    found = []
    for world_id in playable():
        world = settings(database.root, world_id)
        found.append({'id': world_id, 'name': world.get('name') or world_id.title(), 'genre': world.get('genre', ''),
                      'pitch': world.get('pitch', ''), 'here': world_id == current,
                      'yours': world_id != current and theirs(database, world_id) is not None,
                      'art': f'/api/story/art/keyart/{world_id}' if world_data.asset(world_id, KEYART) else None})
    return {'worlds': found, 'here': current}


def enter(state, world_id: str) -> dict:
    """Into the persona's world there, made first when they have none. Already there: nothing changes. A world whose
    story is not yet in it (made on the Worlds page, which places no scene) opens where its campaign starts."""
    database = state.database
    require(world_id in playable(), 'There is no such world.', 404)
    if here(database) == world_id:
        return worlds.view(database)
    place = settings(database.root, world_id).get('starting_place') or {}
    if (found := theirs(database, world_id)) is not None:
        worlds.switch(state, found['id'])
        if here(database) != world_id:
            arrive(database, found['city_id'], place)
        return worlds.view(database)
    city = start_city(world_id, place)
    require(city is not None, 'That world has no town to start in.', 409)
    reason = worlds.busy(state)
    require(reason is None, reason or '', 409)
    worlds.switch(state, worlds.create_world(database, city_id=city)['id'])
    arrive(database, city, place)
    return worlds.view(database)


def arrive(database, city: str, place: dict):
    """The story opens in `city`, at the world's starting place when it is there, not in the app's default town."""
    with database.connect(write=True) as connection:
        data = story.city_data(connection, city)
        opening = place.get('place') if catalog.find(data, place.get('place')) in data['places'] else None
        story.place_scene(connection, city, opening or story.opening_place(data)['id'], database.now())


def keyart(world_id: str) -> bytes:
    found = world_data.asset(world_id, KEYART)
    require(found is not None, 'That world has no key art.', 404)
    return found
