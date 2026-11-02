"""Campaign files and legacy (requirements "Campaign management": "a full campaign file (record, branches, saves,
settings) for backup or moving machines, importable again", and "at campaign start the player may import a finished
campaign's outcome as world history, so an old character can be a legend, a villain or a corpse"; docs/story.md
"Export and legacy").

- **The campaign file** is a verified Dungeon archive of the world being played (dungeon/backup.py): its whole
  database, so every branch, save, the record and the settings. Imported, it becomes a new world of its own, under
  the persona it was played by (made again when this install has no such persona); credentials stay behind.
- **Legacy.** Another world's story, ended or not, can be brought into a new campaign as history: its character,
  how they ended, and what the chapters say they did. As a **legend**, the world remembers them and their deeds.
  As a **villain**, they live on, hidden, and turned: a nemesis who comes back through the director. As a
  **corpse**, they are dead, and the record says so, so the narrator never has them act. The facts are weight 3, so
  they never fade.
"""
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from dungeon import backup, chapters, director, record, remembering, story, timeline, worlds
from dungeon.clock import AppClock
from dungeon.database import Database, identifier, many, one, optional
from dungeon.errors import DomainError, require

ROLES = ('legend', 'villain', 'corpse')
DEEDS = 4
LONGEST = 2_000_000_000


# The campaign file -----------------------------------------------------------------------------------------

def campaign_file(database: Database) -> tuple[bytes, str]:
    """The world being played as one verified archive, and a name for it."""
    data = worlds.registry(database)
    world = worlds.found(data['worlds'], data['active'], 'world')
    created_at = database.now()
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / 'campaign.zip'
        backup.archive(database.path, path, created_at)
        content = path.read_bytes()
    safe = ''.join(char if char.isalnum() else '-' for char in world['name']).strip('-').lower() or 'campaign'
    return content, f"campaign-{safe}-{created_at[:10]}.zip"


def persona_of(connection, timestamp: str) -> dict:
    row = optional(connection, 'SELECT * FROM persona WHERE id=1')
    require(row is not None, 'That campaign file has no character in it.', 422)
    return {'id': row['persona_id'], 'name': row['name'], 'gender': row['gender'], 'age': row['age'],
            'about': row['about'], 'birthday': row['birthday'], 'created_at': timestamp}


def import_campaign(database: Database, content: bytes) -> dict:
    """A campaign file made here or on another machine, as a new world. The world being played stays open."""
    require(0 < len(content) < LONGEST, 'That file is empty or too large to be a campaign file.', 422)
    data = worlds.registry(database)
    world_id = identifier()
    folder = f'{worlds.FOLDER}/{world_id}'
    path = database.root / folder / worlds.DATABASE
    with tempfile.TemporaryDirectory() as scratch:
        upload = Path(scratch) / 'campaign.zip'
        upload.write_bytes(content)
        backup.inspect(upload)
        try:
            made = backup.restore(upload, path, AppClock(database.clock.base))
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    timestamp = database.now()
    with made.connect() as connection:
        persona = persona_of(connection, timestamp)
        city_id = story.scene_row(connection)['city_id']
        name = (one(connection, 'SELECT name FROM persona WHERE id=1')['name'] or 'Imported campaign')
    if worlds.find(data['personas'], persona['id']) is None:
        data['personas'].append(persona)
    world = {'id': world_id, 'name': worlds.unique_name(data, f'{name} (imported)'[:80]), 'persona_id': persona['id'],
             'folder': folder, 'city_id': city_id, 'home': {}, 'created_at': timestamp, 'used_at': timestamp}
    with made.connect() as connection:
        if not worlds.restored_home(connection, world):
            worlds.settle_home(connection, world)
    data['worlds'].append(world)
    worlds.save(database.root, data)
    return worlds.view(database)


# Legacy ----------------------------------------------------------------------------------------------------

def told(database: Database, path: Path) -> dict | None:
    """What a world's story left: its character, whether they died, and its chapters; None with no story. The world
    is opened as it would be to play it, so an older one is brought up to this version's schema first."""
    if not path.exists():
        return None
    try:
        with Database(path, AppClock(database.clock.base)).connect() as connection:
            where, values = timeline.visible(connection)
            if one(connection, f"SELECT COUNT(*) AS n FROM story_messages WHERE {where} AND role='user'", values)['n'] == 0:
                return None
            persona = optional(connection, 'SELECT name, about FROM persona WHERE id=1') or {'name': '', 'about': ''}
            wounds = optional(connection, 'SELECT dead FROM story_wounds WHERE id=1')
            ending = optional(connection, 'SELECT ending FROM story_branches WHERE id=?', (timeline.active(connection),))
            listed = chapters.listing(connection)
            summary = optional(connection, 'SELECT text FROM story_summary ORDER BY rowid DESC LIMIT 1')
            deaths = [row['subject'] for row in many(connection, "SELECT subject FROM record_entries WHERE removed=0 AND "
                                                                 "kind='death' AND truth!='world' ORDER BY created_at")]
    except (sqlite3.Error, DomainError):
        return None
    return {'name': persona['name'], 'about': persona['about'],
            'dead': bool(wounds and wounds['dead']) or bool(ending and ending['ending'] == 'death'),
            'chapters': [{'title': chapter['title'], 'summary': chapter['summary']} for chapter in listed],
            'summary': (summary and summary['text']) or '', 'killed': deaths[:DEEDS]}


def candidates(database: Database) -> list[dict]:
    """Every other world with a story, to bring in as history."""
    data = worlds.registry(database)
    result = []
    for world in data['worlds']:
        if world['id'] == data['active']:
            continue
        found = told(database, worlds.world_path(database.home, world))
        if found and found['name']:
            result.append({'world_id': world['id'], 'world': world['name'], 'name': found['name'],
                           'dead': found['dead'], 'chapters': len(found['chapters'])})
    return result


def deeds(found: dict) -> str:
    done = [chapter['summary'] or chapter['title'] for chapter in found['chapters'] if chapter['summary']
            or not chapter['title'].startswith('Chapter ')]
    told_of = ' '.join(done[-DEEDS:]) or found['summary'] or found['about']
    return ' '.join(told_of.split())[:420]


def heavy(connection, entry: dict | None):
    if entry:
        connection.execute("UPDATE record_entries SET weight=3 WHERE id=?", (entry['id'],))


def chosen(database: Database, world_id: str, role: str) -> dict:
    """The earlier campaign to bring in, checked before the new one starts."""
    require(role in ROLES, 'A legacy character comes back as a legend, a villain or a corpse.', 422)
    data = worlds.registry(database)
    world = worlds.found(data['worlds'], world_id, 'world')
    require(world['id'] != data['active'], 'Bring in another world\'s story, not this one.', 422)
    found = told(database, worlds.world_path(database.home, world))
    require(bool(found and found['name']), 'That world has no story to bring in.', 409)
    return found


def bring(connection, found: dict, role: str, now: datetime):
    """An earlier campaign's character, in this one's record as history (and as a nemesis, for a villain)."""
    name, did, logged = found['name'], deeds(found), now.isoformat()
    # The deeds are the old campaign's own summaries, often in the present tense: framed as an old account, which
    # the narrator's record marks for retelling as history (dungeon/remembering.py), so the journal reads clean.
    history = f'{name} lived in an earlier age.' + (f' {remembering.HISTORY} {did}' if did else '')
    if role == 'legend':
        heavy(connection, record.add(connection, 'fact', name, f'{history} They are remembered as a legend; songs '
                                     'and stories still tell of them.', logged))
    elif role == 'corpse':
        heavy(connection, record.add(connection, 'fact', name, history, logged))
        heavy(connection, record.add(connection, 'death', name, f'{name} is long dead; their bones lie somewhere '
                                     'in this land.', logged))
    else:
        heavy(connection, record.add(connection, 'fact', name, f'{history} Most believe them dead or gone.', logged))
        grudge = (f'{name} did not die. They came back wrong, and they work against everyone who walks the road '
                  'they once walked, the character too.')
        heavy(connection, record.add(connection, 'secret', name, grudge, logged, truth='world'))
        thread_id = director.open_thread(connection, 'grudge', name, f'Some say {name} is still out there.', grudge,
                                         [part.lower() for part in name.split() if len(part) > 2], known=True,
                                         now=logged)
        connection.execute("INSERT INTO story_nemeses (id, name, grudge, remembers, status, since, thread_id) VALUES "
                           "(?, ?, ?, 'Resolve', 'alive', ?, ?)", (f'nemesis-{identifier()[:12]}', name, grudge,
                                                                  logged, thread_id))
