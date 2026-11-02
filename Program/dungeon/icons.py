"""Faction emblems and item icons (requirements "Art"): a picture beside each power in the world and each thing in the
pack or on the counter, with no image backend at all.

- Each world lists them in its art file (engine/art/<world>.json): `emblems` by faction id, and `icons` by item id,
  by the ids in an entry's `items` (one bed for every night's lodging), or for a whole `category` of items (food,
  weapon...). The images are the package's assets/emblems/<id>.webp and assets/icons/<id>.webp, 256 pixels square on
  a transparent background, made once by scripts/art/icons.py in the world's own style.
- An item's own icon wins, then its category's. An item with neither, or a faction with no emblem, has no picture,
  and the screen shows the name alone.
- Items are pictured in the world of the town they came from, so a knife bought in Kingswood keeps its look.

Pictures are not game state: what a thing looks like never changes the story.
"""
from dungeon import tiers, world_data
from dungeon.errors import require

# The kinds of picture, by the asset folder each lives in.
FOLDERS = {'emblem': 'emblems', 'icon': 'icons'}


def url(kind: str, world: str, name: str) -> str:
    return f'/api/story/art/{kind}/{world}/{name}.webp'


def _listed(world: str, key: str, kind: str) -> list[dict]:
    """The art file's entries of one kind whose image is there."""
    entries = ((world_data.read('art', world) or {}).get(key) or []) if world else []
    return [entry for entry in entries if world_data.asset(world, f"{FOLDERS[kind]}/{entry['id']}.webp")]


@world_data.memo
def _emblems(world: str) -> dict[str, str]:
    return {entry['id']: url('emblem', world, entry['id']) for entry in _listed(world, 'emblems', 'emblem')}


@world_data.memo
def _icons(world: str) -> tuple[dict[str, str], dict[str, str]]:
    """An icon by item id, and by category."""
    by_item, by_category = {}, {}
    for entry in _listed(world, 'icons', 'icon'):
        address = url('icon', world, entry['id'])
        if entry.get('category'):
            by_category.setdefault(entry['category'], address)
        else:
            for item_id in (entry['id'], *entry.get('items', [])):
                by_item.setdefault(item_id, address)
    return by_item, by_category


def emblem(world: str | None, faction_id: str) -> str | None:
    return _emblems(world).get(faction_id) if world else None


def icon(city_id: str, item_id: str, category: str) -> str | None:
    """The picture of an item from this town: its own icon, else its category's."""
    world = tiers.world_of(city_id)
    if not world:
        return None
    by_item, by_category = _icons(world)
    return by_item.get(item_id) or by_category.get(category)


def file(kind: str, world: str, name: str) -> bytes:
    found = (world_data.asset(world, f'{FOLDERS[kind]}/{name}') if kind in FOLDERS and name.endswith('.webp')
             and '/' not in name else None)
    require(found is not None, 'There is no such picture.', 404)
    return found
