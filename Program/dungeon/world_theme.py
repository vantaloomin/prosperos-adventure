"""A world's own look (requirements "Play screen and widgets": "per-world themes"): the colors its package asks for in
`world.json` `theme`, so a grimdark continent and a 2009 campus can look different. The story screen wears them
when the player leaves "Use the world's colors" on (src/features/settings/deviceLook.ts); the rest of the app keeps
the player's own scheme.

`theme` is `{"name": "Ember", "palette": {"accent", "background", "surface", "text"}}`, each a #rrggbb color. A
theme with a color missing or malformed is no theme: the screen keeps the player's colors rather than half a look.
The screen also checks the palette reads (text 4.5:1, accent 3:1) before it uses it.
"""
import json
import re
from contextlib import closing
from pathlib import Path

from dungeon import package_lore, packages, story, tiers

KEYS = ('accent', 'background', 'surface', 'text')
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def cleaned(value: object) -> dict | None:
    """A theme as the screen takes it, or None when it is not a whole one."""
    if not isinstance(value, dict) or not isinstance(value.get('palette'), dict):
        return None
    palette = {key: value['palette'].get(key) for key in KEYS}
    if not all(isinstance(color, str) and HEX.match(color) for color in palette.values()):
        return None
    name = value.get('name')
    return {'name': name.strip()[:40] if isinstance(name, str) and name.strip() else 'The world\'s colors',
            'palette': {key: color.lower() for key, color in palette.items()}}


def of_world(root, world_id: str | None) -> dict | None:
    """The theme of a world's package, read from the package file so an edited or imported world looks as edited."""
    if not world_id:
        return None
    # The package as built at start (dungeon/world_data.py), else built now.
    built = Path(root) / packages.FOLDER / f'{world_id}.sqlite'
    path = built if built.is_file() else package_lore.package_path(root, world_id)
    if not path:
        return None
    # Only the world's settings: the package's assets (its maps) are not read for this.
    with closing(packages.connect(path)) as connection:
        row = connection.execute("SELECT value FROM meta WHERE key='world'").fetchone()
    return cleaned(json.loads(row['value']).get('theme')) if row else None


def current(database) -> dict:
    """The theme of the world the story is in, with the world's id; `theme` is None when it ships none."""
    with database.connect() as connection:
        world = tiers.world_of(story.scene_row(connection)['city_id'])
    return {'world': world, 'theme': of_world(database.root, world)}
