"""A world package's lore in play (docs/packages.md): the package's public lorebook, as a lore book of the campaign's
world (dungeon/lore.py), so the narrator reads its entries by keyword like any imported lorebook.

Only the `lore` section comes in: it is public text by design, and the package's hidden truths stay with the director
and the record. Entries for another era than the campaign's are left out (an entry with no `eras` holds in all of
them). The book is read from the package file, so an edited or imported world plays as edited; when the package's
lore changes, the book is replaced on the next campaign start.
"""
import hashlib
import json
import re
from pathlib import Path

from dungeon import lore, packages
from dungeon.database import many

FORMAT = 'World package'


def package_path(root: Path, world_id: str) -> Path | None:
    """The world's package file: a built-in world's built (again) when out of date, an imported one as it is."""
    if world_id in packages.builtin_ids():
        return packages.installed(root, world_id)
    path = Path(root) / packages.FOLDER / f'{world_id}.sqlite'
    return path if path.is_file() else None


TIMED = ('sticky', 'cooldown', 'delay', 'chance', 'group', 'group_weight')


def era_of(contents: dict) -> str | None:
    return ((contents['world'].get('starting_place') or {}).get('era')) or None


def keywords(entry: dict) -> list[str]:
    """The entry's keywords, each also without a leading "The" or a note in brackets: "The Badlands" comes up on
    "badlands", "The Source Font (the seam)" on "Source Font"."""
    found = []
    for word in entry.get('keywords') or []:
        for form in (word, re.sub(r'\s*\([^)]*\)', '', re.sub(r'^the\s+', '', word, flags=re.I)).strip()):
            if form and form.casefold() not in {item.casefold() for item in found}:
                found.append(form)
    return found


def entries(contents: dict, era: str | None) -> list[dict]:
    """The lore entries that hold in `era`, as lore.add_book takes them: keyword-triggered, none always on."""
    found = (contents['sections'].get('lore') or {}).get('entries') or []
    return [{'title': entry.get('title') or entry['id'], 'text': entry['text'], 'keywords': keywords(entry),
             'always': False, 'pattern': False, 'enabled': True,
             # Optional timing (dungeon/lore.py TIMING), as an entry's own fields.
             'timing': {key: entry[key] for key in TIMED if key in entry}}
            for entry in found if entry.get('text') and (not era or not entry.get('eras') or era in entry['eras'])]


def source(world_id: str, chosen: list[dict]) -> str:
    """The book's source_file: the world and a fingerprint of its entries, so a changed lore replaces the book."""
    digest = hashlib.sha256(json.dumps(chosen, sort_keys=True).encode()).hexdigest()[:16]
    return f'package:{world_id}:{digest}'


def bring(connection, root: Path, world_id: str, now: str, era: str | None = None) -> dict | None:
    """The world package's lore as a lore book in this world, added once and replaced when it changed; None when
    the world has no package or no lore."""
    path = package_path(root, world_id)
    if path is None:
        return None
    contents = packages.read(path)
    chosen = entries(contents, era or era_of(contents))
    if not chosen:
        return None
    wanted = source(world_id, chosen)
    held = many(connection, "SELECT id, source_file FROM lore_books WHERE source_format=? AND source_file LIKE ?",
                (FORMAT, f'package:{world_id}:%'))
    if any(row['source_file'] == wanted for row in held):
        return None
    for row in held:
        connection.execute('DELETE FROM lore_books WHERE id=?', (row['id'],))
    name = contents['world'].get('name') or world_id
    return lore.add_book(connection, now, {'name': f'{name} (world package)', 'format': FORMAT, 'entries': chosen,
                                           'description': f"{name}'s public lore, from its world package."}, wanted)
