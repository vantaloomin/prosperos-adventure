"""Where the game reads a world's data (docs/packages.md "In play"): from the world packages in the data folder.

Each kind of engine data (a world's travel map, arcs, factions and tiers; a town's adventure, items, finds and
premades) is read from the package whose `engine` part holds it, so an edited or imported world plays as edited. A
built-in world's package is built from the shipped files when the app starts (adventure/packages.py installed), so
until someone edits it, it holds exactly what `adventure/world/data` does. With no data folder in use (a script, a
test of one loader) or for data no package holds, the shipped JSON file is read.

Reads are cheap: a package's engine part is read once and again only when the file changes, and each read parses
its own copy, as reading the file did. `memo` caches a loader's work the same way.

A world's package facts (`facts`: its hidden truths and secrets, each with its visibility tag, adventure/package_lore.py)
are read the same way, for the context builders to route (adventure/rounds/context.py), and so is a character's
sheet (`person`: its cast or persona entry) and whether they see the game's numbers (`game_knowledge`).

**Game knowledge** (spec "Numbers, System panes and who can see them"): whether a character sees System panes and
game numbers is a fact about them. `world.json` may say so as `game_knowledge`: `{"default": true|false, "people":
{"<field>": {"<value>": true|false}}, "characters": {"<id>": true|false}}`, and a cast or persona entry may carry
its own `game_knowledge`, which wins. "people" matches an entry's field by value, ignoring case ("lineage":
{"native": false}). With no flag at all everyone sees them, as in Dungeon.
"""
import functools
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from adventure import package_lore, packages

_root: Path | None = None


def use(root: Path | None):
    """The data folder whose packages the game reads; built-in worlds are built (again) there now."""
    global _root
    _root = Path(root) if root is not None else None
    if _root is not None:
        for world_id in packages.builtin_ids():
            packages.installed(_root, world_id)


def paths() -> list[Path]:
    """The package files in use: the built-in worlds first, then imported ones."""
    if _root is None:
        return []
    folder = _root / packages.FOLDER
    builtin = [folder / f'{world_id}.sqlite' for world_id in packages.builtin_ids()]
    imported = sorted(path for path in folder.glob('*.sqlite') if path not in builtin) if folder.is_dir() else []
    return [path for path in builtin if path.is_file()] + imported


def version() -> tuple:
    """What changes when any package in use changes: their paths and modification times."""
    found = []
    for path in paths():
        try:
            found.append((str(path), os.stat(path).st_mtime_ns))
        except OSError:
            continue
    return tuple(found)


@functools.lru_cache(maxsize=32)
def _engine(path: str, stamp: int) -> dict[tuple[str, str], str]:
    try:
        with closing(packages.connect(Path(path))) as connection:
            return {(row['kind'], row['key']): row['data'] for row in connection.execute('SELECT kind, key, data FROM engine')}
    except sqlite3.Error:
        return {}


def _held(kind: str) -> dict[str, str]:
    """Every package's `kind` data by key; the first package that holds a key wins."""
    found: dict[str, str] = {}
    for path, stamp in version():
        for (held_kind, key), data in _engine(path, stamp).items():
            if held_kind == kind:
                found.setdefault(key, data)
    return found


def read(kind: str, key: str) -> dict | None:
    """One piece of engine data (`kind` is a folder of adventure/world/data, `key` a world or town id), or None."""
    held = _held(kind).get(key)
    if held is not None:
        return json.loads(held)
    path = packages.DATA / kind / f'{key}.json'
    if not path.is_file():
        # Engine data only a built-in package ships (a world's art list), with no data folder in use.
        path = packages.BUILTIN / key / 'engine' / kind / f'{key}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def asset(world: str, name: str) -> bytes | None:
    """One of a world's assets (a map, a backdrop: `name` under assets/), from the first package of that world that
    holds it, else the built-in world's own folder."""
    for path, stamp in version():
        held, names = _assets(path, stamp)
        if held == world and name in names:
            try:
                with closing(packages.connect(Path(path))) as connection:
                    row = connection.execute('SELECT bytes FROM assets WHERE path=?', (f'assets/{name}',)).fetchone()
            except sqlite3.Error:
                row = None
            if row is not None:
                return bytes(row['bytes'])
    shipped = packages.BUILTIN / world / 'assets' / name
    return shipped.read_bytes() if world in packages.builtin_ids() and shipped.is_file() else None


@functools.lru_cache(maxsize=32)
def _assets(path: str, stamp: int) -> tuple[str | None, frozenset[str]]:
    """The world a package is of, and the names of its assets."""
    try:
        with closing(packages.connect(Path(path))) as connection:
            world = json.loads(connection.execute("SELECT value FROM meta WHERE key='world'").fetchone()['value'])
            return world.get('id'), frozenset(row['path'].removeprefix('assets/')
                                              for row in connection.execute('SELECT path FROM assets'))
    except (sqlite3.Error, TypeError):
        return None, frozenset()


def keys(kind: str) -> list[str]:
    """The keys there is `kind` data for, in a package or shipped, sorted."""
    shipped = {path.stem for path in (packages.DATA / kind).glob('*.json')}
    return sorted(shipped | set(_held(kind)))


def memo(function):
    """A loader's cache that empties when a package in use changes."""
    @functools.wraps(function)
    def wrapper(*args):
        token = version()
        if wrapper.token != token:
            cached.cache_clear()
            wrapper.token = token
        return cached(*args)

    cached = functools.cache(function)
    wrapper.token = None
    wrapper.cache_clear = cached.cache_clear
    return wrapper


def facts(world: str) -> list[dict]:
    """The world's hidden truths and secrets with their visibility tags (adventure/package_lore.py facts), from the
    first package of that world in use, else the built-in world's own folder; [] for a world with neither."""
    return package_lore.facts({'sections': sections(world, tuple(packages.SECTIONS))})


def sections(world: str, names: tuple[str, ...]) -> dict[str, dict]:
    """Some sections of the world's package in use (else its shipped folder), as {name: {key: entries}}."""
    for path, stamp in version():
        if _assets(path, stamp)[0] == world:
            return {name: data for name, data in _sections(path, stamp).items() if name in names}
    return _shipped(world, names) if world in packages.builtin_ids() else {}


@functools.cache
def _shipped(world: str, names: tuple[str, ...]) -> dict[str, dict]:
    folder = packages.BUILTIN / world
    return {name: packages.read_json(folder / f'{name}.json') for name in names if (folder / f'{name}.json').is_file()}


@functools.lru_cache(maxsize=32)
def _sections(path: str, stamp: int) -> dict[str, dict]:
    found: dict[str, dict] = {}
    try:
        with closing(packages.connect(Path(path))) as connection:
            for row in connection.execute('SELECT section, data FROM entries ORDER BY section, position'):
                if row['section'] in packages.SECTIONS:
                    found.setdefault(row['section'], {packages.SECTIONS[row['section']]: []})[
                        packages.SECTIONS[row['section']]].append(json.loads(row['data']))
    except sqlite3.Error:
        return {}
    return found


def person(world: str | None, key: str) -> dict | None:
    """A character's cast or persona entry in the world's package (a copy), or None."""
    if not world:
        return None
    held = sections(world, package_lore.CHARACTERS)
    for name in package_lore.CHARACTERS:
        for entry in (held.get(name) or {}).get(packages.SECTIONS[name]) or []:
            if isinstance(entry, dict) and entry.get('id') == key:
                return json.loads(json.dumps(entry))
    return None


def world_file(world: str | None) -> dict:
    """The world's world.json, from its package in use, else its shipped folder; {} for none."""
    if not world:
        return {}
    for path, stamp in version():
        held, _names = _assets(path, stamp)
        if held == world:
            return dict(_world(path, stamp))
    shipped = packages.BUILTIN / world / 'world.json'
    return packages.read_json(shipped) if world in packages.builtin_ids() and shipped.is_file() else {}


@functools.lru_cache(maxsize=32)
def _world(path: str, stamp: int) -> dict:
    try:
        with closing(packages.connect(Path(path))) as connection:
            return json.loads(connection.execute("SELECT value FROM meta WHERE key='world'").fetchone()['value'])
    except (sqlite3.Error, TypeError):
        return {}


def game_knowledge(world: str | None, key: str, entry: dict | None = None) -> bool:
    """Whether the character `key` sees System panes and game numbers (see "Game knowledge" above)."""
    entry = entry if entry is not None else person(world, key) or {}
    if isinstance(entry.get('game_knowledge'), bool):
        return entry['game_knowledge']
    flag = world_file(world).get('game_knowledge')
    if not isinstance(flag, dict):
        return True
    characters = flag.get('characters') if isinstance(flag.get('characters'), dict) else {}
    if isinstance(characters.get(key), bool):
        return characters[key]
    people = flag.get('people') if isinstance(flag.get('people'), dict) else {}
    for field, values in people.items():
        value = entry.get(field)
        if isinstance(values, dict) and isinstance(value, str):
            found = {str(name).casefold(): seen for name, seen in values.items() if isinstance(seen, bool)}
            if value.casefold() in found:
                return found[value.casefold()]
    return flag.get('default') is not False
