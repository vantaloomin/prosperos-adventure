"""A world package's lore in play (docs/packages.md): the package's public lorebook, as a lore book of the campaign's
world (adventure/lore.py), so the narrator reads its entries by keyword like any imported lorebook.

Only the `lore` section comes in, and the package's hidden truths stay with the director and the record. A lore entry
is public unless the author tagged it (`visibility`: public, known with `known_to`, or gm; adventure/lore.py "Who may
read it"); untagged counts as public. Entries for another era than the campaign's are left out (an entry with no
`eras` holds in all of them). The book is read from the package file, so an edited or imported world plays as
edited; when the package's lore changes, the book is replaced on the next campaign start.

**Package facts** (`facts`, spec "Who sees what"): everything a package hides, each with its visibility tag, for the
context builders (adventure/rounds/context.py) to route. A package's hidden truths and its cast's secrets never count
as public, whatever they are tagged: a hidden truth is known to the cast its `known_by` names by id (a plain name
such as "the veterans" or "gudrun-stoneheart suspects" makes nobody know it), else GM only; a cast member's or
persona's secret is known to them; a power's secret is known to the cast member its `guise` names; any other hidden
field (a faction's secret) is GM only. An entry may add knowers with its own `known_to`, or keep its secret even from
its owner with `"visibility": "gm"`.
"""
import hashlib
import json
import re
from pathlib import Path

from adventure import lore, packages
from adventure.database import many

FORMAT = 'World package'
# Sections whose entries are characters, who know their own secrets.
CHARACTERS = ('cast', 'personas')


def package_path(root: Path, world_id: str) -> Path | None:
    """The world's package file: a built-in world's built (again) when out of date, an imported one as it is."""
    if world_id in packages.builtin_ids():
        return packages.installed(root, world_id)
    path = Path(root) / packages.FOLDER / f'{world_id}.sqlite'
    return path if path.is_file() else None


TIMED = ('sticky', 'cooldown', 'delay', 'chance', 'group', 'group_weight')
TAGS = ('visibility', 'known_to')


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
             # Optional timing (adventure/lore.py TIMING), as an entry's own fields.
             'timing': {key: entry[key] for key in TIMED if key in entry},
             # Who may read it (adventure/lore.py "Who may read it"), when the author tagged it.
             **{key: entry[key] for key in TAGS if key in entry}}
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


# Package facts ------------------------------------------------------------------------------------------

def section(contents: dict, name: str) -> list[dict]:
    found = (contents['sections'].get(name) or {}).get(packages.SECTIONS[name]) or []
    return [entry for entry in found if isinstance(entry, dict) and isinstance(entry.get('id'), str)]


def characters(contents: dict) -> set[str]:
    """The ids of the package's people: its cast and its personas."""
    return {entry['id'] for name in CHARACTERS for entry in section(contents, name)}


def plain(value) -> str:
    """A hidden field as text: a list joined, an object as its fields."""
    if isinstance(value, list):
        return '; '.join(plain(item) for item in value if item)
    if isinstance(value, dict):
        return '; '.join(f'{key}: {plain(item)}' for key, item in value.items() if item)
    return str(value).strip()


def hidden_tag(entry: dict, owners: list[str]) -> tuple[str, list[str]]:
    """A hidden fact's tag: known to its owners and the entry's own `known_to`, else GM only; never public."""
    if entry.get('visibility') == 'gm':
        return 'gm', []
    knowers = lore.keys_of(owners + lore.keys_of(entry.get('known_to')))
    return ('known', knowers) if knowers else ('gm', [])


def owners_of(name: str, entry: dict, people: set[str]) -> list[str]:
    """Who a hidden field of an entry belongs to: a person themselves, the person a power walks as, the people a
    hidden truth names by id as knowing it."""
    if name == 'hidden-truths':
        named = entry.get('known_by') if isinstance(entry.get('known_by'), list) else []
        return [key for key in named if key in people]
    if name in CHARACTERS:
        return [entry['id']]
    guise = entry.get('guise')
    return [guise['cast']] if isinstance(guise, dict) and guise.get('cast') in people else []


def facts(contents: dict) -> list[dict]:
    """Every hidden truth and secret in the package, each with its visibility tag, in section order: section, id,
    field, the entry's name, the text, visibility and known_to."""
    people, found = characters(contents), []
    for name in packages.SECTIONS:
        for entry in section(contents, name):
            fields = ('truth',) if name in packages.HIDDEN_SECTIONS else packages.HIDDEN_FIELDS
            visibility, known_to = hidden_tag(entry, owners_of(name, entry, people))
            for field in fields:
                text = plain(entry.get(field) or '')
                if text:
                    found.append({'section': name, 'id': entry['id'], 'field': field,
                                  'name': str(entry.get('name') or entry.get('title') or entry['id']), 'text': text,
                                  'visibility': visibility, 'known_to': known_to})
    return found


def tag_problems(contents: dict) -> list[str]:
    """What is wrong with the package's visibility tags: a tag that is not public, known or gm, known naming nobody,
    or naming someone who is not in the cast or personas (checked when either section is there)."""
    people, problems = characters(contents), []
    check_people = any(name in contents['sections'] for name in CHARACTERS)
    for name in packages.SECTIONS:
        for entry in section(contents, name):
            visibility = entry.get('visibility')
            known_to = entry.get('known_to')
            if visibility is not None and visibility not in lore.VISIBILITY:
                problems.append(f"{name} {entry['id']}: visibility is public, known or gm")
            if known_to is not None and not (isinstance(known_to, list) and all(isinstance(key, str)
                                                                                for key in known_to)):
                problems.append(f"{name} {entry['id']}: known_to is a list of cast or persona ids")
                continue
            if visibility == 'known' and not lore.keys_of(known_to):
                problems.append(f"{name} {entry['id']}: known needs known_to, the cast or persona ids who know it")
            for key in lore.keys_of(known_to) if check_people else []:
                if key not in people:
                    problems.append(f"{name} {entry['id']}: known_to {key} is not in cast or personas")
    return problems
