"""Art on request (requirements "Art"; docs/story.md "Art"): portraits, places and illustrated passages, made only
when the player asks, through the image backends in Settings (dungeon/images).

- **What can be pictured.** A portrait of the player's character (`player`) or of anyone they have met (their key);
  the scene's place at this hour and weather; a passage of the story (a narrator message's id); or the whole scene
  (the place, who is there, and the latest passage).
- **Built from what code tracks.** A portrait reads the persona's own description, their condition, lasting
  injuries and what they carry; someone met reads who the town says they are, the notes the story kept about them,
  and their mood toward the character from the feeling axes. Nothing comes from a model.
- **One reference per character.** The first portrait made of someone is their reference, sent with every later
  picture of them to a backend that takes one, so they keep looking like themselves.
- **Out of date.** Each picture keeps a fingerprint of what it was built from. When that changes (a new wound, a
  change of heart, the hour moves on) the picture is marked out of date and one click makes it again. A passage
  never goes out of date.
- **Where it goes.** Each request is classified (dungeon/images/content.py) and routed to the enabled backends in
  the player's order (dungeon/images/routing.py): NSFW only to backends that take it, prohibited nowhere. A backend
  that fails passes the request on to the next, so a hosted API's failure (a rejected key too) reaches a local
  ComfyUI set up after it. A provider's content refusal passes it on only to backends that take NSFW.
- **Kept with the chapter** it was made in, so the book can carry it.
- **Passive art** (the `passive_art` setting, off by default) adds pictures on their own after a turn, at most one a
  turn and PASSIVE_CAP a session, only with a backend enabled: the portrait of someone in the scene who has none,
  then a portrait of someone here that has gone out of date (live-state portraits), then the place when it has no
  picture, then the scene when a chapter is about to close.
- **The stage** (`stage`) shows the place's picture behind the story and the portraits of who is here, VN style.
- **Default backdrops** (`backdrop`): with no picture made of the place, the stage shows the world's stock picture of
  that kind of place (engine/art/<world>.json `backdrops`, images in the package's assets/backdrops, made once by
  scripts/art/backdrops.py), so it has a picture with no image backend at all. Picked by the place's own `backdrop`,
  then out in the wild the hex's site or terrain, a blank lot's entry, the most tags shared, the place's kind, the
  street for out and about, else the world's default. An outdoor one has a night image; dawn and dusk tint it.
- **Default portraits** (`stock_portrait`): someone met who is here with no portrait of their own stands on the stage
  in the world's stock portrait of their kind of person (engine/art/<world>-portraits.json `portraits`, images in the
  package's assets/portraits, made once by scripts/art/portraits.py). Picked by their folk, then the words of their
  job, their pronouns and their age; people who fit the same portraits are spread across them by key.

Pictures are not game state: going back in the story keeps them.
"""
import asyncio
import hashlib
import random
import re
from datetime import datetime

from dungeon import (
    chapters,
    combat,
    feelings,
    hexes,
    injuries,
    inventory,
    story,
    story_clock,
    tiers,
    travel,
    world_data,
)
from dungeon.database import decode, identifier, many, one, optional
from dungeon.errors import require
from dungeon.images import backends as image_backends
from dungeon.images import content, routing, storage
from dungeon.images.adapters.base import AdapterError, ImageRequest, size_for
from dungeon.world import catalog, decades, townsfolk

KINDS = ('portrait', 'place', 'scene', 'passage')
PASSIVE_CAP = 6
ASPECT = {'portrait': 'portrait', 'place': 'landscape', 'scene': 'landscape', 'passage': 'landscape'}
STYLE = 'Detailed painterly illustration, natural light, grounded and realistic, no text or lettering'
NEGATIVE = 'text, watermark, signature, caption, logo, extra fingers, deformed hands, blurry'
PASSAGE_CHARS = 700
GEAR = ('weapon', 'weapons', 'armour', 'armor', 'clothing', 'clothes', 'shield')
# The light a default backdrop is shown in, by the hour it starts.
LIGHTS = ((5, 'dawn'), (8, 'day'), (18, 'dusk'), (21, 'night'))
# A stock portrait's `age` band, by the age it ends before.
AGE_BANDS = ((30, 'young'), (55, 'middle'), (10 ** 6, 'old'))
HOURS = ((5, 'at dawn'), (8, 'in the morning'), (12, 'at midday'), (15, 'in the afternoon'), (18, 'at dusk'),
         (21, 'at night'))


def style(world: str | None) -> str:
    """The world's own look (engine/art/<world>.json `style`), else the general one."""
    found = world_data.read('art', world) if world else None
    return (found or {}).get('style') or STYLE


def hour_text(moment: datetime) -> str:
    return next((words for start, words in reversed(HOURS) if moment.hour >= start), 'at night')


def mood(row: dict | None) -> str:
    """Their face toward the character, from the strongest feeling."""
    if not row:
        return 'a neutral expression'
    axes = feelings.of(row)
    axis, value = max(axes.items(), key=lambda pair: abs(pair[1]))
    if abs(value) < 2:
        return 'a neutral expression'
    faces = {'trust': ('an open, easy expression', 'a guarded, suspicious look'),
             'affection': ('a warm smile', 'a cold, hostile look'), 'respect': ('a look of respect', 'a dismissive sneer'),
             'fear': ('a frightened, wary look', 'a bold, unafraid look'),
             'desire': ('a lingering, interested look', 'an uninterested look')}
    return faces[axis][0 if value > 0 else 1]


# What a picture is built from ----------------------------------------------------------------------

def player_prompt(connection, view: dict) -> str:
    row = optional(connection, 'SELECT name, gender, age, about FROM persona WHERE id=1') or {}
    details = ', '.join(str(item) for item in (row.get('age') and f"{row['age']} years old", row.get('gender')) if item)
    level = combat.condition(connection)['level']
    hurt = f'They are {combat.word(connection, level)}.' if level else 'They are unhurt.'
    marks = ' '.join(entry['seen'] for entry in injuries.active(connection, view['now']))
    gear = [item['name'] for item in inventory.carried(connection, view['city']['id'])
            if str(item.get('category', '')).lower() in GEAR][:4]
    return ' '.join(part for part in (
        f"Portrait of {row.get('name') or 'the traveller'}" + (f' ({details})' if details else '') + '.',
        (row.get('about') or '').strip(), hurt, marks, f"Carrying: {', '.join(gear)}." if gear else '',
        f"In {view['place']['name']}, {view['city']['name']}, {hour_text(datetime.fromisoformat(view['local_time']))}.")
        if part)


def person_prompt(connection, view: dict, key: str) -> str:
    row = optional(connection, 'SELECT * FROM story_people WHERE key=?', (key,))
    # Someone here in the scene counts too, though the record has not met them yet (playtest m6a).
    here = next((person['sheet'] for person in view['people'] if person['sheet'].get('key') == key), None)
    require(row is not None or here is not None, "You haven't met them in your story.", 404)
    data = story.city_data(connection, row['city_id'] if row else view['city']['id'])
    sheet = townsfolk.find(data, key) or here or {}
    name = row['name'] if row else sheet.get('name', 'someone')
    who = ', '.join(str(part) for part in (sheet.get('pronouns'), sheet.get('age') and f"{sheet['age']} years old",
                                           sheet.get('occupation') or sheet.get('role')) if part)
    looks = townsfolk.first_impression(sheet) if sheet.get('seed') else ''
    notes = ' '.join(decode(row['notes'])[-2:]) if row else ''
    return ' '.join(part for part in (
        f"Portrait of {name}" + (f' ({who})' if who else '') + f", in {data['name']}.",
        f'{looks[:1].upper()}{looks[1:]}.' if looks else '', notes, f'With {mood(row)}.') if part)


def place_prompt(view: dict) -> str:
    place, moment = view['place'], datetime.fromisoformat(view['local_time'])
    return ' '.join(part for part in (
        f"{place['name']}, {place['neighborhood']}, {view['city']['name']}, {hour_text(moment)}.",
        place.get('summary', ''), view['weather'], 'No people in the foreground.') if part)


def passage_prompt(connection, view: dict, message_id: str) -> str:
    row = optional(connection, "SELECT text FROM story_messages WHERE id=? AND role='narrator'", (message_id,))
    require(row is not None, 'That passage is not in the story.', 404)
    text = row['text'].strip()
    shown = text if len(text) <= PASSAGE_CHARS else text[:PASSAGE_CHARS].rsplit(' ', 1)[0] + '…'
    return f"A scene in {view['place']['name']}, {view['city']['name']}: {shown}"


def scene_prompt(connection, view: dict) -> str:
    latest = optional(connection, "SELECT id FROM story_messages WHERE role='narrator' ORDER BY seq DESC LIMIT 1")
    there = ', '.join(person['sheet']['full'] for person in view['people'][:4])
    return ' '.join(part for part in (
        place_prompt(view).replace(' No people in the foreground.', ''),
        f'Present: {there}.' if there else '',
        passage_prompt(connection, view, latest['id']).split(': ', 1)[1] if latest else '') if part)


def built(connection, database, kind: str, subject: str) -> tuple[str, str]:
    """What the picture shows, and the subject it is kept under (a place is kept by its place)."""
    view = story.scene(connection, story_clock.now(connection, database.clock))
    # A modern world in a past year: clothes, phones and cars of that year (dungeon/world/decades.py).
    year = decades.picture_text(view['data'], datetime.fromisoformat(view['local_time']), database.clock.now().year)
    dated = (lambda prompt: f'{prompt} {year}') if year else (lambda prompt: prompt)
    if kind == 'portrait':
        return (dated(player_prompt(connection, view) if subject == 'player' else
                      person_prompt(connection, view, subject)), subject)
    if kind == 'place':
        return dated(place_prompt(view)), f"{view['city']['id']}/{view['place']['id']}"
    if kind == 'passage':
        return dated(passage_prompt(connection, view, subject)), subject
    return dated(scene_prompt(connection, view)), f"{view['city']['id']}/{view['place']['id']}"


def fingerprint(prompt: str) -> str:
    return hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:16]


# Requests ------------------------------------------------------------------------------------------

def request(database, kind: str, subject: str) -> dict:
    """A picture asked for: queued with what it shows. The caller runs it (make)."""
    require(kind in KINDS, 'That is not something to picture.', 422)
    with database.connect(write=True) as connection:
        prompt, kept = built(connection, database, kind, subject)
        world = tiers.world_of(story.scene_row(connection)['city_id'])
        art_id = f'art-{identifier()[:12]}'
        # The chapter open now (dungeon/chapters.py), which the book carries it with.
        chapter = next((item for item in reversed(chapters.listing(connection)) if item['open']), None)
        connection.execute('INSERT INTO story_art (id, kind, subject, chapter_id, prompt, style, state, status, '
                           "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)",
                           (art_id, kind, kept, chapter['id'] if chapter else None, prompt, style(world),
                            fingerprint(prompt), database.now()))
        return view_of(one(connection, 'SELECT * FROM story_art WHERE id=?', (art_id,)), None)


def reference_of(connection, database, kind: str, subject: str) -> bytes | None:
    if kind != 'portrait':
        return None
    row = optional(connection, "SELECT file FROM story_art WHERE kind='portrait' AND subject=? AND reference=1",
                   (subject,))
    try:
        return storage.path_of(database, row['file']).read_bytes() if row else None
    except FileNotFoundError:
        return None


def finish(database, art_id: str, status: str, **fields):
    names = ', '.join(f'{name}=?' for name in fields)
    with database.connect(write=True) as connection:
        connection.execute(f'UPDATE story_art SET status=?, {names} WHERE id=?' if names else
                           'UPDATE story_art SET status=? WHERE id=?', (status, *fields.values(), art_id))
        row = one(connection, 'SELECT * FROM story_art WHERE id=?', (art_id,))
        # The first portrait of someone becomes their reference.
        if status == 'done' and row['kind'] == 'portrait' and not optional(
                connection, "SELECT 1 FROM story_art WHERE kind='portrait' AND subject=? AND reference=1",
                (row['subject'],)):
            connection.execute('UPDATE story_art SET reference=1 WHERE id=?', (art_id,))


def attempt(state, row: dict, backend: dict, reference: bytes | None) -> ImageRequest:
    config = decode(backend['config'])
    key = image_backends.backend_key(state.database, state.vault, backend)
    width, height = size_for(backend['kind'], ASPECT[row['kind']])
    look = image_backends.style_for(backend, row['style'])
    return ImageRequest(job_id=row['id'], prompt=f"{look}. {row['prompt']}" if look else row['prompt'],
                        negative=NEGATIVE, seed=random.SystemRandom().randint(1, 2 ** 31 - 1), width=width,
                        height=height, backend=backend, config=config, key=key,
                        raw_dir=storage.raw_directory(state.database),
                        reference=reference if image_backends.takes_reference(backend) else None)


async def make(state, art_id: str):
    """Make a queued picture on the first backend that will take it, passing it on when one fails."""
    database = state.database
    with database.connect(write=True) as connection:
        row = one(connection, 'SELECT * FROM story_art WHERE id=?', (art_id,))
        connection.execute("UPDATE story_art SET status='running' WHERE id=?", (art_id,))
        enabled = image_backends.ordered(connection, enabled_only=True)
        reference = reference_of(connection, database, row['kind'], row['subject'])
    found = routing.route(content.classify({'prompt': row['prompt']}), enabled)
    if found.refusal:
        finish(database, art_id, 'refused', error=found.refusal)
        return
    error, refused = 'No image backend could make it.', False
    for backend in found.backends:
        # A provider's content refusal counts the picture as NSFW from then on: never offered to a backend that
        # takes safe requests only (F6), a local ComfyUI or an NSFW-allowed API still may.
        if refused and not image_backends.accepts_nsfw(backend):
            continue
        try:
            result = await state.image_adapters[backend['kind']].generate(attempt(state, row, backend, reference))
            kept = storage.store(database, art_id, result.data)
        except AdapterError as failure:
            error = failure.message
            refused = refused or failure.code == 'refused'
            if failure.code == 'auth':
                image_backends.block(database, backend['id'], failure.message)
            continue
        finish(database, art_id, 'done', file=kept['file'], width=kept['width'], height=kept['height'],
               backend_id=backend['id'], done_at=database.now())
        return
    finish(database, art_id, 'failed', error=error)


def start(state, art_id: str):
    """Run the picture in the background; tests without a background run it at once."""
    if state.background:
        task = asyncio.get_running_loop().create_task(make(state, art_id))
        state.art_tasks = getattr(state, 'art_tasks', set()) | {task}
        task.add_done_callback(lambda done: state.art_tasks.discard(done))
        return None
    return make(state, art_id)


# The gallery ---------------------------------------------------------------------------------------

def view_of(row: dict, current: str | None) -> dict:
    return {'id': row['id'], 'kind': row['kind'], 'subject': row['subject'], 'chapter_id': row['chapter_id'],
            'status': row['status'], 'error': row['error'], 'reference': bool(row['reference']),
            'url': f"/api/story/art/{row['id']}/file" if row['file'] else None, 'width': row['width'],
            'height': row['height'], 'created_at': row['created_at'],
            'stale': bool(current and row['status'] == 'done' and current != row['state'])}


def current_state(connection, database, row: dict) -> str | None:
    """The fingerprint the picture would have now; None for a passage, or when it can no longer be built."""
    if row['kind'] == 'passage':
        return None
    try:
        prompt, kept = built(connection, database, row['kind'], row['subject'] if row['kind'] == 'portrait' else '')
    except Exception:  # noqa: BLE001 - someone gone or a place left: the picture stays as it was.
        return None
    return fingerprint(prompt) if kept == row['subject'] else None


def gallery(database) -> list[dict]:
    """The newest picture of each subject, marked when out of date, newest first; failures since the last made one
    too."""
    with database.connect() as connection:
        rows = many(connection, 'SELECT * FROM story_art ORDER BY created_at DESC, rowid DESC')
        seen, out = set(), []
        for row in rows:
            if (row['kind'], row['subject']) in seen:
                continue
            seen.add((row['kind'], row['subject']))
            out.append(view_of(row, current_state(connection, database, row)))
        return out


def stage(database) -> dict:
    """What the story's stage shows (requirements "Art": background art and VN portraits): the newest finished
    picture of the place behind the story, and the newest finished portrait of each person here who has one."""
    with database.connect() as connection:
        view = story.scene(connection, story_clock.now(connection, database.clock))
        here = f"{view['city']['id']}/{view['place']['id']}"
        known = {row['key']: row['name'] for row in many(connection, 'SELECT key, name FROM story_people')}
        sheets = {person['sheet']['key']: person['sheet'] for person in view['people']
                  if person['sheet'].get('key') in known}
        done = many(connection, "SELECT * FROM story_art WHERE status='done' AND file IS NOT NULL AND "
                                "kind IN ('place', 'portrait') ORDER BY created_at DESC, rowid DESC")
        place = next((row for row in done if row['kind'] == 'place' and row['subject'] == here), None)
        fallback = None if place else backdrop(connection, view)
    world, portraits = tiers.world_of(view['city']['id']), []
    for key, sheet in sheets.items():
        if row := next((row for row in done if row['kind'] == 'portrait' and row['subject'] == key), None):
            portraits.append({'key': key, 'name': known[key], 'url': f"/api/story/art/{row['id']}/file",
                              'width': row['width'], 'height': row['height']})
        elif stock := stock_portrait(world, sheet):
            portraits.append({'key': key, 'name': known[key], 'url': stock, 'width': None, 'height': None,
                              'default': True})
    made = place and {'url': f"/api/story/art/{place['id']}/file", 'width': place['width'], 'height': place['height']}
    return {'background': made or fallback, 'portraits': portraits}


# Default backdrops ---------------------------------------------------------------------------------

def backdrops(world: str | None) -> list[dict]:
    return ((world_data.read('art', world) if world else None) or {}).get('backdrops', [])


def light(moment: datetime) -> str:
    return next((word for start, word in reversed(LIGHTS) if moment.hour >= start), 'night')


def out_in_the_wild(connection, world: str, city_id: str, place_id: str) -> tuple[str | None, str] | None:
    """Out in the wild on a hex crawl: the found site's kind in this hex (or None), and its terrain ('road' on one)."""
    for travel_map in travel.maps():
        wild = travel_map.get('wild') if travel_map.get('world') == world and hexes.is_hex(travel_map) else None
        if not wild or (wild.get('city'), wild.get('place')) != (city_id, place_id):
            continue
        board = hexes.grid(connection, travel_map)
        if where := hexes.position(connection, board):
            cell, site = board.cell(where['at']), hexes.found_sites(connection, board).get(where['at'])
            return site and site['kind'], 'road' if cell['road'] else cell['terrain']
    return None


def pick(entries: list[dict], place: dict | None, wild: tuple[str | None, str] | None, street: bool) -> dict | None:
    """The backdrop for a place, in the order the module notes give."""
    place = place or {}
    by_id = {entry['id']: entry for entry in entries}
    tags = [tag for tag in place.get('tags', []) if tag != 'lot']
    lot = tags[0] if 'lot' in place.get('tags', []) and tags else None
    shared = max(entries, key=lambda entry: len(set(entry.get('tags', [])) & set(tags)), default=None)
    steps = (by_id.get(place.get('backdrop')),
             wild and next((entry for entry in entries if wild[0] in entry.get('sites', [])), None),
             wild and next((entry for entry in entries if wild[1] in entry.get('terrains', [])), None),
             lot and next((entry for entry in entries if lot in entry.get('lots', [])), None),
             shared if shared and set(shared.get('tags', [])) & set(tags) else None,
             next((entry for entry in entries if place.get('kind') in entry.get('kinds', [])), None) if not street else None,
             next((entry for entry in entries if entry.get('street')), None) if street else None,
             next((entry for entry in entries if entry.get('default')), None))
    return next((entry for entry in steps if entry), None)


def backdrop(connection, view: dict) -> dict | None:
    """The world's stock picture of this kind of place, for the stage when none is made, in the hour's light."""
    world = tiers.world_of(view['city']['id'])
    entries = backdrops(world)
    if not entries:
        return None
    place_id = view['place']['id']
    wild = out_in_the_wild(connection, world, view['city']['id'], place_id)
    entry = pick(entries, catalog.find(view['data'], place_id), wild, place_id.startswith('~'))
    if entry is None:
        return None
    owner = entry.get('from') or world
    shade = light(datetime.fromisoformat(view['local_time']))
    night = entry.get('outdoor') and shade == 'night' and world_data.asset(owner, f"backdrops/{entry['id']}-night.webp")
    name = f"{entry['id']}-night.webp" if night else f"{entry['id']}.webp"
    if not night and not world_data.asset(owner, f'backdrops/{name}'):
        return None
    return {'url': f'/api/story/art/backdrop/{owner}/{name}', 'width': None, 'height': None, 'default': True,
            'light': shade if entry.get('outdoor') and not night else 'day'}


def backdrop_file(world: str, name: str) -> bytes:
    found = world_data.asset(world, f'backdrops/{name}') if name.endswith('.webp') and '/' not in name else None
    require(found is not None, 'There is no such backdrop.', 404)
    return found


# Default portraits --------------------------------------------------------------------------------

def stock_portraits(world: str | None) -> list[dict]:
    return ((world_data.read('art', f'{world}-portraits') if world else None) or {}).get('portraits', [])


def age_band(age) -> int | None:
    """Which of AGE_BANDS an age falls in, by index."""
    return next(index for index, (end, _band) in enumerate(AGE_BANDS) if age < end) if isinstance(age, int) else None


def portrait_pick(entries: list[dict], sheet: dict) -> dict | None:
    """The stock portrait for someone, in the order the module notes give, or None."""
    folk = sheet.get('folk')
    job = f"{sheet.get('occupation') or ''} {sheet.get('role') or ''}".lower()
    pronoun = next((word for word in ('she', 'he') if str(sheet.get('pronouns', '')).startswith(word)), None)
    band = age_band(sheet.get('age'))
    bands = [name for _end, name in AGE_BANDS]
    scored = []
    for entry in entries:
        if (entry.get('folk') and folk not in entry['folk']) or (pronoun and entry.get('pronouns', pronoun) != pronoun):
            continue
        named = any(re.search(rf'\b{re.escape(word.lower())}\b', job) for word in entry.get('roles', []))
        if not (entry.get('folk') or named or entry.get('default')):
            continue
        near = 2 - abs(band - bands.index(entry['age'])) if band is not None and entry.get('age') in bands else 0
        scored.append((8 * bool(entry.get('folk')) + 4 * named + near, entry))
    best = max((score for score, _entry in scored), default=None)
    tied = [entry for score, entry in scored if score == best]
    if not tied:
        return None
    return tied[int(hashlib.sha1(str(sheet.get('key', '')).encode('utf-8')).hexdigest(), 16) % len(tied)]


def stock_portrait(world: str | None, sheet: dict) -> str | None:
    """The url of the world's stock portrait for someone, when it has been made."""
    entry = portrait_pick(stock_portraits(world), sheet)
    name = entry and f"{entry['id']}.webp"
    return f'/api/story/art/portrait/{world}/{name}' if name and world_data.asset(world, f'portraits/{name}') else None


def portrait_file(world: str, name: str) -> bytes:
    found = world_data.asset(world, f'portraits/{name}') if name.endswith('.webp') and '/' not in name else None
    require(found is not None, 'There is no such portrait.', 404)
    return found


def file_of(database, art_id: str):
    with database.connect() as connection:
        row = optional(connection, 'SELECT file FROM story_art WHERE id=?', (art_id,))
    require(row is not None and row['file'], 'That picture is not made.', 404)
    return storage.path_of(database, row['file'])


# Passive art --------------------------------------------------------------------------------------

def wanted(connection, database, present: list[str]) -> tuple[str, str] | None:
    """The one picture this turn calls for, if any: someone here with no portrait, the place with no picture, or the
    scene as a chapter closes."""
    pictured = {(row['kind'], row['subject']) for row in many(connection, 'SELECT kind, subject FROM story_art')}
    if who := next((key for key in present if ('portrait', key) not in pictured), None):
        return 'portrait', who
    # Live-state portraits: someone here whose portrait no longer shows them as they are (a wound, a change of heart).
    if who := next((key for key in present if stale_portrait(connection, database, key)), None):
        return 'portrait', who
    row = story.scene_row(connection)
    here = f"{row['city_id']}/{row['place_id']}"
    if ('place', here) not in pictured and not row['place_id'].startswith('~'):
        return 'place', ''
    last_line = optional(connection, "SELECT created_at FROM story_messages WHERE role='user' ORDER BY seq DESC LIMIT 1")
    latest_scene = optional(connection, "SELECT created_at FROM story_art WHERE kind='scene' ORDER BY created_at DESC "
                                        'LIMIT 1')
    if chapters.pending(connection) and last_line and (not latest_scene or latest_scene['created_at'] < last_line['created_at']):
        return 'scene', ''
    return None


def stale_portrait(connection, database, key: str) -> bool:
    row = optional(connection, "SELECT * FROM story_art WHERE kind='portrait' AND subject=? ORDER BY created_at DESC, "
                               'rowid DESC LIMIT 1', (key,))
    if row is None or row['status'] != 'done':
        return False
    current = current_state(connection, database, row)
    return bool(current and current != row['state'])


async def passive(state, present: list[str]):
    """After a turn, with Passive art on: the picture the turn calls for, in the background, within the cap."""
    database = state.database
    if getattr(state, 'passive_made', 0) >= PASSIVE_CAP:
        return
    with database.connect() as connection:
        on = one(connection, 'SELECT passive_art FROM workspace_settings WHERE id=1')['passive_art']
        if not on or not image_backends.ordered(connection, enabled_only=True):
            return
        met = {row['key'] for row in many(connection, 'SELECT key FROM story_people')}
        found = wanted(connection, database, [key for key in present if key in met])
    if found is None:
        return
    state.passive_made = getattr(state, 'passive_made', 0) + 1
    asked = request(database, *found)
    if (running := start(state, asked['id'])) is not None:
        await running
