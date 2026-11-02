"""Small, lasting changes to a city: a cafe opening, road works on the way to work, a favourite spot closing.

Seeded changes come from the city and the month alone, so every run and every generator sees the same ones and
nothing needs storing. The workspace keeps only what a seed cannot know: changes the user adds, seeded ones the
user dismisses. `apply` gives
a city as it stands on one day, which is what CatalogWorld hands the life simulation, so a closed place drops out
of outings, a new one can be picked, and road works slow trips through their neighbourhood. Changes are dated,
so events composed before a change keep the place they happened at.
"""
import re
from datetime import date, datetime, timedelta
from functools import cache

from dungeon.clock import zone
from dungeon.database import decode, encode, identifier, many, optional
from dungeon.errors import DomainError, require
from dungeon.world import catalog
from dungeon.world.generators import FOOD, pick, unit
from dungeon.world.schema import Changes

# Seeded changes start with the feature; a city visited on earlier dates (London in 1895) looks back a year.
EPOCH, HISTORY = date(2026, 10, 1), timedelta(days=365)
# The chance of each kind of change in a city in one month, and how many days ahead people hear of it.
RATES = {'opening': 0.45, 'renovation': 0.35, 'roadworks': 0.45, 'closing': 0.2}
LEAD = {'opening': 10, 'renovation': 4, 'roadworks': 6, 'closing': 14}
SPANS = {'renovation': (14, 56), 'roadworks': (10, 70)}
# A place renovated once is left alone for this long.
RESTED = timedelta(days=365)
CLOSABLE = {'cafe', 'restaurant', 'bar', 'nightlife', 'shopping', 'fitness', 'tavern', 'inn', 'workshop', 'market'}
RENOVATED = CLOSABLE | {'museum', 'library', 'venue', 'attraction'}
KINDS = ('opening', 'closing', 'renovation', 'roadworks', 'news')
# What chat context still mentions: permanent changes this many days on, reopenings a week on, at most LIMIT.
RECENT, REOPENED, LIMIT = 30, 7, 6
# How long a headline from a real lookup stays something the companion has heard about, and how many per lookup.
SOURCE_ID = 'city-changes'
SOURCE = {'kind': 'curated', 'title': 'Changes to the city since its data was written (seeded, or added by you)',
          'license': 'CC0-1.0', 'retrieved': '2026-10-05', 'url': None, 'note': ''}
LABELS = {'fitness': 'studio', 'shopping': 'shop', 'nightlife': 'club', 'cafe': 'cafe'}


@cache
def bank() -> dict:
    return Changes.model_validate_json((catalog.DATA / 'changes.json').read_text(encoding='utf-8')).model_dump()


def style(data: dict) -> dict:
    return bank()['styles'][bank()['eras'][data['era']]]


def resolve(city: str, extra: dict[str, dict]) -> dict | None:
    """A city by id, or by text that names it ("Fells Point, Baltimore")."""
    if city in catalog.cities() or city in extra:
        return catalog.city(city, extra)
    match = catalog.resolve(city, extra)
    return catalog.city(match['city'], extra) if match else None


def slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower().replace('’', '').replace("'", '')).strip('-')[:50]


def day_text(value: str) -> str:
    day = date.fromisoformat(value)
    return f'{day:%b} {day.day}'


# --- Seeded changes ---

def months(first: date, last: date):
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def seeded(data: dict, through: date) -> list[dict]:
    """Every seeded change announced by `through`, oldest first. Each month is decided from the city id and the
    month, so the same city always changes the same way; places already closed are not closed again."""
    first = EPOCH if through >= EPOCH else through - HISTORY
    return [change for change in _seeded(data, first, through + timedelta(days=max(LEAD.values())))
            if change['announced'] <= through.isoformat()]


_SEEDED: dict[tuple, list[dict]] = {}


def _seeded(data: dict, first: date, last: date) -> list[dict]:
    key = (data['id'], data.get('data_version', ''), len(data['places']), first.year, first.month, last.year,
           last.month)
    if key not in _SEEDED:
        state = {'closed': set(), 'names': {place['name'].lower() for place in data['places']}, 'opened': {}, 'renovated': {}}
        found = []
        for year, month in months(first, last):
            found += month_changes(data, year, month, state)
        _SEEDED[key] = found
    return _SEEDED[key]


def month_changes(data: dict, year: int, month: int, state: dict) -> list[dict]:
    seed = f"{data['id']}:{year:04d}-{month:02d}"
    found = []
    for kind, rate in RATES.items():
        if unit(seed, kind) >= rate:
            continue
        start = date(year, month, 1 + int(unit(seed, kind, 'day') * 28))
        change = MAKERS[kind](data, f'{seed}:{kind}', start, state)
        if change:
            span = SPANS.get(kind)
            ends = start + timedelta(days=span[0] + int(unit(seed, kind, 'span') * (span[1] - span[0]))) if span \
                else None
            found.append(change | {'id': f'seed-{data["id"]}-{year:04d}-{month:02d}-{kind}', 'city': data['id'],
                                   'kind': kind, 'origin': 'seeded', 'starts': start.isoformat(),
                                   'ends': ends.isoformat() if ends else None,
                                   'announced': (start - timedelta(days=LEAD[kind])).isoformat()})
    return found


def new_place(data: dict, kind: str, name: str, hood: str, summary: str, seed: str, place_id: str) -> dict:
    """A place for an opening, keeping the hours, setting and price level of one of the city's places of its kind."""
    similar = [place for place in data['places'] if place['kind'] == kind]
    template = pick(seed, 'template', similar) or {'cost': '$$', 'setting': 'indoor', 'good_for': ['solo', 'friends'],
                                                   'day_parts': ['afternoon', 'evening'], 'seasons': [], 'tags': []}
    return {'id': place_id, 'name': name, 'kind': kind, 'neighborhood': hood, 'summary': summary,
            'tags': sorted({*template.get('tags', [])[:9], 'new'}), 'cost': template['cost'],
            'setting': template['setting'], 'good_for': list(template['good_for']),
            'day_parts': list(template['day_parts']), 'seasons': list(template.get('seasons', [])),
            'cuisine': template.get('cuisine', ''), 'source': SOURCE_ID}


def make_opening(data: dict, seed: str, start: date, state: dict) -> dict | None:
    words = style(data)['openings']
    kinds = sorted(kind for kind in words if any(place['kind'] == kind for place in data['places']))
    kind = pick(seed, 'kind', kinds)
    if kind is None:
        return None
    bank_words = words[kind]
    name = f"{pick(seed, 'first', bank_words['first'])} {pick(seed, 'second', bank_words['second'])}"
    if name.lower() in state['names']:
        return None
    state['names'].add(name.lower())
    hood = pick(seed, 'hood', data['neighborhoods'])
    place = new_place(data, kind, name, hood['id'], bank_words['summary'], seed,
                      f'new-{slug(name)}-{start:%Y%m}')
    state['opened'][place['id']] = (place, start)
    return {'place': place['id'], 'name': name, 'neighborhood': hood['id'], 'summary': bank_words['summary'],
            'place_kind': kind, 'opened': place}


def keeps_food(data: dict, place: dict, closed: set) -> bool:
    """Closing this place still leaves its neighbourhood somewhere to eat or drink."""
    if place['kind'] not in FOOD:
        return True
    return any(other['kind'] in FOOD and other['neighborhood'] == place['neighborhood'] and other['id'] != place['id']
               and other['id'] not in closed for other in data['places'])


def shut(data: dict, seed: str, start: date, state: dict, kinds: set, reasons: list[str], close: bool) -> dict | None:
    """Close a place for good or for a while. In a real city only places that opened here are closed by a seed:
    the shipped places are real businesses, and saying one shut would be a false claim about it."""
    opened = [place for place, day in state['opened'].values() if day < start]
    pool = opened + ([] if data['setting'] == 'real' else data['places'])
    lately = (start - RESTED).isoformat()
    candidates = [place for place in pool if place['kind'] in kinds and place['id'] not in state['closed']
                  and state['renovated'].get(place['id'], '') < lately and keeps_food(data, place, state['closed'])]
    place = pick(seed, 'place', candidates)
    if place is None:
        return None
    if close:
        state['closed'].add(place['id'])
    else:
        state['renovated'][place['id']] = start.isoformat()
    return {'place': place['id'], 'name': place['name'], 'neighborhood': place['neighborhood'],
            'summary': pick(seed, 'reason', reasons), 'place_kind': place['kind']}


def make_closing(data, seed, start, state):
    return shut(data, seed, start, state, CLOSABLE, style(data)['closing'], True)


def make_renovation(data, seed, start, state):
    return shut(data, seed, start, state, RENOVATED, style(data)['renovation'], False)


def make_roadworks(data, seed, start, state):
    hood = pick(seed, 'hood', data['neighborhoods'])
    works = pick(seed, 'works', style(data)['roadworks'])
    return {'place': None, 'name': hood['name'], 'neighborhood': hood['id'], 'summary': works['summary'],
            'delay': works['delay']}


MAKERS = {'opening': make_opening, 'closing': make_closing, 'renovation': make_renovation,
          'roadworks': make_roadworks}


# --- Stored changes ---

def row_view(row: dict) -> dict:
    details = decode(row['details']) or {}
    return {'id': row['id'], 'city': row['city_id'], 'kind': row['kind'], 'origin': row['origin'],
            'place': row['place_id'], 'name': row['name'], 'neighborhood': row['neighborhood_id'],
            'summary': row['summary'], 'announced': row['announced_on'], 'starts': row['starts_on'],
            'ends': row['ends_on'], 'observation': row['observation_id'], **details}


def stored(connection, city_id: str) -> tuple[list[dict], set[str]]:
    """The workspace's own changes for a city, and the ids of seeded changes the user dismissed."""
    rows = many(connection, 'SELECT * FROM world_changes WHERE city_id=? ORDER BY starts_on, created_at', (city_id,))
    dismissed = {row['change_id'] for row in many(connection, 'SELECT change_id FROM world_change_dismissals '
                                                  'WHERE city_id=?', (city_id,))}
    return [row_view(row) for row in rows], dismissed


def known(data: dict, day: date, saved: tuple[list[dict], set[str]] = ((), frozenset())) -> list[dict]:
    """Every change to the city that people have heard of by `day`, oldest first."""
    own, dismissed = saved
    seeds = [change for change in seeded(data, day) if change['id'] not in dismissed]
    return sorted([*seeds, *(change for change in own if change['announced'] <= day.isoformat())],
                  key=lambda change: (change['starts'], change['id']))


def active(change: dict, day: date) -> bool:
    today = day.isoformat()
    return change['starts'] <= today and (change['ends'] is None or today < change['ends'])


def apply(data: dict, changes: list[dict], day: date) -> dict:
    """The city as it stands on `day`: closed places gone, opened ones added, road works on their neighbourhoods
    (`works`, which commute estimates use). The cached city is not changed."""
    live = [change for change in changes if change['kind'] != 'news' and active(change, day)]
    if not live:
        return data
    closed = {change['place'] for change in live if change['kind'] in ('closing', 'renovation')}
    opened = [change['opened'] for change in live if change['kind'] == 'opening']
    works = {change['neighborhood']: {'id': change['id'], 'summary': change['summary'], 'delay': change['delay'],
                                      'until': change['ends']} for change in live if change['kind'] == 'roadworks'}
    result = dict(data)
    result['places'] = [place for place in [*data['places'], *opened] if place['id'] not in closed]
    result['neighborhoods'] = [hood | {'works': works[hood['id']]} if hood['id'] in works else hood
                               for hood in data['neighborhoods']]
    result['sources'] = data['sources'] | {SOURCE_ID: SOURCE}
    return result


# --- Changes the user makes ---

def _place(data: dict, place_id: str | None) -> dict:
    found = next((place for place in data['places'] if place['id'] == place_id), None)
    require(found is not None, f'{data["name"]} has no place {place_id!r}.', 422)
    return found


def _fields(data: dict, change: dict) -> dict:
    """The stored columns for a change the user describes, checked against the city."""
    kind, summary = change['kind'], change.get('summary') or ''
    if kind in ('closing', 'renovation'):
        place = _place(data, change.get('place_id'))
        return {'place_id': place['id'], 'neighborhood_id': place['neighborhood'], 'name': place['name'],
                'summary': summary or style(data)[kind][0], 'details': {'place_kind': place['kind']}}
    hood = catalog.neighborhood(data, change.get('neighborhood') or '')
    if kind == 'roadworks':
        return {'place_id': None, 'neighborhood_id': hood['id'], 'name': hood['name'],
                'summary': summary or style(data)['roadworks'][0]['summary'],
                'details': {'delay': change.get('delay') or style(data)['roadworks'][0]['delay']}}
    name, place_kind = change.get('name'), change.get('place_kind')
    require(bool(name) and bool(place_kind), 'A new place needs a name and a kind.', 422)
    place_id = f'new-{slug(name)}-{change["starts_on"].replace("-", "")[:6]}'
    require(catalog.find(data, place_id) is None, f'{data["name"]} already has a place like {name!r}.', 409)
    place = new_place(data, place_kind, name, hood['id'], summary or f'A new {LABELS.get(place_kind, place_kind)}.',
                      place_id, place_id)
    return {'place_id': place_id, 'neighborhood_id': hood['id'], 'name': name, 'summary': place['summary'],
            'details': {'place_kind': place_kind, 'opened': place}}


def add(connection, data: dict, change: dict, now: str) -> dict:
    """Store a change the user made to a city. `change` holds kind, starts_on, and ends_on for temporary ones."""
    require(change['kind'] in MAKERS, 'Choose an opening, closing, renovation or road works.', 422)
    ends = change.get('ends_on')
    require(change['kind'] in SPANS or not ends, 'Openings and closings are lasting; leave out the end date.', 422)
    require(not ends or ends > change['starts_on'], 'The end date must come after the start date.', 422)
    fields, change_id = _fields(data, change), identifier()
    connection.execute(
        'INSERT INTO world_changes (id, city_id, kind, origin, place_id, neighborhood_id, name, summary, details, '
        "announced_on, starts_on, ends_on, created_at) VALUES (?, ?, ?, 'user', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (change_id, data['id'], change['kind'], fields['place_id'], fields['neighborhood_id'], fields['name'],
         fields['summary'], encode(fields['details']), min(change['starts_on'], now[:10]), change['starts_on'],
         ends, now))
    return row_view(optional(connection, 'SELECT * FROM world_changes WHERE id=?', (change_id,)))


def remove(connection, data: dict, change_id: str, now: str) -> dict:
    """Delete a stored change, or dismiss a seeded one so it never happens."""
    if connection.execute('DELETE FROM world_changes WHERE id=? AND city_id=?', (change_id, data['id'])).rowcount:
        return {'deleted': change_id}
    if change_id.startswith(f'seed-{data["id"]}-'):
        connection.execute('INSERT OR IGNORE INTO world_change_dismissals (change_id, city_id, dismissed_at) '
                           'VALUES (?, ?, ?)', (change_id, data['id'], now))
        return {'dismissed': change_id}
    raise DomainError(f'{data["name"]} has no change {change_id!r}.', 404, 'unknown_change')


# --- Chat context ---

def newsworthy(change: dict, day: date) -> bool:
    """Coming soon, under way, or recent enough that a local would still bring it up."""
    today = day.isoformat()
    if change['starts'] > today or active(change, day) and change['ends']:
        return True
    if change['ends'] is None:
        return change['starts'] >= (day - timedelta(days=RECENT)).isoformat()
    return change['kind'] != 'news' and change['ends'] >= (day - timedelta(days=REOPENED)).isoformat()


def change_text(change: dict, data: dict, day: date) -> str:
    hoods = {hood['id']: hood['name'] for hood in data['neighborhoods']}
    where, name, summary = hoods.get(change['neighborhood'], ''), change['name'], change['summary']
    soon, ended = change['starts'] > day.isoformat(), bool(change['ends']) and change['ends'] <= day.isoformat()
    starts, ends = day_text(change['starts']), day_text(change['ends']) if change['ends'] else ''
    kind = change['kind']
    if kind == 'news':
        return (f"- Heard about (a real listing from {change.get('service') or 'a lookup'}, {starts}): «{name}». "
                'You have not been unless your recent life says so')
    if kind == 'opening':
        label = LABELS.get(change.get('place_kind', ''), change.get('place_kind', 'place'))
        return f'- {name}, a new {label} in {where}, ' + (f'opens {starts}' if soon else f'opened {starts}')
    if kind == 'roadworks' and ended:
        return f'- {where}: {summary} finished {ends}'
    if kind == 'roadworks':
        return f'- {where}: {summary} ' + (f'from {starts} to {ends}' if soon else f'until {ends}') + \
            '; trips by road through there take longer'
    if kind == 'closing':
        return f'- {name} ({where}) ' + (f'closes {starts}: {summary}' if soon else f'{summary} on {starts}')
    if ended:
        return f'- {name} ({where}) reopened {ends} after being {summary}'
    return f'- {name} ({where}) ' + (f'will be {summary} {starts} to {ends}' if soon else f'{summary} until {ends}')


def context_lines(connection, version: dict, now: datetime) -> list[tuple[str, str]]:
    """What a local would know about changes in the companion's city today, newest first, at most LIMIT."""
    from dungeon.world import custom
    definition = version['definition']
    data = None
    extra = custom.all_cities(connection)
    for text in (definition.get('home_city'), definition.get('location')):
        if text and (data := resolve(text, extra)):
            break
    if not data:
        return []
    day = now.astimezone(zone(version['timezone'])).date()
    found = [change for change in known(data, day, stored(connection, data['id'])) if newsworthy(change, day)]
    found.sort(key=lambda change: change['starts'], reverse=True)
    return [(change['id'], change_text(change, data, day)) for change in found[:LIMIT]]
