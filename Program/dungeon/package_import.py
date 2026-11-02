"""The world importer (requirements "World packages"; docs/packages.md "The importer"): an existing world's files made
into a package, one reviewed section at a time.

The author hands over the world's files (Markdown or text documents, lorebook JSON). Documents are kept as written
(`canon/<name>.md`), and a lorebook in any format the Lore screen reads (dungeon/imports/lorebooks.py) becomes the
`lore` section with no model at all. Every other section (regions, settlements, factions, powers, cast, personas,
hidden truths, planned beats) is drafted by a model from the documents when the author asks for it, and nothing
reaches the package until the author has read the section, changed what they want and approved it. Entries with a
hidden truth are counted on each section, so the author sees what the player must not.

A draft is a JSON file in the data folder (package-drafts/<id>.json) until it is finished: then it is checked like
a world folder (dungeon/packages.py validate) and written as the world's package.
"""
import json
import re
from pathlib import Path

from dungeon import packages, record
from dungeon.errors import DomainError, require
from dungeon.imports import lorebooks
from dungeon.text_models import config_for

FOLDER = 'package-drafts'
JOB = 'importer'
MAX_FILES = 200
MAX_BYTES = 4_000_000
# How much of the world's documents one drafting call reads; the rest is named as left out.
MAX_SOURCE = 60_000
MAX_ENTRIES = 200
# What the model is told each section holds: the fields of the built-in worlds' section files.
GUIDES = {
    'regions': 'Regions of the world: id, name, kind (land, sea, island or plane), terrain, summary, danger_tier '
               '(local, regional, realm, world or mythic).',
    'settlements': 'Cities, towns, villages, fortresses and sites: id, name, region (a region id), kind, size '
                   '(hamlet, village, town, city or metropolis), summary, ruled_by, peoples.',
    'factions': 'Realms, orders, cults, companies, gangs and courts: id, name, kind, tier, seat (a settlement id), '
                'summary, goals (a list), secret (only what is hidden from the player character).',
    'deities': 'Gods, patrons, spirits and other powers: id, name, group, domain (a list), status, nature, boons, '
               'price, secret (only what is hidden).',
    'cast': 'Named people: id, name, role, settlement (a settlement id), faction (a faction id), tier, look, voice, '
            'wants (a list), fears (a list), relationships (an object of person id to a line), secret (only what is '
            'hidden from the player character).',
    'personas': 'Characters a player could play: id, name, concept, look, background.',
    'hidden-truths': 'What is really so that the player character does not know: id, truth, believed (what most '
                     'people think instead), known_by (a list), surfaces (ways it can come out in play), stakes.',
    'beats': 'Planned story arcs the game steers toward without forcing them: id, name, tier, summary, stages (a '
             'list of short lines, in order).',
    'lore': 'Public lore entries the narrator reads by keyword: id, title, keywords (a list of words that bring '
            'it up), text. Nothing hidden from the player character goes here.',
}
DRAFT = """You turn a tabletop world's own documents into one section of a world package. Section: {section}. \
{guide}
Use only what the documents say; leave a field out rather than invent it, and write names as the documents do. Ids \
are lowercase-kebab-case and unique; a field that names another entry uses that entry's id. Put anything the player \
character must not know in the hidden fields only. Answer with JSON only: {{"entries": [ ... ]}}."""
SHAPE = {'type': 'object', 'properties': {'entries': {'type': 'array', 'items': {'type': 'object'}}},
         'required': ['entries']}
STATUSES = ('empty', 'drafted', 'approved')


def slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower().replace("'", '').replace('’', '')).strip('-')[:60]


def folder(root: Path) -> Path:
    return Path(root) / FOLDER


def path_for(root: Path, draft_id: str) -> Path:
    path = folder(root) / f'{draft_id}.json'
    require(packages.ID.match(draft_id) is not None and path.is_file(), 'That world import does not exist.', 404)
    return path


def load(root: Path, draft_id: str) -> dict:
    return json.loads(path_for(root, draft_id).read_text(encoding='utf-8'))


def save(root: Path, draft: dict) -> dict:
    packages.dump(folder(root) / f"{draft['id']}.json", draft)
    return view(draft)


# Starting --------------------------------------------------------------------------------------------

def start(root: Path, name: str, files: list[dict], now: str) -> dict:
    """A new import from the world's files: documents kept, a lorebook read as the lore section."""
    world_id = slug(name)
    require(bool(world_id), 'Give the world a name.', 422)
    require(world_id not in packages.builtin_ids(), f'{name} is a built-in world; give the import another name.', 409)
    require(bool(files) and len(files) <= MAX_FILES, f'Add between 1 and {MAX_FILES} files.', 422)
    require(sum(len(item['text']) for item in files) <= MAX_BYTES, 'These files are too big to import at once.', 413)
    draft = {'id': world_id, 'created_at': now, 'world': {'schema_version': 1, 'id': world_id, 'name': name},
             'documents': {}, 'sections': {section: blank() for section in packages.SECTIONS}, 'notes': []}
    for item in files:
        take(draft, item['name'], item['text'])
    return save(root, draft)


def blank() -> dict:
    return {'status': 'empty', 'entries': [], 'from': ''}


def take(draft: dict, name: str, text: str):
    """One file into the draft: a lorebook into the lore section, anything else kept as a document."""
    book = lorebook(name, text)
    if book is not None:
        lore = draft['sections']['lore']
        lore['entries'] = unique(lore['entries'] + [lore_entry(found) for found in book['entries']])
        lore['status'], lore['from'] = 'drafted', 'lorebook'
        draft['notes'].append(f"{name}: {book['format']}, {len(book['entries'])} entries, read as the lore section.")
        return
    path = f"canon/{slug(Path(name).stem) or 'document'}.md"
    while path in draft['documents']:
        path = path.removesuffix('.md') + '-2.md'
    draft['documents'][path] = text


def lorebook(name: str, text: str) -> dict | None:
    if not name.lower().endswith('.json'):
        return None
    try:
        value = json.loads(text)
        found = lorebooks.kind_of(value)
        return lorebooks.book(value, *found, Path(name).stem) if found else None
    except (ValueError, DomainError):
        return None


def lore_entry(entry: dict) -> dict:
    return {'id': slug(entry['title']) or 'entry', 'title': entry['title'], 'keywords': entry['keywords'],
            'text': entry['text']}


def unique(entries: list[dict]) -> list[dict]:
    """Entries with ids made unique (a repeated id gets -2, -3)."""
    seen, kept = set(), []
    for entry in entries:
        base = entry['id']
        number = 1
        while entry['id'] in seen:
            number += 1
            entry = entry | {'id': f'{base}-{number}'}
        seen.add(entry['id'])
        kept.append(entry)
    return kept


# Drafting --------------------------------------------------------------------------------------------

def source_text(draft: dict) -> str:
    """The world's documents for a drafting call, cut to MAX_SOURCE characters."""
    text = '\n\n'.join(f'# {path}\n\n{body}' for path, body in draft['documents'].items())
    if len(text) > MAX_SOURCE:
        text = text[:MAX_SOURCE] + '\n\n[The rest of the documents is left out.]'
    return text


def known_ids(draft: dict) -> str:
    """The ids of entries already in other sections, so a drafted entry can name them."""
    lines = [f"{name}: {', '.join(entry['id'] for entry in data['entries'][:80])}"
             for name, data in draft['sections'].items() if data['entries']]
    return ('\n\nIds already in the package:\n' + '\n'.join(lines)) if lines else ''


def entries_from(answer: str) -> list[dict]:
    """The model's entries, each given a kebab-case id from its id, name or title; the rest dropped."""
    data = record.read_json(answer)
    found = data.get('entries') if isinstance(data, dict) else None
    require(isinstance(found, list), 'The model did not answer with entries. Try again, or use another model.', 502)
    kept = []
    for entry in found[:MAX_ENTRIES]:
        if not isinstance(entry, dict):
            continue
        entry_id = slug(entry.get('id') or entry.get('name') or entry.get('title') or '')
        if entry_id:
            kept.append(entry | {'id': entry_id})
    return unique(kept)


async def draft_section(state, root: Path, draft_id: str, section: str) -> dict:
    """A section drafted by the importer's model from the documents, for the author to review."""
    require(section in packages.SECTIONS, 'That is not a section of a world package.', 404)
    draft = load(root, draft_id)
    require(bool(draft['documents']), 'This import has no documents to draft from.', 409)
    with state.database.connect() as connection:
        config = config_for(connection, JOB)
    require(config is not None, 'Choose a model for the World importer, or a Default one, in Settings > Models.', 409)
    asking = f"World: {draft['world']['name']}{known_ids(draft)}\n\n{source_text(draft)}"
    answer = await record.schema_first(state, config, DRAFT.format(section=section, guide=GUIDES[section]), asking,
                                       SHAPE, lambda answer: isinstance((record.read_json(answer) or {}).get('entries'), list))
    draft = load(root, draft_id)
    draft['sections'][section] = {'status': 'drafted', 'entries': entries_from(answer), 'from': 'model'}
    return save(root, draft)


# Review ----------------------------------------------------------------------------------------------

def review(root: Path, draft_id: str, section: str, entries: list | None, status: str) -> dict:
    """The author's word on a section: its entries as edited, and drafted (still to read), approved or cleared."""
    require(section in packages.SECTIONS, 'That is not a section of a world package.', 404)
    require(status in STATUSES, 'A section is empty, drafted or approved.', 422)
    draft = load(root, draft_id)
    held = draft['sections'][section]
    if entries is not None:
        problems: list[str] = []
        packages.section_ids(section, entries, problems)
        require(not problems, '; '.join(problems[:6]), 422)
        held['entries'] = entries
    if status == 'empty':
        held.update(blank())
    else:
        require(bool(held['entries']), 'There is nothing in this section to approve.', 409)
        held['status'] = status
    return save(root, draft)


def contents(draft: dict) -> dict:
    """The package the draft makes: its approved sections only."""
    sections = {name: {'schema_version': 1, packages.SECTIONS[name]: data['entries']}
                for name, data in draft['sections'].items() if data['status'] == 'approved'}
    return {'world': draft['world'], 'sections': sections, 'documents': draft['documents'], 'engine': {},
            'assets': {}}


def checked(found: dict) -> list[str]:
    """What is wrong with the package: what the validator finds, and names of entries in a section not approved
    (the validator checks those only when the section is there)."""
    problems = packages.validate(found)
    sections = found['sections']
    for section, field, target in packages.REFERENCES:
        if section in sections and target not in sections:
            problems += packages.broken_references(section, sections[section][packages.SECTIONS[section]], field,
                                                   target, set())
    return problems


def view(draft: dict) -> dict:
    """The draft as the review screen shows it: each section with its entries, how many hold a hidden truth, and
    what stands in the way of finishing."""
    waiting = [name for name, data in draft['sections'].items() if data['status'] == 'drafted']
    problems = checked(contents(draft))
    sections = [{'id': name, 'status': data['status'], 'from': data['from'], 'entries': data['entries'],
                 'hidden': sum(packages.hidden(name, entry) for entry in data['entries'])}
                for name, data in draft['sections'].items()]
    return {'id': draft['id'], 'name': draft['world']['name'], 'created_at': draft['created_at'],
            'documents': sorted(draft['documents']), 'notes': draft['notes'], 'sections': sections,
            'waiting': waiting, 'problems': problems,
            'ready': not waiting and not problems and any(item['status'] == 'approved' for item in sections)}


def drafts(root: Path) -> list[dict]:
    found = sorted(folder(root).glob('*.json')) if folder(root).is_dir() else []
    return [{'id': draft['id'], 'name': draft['world']['name'], 'created_at': draft['created_at']}
            for draft in (json.loads(path.read_text(encoding='utf-8')) for path in found)]


def finish(root: Path, draft_id: str, replace: bool = False) -> dict:
    """The approved draft written as the world's package; the draft is then gone."""
    draft = load(root, draft_id)
    shown = view(draft)
    require(not shown['waiting'], f"Approve or clear these sections first: {', '.join(shown['waiting'])}.", 409)
    require(not shown['problems'], 'The package has problems: ' + '; '.join(shown['problems'][:8]), 422)
    require(shown['ready'], 'Approve at least one section first.', 409)
    target = Path(root) / packages.FOLDER / f'{draft_id}.sqlite'
    require(replace or not target.exists(), f"There is already a {draft['world']['name']} package.", 409)
    summary = packages.summary(packages.write(contents(draft), target))
    path_for(root, draft_id).unlink()
    return summary


def remove(root: Path, draft_id: str):
    path_for(root, draft_id).unlink()
