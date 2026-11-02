"""Story mode: free-form roleplay with a narrator around the cities (docs/story.md).

The story has its own scene (`story_scene`: the city and place the user is at) and its own history
(`story_messages`).

The app decides the scene from the city data and the townsfolk rules: the place, the local time and
weather, and who is there at that hour. The narrator model only voices it. Moving somewhere else is the
user's choice in the place picker, not the model's.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone, tzinfo

from dungeon import (
    appearance,
    authors_note,
    beats,
    bonds,
    chapters,
    combat,
    delving,
    director,
    factions,
    feelings,
    finds,
    growth,
    happenings,
    hexes,
    icons,
    in_character,
    injuries,
    institutions,
    inventory,
    jobs,
    judge,
    labour,
    leaving,
    library,
    lies,
    lore,
    pace,
    party,
    passages,
    plotting,
    politics,
    prompt_library,
    quests,
    receipt,
    record,
    referee,
    remembering,
    rest,
    safety,
    story_clock,
    story_people,
    stress,
    sworn,
    table,
    tiers,
    timeline,
    tone,
    townmap,
    travel,
    turn,
)
from dungeon.authors_note import NOTE_CLOSE
from dungeon.clock import zone
from dungeon.database import decode, encode, identifier, many, one, optional, settings
from dungeon.errors import DomainError, require
from dungeon.life import ages
from dungeon.narration import prompt as narration_prompt
from dungeon.narration import prose
from dungeon.providers.chat import INCOMPLETE
from dungeon.providers.scheduling import CONVERSATION
from dungeon.rules import brp, fate, ironsworn, marvel, narrative, srd52
from dungeon.rules import passages as rule_passages
from dungeon.sheet import compel_line, spell_actions, unprepared
from dungeon.sheet import native as native_sheet
from dungeon.sheet import ruleset as ruleset_of
from dungeon.sheet import stats as sheet_stats
from dungeon.text_models import config_for, default_name, key_for, reply_config
from dungeon.world import catalog, changes, custom, decades, generators, inside, life_details, townsfolk

JOB = 'story'
log = logging.getLogger(__name__)
DEFAULT_CITY = 'kingswood'
HISTORY_LIMIT = 200
CHARS_PER_TOKEN = 4
# The kinds a story starts at when nothing else is chosen: somewhere people sit and talk.
OPENING_KINDS = ('cafe', 'tavern', 'bar', 'restaurant', 'market', 'park')

# An OOC line is a question for the game master. Companion's note had the model answer as the AI, and it then
# announced itself unasked; here it answers as the table's game master, from what the game holds.
OUT_OF_CHARACTER = (
    "The player's latest message is out of character (it starts with OOC: or is in double parentheses): a question "
    'for the game master, not part of the story. Answer it plainly and briefly, out of the story, from what the game '
    'holds here (the scene, the record, the quests, the map) and nothing invented; say so when the game does not '
    "know. Keep hidden truth hidden. Only if they ask what you are, say you are an AI model ({model}) running the "
    'game. The story resumes with their next message.')


def map_text(connection, view: dict) -> str:
    """The travel map as the character knows it, for an OOC answer about where they can go."""
    known = travel.view(connection, view['city']['id'], view['place']['id'])
    if not known:
        return ''
    names = {place['id']: place['name'] for place in known['places']}
    here = next((place['name'] for place in known['places'] if place['here']), view['city']['name'])
    roads = [f"{names[road['from']]} to {names[road['to']]}: {road['hours']} hours by {road['terrain']}, "
             f"{road['danger']} danger" for road in known['roads']]
    # A town on the map is a city of its own (Kingswood), with its places; a place on the Road is only itself.
    town = view['city']['id'] in names
    places = ', '.join(place['name'] for place in view['data']['places']) if town else ''
    return (f"\n\n## The map as the character knows it\nHere: {here}."
            + (f" Places in {view['city']['name']}, reached by going there: {places}." if places else '')
            + "\nKnown roads:\n" + '\n'.join(f'- {road}' for road in roads))


def intensity(connection, data: dict) -> dict:
    """How far the story goes on the page, per category, with veils and the voice (dungeon/tone.py)."""
    return tone.of(connection, data)


def no_model() -> DomainError:
    return DomainError('Add a text model in Settings > Models to tell the story.', 409, 'no_connection')


# The scene ----------------------------------------------------------------------------------------

def city_data(connection, city_id: str) -> dict:
    """The city as the story has it, in this world's town."""
    return city_for(connection, city_id, town_seed(connection))


def town_seed(connection) -> str:
    """The seed of this world's town (dungeon/worlds.py build): '' in the first world, so each world has its own people."""
    row = optional(connection, 'SELECT town_seed FROM persona WHERE id=1')
    return row['town_seed'] or '' if row else ''


def city_for(connection, city_id: str, town: str) -> dict:
    """The city with the town `town` seeds (`data['town']`, dungeon/world/townsfolk.py): another town makes another
    person of the same key. `you` is the townsperson the user became there, who is no longer one of its people."""
    data = changes.resolve(city_id, custom.all_cities(connection))
    if data is None:
        raise DomainError(f'No world data for city {city_id!r}.', 404, 'unknown_city')
    data = data | {'kin': [], 'town': town, 'you': you(connection, town), 'kept': ()} | hamlets(connection, data)
    # The buildings looked at on the town map (dungeon/townmap.py) are places of the town too.
    return data | townmap.lot_places(connection, data)


def hamlets(connection, data: dict) -> dict:
    """The hamlets the character has found out in the wild, as places of the Road city the wild is on
    (dungeon/hexes.py hamlets): each one the wild place's setting, under its own name, with its own people."""
    found = []
    for travel_map in travel.maps():
        wild = travel_map.get('wild')
        if wild and wild['city'] == data['id'] and (template := catalog.find(data, wild['place'])):
            found += [template | hamlet for hamlet in hexes.hamlets(connection, travel_map)]
    return {'places': [*data['places'], *found]} if found else {}


def you(connection, town: str) -> str:
    """The townsperson the user became in this world (dungeon/worlds.py, Become a townsperson), when this town is
    theirs."""
    row = optional(connection, 'SELECT townsfolk_key, town_seed FROM persona WHERE id=1')
    return row['townsfolk_key'] if row and row['townsfolk_key'] and row['town_seed'] == town else ''


def opening_place(data: dict) -> dict:
    for kind in OPENING_KINDS:
        if found := catalog.places(data, kind=kind):
            return found[0]
    return data['places'][0]


def scene_row(connection) -> dict:
    """Where the story is; a new story starts in Kingswood, the slice town, at its tavern or another opening place. A place or city that
    has since gone falls back the same way."""
    row = optional(connection, 'SELECT city_id, place_id FROM story_scene WHERE id=1')
    known = row and changes.resolve(row['city_id'], custom.all_cities(connection))
    data = city_data(connection, row['city_id'] if known else DEFAULT_CITY)
    if known and catalog.find(data, row['place_id']) in data['places']:
        return {'city_id': row['city_id'], 'place_id': row['place_id']}
    return {'city_id': data['id'], 'place_id': opening_place(data)['id']}


def city_zone(data: dict) -> tzinfo:
    """The city's clock. A fantasy world keeps no daylight saving, so its clock never runs back an hour (playtest
    m6b): its zone's standard offset all year. A city may also say `"dst": false`."""
    found = zone(data['timezone'])
    if data.get('era') != 'fantasy' and data.get('dst', True):
        return found
    probe = datetime(2001, 1, 15, tzinfo=found)
    return timezone(probe.utcoffset() - (probe.dst() or timedelta(0)))


def local_moment(data: dict, now: datetime) -> datetime:
    return now.astimezone(city_zone(data)).replace(tzinfo=None)


def present(connection, data: dict, place_id: str, moment: datetime) -> list[dict]:
    """Who the townsfolk rules put at the place now: the people seeded there and residents whose rules bring them."""
    day = moment.date()
    seeded = [] if place_id.startswith('~') else townsfolk.at_place(data, place_id, day)
    # The dead, taken, missing and conscripted are not about (dungeon/beats.py); the party is with the character
    # (dungeon/party.py), not where their own rules would put them.
    people, seen = [], beats.gone(connection) | party.keys(connection)
    for sheet in [*seeded, *townsfolk.reaching(data, place_id, day)]:
        if sheet['key'] in seen:
            continue
        seen.add(sheet['key'])
        found = townsfolk.whereabouts(sheet, data, moment)
        if found['place'] and found['place']['id'] == place_id:
            # How old they are now (dungeon/life/ages.py).
            people.append({'sheet': {**sheet, 'age': ages.town_age(connection, sheet, day)}, **found})
    place = catalog.find(data, place_id)
    return people + party.present(connection, townsfolk.view(place) if place else {'id': place_id})


def who(sheet: dict, place: dict, data: dict, doing: str = '') -> str:
    """'the barista there', 'a regular at Daily Grind', 'a local from Canton waiting for the bus'."""
    if doing == party.DOING:
        return f"travelling with the player's character ({sheet.get('occupation') or sheet['role']})"
    if sheet['kind'] == 'resident':
        local = f"a local from {townsfolk.neighborhood_name(data, sheet['home'])}"
        return f'{local} {doing}' if doing.startswith('waiting for') else local
    if sheet['place']['id'] == place.get('id'):
        return "a regular there" if not sheet['staff'] else f"the {sheet['role']} there"
    return f"a regular at {sheet['place']['name']}" if not sheet['staff'] else \
        f"the {sheet['role']} from {sheet['place']['name']}"


def weather_text(conditions: dict) -> str:
    text = f"High {conditions['high_f']}°F, low {conditions['low_f']}°F, "
    text += 'with rain.' if conditions['rain'] else 'dry.'
    # The month's note can describe sunshine, so it is left out on a rainy day.
    return text if conditions['rain'] else f"{text} {conditions['note']}"


def scene(connection, now: datetime) -> dict:
    row = scene_row(connection)
    data = city_data(connection, row['city_id'])
    place = catalog.find(data, row['place_id'])
    moment = local_moment(data, now)
    weather = generators.conditions(data, moment.date())
    hood = townsfolk.neighborhood_name(data, place['neighborhood'])
    return {'city': {'id': data['id'], 'name': data['name'], 'era': data.get('era', 'modern')},
            'place': {'id': place['id'], 'name': place['name'], 'kind': place['kind'], 'summary': place.get('summary', ''),
                      'neighborhood': hood, 'spots': inside.names(inside.for_place(place, data.get('era')))},
            'local_time': moment.isoformat(timespec='minutes'), 'weather': weather_text(weather) if weather else '',
            'people': present(connection, data, place['id'], moment), 'data': data, 'now': now,
            'street': townmap.street(connection, data, place['id']),
            'known': story_people.known(connection), 'dead': record.dead(connection)}


def initiative(sheet: dict, data: dict, moment: datetime | None) -> str:
    """A named person's own business: who they are and what they are after, for them to act on unprompted."""
    if not sheet.get('notable'):
        return ''
    wants = sheet.get('wants') or (townsfolk.story(sheet, data, moment.date())['goal']['text'] if moment else '')
    return (f" {sheet['about']}" + (f' Right now they are after this: {wants}.' if wants else '') +
            ' They pursue their own ends in the scene without waiting to be asked.')


def person_line(person: dict, place: dict, data: dict, known: dict | None = None,
                moment: datetime | None = None) -> str:
    sheet = person['sheet']
    seen = who(sheet, place, data, person['doing'])
    pronouns = f", {sheet['pronouns']}" if sheet.get('pronouns') else ''
    job = sheet.get('occupation') or sheet['role']
    # "working as the owner" already says the job: no "working as the owner, owner."
    job = '' if f' {job}' in f" {person['doing']}" else f', {job}'
    # Their kind when they aren't human ("Half-elf"), so the narrator never writes an elf as a man.
    folk = townsfolk.folk_label(data, sheet)
    folk = f', {folk}' if folk else ''
    return (f"- {seen[0].upper()}{seen[1:]}: {sheet['full']}{pronouns}, {sheet['age']}{folk}, {person['doing']}{job}. "
            f"{townsfolk.first_impression(sheet).capitalize()}; "
            f"{sheet['quirk']}.{life_text(data, sheet)}{initiative(sheet, data, moment)} Mood: {person['mood']}."
            f"{story_people.remembered(known, moment.date().isoformat() if moment else None)}"
            f"{person.get('note', '')}")


def life_text(data: dict, sheet: dict) -> str:
    """Where they come from, a taste and a story they might tell, for the model to use or leave."""
    found = life_details.for_sheet(data, sheet)
    if not found:
        return ''
    story = f" Might tell the story of the time they {found['stories'][0]}." if found['stories'] else ''
    return f" {found['origin'][:1].upper()}{found['origin'][1:]}; {found['likes'][0]}.{story}"


# Places that hold their own crowd: empty of townsfolk, they are empty, and the narrator fills them with nobody.
ROOMS = {'bar', 'cafe', 'inn', 'nightlife', 'restaurant', 'tavern', 'venue'}
EMPTY_ROOM = ('- Nobody is here now: the room is empty, or near enough. No patrons, no drinkers, no crowd to talk to; '
              'invent none.')


def scene_text(view: dict) -> str:
    data, place = view['data'], view['place']
    moment = datetime.fromisoformat(view['local_time'])
    when = f"{moment:%A} {moment.day} {moment:%B}" + (f", {moment.year}" if data.get('era', 'modern') == 'modern' else '')
    lines = [f"Place: {place['name']}, a {place['kind']} in {place['neighborhood']}, {data['name']}. {place['summary']}",
             f"City: {data['summary']}" + ('' if townsfolk.modern(data) else f" The era is {data['era']}."),
             f"Local time: {when}, {moment.strftime('%H:%M')} ({townsfolk.part_of_day(moment.hour * 60 + moment.minute)})."]
    if place.get('spots'):
        lines.append(f"Spots here, for detail only (nobody moves between them): {', '.join(place['spots'])}.")
    if street := townmap.street_text(view.get('street', [])):
        lines.append(street)
    if view['weather']:
        lines.append(f"Weather: {view['weather']}")
    lines.append('Who is here (their names are for you; the user knows only the names of people they have met):')
    lines += [person_line(person, {'id': place['id']}, data, view['known'].get(person['sheet']['key']), moment)
              for person in view['people']] or \
        [EMPTY_ROOM if place['kind'] in ROOMS else '- Nobody the story knows; only passers-by.']
    lines += away_lines(view)
    return '## Scene\n' + '\n'.join(lines)


def away_lines(view: dict) -> list[str]:
    """The notables who run this place but are not here now, so the narrator invents no one else in their post."""
    here = {person['sheet'].get('full') for person in view['people']}
    return [f"- Not here now: {notable['name']} ({notable.get('pronouns', 'they/them')}), the {notable['role']} "
            f"here. Whoever minds the place stands in; {notable['name']} is still the {notable['role']}, so invent "
            "no other."
            for notable in view['data'].get('notables', [])
            if notable.get('place') == view['place']['id'] and notable.get('staff') and notable['name'] not in here
            and notable['name'].lower() not in view.get('dead', set())]


def scene_view(view: dict) -> dict:
    """The scene for the screen: what the user can see, never the names of people they have not met."""
    data = view['data']
    return {key: view[key] for key in ('city', 'place', 'local_time', 'weather')} | {
        'places': [{'id': item['id'], 'name': item['name'], 'kind': item['kind'],
                    'neighborhood': townsfolk.neighborhood_name(data, item['neighborhood'])} for item in data['places']],
        'around': [seen(person, view) for person in view['people']],
        # The same people with the key a picture is asked by (dungeon/art.py); a key names no one.
        'present': [{'key': person['sheet']['key'], 'label': seen(person, view)} for person in view['people']]}


def seen(person: dict, view: dict) -> str:
    """'the barista', or 'Dana, the barista' once the user has met her."""
    sheet = person['sheet']
    said = who(sheet, {'id': view['place']['id']}, view['data'], person['doing']).removesuffix(' there')
    return f"{sheet['name']}, {said}" if sheet['key'] in view['known'] else said


# The player's character ---------------------------------------------------------------------------

STRONG, WEAK = 14, 7


def persona_text(connection) -> tuple[str, str | None]:
    """Who the player is, for the narrator: what they wrote about themselves and, in words, what their stats make
    them good and bad at. Never the numbers. ('', None) when they have not said who they are."""
    row = optional(connection, 'SELECT name, gender, age, about FROM persona WHERE id=1')
    if not row or not row['name']:
        return '', None
    details = ', '.join(str(item) for item in (row['gender'], row['age']) if item)
    lines = [f"{row['name']}" + (f' ({details})' if details else '') + '.']
    if row['about']:
        lines.append(row['about'].strip())
    played = ruleset_of(connection)
    native = native_sheet(connection) if played != marvel.ID else None
    if native:
        lines.append(srd52.described(native) if played == srd52.ID else brp.described(native) if played == brp.ID
                     else narrative.described(native) if played == narrative.ID else fate.described(native)
                     if played == fate.ID else ironsworn.described(native))
    stats = {} if native else sheet_stats(connection)
    if strong := [marvel.MEANINGS[stat] for stat, value in stats.items() if value >= STRONG]:
        lines.append(f"Good at: {'; '.join(strong)}.")
    if weak := [marvel.MEANINGS[stat] for stat, value in stats.items() if value <= WEAK]:
        lines.append(f"Poor at: {'; '.join(weak)}.")
    lines.append('Write their actions and words in their own voice, from what is here; invent nothing about their '
                 'past.')
    return '\n'.join(line for line in lines if line), row['name']


# Gear and the shop --------------------------------------------------------------------------------

def shop_view(connection, view: dict) -> dict | None:
    """The shop where the story is, if it is one: open while one of its staff is at work."""
    shop = inventory.shop_at(view['city']['id'], view['place']['id'])
    if shop is None:
        return None
    staff = [person['sheet'] for person in view['people'] if person['sheet'].get('staff') and not person.get('party')
             and person['sheet']['place']['id'] == view['place']['id']]
    keeper = f"the {staff[0].get('occupation') or staff[0]['role']}" if staff else ''
    found = inventory.window(connection, view['city']['id'], shop, bool(staff), keeper, story_day(view))
    for row in found['stock']:
        row['icon'] = icons.icon(view['city']['id'], row['item_id'], row['category'])
    return found | {'keeper_key': staff[0]['key'] if staff else ''}


def story_day(view: dict) -> str:
    return view['local_time'][:10]


def gear(database) -> dict:
    """The character's purse and pack, and the shop window where the story is."""
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        city = view['city']['id']
        rows = inventory.carried(connection, city)
        return {'coins': inventory.purse(connection), 'currency': view['data']['currency'],
                'slots': {'used': inventory.used(rows), 'max': None if inventory.capacity(connection) ==
                          inventory.UNLIMITED else inventory.capacity(connection)},
                'looks': appearance.summary(connection, city, view['data'].get('appearance', 'full')),
                'items': [{key: row[key] for key in ('id', 'item_id', 'name', 'category', 'qty', 'slots')} |
                          {'stolen': bool(row['stolen']), 'condition': row['condition'],
                           'icon': icons.icon(row['city_id'], row['item_id'], row['category'])}
                          for row in rows],
                'shop': shop_view(connection, view)}


def trade(database, kind: str, key: str, qty: int) -> dict:
    """Buy an item from the shop here, or sell it one of the character's; the story gets a line about it."""
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        city = view['city']['id']
        shop = inventory.shop_at(city, view['place']['id'])
        require(shop is not None, 'There is no shop here.', 404)
        require(shop_view(connection, view)['open'], 'The shop is closed; nobody is behind the counter.', 409)
        done = (inventory.buy(connection, city, shop, key, qty, database.now(), story_day(view)) if kind == 'buy'
                else inventory.sell(connection, city, shop, key, qty, database.now(), story_day(view)))
        what = done['name'] if done['qty'] == 1 else f"{done['qty']} × {done['name']}"
        verb = 'buy' if kind == 'buy' else 'sell'
        price = inventory.money_text(done['amount'], view['data']['currency'])
        mended = f" The smith mends {'; '.join(done['mended'])}." if done.get('mended') else ''
        add(connection, database.now(), 'scene', f"You {verb} {what} for {price}" + ('' if price.endswith('.') else '.')
            + mended, scene_row(connection))
    return gear(database)


# History ------------------------------------------------------------------------------------------

def next_seq(connection) -> int:
    return one(connection, 'SELECT COALESCE(MAX(seq), 0) + 1 AS seq FROM story_messages')['seq']


def add(connection, now: str, role: str, text: str, where: dict, **extra) -> dict:
    message_id = identifier()
    connection.execute(
        'INSERT INTO story_messages (id, seq, role, text, client_id, reply_to, status, error, city_id, place_id, '
        'created_at, branch_id, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (message_id, next_seq(connection), role, text, extra.get('client_id'), extra.get('reply_to'),
         extra.get('status', 'complete'), extra.get('error'), where['city_id'], where['place_id'], now,
         timeline.active(connection), encode(extra.get('flags', []))))
    return one(connection, 'SELECT * FROM story_messages WHERE id=?', (message_id,))


def messages(connection, limit: int = HISTORY_LIMIT) -> list[dict]:
    where, values = timeline.visible(connection)
    rows = many(connection, 'SELECT id, seq, role, text, reply_to, status, error, city_id, place_id, created_at, '
                f'flags, previous FROM story_messages WHERE {where} ORDER BY seq DESC LIMIT ?', (*values, limit))
    # The app's crisis note under a user's line that sounds like self-harm (dungeon/safety.py), and a narration's
    # flagged passages, and whether it can switch back to its wording before a rewrite (dungeon/passages.py).
    return [{**row, 'crisis_help': row['role'] == 'user' and safety.crisis(row['text']),
             'flags': passages.shown(decode(row['flags'])), 'previous': row['previous'] is not None}
            for row in reversed(rows)]


def narration_format(connection) -> narration_prompt.Format:
    """The player's narration format, kept at the Table (dungeon/table.py): point of view, tense and length."""
    rules = table.rules(connection)
    return narration_prompt.Format(pov=rules['pov'], tense=rules['tense'], length=rules['length'])


def dice_shown(connection) -> bool:
    """Roll visibility (Story > Tone and rules > Dice and hidden values): hidden unless the player shows them."""
    # Narrative Only shows no roll card at all; the GM view still shows its verdicts.
    return table.rule(connection, 'show_odds') and (ruleset_of(connection) != narrative.ID
                                                    or table.rule(connection, 'gm_view'))


def with_rolls(connection, rows: list[dict]) -> list[dict]:
    """The rolls under each of the player's lines, and how long its turn took (dungeon/pace.py), only while the dice
    are shown; hidden dice never leave the app."""
    if not dice_shown(connection):
        return rows
    return [{**row, 'rolls': [turn.shown(roll) for roll in turn.saved(connection, row['id'])],
             'pace': decode(pace.saved(connection, row['id']) or 'null')}
            if row['role'] == 'user' else row for row in rows]


def with_receipts(connection, rows: list[dict], currency: dict) -> list[dict]:
    """What each recent turn changed, under the player's line (dungeon/receipt.py)."""
    found = receipt.receipts(connection, rows, currency)
    return [{**row, 'receipt': found[row['id']]} if found.get(row['id']) else row for row in rows]


def story(database) -> dict:
    with database.connect() as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        rows = messages(connection)
        rows = happenings.with_cards(connection, rows, set(intensity(connection, view['data'])['veils']))
        return {'scene': scene_view(view), 'messages': with_receipts(connection, with_rolls(connection, rows),
                                                                     view['data']['currency']),
                'people': people(connection, view), 'ready': config_for(connection, JOB) is not None,
                'dice_shown': dice_shown(connection), 'bands': turn.bands(ruleset_of(connection)) if dice_shown(connection) else None,
                'branches': timeline.branches(connection),
                'campaign': chapters.view(connection),
                'fight': combat.view(connection, dice_shown(connection)) | {
                    'injuries': injuries.view(connection, view['now']),
                    'stress': stress.view(connection, dice_shown(connection))},
                'injury_persistence': injuries.persistence(connection),
                'table': table.rules(connection),
                'intensity': intensity(connection, view['data']),
                'map': travel.view(connection, view['city']['id'], view['place']['id']),
                'interior': delving.view(connection),
                'factions': powers(connection, view), 'tier': standing(connection, view),
                # Whether Talk of the town has anything to show here (dungeon/politics.py).
                'politics': politics.on(connection, view['data'], view['place']['id'])}


def standing(connection, view: dict) -> dict | None:
    """The character's tier and its track (dungeon/tiers.py), for the screen."""
    world = tiers.world_of(view['city']['id'])
    return tiers.view(connection, world, dice_shown(connection)) if world else None


def powers(connection, view: dict) -> list[dict]:
    """The factions the character knows of (dungeon/factions.py), for the screen."""
    found = happenings.where(view['city']['id'], view['place']['id'])
    if found is None:
        return []
    visited = {row['node_id'] for row in many(connection, 'SELECT node_id FROM story_map WHERE visited=1')}
    return [faction | {'emblem': icons.emblem(found['world'], faction['id'])}
            for faction in factions.view(connection, found['world'], visited | {found['node']}, dice_shown(connection))]


def ending(connection) -> str:
    """How the branch being left ended, when the character died or was lost there (dungeon/chapters.py tree)."""
    return 'death' if combat.condition(connection)['dead'] else 'lost' if growth.lost(connection) else ''


def back(database, message_id: str) -> dict:
    """Go back to before one of the player's lines; the line comes back as a draft to send again, with new dice."""
    with database.connect(write=True) as connection:
        chapters.no_going_back(connection)
        line = timeline.back(connection, message_id, database.now(), ending(connection))
    return story(database) | {'draft': line['text']}


def switch_branch(database, branch_id: str) -> dict:
    with database.connect(write=True) as connection:
        if branch_id != timeline.active(connection):
            chapters.no_going_back(connection)
        timeline.switch(connection, branch_id, database.now(), ending(connection))
    return story(database)


def chapter_back(database, chapter_id: str) -> dict:
    """Play on from the start of a chapter in the tree: in its branch, back to before its first line."""
    with database.connect(write=True) as connection:
        chapters.no_going_back(connection)
        row = optional(connection, 'SELECT branch_id, seq FROM story_chapters WHERE id=?', (chapter_id,))
        require(row is not None, 'That chapter is not in this story.', 404)
        if row['branch_id'] != timeline.active(connection):
            timeline.switch(connection, row['branch_id'], database.now(), ending(connection))
        line = optional(connection, "SELECT id FROM story_messages WHERE branch_id=? AND seq=? AND role='user'",
                        (row['branch_id'], row['seq']))
        require(line is not None, 'That chapter has no line to go back to.', 409)
    return back(database, line['id'])


def bookmark_go(database, bookmark_id: str) -> dict:
    """Play on in the branch a bookmark's line was told in; the screen then shows the line."""
    with database.connect() as connection:
        marked = chapters.marked_branch(connection, bookmark_id)
        where, values = timeline.visible(connection)
        here = optional(connection, f'SELECT 1 FROM story_messages WHERE id=? AND {where}',
                        (marked['message_id'], *values))
    result = story(database) if here else switch_branch(database, marked['branch_id'])
    return result | {'message_id': marked['message_id']}


def people(connection, view: dict) -> list[dict]:
    """Everyone the user has met in the story, most recent first, with where their rules put them now; with the
    dice shown, how they feel about the character too."""
    result, cities, shown, with_them = [], {}, dice_shown(connection), party.keys(connection)
    for row in view['known'].values():
        if row['city_id'] not in cities:
            try:
                cities[row['city_id']] = city_data(connection, row['city_id'])
            except DomainError:
                cities[row['city_id']] = None
        data = cities[row['city_id']]
        sheet = townsfolk.find(data, row['key']) if data else None
        if sheet is None:
            continue  # Their city is gone, or its townsfolk were seeded anew.
        now = {'doing': 'travelling with you', 'place': None} if row['key'] in with_them else \
            townsfolk.whereabouts(sheet, data, local_moment(data, view['now']))
        result.append({'key': row['key'], 'name': row['name'], 'role': sheet.get('occupation') or sheet['role'],
                       'city': data['name'], 'meetings': row['meetings'], 'last_met_at': row['last_met_at'],
                       'notes': row['notes'], 'doing': now['doing'],
                       'feelings': feelings.shown(row) if shown else '', 'bond': row.get('bond'),
                       'party': row['key'] in with_them,
                       'place': now['place'] and {'id': now['place']['id'], 'name': now['place']['name'],
                                                  'city_id': data['id']}})
    return result


def find(database, key: str) -> dict:
    """Go to where someone the user has met is right now."""
    with database.connect() as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        person = next((item for item in people(connection, view) if item['key'] == key), None)
    require(person is not None, "You haven't met them in your story.", 404)
    place = person['place']
    require(place is not None and not place['id'].startswith('~'),
            f"{person['name'].split()[0]} isn't anywhere you can go right now ({person['doing']}).", 409)
    return move(database, place['city_id'], place['id'])


def move(database, city_id: str, place_id: str | None) -> dict:
    """Go somewhere else: another place in this city, or another city (its opening place unless one is named)."""
    with database.connect(write=True) as connection:
        data = city_data(connection, city_id)
        place = catalog.find(data, place_id) if place_id else opening_place(data)
        require(place is not None and place in data['places'], 'No such place in this city.', 404)
        if combat.fight(connection) is not None and leaving.free_from_fights(connection):
            # The Table lets the character walk out of a fight (dungeon/leaving.py).
            combat.walk_away(connection, database.now())
        require(combat.fight(connection) is None, "You're in a fight. Get away first.", 409)
        held = combat.captors(connection)
        require(not held, f"You're held prisoner by {held}. Get free first.", 409)
        view = scene(connection, story_clock.now(connection, database.clock))
        stopping = leaving.blocking(connection, view)
        require(stopping is None, f"{stopping and stopping['name'].split()[0]} won't let you just walk away. Say how you "
                'leave in the story.', 409)
        moving_from = scene_row(connection)['city_id']
        if scene_row(connection) != {'city_id': data['id'], 'place_id': place['id']}:
            place_scene(connection, data['id'], place['id'], database.now())
            # The next line opens a chapter in the new place (dungeon/chapters.py).
            chapters.mark(connection, 'place')
            pass_time(database, connection, story_clock.ACROSS_TOWN_MINUTES if moving_from == data['id'] else
                      story_clock.ANOTHER_CITY_MINUTES)
            arrive(connection, database.now())
    return story(database)


# A line that goes somewhere by name: the words after "go to", "head over to" and the like.
GOING = re.compile(r'\b(?:go|goes|going|head|heads|heading|walk|walks|walking|make (?:my|our) way|wander|wanders|'
                   r'stroll|strolls|hurry|hurries|return|returns|cross|crosses)\b(?:\s+(?:back|over|down|up|across|'
                   r'out|on|off|straight))*\s+(?:to|towards?|into|in at|onto|through)\s+(?P<where>[^.!?;,]+)', re.I)
# A stretch spent somewhere by name: "I spend the day at the Crossroads market", "pass the afternoon on the green".
SPENDING = re.compile(r'\b(?:spend|spends|spending|pass|passes|passing|while away)\s+(?:the|all|a|an|some|my)?\s*'
                      r'(?:whole\s+)?(?:day|morning|afternoon|evening|hours?|time|while)\s+(?:\w+\s+){0,3}?'
                      r'(?:at|on|in|around|by|down at|out at|over at)\s+(?P<where>[^.!?;,]+)', re.I)
# Where a rest is taken: "I sleep at the bunkhouses".
SLEEPING_AT = re.compile(r'\b(?:at|in)\s+(?P<where>[^.!?;,]+)', re.I)
PLACE_FILLER = {'the', 'of', 'a', 'an', 's', 'old', 'and'}


def place_words(text: str) -> set[str]:
    return set(re.findall(r'[a-z]+', text.lower())) - PLACE_FILLER


def walked_to(connection, text: str, clock=None) -> dict | None:
    """A place in this town the player's line goes to by name or kind ("I go to the shrine", "I sleep at the
    bunkhouses"), or the room of their next class ("I head to my first class"), with its city id; none when the
    words fit no place, or two equally, or there is a fight on."""
    if combat.fight(connection) is not None or combat.captors(connection):
        return None
    row = scene_row(connection)
    data = city_data(connection, row['city_id'])
    spans = [found.group('where') for found in (*GOING.finditer(text), *SPENDING.finditer(text))]
    if rest.resting(text):
        spans += [found.group('where') for found in SLEEPING_AT.finditer(text)]
    for where in spans:
        # Only the place itself: "the shrine", not "the shrine and ask Mother Rook".
        where = re.split(r'\b(?:and|then|to|so|where|while|with|for|until|because|onto|into|through)\b', where,
                         maxsplit=1)[0]
        words = place_words(where)
        # A place's words: its name, its kind and its id ("the-gate-arch" is "the east gate" to the player too).
        # Out in the wild and the hamlets found there are reached by travel (dungeon/travel.py), not across town.
        scored = [(len(words & (place_words(place['name']) | place_words(place['id']) | {place['kind']})), place)
                  for place in data['places'] if not {'wild', 'hamlet'} & set(place.get('tags', ()))]
        best = max((hits for hits, _ in scored), default=0)
        top = [place for hits, place in scored if hits == best]
        if best and len(top) == 1:
            return None if top[0]['id'] == row['place_id'] else top[0] | {'city_id': data['id']}
    if spans and clock is not None and (room := institutions.class_place(
            connection, data['id'], ' '.join(spans), story_clock.now(connection, clock))):
        found = catalog.find(data, room)
        return None if room == row['place_id'] or found is None else found | {'city_id': data['id']}
    return None


def place_scene(connection, city_id: str, place_id: str, now: str):
    connection.execute('INSERT INTO story_scene (id, city_id, place_id, updated_at) VALUES (1, ?, ?, ?) ON CONFLICT(id) '
                       'DO UPDATE SET city_id=excluded.city_id, place_id=excluded.place_id, '
                       'updated_at=excluded.updated_at', (city_id, place_id, now))
    # The street outside is seen on arrival (dungeon/townmap.py).
    townmap.pass_by(connection, city_data(connection, city_id), place_id)
    if story_clock.running(connection):
        # A town reached mid-campaign begins its own quests (dungeon/quests.py reach).
        quests.reach(connection, city_id, story_clock.now(connection, None))


def pass_time(database, connection, minutes: int):
    """The story clock moves on: any deadline it passes lands (dungeon/quests.py), and the factions' clocks run
    (dungeon/factions.py)."""
    before = story_clock.now(connection, database.clock)
    story_clock.advance(connection, minutes)
    after = story_clock.now(connection, database.clock)
    quests.check(connection, after, database.now())
    row = optional(connection, 'SELECT city_id, place_id FROM story_scene WHERE id=1')
    if row and (found := happenings.where(row['city_id'], row['place_id'])):
        factions.advance(connection, found['world'], before, after, database.now())
        # And the director's arcs, on their own clocks (dungeon/director.py).
        director.advance(connection, found['world'], before, after, database.now())
    if row:
        # Classes attended or missed, and the demands of the character's institutions (dungeon/institutions.py).
        institutions.advance(connection, before, after, row['city_id'], row['place_id'], database.now())


def arrive(connection, now: str) -> dict:
    """The line that opens a scene: "You arrive at …", where the scene is now."""
    row = scene_row(connection)
    data = city_data(connection, row['city_id'])
    place = catalog.find(data, row['place_id'])
    hood = townsfolk.neighborhood_name(data, place['neighborhood'])
    return add(connection, now, 'scene', f"You arrive at {place['name']}, {hood}, {data['name']}.", row)


def clear(database) -> dict:
    """A new story: the history, the people met and the record go, the scene stays where it is."""
    with database.connect(write=True) as connection:
        connection.execute('DELETE FROM story_messages')
        connection.execute('DELETE FROM story_people')
        for name in ('record_entries', 'record_corrections', 'story_summary', 'story_clock', 'story_quests',
                      'story_inventory', 'story_purse', 'story_stock', 'story_shops', 'story_markets', 'story_services', 'story_appearance', 'story_appearance_turns', 'story_trades', 'story_wounds', 'story_fight',
                      'story_haggles', 'story_counter', 'story_turn_steps', 'story_finds', 'story_looks',
                      'story_rounds', 'story_map', 'story_hexes', 'story_sites', 'story_lots', 'story_places', 'story_position', 'story_interior', 'story_interior_rooms', 'story_interior_ways', 'story_delves', 'story_journeys', 'story_rests', 'story_injuries', 'story_treatments', 'story_stress',
                      'story_cards', 'story_clocks', 'story_reputation', 'story_fates', 'story_bonds', 'story_party', 'story_real', 'story_beats', 'story_word',
                      'story_offpage', 'story_tier', 'story_marks', 'story_dark',
                      'story_director', 'story_arcs', 'story_threads', 'story_nemeses', 'story_seeds',
                      'story_arc_beats', 'story_sheet', 'story_enrollment', 'story_attendance', 'story_grades', 'story_art',
                      'lore_timers'):
            connection.execute(f'DELETE FROM {name}')
        politics.clear(connection)
        timeline.clear(connection)
        chapters.clear(connection)
    return story(database)


# The narrator -------------------------------------------------------------------------------------

def model_messages(rows: list[dict], budget_chars: int) -> list[dict]:
    """The story so far as chat turns, newest kept when it does not all fit. A move is a note on the user's side."""
    chat, used = [], 0
    for row in reversed(rows):
        if row['role'] == 'narrator' and row['status'] != 'complete':
            continue
        text = f"[{row['text']}]" if row['role'] == 'scene' else row['text']
        used += len(text)
        if used > budget_chars and chat:
            break
        role = 'assistant' if row['role'] == 'narrator' else 'user'
        if chat and chat[0]['role'] == role:
            chat[0] = {'role': role, 'content': text + '\n\n' + chat[0]['content']}
        else:
            chat.insert(0, {'role': role, 'content': text})
    return chat


def steered(chat: list[dict], steer: str) -> list[dict]:
    """The story's author's note (dungeon/authors_note.py) right before the user's latest words."""
    if not steer or not chat or chat[-1]['role'] != 'user':
        return chat
    return [*chat[:-1], {'role': 'user', 'content': f"{steer}\n{NOTE_CLOSE}\n{chat[-1]['content']}"}]


def prompt(connection, now: datetime, config: dict, latest: dict, outcomes: list[dict] | None = None,
           fought: list[str] | None = None, traded: list[str] | None = None,
           looked: list[str] | None = None, travelled: list[str] | None = None,
           rested: list[str] | None = None, tended: list[str] | None = None,
           carded: list[str] | None = None, meanwhile: list[str] | None = None,
           noted: list[str] | None = None, ruled: str = '') -> dict:
    view = scene(connection, now)
    craft = narration_prompt.craft_for(config.get('context_tokens'), prompt_library.text(connection, 'narrator-craft'))
    who_text, name = persona_text(connection)
    for extra in (combat.condition_text(connection), stress.prompt_text(connection), growth.prompt_text(connection),
                  injuries.prompt_text(connection, now),
                  inventory.prompt_text(connection, view['city']['id'], view['data']['currency'], story_day(view)),
                  appearance.prompt_text(connection, view['city']['id'], view['data'].get('appearance', 'full'))):
        if extra:
            who_text = f'{who_text}\n{extra}' if who_text else extra
    shop, level = shop_view(connection, view), intensity(connection, view['data'])
    found = happenings.where(view['city']['id'], view['place']['id'])
    after = record.summary(connection)['through_seq']
    rows = [row for row in messages(connection) if after < row['seq'] <= latest['seq']]
    # What the scene is about, for the facts recalled by relevance (dungeon/remembering.py).
    focus = ' '.join([latest['text'], view['place']['name'], *(person['sheet']['name'] for person in view['people']),
                      *(row['text'] for row in rows[-2:])])
    moment = datetime.fromisoformat(view['local_time'])
    place_text = place_prompt(connection, view, shop)

    window = remembering.room(connection, config)
    # What the town argues about and where the people here stand (dungeon/politics.py).
    politics_text = politics.prompt_text(connection, view)
    # Lorebook entries switched on: always-on ones, those named lately and those that fit the moment (dungeon/lore.py).
    # Timed entries count the story's lines on this branch (dungeon/lore.py "Timing").
    lore_text, lore_started = lore.chosen(connection, view['data'], view['place']['id'], local_moment(view['data'], now),
                                          [row['text'] for row in rows], name or '', line_number(connection, latest),
                                          timeline.active(connection))
    # Passages of the world's reference library that fit the last few messages (dungeon/library.py).
    shelf, passages_given = library.prompt_text(connection, [row['text'] for row in rows], latest['seq'])
    # The summary gives way first, then the record's facts, then the rule text (dungeon/rules/passages.py), so the
    # recent turns keep at least half the window.
    for summary_kept, facts, rules_kept in ((True, record.IN_PROMPT, True), (False, record.IN_PROMPT, True),
                                            (False, record.IN_PROMPT // 4, True), (False, record.IN_PROMPT // 4, False)):
        memory = '\n\n'.join(part for part in (summary_kept and record.summary_text(connection),
                                                 record.prompt_text(connection, focus, facts),
                                                 quests.prompt_text(connection, now),
                                                 institutions.prompt_text(connection, now), beats.prompt_text(connection),
                                                 found and factions.prompt_text(connection, found['world'],
                                                                                found['node']),
                                                 politics_text,
                                                 found and tiers.prompt_text(connection, found), lore_text,
                                                 shelf)
                             if part)
        system = narration_prompt.system(prompt_library.text(connection, 'story-narrator'), craft, scene=place_text,
                                         persona=who_text, persona_name=name, memory=memory, narration=narration_format(connection),
                                         intensity=tone.narration(level),
                                         outcomes=outcomes, rolls_shown=dice_shown(connection),
                                         rules=ruled if rules_kept else '')
        if len(system) <= (window - config['max_output_tokens']) * CHARS_PER_TOKEN // 2:
            break
    for extra in (travel.prompt_text(travelled or []), rest.prompt_text(rested or []),
                  injuries.treatment_text(tended or []), happenings.prompt_text(carded or []),
                  beats.cutaway_text(meanwhile or []), *(noted or []), combat.prompt_text(fought or [], connection),
                  counter_text(traded or []), finds.prompt_text(looked or [])):
        if extra:
            system += '\n\n' + extra
    if in_character.out_of_character(latest['text']):
        system += '\n\n' + OUT_OF_CHARACTER.format(model=default_name(config)) + map_text(connection, view)
    budget = (window - config['max_output_tokens']) * CHARS_PER_TOKEN - len(system)
    # Older messages are in the summary; the narrator reads the rest word for word.
    chat = model_messages(rows, max(budget, 2000))
    if not in_character.out_of_character(latest['text']):
        chat = steered(chat, authors_note.prompt_text(connection, 'story'))
    return {'system': system, 'messages': chat, 'people': view['people'], 'library': passages_given,
            'city_id': view['city']['id'], 'day': moment.date(), 'year': decades.year_of(view['data'], moment),
            'lore': lore_started, 'line': line_number(connection, latest)}


def place_prompt(connection, view: dict, shop: dict | None) -> str:
    """The scene, the shop here, the year in a modern world set in a past one (Havenbrooke's 2009: its things, slang,
    media, prices, and what isn't yet; dungeon/world/decades.py) and, out in the wild, the land around."""
    return '\n\n'.join(part for part in (
        scene_text(view), shop and inventory.shop_prompt(shop, view['data']['currency']),
        decades.prompt_text(view['data'], datetime.fromisoformat(view['local_time']), town_seed(connection)),
        travel.wild_text(connection, view['city']['id'], view['place']['id'])) if part)


def line_number(connection, latest: dict) -> int:
    """Which of the player's lines on this branch `latest` is, counting from 1."""
    where, values = timeline.visible(connection)
    return one(connection, f"SELECT COUNT(*) AS n FROM story_messages WHERE {where} AND role='user' AND seq<=?",
               (*values, latest['seq']))['n']


async def narrate(state, packet: dict, config: dict, active: bool, on_text=None) -> tuple[str, str | None]:
    """The narrator's reply as it is written; `on_text(piece)` gets each piece as it comes, for the stream."""
    guard, text, error = in_character.Guard(active), [], None
    async with state.scheduler.reserve(config, CONVERSATION):
        async for chunk in state.provider.stream(config, key_for(state.vault, config), packet['system'],
                                                        packet['messages']):
            piece = guard.feed(chunk.text)
            text.append(piece)
            if piece and on_text is not None:
                await on_text(piece)
            if chunk.finish_reason == 'content_filter':
                error = INCOMPLETE[chunk.finish_reason]
    text.append(tail := guard.flush())
    if tail and on_text is not None:
        await on_text(tail)
    return ''.join(text).strip(), error


async def complete(state, config: dict, system: str, messages: list[dict]) -> str:
    """One whole reply from the story's model, for the narration's rewrite pass."""
    async with state.scheduler.reserve(config, CONVERSATION):
        return ''.join([chunk.text async for chunk in state.provider.stream(
            config, key_for(state.vault, config), system, messages)])


def counter_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The shop's part of the turn (dungeon/inventory.py), decided once: a haggle settled by the player's Allure roll,
    then anything the line buys or sells, at today's price."""
    database = state.database
    with database.connect(write=True) as connection:
        if (kept := optional(connection, 'SELECT lines FROM story_counter WHERE message_id=?', (user['id'],))):
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        found = shop_view(connection, view)
        if not found:
            return []
        if not found['open']:
            lines = [] if not trading(user['text']) else [
                'The shop is shut: nobody is behind the counter, so nothing is bought, sold or haggled over.']
            connection.execute('INSERT INTO story_counter (message_id, lines) VALUES (?, ?)', (user['id'], encode(lines)))
            return lines
        city, shop, day = view['city']['id'], inventory.shop_at(view['city']['id'], view['place']['id']), story_day(view)
        lines = haggle_lines(connection, city, shop, day, rolls, found['keeper_key'], getattr(state, 'dice', None))
        stock_rows = inventory.window(connection, city, shop, True, '', day)['stock']
        lines += inventory.lift(connection, city, shop, user['text'], rolls, stock_rows)
        lines += inventory.buy_in_story(connection, city, shop, user['text'], stock_rows, day, database.now(),
                                        view['data']['currency'])
        lines += inventory.sell_in_story(connection, city, shop, user['text'], day, database.now(),
                                         view['data']['currency'])
        connection.execute('INSERT INTO story_counter (message_id, lines) VALUES (?, ?)', (user['id'], encode(lines)))
        return lines


def trading(text: str) -> bool:
    """Whether a line deals at the counter: buys, sells or haggles."""
    return any(pattern.search(text) for pattern in (inventory.BUY, inventory.SELL, inventory.HAGGLE))


def haggle_lines(connection, city: str, shop: dict, day: str, rolls: list[dict], keeper_key: str,
                 rng=None) -> list[str]:
    """A haggle settled by the character's Allure against the keeper's Resolve (dungeon/inventory.py opposed);
    under Narrative Only the judge's verdict stands alone."""
    roll = next((roll for roll in rolls if roll['stat'] == 'Allure' and inventory.HAGGLE.search(roll['action'])), None)
    if roll is None:
        return []
    if inventory.haggled_today(connection, city, shop, day):
        return ['The shopkeeper has already haggled with the character today and will not move on price again.']
    band, keeper = (roll['band'], None) if ruleset_of(connection) == narrative.ID else \
        inventory.opposed(shop, roll['band'], rng)
    percent = inventory.haggle(connection, city, shop, band, day)
    if band == 'success_cost' and keeper_key:
        feelings.change(connection, keeper_key, {'affection': -1}, 'Beat me down on price.')
    held = ['The keeper drives a hard bargain and holds firm: the haggle lands a step worse than it might have.'] \
        if keeper and band != roll['band'] else []
    return held + [f"The haggle settles today's prices: {inventory.haggle_text(percent) or 'no change'}."]


def scene_break(connection, user: dict, travelled: list[str], rested: list[str], fought: list[str]) -> str | None:
    """Why the line ends a chapter, if it does: a new place, time passing on the road or in rest, a fight over."""
    now = scene_row(connection)
    # A line that went somewhere opened its own chapter as it arrived (received).
    if (now['city_id'], now['place_id']) != (user['city_id'], user['place_id']) and not chapters.opens(connection, user):
        return 'place'
    if travelled or rested:
        return 'time'
    if fought and not combat.fight(connection):
        return 'fight'
    return None


def opening_turn(state, user: dict) -> list[str]:
    """A line that opens a new chapter begins with a short "previously" (dungeon/chapters.py)."""
    with state.database.connect() as connection:
        text = chapters.opening(connection, user)
    return [text] if text else []


def recall_turn(state, rolls: list[dict]) -> list[str]:
    """A faded detail the line tried to recall (dungeon/remembering.py), brought back to mind on a success."""
    with state.database.connect(write=True) as connection:
        lines = remembering.recalled(connection, rolls)
    return ['## What the character remembers\n' + '\n'.join(lines)] if lines else []


def look_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """What the line looks into and takes (dungeon/finds.py), decided once, before the narrator describes it."""
    database = state.database
    with database.connect(write=True) as connection:
        if (kept := optional(connection, 'SELECT lines FROM story_looks WHERE message_id=?', (user['id'],))):
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        city = view['city'] | {'currency': view['data']['currency']}
        lines = finds.look(connection, city, view['place'], user['text'], rolls, getattr(state, 'dice', None),
                           database.now())
        lines += finds.take(connection, city, view['place'], user['text'], database.now())
        connection.execute('INSERT INTO story_looks (message_id, lines) VALUES (?, ?)', (user['id'], encode(lines)))
        return lines


def in_scene(state, user: dict, rolls: list[dict], travelled: list[str], rested: list[str]) -> tuple[list[str], ...]:
    """The turn where the character is: a fight round, the counter, treatment, what is looked into, and what all of
    it (and the road and the rest) did to how the character looks."""
    with state.database.connect() as connection:
        hurt_before = combat.condition(connection)['level']
    fought = fight_round(state, user, rolls)
    traded = counter_turn(state, user, rolls)
    tended = treat_turn(state, user, rolls)
    looked = look_turn(state, user, rolls)
    with state.database.connect() as connection:
        wounded = combat.condition(connection)['level'] > hurt_before
    return fought, traded, tended, looked, appearance_turn(state, user, wounded, travelled, rested, fought, traded)


def appearance_turn(state, user: dict, wounded: bool, travelled: list[str], rested: list[str], fought: list[str],
                    traded: list[str]) -> list[str]:
    """What the turn did to how the character looks (dungeon/appearance.py), decided once, as a note for the narrator."""
    database = state.database
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        camp = rest.kept(connection, user['id'])
        clothing = [entry['name'] for entry in inventory.catalog(view['city']['id'])['items']
                    if entry['category'] == 'clothing']
        events = {'travelled': bool(travelled), 'camped': bool(rested and camp and camp.get('outside')),
                  'fought': bool(fought), 'wounded': wounded,
                  'bought_clothes': any(f'buys {name}' in line for line in traded for name in clothing)}
        lines = appearance.changed(connection, user['id'], user['text'], events, view['place']['name'],
                                   story_day(view), view['data'].get('appearance', 'full'))
    return [appearance.note_text(lines)] if lines else []


def travel_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The journey a line sets out on (dungeon/travel.py), walked once: the roads, the time, the food, where it ends."""
    database = state.database
    with database.connect(write=True) as connection:
        planned = travel.journey(connection, user['id'])
        if planned is None:
            return []
        if planned['lines'] is None:
            planned['lines'] = walk(database, connection, planned, rolls, user['id'])
            connection.execute('UPDATE story_journeys SET lines=? WHERE message_id=?',
                               (encode(planned['lines']), user['id']))
        return planned['lines']


def delve_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The line's move inside an interior (dungeon/delving.py), played once, and where the character is in it."""
    database = state.database
    with database.connect(write=True) as connection:
        lines, minutes = delving.walked(connection, user['id'], rolls, user['city_id'])
        if minutes:
            pass_time(database, connection, minutes)
        here = delving.here_text(connection)
        return lines + ([here] if here else [])


def rest_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The rest a line takes (dungeon/rest.py), slept once: the nights, what one turned up, the food, the mending."""
    database = state.database
    with database.connect(write=True) as connection:
        resting = rest.kept(connection, user['id'])
        if resting is None:
            return []
        if resting['lines'] is None:
            resting['lines'] = slept(database, connection, resting, rolls, user['id'], getattr(state, 'dice', None))
            connection.execute('UPDATE story_rests SET lines=? WHERE message_id=?',
                               (encode(resting['lines']), user['id']))
        return resting['lines']


def slept(database, connection, resting: dict, rolls: list[dict], message_id: str, rng=None) -> list[str]:
    if resting.get('fighting'):
        return ["The player's character cannot rest with a fight on their hands."]
    row = scene_row(connection)
    local = local_moment(city_data(connection, row['city_id']), story_clock.now(connection, database.clock))
    if resting.get('morning') and resting['nights'] == 1 and rest.awake(local):
        return ["It is morning already: the player's character is not tired enough to sleep, and no time passes."]
    nights, lost, cut_short, happened = rest.night(resting, rolls)
    if resting.get('outside') and not cut_short:
        drawn, _ = life_card(database, connection, 'rest', message_id)
        happened += drawn
        if combat.fight(connection) is not None:
            nights, lost, cut_short = 0, 0, True
            happened.append('The rest ends here, in the dark, with a fight on its hands.')
    hungry = 0
    if resting.get('outside') and nights > 1:
        _, hungry = travel.eat(connection, resting['food'], nights - 1)
    # A bed paid for here tonight (dungeon/inventory.py services): the narrator plays it, and a private room's quiet
    # eases one more point of stress. Before dawn, last evening's bed still counts.
    nights_of = [local.date()] + ([local.date() - timedelta(days=1)] if local.hour < rest.WAKE_HOUR else [])
    paid = next((found for day in nights_of
                 if (found := inventory.bed(connection, row['city_id'], row['place_id'], day.isoformat()))), None)
    pass_time(database, connection, rest.minutes(nights, cut_short, local, resting.get('morning', False)))
    lines = [rest.opening(resting), *happened]
    if paid:
        lines.append(f"They sleep in what they paid for: {paid['name']}.")
    if hungry:
        lines.append(f"The pack runs out of food: {hungry} hungry day{'s' if hungry > 1 else ''}, and no mending on them.")
    # A night's sleep turns what the character used into growth (dungeon/growth.py).
    grown = growth.grow(connection, database.now(), rng) if nights - lost > 0 else []
    comfort = 1 if paid and paid.get('tier') == 'private' and nights - lost > 0 else 0
    return (lines + combat.mend(connection, nights - lost - hungry)
            + stress.ease(connection, nights - lost - hungry + comfort) + grown)


def treat_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The treatment a line asks for (dungeon/injuries.py), decided once: a healer's, for a fee, or the character's own."""
    database = state.database
    with database.connect(write=True) as connection:
        if (kept := optional(connection, 'SELECT lines FROM story_treatments WHERE message_id=?', (user['id'],))):
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        lines = injuries.treat(connection, user['text'], view['people'], rolls, view['data']['currency'],
                               getattr(state, 'dice', None)) + unprepared(connection, user['text'])
        if lines:
            connection.execute('INSERT INTO story_treatments (message_id, lines) VALUES (?, ?)',
                               (user['id'], encode(lines)))
        return lines


def walk(database, connection, planned: dict, rolls: list[dict], message_id: str) -> list[str]:
    travel_map, start = travel.find(planned['from'])
    if planned.get('unknown'):
        return [f"The player's character does not know the way to {travel.nodes(travel_map)[planned['to']]['name']}: "
                'it is on no road they know of, and nobody has told them how to get there.']
    if planned.get('search'):
        minutes, found = travel.search(connection, planned, rolls)
        pass_time(database, connection, minutes)
        return found
    if not planned['legs']:
        return travel.blocked(planned)
    happened = []
    if planned.get('mode') == 'hex' and (waited := travel.till_light(story_clock.now(connection, database.clock),
                                                                     planned)):
        # Nobody walks off the road in the dark unless they say so: they wait for first light, then set out.
        pass_time(database, connection, waited)
        happened.append('It is dark: the character waits out the night and sets out at first light.')
    legs, travelled = travel.travelled(planned, rolls)
    happened += travelled
    spent, nights, days = travel.minutes(legs, travel_map['hours_a_day'])
    eaten, hungry = travel.eat(connection, travel_map['food'], days)
    pass_time(database, connection, spent)
    travel.walked(connection, travel_map, planned, legs)
    end, opening, ended = travel.ending(connection, travel_map, planned, legs, rolls)
    happened += ended
    place_scene(connection, end['city'], end['place'], database.now())
    add(connection, database.now(), 'scene', opening, scene_row(connection))
    # Signs warn when the road ends somewhere above the character (dungeon/tiers.py).
    found = happenings.where(end['city'], end['place'])
    happened += [warned] if found and (warned := tiers.warning(connection, found)) else []
    # A map can keep the road's cards off it: a ramble in Havenbrooke's woods meets no late bus.
    if not any(travel.STOPPED in line for line in happened) and travel_map.get('road_cards', True):
        drawn, minutes = life_card(database, connection, 'road', message_id)
        happened += drawn
        pass_time(database, connection, minutes)
    return travel.lines_for(travel_map, planned, legs, nights, eaten, hungry) + happened


def life_card(database, connection, kind: str, message_id: str) -> tuple[list[str], int]:
    """A Life Card draw for the line where the scene is now (dungeon/happenings.py), kept with it; what the
    narrator is told and the minutes it costs."""
    view = scene(connection, story_clock.now(connection, database.clock))
    data, day = view['data'], datetime.fromisoformat(view['local_time']).date()
    drawn = happenings.draw(connection, kind, f'{message_id}:{kind}', view['city']['id'], view['place']['id'], data,
                            intensity(connection, data), day)
    persona = optional(connection, 'SELECT name FROM persona WHERE id=1')
    lines, minutes = happenings.play(connection, drawn, {
        'people': view['people'], 'name': persona and persona['name'], 'data': data, 'map': drawn['map'],
        'now': story_clock.now(connection, database.clock), 'logged': database.now(),
        'rng': None, 'levels': intensity(connection, data)['levels'], 'city': view['city']['id'],
        'day': day.isoformat()}) if drawn else ([], 0)
    happenings.keep(connection, message_id, kind, day, drawn and drawn['card']['id'], lines)
    return lines, minutes


def town_turn(state, user: dict) -> list[str]:
    """A day in town draws a Life Card once, on the first line of the story day there."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = many(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene IN ('news', 'town') "
                                "ORDER BY scene", (user['id'],))
        if kept:
            return [line for row in kept for line in decode(row['lines'])]
        view = scene(connection, story_clock.now(connection, database.clock))
        found = happenings.where(view['city']['id'], view['place']['id'])
        day = datetime.fromisoformat(view['local_time']).date()
        if not found or not found['town'] or combat.fight(connection):
            return []
        # The news among the powers since the character was last in a town (dungeon/factions.py).
        # And the word about the people they know (dungeon/beats.py).
        lines = factions.news(connection, found['world'], database.now()) + beats.heard(
            connection, story_clock.now(connection, database.clock), database.now())
        if lines:
            happenings.keep(connection, user['id'], 'news', day, None, lines)
        if not happenings.drawn_today(connection, 'town', day):
            drawn, minutes = life_card(database, connection, 'town', user['id'])
            # A faction holding the town may need something done (dungeon/jobs.py).
            work = jobs.offer(connection, found['world'], found['node'], view['city']['id'],
                              happenings.wage(view['data']), view['data']['currency'],
                              story_clock.now(connection, database.clock), getattr(state, 'dice', None),
                              looking=jobs.seeking(user['text']))
            if work:
                happenings.keep(connection, user['id'], 'news', day, None, lines + work)
            lines += drawn + work
            pass_time(database, connection, minutes)
        elif jobs.seeking(user['text']):
            # Going looking for work finds it at the character's tier or below, any line (dungeon/jobs.py).
            work = jobs.offer(connection, found['world'], found['node'], view['city']['id'],
                              happenings.wage(view['data']), view['data']['currency'],
                              story_clock.now(connection, database.clock), getattr(state, 'dice', None), looking=True)
            if work:
                happenings.keep(connection, user['id'], 'news', day, None, lines + work)
            lines += work
        return lines


def director_turn(state, user: dict) -> list[str]:
    """The director's hidden note for the line (dungeon/director.py), written once and kept with it."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='director'",
                        (user['id'],))
        if kept:
            return decode(kept['lines'])
        now = story_clock.now(connection, database.clock)
        view = scene(connection, now)
        found = happenings.where(view['city']['id'], view['place']['id'])
        text = director.note(connection, found['world'], found['node'], view['people'],
                             happenings.drama(connection, view['data']), now) if found else ''
        happenings.keep(connection, user['id'], 'director', datetime.fromisoformat(view['local_time']).date(), None,
                        [text] if text else [])
        return [text] if text else []


def beats_turn(state, user: dict) -> list[str]:
    """The lives going on off the page (dungeon/beats.py), once for each line; the cutaways the narrator may show."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = beats.saved(connection, user['id'])
        if kept is not None:
            return kept
        now = story_clock.now(connection, database.clock)
        view = scene(connection, now)
        lines = beats.fire(connection, user['id'], view, intensity(connection, view['data']), now,
                           database.now(), getattr(state, 'dice', None))
        beats.keep(connection, user['id'], datetime.fromisoformat(view['local_time']).date(), lines)
        return lines


def labour_turn(state, user: dict) -> list[str]:
    """A stretch of work for hire in a town, paid the town's day wage (dungeon/labour.py), once for the line."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='work'", (user['id'],))
        if kept:
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        found = happenings.where(view['city']['id'], view['place']['id'])
        if not found or not found['town'] or combat.fight(connection):
            return []
        lines = labour.pay(connection, user['text'], happenings.wage(view['data']), view['data']['currency'],
                           line_minutes(connection, user['id']))
        if lines:
            happenings.keep(connection, user['id'], 'work', datetime.fromisoformat(view['local_time']).date(), None,
                            lines)
        return lines


def lie_turn(state, user: dict) -> list[str]:
    """Someone the line questions who has something to hide lies, and the character's insight is rolled
    (dungeon/lies.py), once for the line."""
    database = state.database
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        if combat.fight(connection):
            return []
        return lies.turn(connection, user['id'], view, user['text'], view['local_time'][:10], database.now(),
                         getattr(state, 'dice', None))


def bond_turn(state, user: dict) -> list[str]:
    """A line that pledges the character to someone there forges a bond (dungeon/bonds.py), once for the line."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='bond'", (user['id'],))
        if kept:
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        lines = bonds.sworn(connection, user['text'], view['people'], database.now())
        if lines:
            happenings.keep(connection, user['id'], 'bond', datetime.fromisoformat(view['local_time']).date(), None,
                            lines)
        return lines


def vow_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """Under Ironsworn, a line's vow moves (dungeon/sworn.py declared): a vow sworn, a milestone on one it pursues
    with a landed roll, or one fulfilled; once for the line."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='vow'", (user['id'],))
        if kept:
            return decode(kept['lines'])
        now = story_clock.now(connection, database.clock)
        day = now.date()
        lines = sworn.declared(connection, user['city_id'], user['text'], rolls, day.isoformat(), now)
        if lines:
            happenings.keep(connection, user['id'], 'vow', day, None, lines)
        return lines


def party_turn(state, user: dict) -> list[str]:
    """Asking someone along, or parting ways (dungeon/party.py), once for the line."""
    database = state.database
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        if combat.fight(connection):
            return []
        return party.turn(connection, user['id'], view, user['text'], view['local_time'][:10], database.now(),
                          getattr(state, 'dice', None))


def counter_text(lines: list[str]) -> str:
    return '## At the counter (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''


def fight_round(state, user: dict, rolls: list[dict]) -> list[str]:
    """The fight's part of the turn (dungeon/combat.py): a fight the player starts or a danger brings, one round."""
    database = state.database
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        bitten = next((roll for roll in rolls if roll.get('threat') and roll['band'] in quests.BITES), None)
        foe = quests.foe_for(user['city_id'], user['place_id'], bitten['threat']) if bitten else None
        sent = ''
        if bitten and foe is None:
            foe = delving.foe_for(connection, bitten['threat'])
        # Attacking a room's foes inside an interior starts the fight with them.
        if foe is None and not bitten and combat.fight(connection) is None and combat.attacks(user['text']):
            foe = delving.room_foe(connection)
        if bitten and foe is None and (foe := travel.foe_for(bitten['threat'])):
            # A road's foes are at its region's tier, or sent by an enemy above it (dungeon/tiers.py).
            found = happenings.where(view['city']['id'], view['place']['id'])
            foe, sent = tiers.foe(connection, found, foe, found['tier']) if found else (foe, '')
        moment = story_clock.now(connection, database.clock)
        def aftermath(events):
            # What the fight did to the character, and what it left between them and a foe (dungeon/director.py).
            director.history(connection, events, moment, database.now(), getattr(state, 'dice', None))
            return stress.aftermath(connection, moment, events, getattr(state, 'dice', None), database.now())

        def spoils(fallen, wants):
            # The bodies a fight won leaves, with what they carried (dungeon/finds.py).
            return finds.spoils(connection, view['city'], view['place'], fallen, wants, getattr(state, 'dice', None),
                                database.now())

        usable = [row for row in inventory.carried(connection, view['city']['id']) if row['condition'] != 'broken']
        fought = combat.turn(connection, user['id'], view['people'], rolls, foe, usable, getattr(state, 'dice', None),
                             database.now(), aftermath, spoils, user['text'])
        delving.fought(connection, combat.fight(connection) is not None, not combat.condition(connection)['dead'])
        return ([sent] if sent else []) + fought


class After:
    """What a turn still does once its reply is on screen (dungeon/pace.py): fact extraction and the summary. It runs
    once, after the response or, if the next turn comes first, at the start of that turn."""

    def __init__(self, work):
        self.work, self.started, self.done = work, False, None

    async def run(self):
        if self.started:
            if self.done is not None:
                await self.done.wait()
            return
        self.started, self.done = True, asyncio.Event()
        try:
            await self.work()
        finally:
            self.done.set()


async def settled(state):
    """The last turn's after-work, finished before a new turn starts."""
    if (after := getattr(state, 'after_turn', None)) is not None:
        await after.run()


def judging(connection, text: str, actions: list[dict], moment: datetime) -> dict | None:
    """What the Narrative Only judge is asked (dungeon/judge.py): the scene, and who its people are drawn to."""
    view = scene(connection, moment)
    return judge.asking(connection, persona_text(connection)[0], scene_text(view), text, actions, view['people'])


async def turn_rolls(state, user: dict, steps: pace.Steps) -> list[dict]:
    """The line's rolls, then the roll to get away from someone who would stop the character leaving
    (dungeon/leaving.py), made into a card once."""
    rolls = await rolled(state, user, steps)
    with state.database.connect(write=True) as connection:
        return [*rolls, *leaving.card(connection, user['id'], state.database.now())]


def leave_turn(state, user: dict) -> list[str]:
    """What the line's try at leaving came to (dungeon/leaving.py), for the narrator."""
    with state.database.connect() as connection:
        return leaving.lines(connection, user['id'])


async def rolled(state, user: dict, steps: pace.Steps) -> list[dict]:
    """The turn's rolls: kept from an earlier telling, or decided now (obvious lines skip the Referee's model)."""
    database = state.database
    with database.connect() as connection:
        rolls, splitter = turn.saved(connection, user['id']), referee.own_model(connection)
        decisions = referee.decision_model(connection)
        # Mid-fight nothing is obvious: "I go for the nearest one" is an attack, not a walk.
        fighting = combat.fight(connection) is not None
        foes = combat.fighting_whom(connection)
        # A prisoner is held, not out in the place: its danger is for those who walk it.
        held = combat.captors(connection)
    if rolls:
        return rolls
    with database.connect(write=True) as connection:
        # Someone who kept the character from leaving keeps them from setting out too (dungeon/leaving.py).
        held_back = leaving.stopped(connection, user['id'])
        # Inside an interior a line moves between its rooms (dungeon/delving.py); journeys wait till they are out.
        delving_in = delving.inside(connection) is not None
        delving_now = [] if held_back or fighting else delving.decide(
            connection, user['id'], user['city_id'], user['place_id'], user['text'], getattr(state, 'dice', None))
        delve = delving.kept(connection, user['id'])
        travelling = [] if held_back or delving_in or delve else travel.decide(
            connection, user['id'], user['city_id'], user['place_id'], user['text'], getattr(state, 'dice', None))
        # Going in, along a passage, searching or coming out is rolled by the interior, not split by the Referee.
        journeying = travel.journey(connection, user['id']) is not None or bool(delve and delve['kind'] != 'stay')
    since = steps.clock()
    obvious = pace.obvious(user['text']) and not fighting
    # A journey's dangers and bearings are rolled by the journey (dungeon/travel.py): walking itself is no feat, and
    # "I strike out north-east" is no attack.
    # Nor is bedding down mid-fight a feat to roll: the rest is refused (dungeon/rest.py) and the foes come on.
    sleeping = fighting and rest.resting(user['text'])
    actions = [] if journeying or sleeping else await referee.decide(
        state, user['text'], None if obvious else splitter, None if obvious else decisions, foes)
    steps.timed('referee', since)
    if not held and (hazard := quests.danger_action(user['city_id'], user['place_id'], getattr(state, 'dice', None))):
        actions = [*actions, hazard]
    with database.connect(write=True) as connection:
        actions = [*actions, *travelling, *delving_now]
        if not held_back and (camp := rest.decide(connection, user['id'], user['city_id'], user['place_id'],
                                                  user['text'], getattr(state, 'dice', None))):
            actions = [*actions, camp]
        moment = story_clock.now(connection, database.clock)
        if mend := injuries.decide(connection, user['text'], scene(connection, moment)['people']):
            actions = [*actions, mend]
        elif aid := injuries.first_aid(connection, user['text'], actions):
            actions = [*actions, aid]
        if injuries.unhurt(connection, user['text']):
            actions = injuries.untreated(actions)
        if memory := remembering.recall_action(connection, user['text']):
            # The recall roll is the line's Mind roll; the Referee's own is dropped for it.
            actions = [*(action for action in actions if action['stat'] != 'Mind'), memory]
        actions = spell_actions(connection, user['text'], actions)
        actions = injuries.adjust(connection, combat.adjust(connection, feelings.adjust(connection, actions)), moment)
        # Under Narrative Only a judge gives each action its verdict before it is kept (dungeon/judge.py).
        ask = None if turn.saved(connection, user['id']) else judging(connection, user['text'], actions, moment)
        if ask is None:
            if saved := turn.saved(connection, user['id']):
                return saved
            rolls = turn.store(connection, user['id'], actions, database.now(), getattr(state, 'dice', None))
            # Under Fate, a line that acts on the trouble earns its Fate point even with nothing rolled.
            compel_line(connection, user['text'], rolls)
            return rolls
    actions = await judge.judged(state, actions, ask)
    with database.connect(write=True) as connection:
        return turn.saved(connection, user['id']) or turn.store(connection, user['id'], actions, database.now(),
                                                                getattr(state, 'dice', None))


async def told(state, packet: dict, config: dict, in_story: bool, steps: pace.Steps,
               on_text) -> tuple[str, str | None, list[dict]]:
    """The narration, then (time allowing) the prose rewrite and, only when it names the dead, the contradiction check;
    with what the checks left in it, flagged for the player to rewrite (dungeon/passages.py)."""
    since = steps.clock()
    try:
        text, error = await narrate(state, packet, config, in_story, on_text)
    except DomainError as failure:
        text, error = '', failure.message
    steps.timed('narrator', since)
    if not text or error or not in_story:
        return text, error, []
    rewrite = lambda system, messages: complete(state, config, system, messages)  # noqa: E731
    since, timely = steps.clock(), steps.has_time()
    text, _ = await prose.polish(text, rewrite if timely else None)
    if timely:
        steps.timed('rewrite', since)
    else:
        steps.skip('rewrite')
    with state.database.connect() as connection:
        names = pace.named_dead(record.dead(connection), text)
        checking = bool(settings(connection)['contradiction_check'])
    unchecked = []
    if names and checking and steps.has_time():
        since = steps.clock()
        text = await pace.contradiction(text, names, rewrite)
        steps.timed('contradiction', since)
    elif names:
        # Skipped for time, or by the player's setting: the passage is flagged for them to rewrite instead.
        steps.skip('contradiction')
        unchecked = names
    # A past-year world (dungeon/world/decades.py): narration naming something from a later year gets one rewrite
    # while there is time; what is left is flagged for the player.
    year = packet.get('year')
    if (later := decades.anachronisms(text, year)) and steps.has_time():
        since = steps.clock()
        text = await anachronism_rewrite(text, later, year, rewrite)
        steps.timed('anachronism', since)
    with state.database.connect() as connection:
        return text, None, passages.flags(text, passages.dead_reasons(connection, unchecked),
                                          later=passages.later_reasons(text, year))


async def anachronism_rewrite(text: str, later: list[dict], year: int, rewrite) -> str:
    """The narration without the things from after its year, when a rewrite takes them out and keeps the rest."""
    notes = [f'- {decades.why(finding, year)}' for finding in later]
    try:
        revised = prose.without_dashes((await rewrite(prose.REWRITE, [{'role': 'user', 'content': (
            f'Narration:\n\n{text}\n\nFix these:\n' + '\n'.join(notes))}])).strip())
    except Exception as error:  # noqa: BLE001 - the draft stands, flagged; a failed rewrite never loses a turn
        log.warning('The anachronism rewrite failed: %s', error)
        return text
    if prose.acceptable(text, revised) and len(decades.anachronisms(revised, year)) < len(later):
        return revised
    return text


async def afterwards(state, user: dict, reply: dict, packet: dict, steps: pace.Steps):
    """Fact extraction and the summary, once the reply is on screen; a failure here never loses the turn."""
    database = state.database
    try:
        since = steps.clock()
        with database.connect() as connection:
            there = [{'key': row['key'], 'name': row['name']} for row in feelings.met(connection)
                     if row['key'] in {person['sheet']['key'] for person in packet['people']}]
            ask = (quests.ending_ask(connection) + quests.oath_ask() + feelings.feelings_ask(there)
                   + growth.dark_ask() + plotting.ENGAGED_ASK)
            extra = (quests.ending_schema(connection) | quests.OATH_SCHEMA | feelings.feelings_schema(there)
                     | growth.dark_schema() | plotting.ENGAGED_SCHEMA)
        answered = await record.extract(state, user['text'], reply, ask, extra)
        with database.connect(write=True) as connection:
            for item in quests.endings(answered):
                quests.end(connection, item['id'], item['status'], item['outcome'], database.now())
                chapters.mark(connection, 'quest')
            # What the character did that feeds a dark track (dungeon/growth.py).
            for track in growth.darkened(answered):
                view = scene(connection, story_clock.now(connection, database.clock))
                growth.darken(connection, track, 1, intensity(connection, view['data'])['levels'], database.now(),
                              getattr(state, 'dice', None))
            # An oath the character swore is an obligation, with its deadline, or a vow on a quest they already have
            # (dungeon/quests.py).
            for oath in quests.oaths(answered):
                quests.vow(connection, user['city_id'], user['text'], oath, story_clock.now(connection, database.clock))
            feelings.from_answer(connection, answered, {person['key'] for person in there})
        # A detail the player took an interest in may be given a meaning; arc stages get their beats planned
        # (dungeon/plotting.py).
        await plotting.adopt(state, plotting.engaged(answered), reply['id'], getattr(state, 'dice', None))
        await plotting.plan(state)
        steps.timed('extraction', since)
        since = steps.clock()
        with database.connect() as connection:
            rows = messages(connection)
        await record.fold(state, rows)
        await chapters.summarize(state)
        steps.timed('summary', since)
        # A picture the turn calls for, with Passive art on (dungeon/art.py); art reads the scene from here.
        from dungeon import art
        await art.passive(state, [person['sheet']['key'] for person in packet['people']])
        with database.connect(write=True) as connection:
            if optional(connection, 'SELECT 1 FROM story_messages WHERE id=?', (user['id'],)):
                pace.save(connection, user['id'], steps)
    except Exception:  # noqa: BLE001 - facts missed are better than a story that stops
        log.exception('After the turn')


async def no_event(_event: dict):
    pass


async def answer(state, user: dict, on_text=None, on_event=None) -> dict:
    """The narrator's reply to the user's message, saved complete or failed with the reason. Fact extraction and the
    summary are left for `state.after_turn`, run once the reply is on screen (dungeon/pace.py). `on_event(event)` hears
    the turn's stages as they happen, for the stream: reading the line, the actions and each roll, then writing; with
    the dice hidden, only what was tried and with which stat (dungeon/turn.py)."""
    emit = on_event or no_event
    database = state.database
    in_story = not in_character.out_of_character(user['text'])
    # No model fails the turn before it says it has begun.
    with database.connect() as connection:
        if config_for(connection, JOB) is None:
            raise no_model()
    if in_story:
        await emit({'stage': 'reading'})
    await settled(state)
    with database.connect(write=True) as connection:
        # The narrator's Mix, when it is on, picks this turn's model (dungeon/text_models.py reply_config).
        config = reply_config(connection, JOB)
        if config is None:
            raise no_model()
        steps = pace.Steps(pace.budget_for(connection, config), getattr(state, 'pace_clock', None) or time.monotonic)
    rolls = await turn_rolls(state, user, steps) if in_story else []
    if rolls:
        with database.connect() as connection:
            shown = dice_shown(connection)
            ruleset = ruleset_of(connection)
        await emit({'actions': turn.announced(rolls, shown)} | ({'bands': turn.bands(ruleset)} if shown else {}))
        for roll in rolls:
            await emit({'roll': turn.shown(roll) if shown else turn.hidden(roll)})
    travelled = travel_turn(state, user, rolls) if in_story else []
    delved = delving.prompt_text(delve_turn(state, user, rolls)) if in_story else ''
    rested = rest_turn(state, user, rolls) if in_story else []
    carded = town_turn(state, user) if in_story else []
    meanwhile = beats_turn(state, user) if in_story else []
    noted = director_turn(state, user) + recall_turn(state, rolls) + opening_turn(state, user) if in_story else []
    with database.connect() as connection:
        noted += [away_text(connection, user['id'])] if in_story else []
    noted += [delved, labour.prompt_text(labour_turn(state, user)), lies.prompt_text(lie_turn(state, user)),
              bonds.prompt_text(bond_turn(state, user)), party.prompt_text(party_turn(state, user)),
              sworn.prompt_text(vow_turn(state, user, rolls)), leaving.prompt_text(leave_turn(state, user))] \
        if in_story else []
    fought, traded, tended, looked, looks = (in_scene(state, user, rolls, travelled, rested) if in_story
                                             else ([], [], [], [], []))
    noted = noted + looks
    with database.connect() as connection:
        # The rule text that fits what the turn resolved (dungeon/rules/passages.py).
        ruled = rule_passages.text(ruleset_of(connection), rolls, user['text'], fought, config.get('context_tokens'),
                              table.rule(connection, 'rule_text') == 'on') if in_story else ''
        packet = prompt(connection, story_clock.now(connection, database.clock), config, user,
                        turn.outcomes(rolls) if in_story else None, fought, traded, looked, travelled, rested, tended, carded,
                        meanwhile, noted, ruled)
    await emit({'stage': 'writing'})
    text, error, flagged = await told(state, packet, config, in_story, steps, on_text)
    status = 'complete' if text and not error else 'failed'
    error = None if status == 'complete' else error or 'The model returned no story text.'
    with database.connect(write=True) as connection:
        connection.execute("DELETE FROM story_messages WHERE reply_to=? AND status='failed'", (user['id'],))
        if status == 'complete' and in_story:
            story_people.note_exchange(connection, packet['people'], packet['city_id'], user['text'], text,
                                       database.now(), packet['day'])
            feelings.from_rolls(connection, rolls)
            growth.mark(connection, rolls, user['id'])
            remembering.refresh(connection, f"{user['text']}\n{text}")
            # A place of the town named in the story is one the character knows of now (dungeon/townmap.py).
            townmap.heard(connection, city_data(connection, scene_row(connection)['city_id']), text)
            library.mark_given(connection, packet['library'], user['seq'])
            lore.remember(connection, packet.get('lore', []), packet.get('line', 0))
            if reason := scene_break(connection, user, travelled, rested, fought):
                chapters.mark(connection, reason)
            # What the line touched in the GM's notebook, and the scene's kind (dungeon/director.py).
            if found := happenings.where(packet['city_id'], scene_row(connection)['place_id']):
                director.touch(connection, found['world'], f"{user['text']}\n{text}",
                               director.scene_kind(rolls, fought, packet['people'], noted), user['id'],
                               database.now())
                plotting.after_line(connection, text, user['id'])
        reply = add(connection, database.now(), 'narrator', text, scene_row(connection), reply_to=user['id'],
                    status=status, error=error,
                    flags=flagged)
        pace.save(connection, user['id'], steps)
    if status == 'complete' and in_story:
        state.after_turn = After(lambda: afterwards(state, user, reply, packet, steps))
    return reply


def received(database, text: str, client_id: str, rng=None) -> tuple[dict, dict | None]:
    """The user's message, saved once whatever retries come; with the narrator's reply if it already has one."""
    with database.connect(write=True) as connection:
        user = optional(connection, 'SELECT * FROM story_messages WHERE client_id=?', (client_id,))
        if user is None:
            after = ' In Ironman, that is final: start a new story.' if chapters.ironman(connection) else \
                ' Go back to an earlier line to play on.'
            require(not combat.condition(connection)['dead'], 'Your character is dead.' + after, 409)
            require(not growth.lost(connection), f'Your character is lost to {growth.lost(connection)}.' + after, 409)
            user = add(connection, database.now(), 'user', text, scene_row(connection), client_id=client_id)
            # A world in real time went on while the player was away (dungeon/story_clock.py caught_up).
            real_time(database, connection, user)
            timeline.save(connection, user['id'])
            walked = None if in_character.out_of_character(text) else walked_to(connection, text, database.clock)
            # Someone there may keep the character from going (dungeon/leaving.py): then they go nowhere.
            if not in_character.out_of_character(text) and leave_line(database, connection, user, text, walked, rng):
                walked = None
            if walked and (walked['city_id'], walked['id']) != (user['city_id'], user['place_id']):
                # A line that goes somewhere opens the chapter there.
                chapters.mark(connection, 'place')
            # A break left pending by the last line opens a new chapter with this one (dungeon/chapters.py).
            chapters.arrive(connection, user, database.now())
            # The time the line takes passes as it is sent: the narrator writes the scene after it.
            if not in_character.out_of_character(text):
                sit_through(database, connection, user, text)
                line_time(database, connection, user, text, walked)
        reply = optional(connection, "SELECT * FROM story_messages WHERE reply_to=? AND status='complete'",
                         (user['id'],))
        return user, reply


def line_time(database, connection, user: dict, text: str, walked: dict | None):
    """The time a line takes, passed as it is sent; the minutes kept with it (story_cards scene 'clock') for the work
    it pays (dungeon/labour.py). A rest passes its own nights (dungeon/rest.py), and a journey its own hours
    (dungeon/travel.py)."""
    local = local_moment(city_data(connection, user['city_id']), story_clock.now(connection, database.clock))
    if walked:
        # "I go to the shrine": the story moves there before the narrator writes, as "Go somewhere else" would;
        # "I spend the day at the market" spends it there too.
        place_scene(connection, walked['city_id'], walked['id'], database.now())
        minutes = story_clock.ACROSS_TOWN_MINUTES + story_clock.spent(text, local)
        pass_time(database, connection, minutes)
        arrive(connection, database.now())
    elif delving.inside(connection) and delving.moving(text):
        return  # a move inside an interior passes its own minutes (dungeon/delving.py)
    elif not leaving.stopped(connection, user['id']) and (
            rest.resting(text) or out_on_the_map(connection, user, text)):
        return
    else:
        minutes = story_clock.minutes_for(text, bool(referee.by_keywords(text)), local)
        pass_time(database, connection, minutes)
    happenings.keep(connection, user['id'], 'clock', local.date(), None, [minutes])


def out_on_the_map(connection, user: dict, text: str) -> bool:
    """Whether a line sets out on a journey: not from inside an interior, where it moves between rooms."""
    return delving.inside(connection) is None and travel.setting_out(connection, user['city_id'], user['place_id'], text)


def leave_line(database, connection, user: dict, text: str, walked: dict | None, rng=None) -> bool:
    """Whether someone there stops the line leaving (dungeon/leaving.py), decided once as it is sent."""
    going = bool(walked and (walked['city_id'], walked['id']) != (user['city_id'], user['place_id'])) or \
        out_on_the_map(connection, user, text)
    view = scene(connection, story_clock.now(connection, database.clock))
    kept = leaving.decide(connection, user['id'], view, text, going, database.now(), rng)
    return bool(kept and kept['stopped'])


def living(connection, city_id: str) -> bool:
    """Whether the campaign's world keeps real time: the Table's clock, else the world's own (dungeon/tiers.py)."""
    chosen = table.rule(connection, 'clock')
    return (tiers.clock(tiers.world_of(city_id)) if chosen in (None, 'world') else chosen) == 'real_time'


def real_time(database, connection, user: dict):
    """The real time since the last line passes before this one, in a world that lives in real time; a long gap is
    kept with the line for the narrator (story_cards scene 'away')."""
    minutes = story_clock.caught_up(connection, database.clock.now(), living(connection, user['city_id']))
    if minutes:
        pass_time(database, connection, minutes)
    if minutes >= story_clock.AWAY:
        happenings.keep(connection, user['id'], 'away', story_clock.now(connection, database.clock).date(), None,
                        [minutes])


def away_text(connection, message_id: str) -> str:
    kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='away'", (message_id,))
    if not kept:
        return ''
    minutes = decode(kept['lines'])[0]
    days, hours = divmod(minutes // 60, 24)
    gap = ' and '.join(part for part in (f"{days} day{'s' if days != 1 else ''}" if days else '',
                                         f"{hours} hour{'s' if hours != 1 else ''}" if hours else '') if part)
    return ('## While the player was away (decided by the game)\n'
            f"- {gap or 'An hour'} passed in the world since the character's last moment: people went on with their "
            'lives. Open on where the character is now, with what changed showing, not told.')


def line_minutes(connection, message_id: str) -> int | None:
    kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='clock'", (message_id,))
    return decode(kept['lines'])[0] if kept else None


def sit_through(database, connection, user: dict, text: str):
    """A line that goes on after the class held here ("after class I...") passes the class first, so it is attended
    (dungeon/institutions.py)."""
    if minutes := institutions.until_class_ends(connection, user['city_id'], user['place_id'], text,
                                               story_clock.now(connection, database.clock)):
        pass_time(database, connection, minutes)


async def send(state, text: str, client_id: str, on_text=None, on_event=None) -> dict:
    user, reply = received(state.database, text, client_id, getattr(state, 'dice', None))
    return {'message': user, 'reply': reply or await answer(state, user, on_text, on_event)}


async def retry(state, on_text=None, on_event=None) -> dict:
    """Tell the last part again: a new reply to the user's latest message, replacing the one there."""
    await settled(state)
    with state.database.connect(write=True) as connection:
        where, values = timeline.visible(connection)
        user = optional(connection, f"SELECT * FROM story_messages WHERE role='user' AND {where} ORDER BY seq DESC "
                                    'LIMIT 1', values)
        # A line from before going back is shared with the branch it came from; its reply stays as it was told.
        require(user is not None and user['branch_id'] == timeline.active(connection),
                'There is nothing to retell yet.', 409)
        # The facts the old reply brought in go with it.
        connection.execute('DELETE FROM record_entries WHERE message_id IN (SELECT id FROM story_messages WHERE '
                           'reply_to=?)', (user['id'],))
        connection.execute('DELETE FROM story_messages WHERE reply_to=?', (user['id'],))
        # So are the meetings and feelings it moved; the kept rolls move them again.
        timeline.restore_at(connection, user['id'], ('story_people',))
    return {'message': user, 'reply': await answer(state, user, on_text, on_event)}


# Rewrite -----------------------------------------------------------------------------------------

def story_year(connection, database) -> int | None:
    """The story's year in a modern world set in a past one (dungeon/world/decades.py); None in the present."""
    view = scene(connection, story_clock.now(connection, database.clock))
    return decades.year_of(view['data'], datetime.fromisoformat(view['local_time']), database.clock.now().year)

def narration(connection, message_id: str) -> dict:
    """A narration the player may reword: told in the branch being played, so no other branch shares it."""
    where, values = timeline.visible(connection)
    row = optional(connection, f"SELECT * FROM story_messages WHERE id=? AND role='narrator' AND status='complete' "
                               f'AND {where}', (message_id, *values))
    require(row is not None, 'That part of the story is not there to rewrite.', 404)
    require(row['branch_id'] == timeline.active(connection),
            'That part comes from before you went back, and another branch shares it, so it stays as it was.', 409)
    return row


def reworded(state, connection, row: dict, text: str, flagged: list[dict], previous: dict | None):
    """The narration's new wording saved, and its facts taken again from it once the reply is back (the facts the
    old wording brought in go with it)."""
    connection.execute('UPDATE story_messages SET text=?, flags=?, previous=? WHERE id=?',
                       (text, encode(flagged), encode(previous) if previous else None, row['id']))
    connection.execute("DELETE FROM record_entries WHERE message_id=? AND source='narrator'", (row['id'],))
    user = optional(connection, 'SELECT * FROM story_messages WHERE id=?', (row['reply_to'],))
    if user is not None:
        state.after_turn = After(lambda: record.extract(state, user['text'], {'id': row['id'], 'text': text}))


async def rewritten(state, message_id: str, passage: str, note: str = '') -> dict:
    """A passage of a narration in new words (dungeon/passages.py): the dice and the record's facts stay."""
    await settled(state)
    database = state.database
    with database.connect() as connection:
        row, config = narration(connection, message_id), config_for(connection, JOB)
        if config is None:
            raise no_model()
        where = passages.span(row['text'], passage)
        require(where is not None, 'Select a passage of this part of the story to rewrite.', 422)
        system = '\n\n'.join(part for part in (passages.SYSTEM, record.prompt_text(connection)) if part)
    before, flagged = row['text'][where[0]:where[1]], decode(row['flags'])
    revised = prose.without_dashes((await complete(
        state, config, system, passages.request(row['text'], before, flagged, note))).strip())
    require(prose.acceptable(before, revised), 'The rewrite came back too different, so the passage stays as it was. '
                                               'Try again.', 502)
    text = row['text'][:where[0]] + revised + row['text'][where[1]:]
    with database.connect(write=True) as connection:
        dead, kept = passages.still_dead(flagged, text)
        later = passages.later_reasons(text, story_year(connection, database))
        reworded(state, connection, row, text, passages.flags(text, dead, kept, later),
                 {'text': row['text'], 'flags': flagged})
    return story(database)


async def switched(state, message_id: str) -> dict:
    """A rewritten narration back to its wording before the rewrite; switching again brings the rewrite back."""
    await settled(state)
    database = state.database
    with database.connect(write=True) as connection:
        row = narration(connection, message_id)
        require(row['previous'] is not None, 'That part has not been rewritten.', 409)
        previous = decode(row['previous'])
        reworded(state, connection, row, previous['text'], previous['flags'],
                 {'text': row['text'], 'flags': decode(row['flags'])})
    return story(database)
