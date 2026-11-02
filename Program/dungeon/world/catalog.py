"""Loading and querying the shipped city data. Everything here is read-only and needs no network."""
import hashlib
import json
import logging
import math
import os
import re
from functools import cache
from pathlib import Path

from pydantic import ValidationError

from dungeon import world_data
from dungeon.errors import DomainError
from dungeon.identity import VERSION, data_dir
from dungeon.world import decades
from dungeon.world import mend as mending
from dungeon.world.schema import Career, Careers, City, Featured, Holidays, Names

DATA = Path(__file__).parent / 'data'
LOG = logging.getLogger(__name__)
BUILTIN_CITIES = DATA / 'cities'
FEATURED = DATA / 'featured.json'


@cache
def careers() -> dict[str, dict]:
    """The shared career catalogue, across every era."""
    catalogue = Careers.model_validate_json((DATA / 'careers.json').read_text(encoding='utf-8'))
    return {career.id: career.model_dump() for career in catalogue.careers}


def careers_for(data: dict, *, needs_met: bool = True) -> dict[str, dict]:
    """Careers a city offers: the shared ones for its era, then its own (which win on a shared id).
    A shared career that `needs` a kind of place (a beach) is left out where the city has none and
    no employer for it, unless `needs_met` is False. In a modern city, a career with `years` is only offered in
    those years."""
    if not needs_met:
        return of_the_year({key: value for key, value in careers().items() if data['era'] in value['eras']} |
                           {career['id']: career for career in data['careers']}, data)
    kinds = {place['kind'] for place in data.get('places', [])}
    hired = {career for employer in data.get('employers', []) for career in employer['careers']}
    shared = {key: value for key, value in careers().items() if data['era'] in value['eras']
              and (not value['needs'] or kinds & set(value['needs']) or key in hired)}
    return of_the_year(shared | {career['id']: career for career in data['careers']}, data)


def of_the_year(offered: dict[str, dict], data: dict) -> dict[str, dict]:
    """The careers that exist in a modern city's year (dungeon/world/decades.py): one that came later, or had ended,
    is left out."""
    year = decades.offered_year(data)
    return offered if year is None else {key: value for key, value in offered.items()
                                         if decades.in_years(value, year)}


def everyday(offered: dict[str, dict]) -> dict[str, dict]:
    """The careers without the adult ones, for anything the app rolls by itself (a townsperson's job, a job change)."""
    return {key: career for key, career in offered.items() if not career.get('adult')}


@cache
def names() -> dict:
    """The shared name banks and each era's default bank and group weights."""
    return Names.model_validate_json((DATA / 'names.json').read_text(encoding='utf-8')).model_dump()


def name_groups(data: dict) -> tuple[dict[str, dict], dict[str, float]]:
    """The name groups a city draws residents' names from, and the weight of each.

    A city's own `names.mix` wins; a city with its own groups and no mix uses only those; otherwise the era's
    weights apply when the city keeps its era's bank, else every group of the bank weighs the same.

    A kind the city's `kinds` block lists (`{"dwarf": {"share": 0.1}}`) that none of its groups is tied to takes its
    names from the `peoples` bank's group for it (scripts/world/peoples.py), outside the mix: the share decides how
    many there are (dungeon/world/lifespans.py `shares`).
    """
    own = data.get('names') or {}
    era = names()['eras'][data['era']]
    bank = own.get('bank') or era['bank']
    base = names()['banks'][bank] | own.get('groups', {})
    groups = base
    listed = data.get('kinds')
    if isinstance(listed, dict) and listed:
        tied = {group.get('kind') for group in base.values()}
        peoples = names()['banks'].get('peoples', {})
        groups = {key: peoples[key] for key in listed if key in peoples and key not in tied} | base
    if own.get('mix'):
        mix = own['mix']
    elif own.get('groups'):
        mix = dict.fromkeys(own['groups'], 1.0)
    elif bank == era['bank'] and era['mix']:
        mix = era['mix']
    else:
        mix = {}
    # Weights for groups the bank lacks (say, after a city changes era) are ignored.
    mix = {key: weight for key, weight in mix.items() if weight > 0 and key in groups}
    return groups, mix or dict.fromkeys(base, 1.0)


@cache
def holiday_calendars() -> dict[str, dict]:
    """The shared holiday calendars by id."""
    return Holidays.model_validate_json((DATA / 'holidays.json').read_text(encoding='utf-8')).model_dump()['calendars']


ERA_CALENDARS = {'victorian': 'uk-victorian', 'steampunk': 'uk-victorian', 'medieval': 'medieval-england',
                 'frontier': 'us-1880s'}
US_NAMES = {'us', 'usa', 'u.s.', 'u.s.a.', 'united states', 'united states of america'}
UK_NAMES = {'uk', 'u.k.', 'united kingdom', 'great britain', 'britain', 'england', 'wales'}
KOREA_NAMES = {'south korea', 'korea', 'republic of korea'}
# Today's calendar by country, and an era's by country where it differs from place to place.
MODERN_CALENDARS = {**dict.fromkeys(US_NAMES, 'us'), **dict.fromkeys(UK_NAMES, 'uk'),
                    **dict.fromkeys(KOREA_NAMES, 'south-korea'), 'japan': 'japan'}
COUNTRY_CALENDARS = {'jazz-age': dict.fromkeys(US_NAMES, 'us-1920s')}


def calendar_id(data: dict) -> str | None:
    """The shared calendar a city keeps: its own choice, else one fitting its era and country."""
    chosen = data.get('calendar')
    if chosen:
        return None if chosen == 'none' else chosen
    country = data['country'].strip().lower()
    if data['era'] in ('modern', 'future', 'other'):
        return MODERN_CALENDARS.get(country)
    if data['era'] in COUNTRY_CALENDARS:
        return COUNTRY_CALENDARS[data['era']].get(country)
    return ERA_CALENDARS.get(data['era'])


OMIT_WHEN_EMPTY = {'townsfolk', 'kinds', 'politics'}


def unset_work_rules(data: dict):
    """Who worked a job in its era and at what ages (schema Career.worked_by and ages, City.work_by_gender) are
    newer than most cities: left out when unset, so their data_version stays the same."""
    if data.get('work_by_gender') is None:
        data.pop('work_by_gender', None)
    for career in data['careers']:
        for key in ('worked_by', 'ages'):
            if career.get(key) is None:
                career.pop(key, None)


def prepare(raw: bytes | str | dict, *, mend: bool = False) -> dict:
    """Validate one city definition and give it a `data_version`. Raises pydantic's ValidationError.

    With `mend` (user cities and packs), small mistakes are mended first (dungeon/world/mend.py), careers an
    employer names that the app lacks are added as the city's own, and `import_notes` says what changed."""
    notes = []
    if mend:
        raw, notes = mending.mend(raw if isinstance(raw, dict) else json.loads(raw))
    model = City.model_validate(raw) if isinstance(raw, dict) else City.model_validate_json(raw)
    # The townsfolk block is optional and newer than most cities: left out when absent, so their data_version
    # stays the same.
    data = model.model_dump(mode='json', exclude=OMIT_WHEN_EMPTY - model.model_fields_set)
    unset_work_rules(data)
    from dungeon.world import lifespans, politics
    notes += lifespans.clean(data)
    notes += politics.clean(data)
    known = careers_for(data)
    for employer in data['employers']:
        unknown = set(employer['careers']) - set(known)
        if unknown and mend:
            for career_id in sorted(unknown):
                data['careers'].append(new_career(career_id, employer))
                notes.append(f'Added the job "{data["careers"][-1]["name"]}", which {employer["name"]} hires for.')
            known = careers_for(data)
        elif unknown:
            raise ValueError(f'{employer["id"]} names careers this city does not offer: {sorted(unknown)}.')
    own = data.get('names') or {}
    if own.get('bank') and own['bank'] not in names()['banks']:
        if not mend:
            raise ValueError(f'Unknown name bank {own["bank"]!r}; the banks are {sorted(names()["banks"])}.')
        notes.append(f'There is no name bank "{own["bank"]}", so names come from the era\'s usual one.')
        own['bank'] = None
    if data.get('calendar') not in (None, 'none', *holiday_calendars()):
        if not mend:
            raise ValueError(f'Unknown calendar {data["calendar"]!r}; the calendars are {sorted(holiday_calendars())}.')
        notes.append(f'There is no holiday calendar "{data["calendar"]}", so the usual one for the era is used.')
        data['calendar'] = None
    # Identifies the exact data a generator used, so a recorded event can name its inputs (PRD T7).
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    data['data_version'] = hashlib.sha256(canonical.encode()).hexdigest()[:12]
    return data | ({'import_notes': notes} if notes else {})


def new_career(career_id: str, employer: dict) -> dict:
    """A career a city's employer names that the app lacks, made from its id so the employer can hire for it."""
    name = career_id.replace('-', ' ').capitalize()
    return Career(id=career_id, name=name, sector=employer['sector'], schedule='office', pay='$$',
                  summary=f'{name} work, as at {employer["name"]}.'[:400], themes=['work', employer['sector']]
                  ).model_dump(mode='json')


PACKS_ENV = 'DUNGEON_CITY_PACKS'
# Personal city packs (PRD W5), such as private fan cities. The checkout's folder is gitignored.
CHECKOUT_PACKS = Path(__file__).resolve().parents[2] / 'private-cities'


def pack_dirs() -> list[Path]:
    """Folders searched for city packs: `DUNGEON_CITY_PACKS` (os.pathsep-separated) or the defaults."""
    if os.environ.get(PACKS_ENV):
        return [Path(item) for item in os.environ[PACKS_ENV].split(os.pathsep) if item]
    return [CHECKOUT_PACKS, data_dir() / 'city-packs']


def city_files(folder: Path) -> list[Path]:
    """The city files in a folder, without hidden files: macOS writes a `._<name>.json` beside each file it copies
    to a drive formatted for Windows (exFAT, FAT32), and those hold Finder data, not a city."""
    return sorted(path for path in folder.glob('*.json') if not path.name.startswith('.')) if folder.is_dir() else []


def _add_pack(path: Path, result: dict, errors: list) -> None:
    """Load one city file leniently, as a pack, or say why it did not load."""
    try:
        data = prepare(path.read_bytes(), mend=True)
    except Exception as error:  # reported, never raised
        if not isinstance(error, (ValidationError, ValueError, OSError)):
            LOG.exception('Skipped the city file %s', path)
        errors.append({'file': str(path), 'error': str(error)[:2000]})
        return
    if data['id'] in result:
        errors.append({'file': str(path), 'error': f'City id {data["id"]!r} is already loaded.'})
        return
    result[data['id']] = data | {'builtin': False, 'origin': 'pack', 'pack_file': str(path)}


def _add_held(key: str, result: dict, errors: list) -> None:
    """Load one town an imported world package holds (one made in Worldsmith, say), leniently, as a pack is."""
    try:
        data = prepare(world_data.read('cities', key), mend=True)
    except Exception as error:  # reported, never raised
        if not isinstance(error, (ValidationError, ValueError, TypeError)):
            LOG.exception('Skipped the packaged city %s', key)
        errors.append({'file': f'world package city {key}', 'error': str(error)[:2000]})
        return
    if data['id'] != key or data['id'] in result:
        errors.append({'file': f'world package city {key}', 'error': f'City id {data["id"]!r} is already loaded.'})
        return
    result[key] = data | {'builtin': False, 'origin': 'package'}


@cache
def _library() -> tuple[dict[str, dict], tuple[dict, ...]]:
    """Every city that loads, and what went wrong with each file that did not. One bad file must never take every
    city list, and everything built on them (the life sim), down with it.

    The shipped cities load strictly. A file that is not one of them, such as a city a tester dropped among the
    built-in ones, loads like a pack, mended, and anything that still fails is reported (Settings > Cities >
    Pack folders). Then the towns of imported world packages that no shipped file has (docs/packages.md "In play").
    Asking for a city that is not there reads them all again (`city`), so a world installed while the app runs is
    found without a restart."""
    result, errors, strays = {}, [], []
    for path in city_files(BUILTIN_CITIES):
        try:
            data = prepare(path.read_bytes())
        except (ValidationError, ValueError, OSError):
            strays.append(path)
            continue
        if data['id'] != path.stem:
            strays.append(path)
            continue
        result[data['id']] = data | {'builtin': True, 'origin': 'builtin'}
    for path in strays:
        LOG.warning('%s is not a valid built-in city, so it loads like a city pack', path)
        _add_pack(path, result, errors)
    for key in world_data.keys('cities'):
        if key not in result:
            _add_held(key, result, errors)
    for folder in pack_dirs():
        for path in city_files(folder):
            _add_pack(path, result, errors)
    return result, tuple(errors)


def cities() -> dict[str, dict]:
    """Built-in cities shipped with the app, then any city packs found in the pack folders. Read-only."""
    return _library()[0]


def packs() -> dict:
    """What the pack folders hold, for the interface and for troubleshooting a pack that did not load."""
    loaded = [summary(data) | {'file': data['pack_file']} for data in cities().values() if data['origin'] == 'pack']
    return {'folders': [str(folder) for folder in pack_dirs()], 'loaded': loaded, 'errors': list(_library()[1])}


def reload() -> dict:
    _library.cache_clear()
    return packs()


def city(city_id: str, extra: dict[str, dict] | None = None) -> dict:
    """A built-in city, or one of `extra` (the user's own cities)."""
    found = cities().get(city_id) or (extra or {}).get(city_id)
    if not found and world_data.paths():
        # A world package installed or imported since the list was read (one made in Worldsmith).
        _library.cache_clear()
        found = cities().get(city_id)
    if not found:
        raise DomainError(f'No world data for city {city_id!r}.', 404, 'unknown_city')
    return found


CATEGORIES = ('real', 'other-eras', 'fictional')
PAST_ERAS = {'victorian', 'frontier', 'jazz-age', 'medieval', 'other'}


def category(data: dict) -> str:
    """The city's shelf in city lists: 'custom' for the user's own, else its named category, else one worked out from
    its setting and era. A real or realistic past (an original frontier town) is another era; legends are fiction."""
    if data.get('origin', 'user') == 'user':
        return 'custom'
    if data.get('category') in CATEGORIES:
        return data['category']
    setting, era = data.get('setting', 'real'), data.get('era', 'modern')
    if era == 'modern':
        return 'real' if setting == 'real' else 'fictional'
    return 'other-eras' if era in PAST_ERAS and setting != 'fictional' else 'fictional'


def summary(data: dict) -> dict:
    keys = ('id', 'name', 'setting', 'era', 'basis', 'region', 'country', 'timezone', 'aliases', 'summary',
            'data_version')
    return {key: data[key] for key in keys} | {
        'counts': {key: len(data[key]) for key in ('neighborhoods', 'places', 'colleges', 'employers',
                                                   'annual_events')}, 'builtin': data.get('builtin', False),
        'origin': data.get('origin', 'user'), 'category': category(data), 'distribution': data['distribution'],
        'home': data.get('home', True),
        'import_notes': data.get('import_notes', [])}


def neighborhood(data: dict, hood_id: str) -> dict:
    for hood in data['neighborhoods']:
        if hood['id'] == hood_id:
            return hood
    raise DomainError(f'No neighborhood {hood_id!r} in {data["name"]}.', 404, 'unknown_neighborhood')


def find(data: dict, record_id: str) -> dict | None:
    for group in ('neighborhoods', 'places', 'colleges', 'employers', 'career_hubs', 'transit', 'annual_events'):
        for item in data[group]:
            if item['id'] == record_id:
                return item
    return None


def places(data: dict, *, kind: str | None = None, neighborhood: str | None = None, tag: str | None = None,
           good_for: str | None = None) -> list[dict]:
    return [item for item in data['places']
            if (kind is None or item['kind'] == kind) and (neighborhood is None or item['neighborhood'] == neighborhood)
            and (tag is None or tag in item['tags']) and (good_for is None or good_for in item['good_for'])]


def distance_km(a: dict, b: dict) -> float:
    """Great-circle distance between two records with `lat` and `lon`."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a['lat'], a['lon'], b['lat'], b['lon']))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def nearby(data: dict, hood_id: str, limit: int = 4) -> list[dict]:
    """The closest other neighborhoods, nearest first."""
    origin = neighborhood(data, hood_id)
    others = [hood for hood in data['neighborhoods'] if hood['id'] != hood_id]
    return sorted(others, key=lambda hood: (distance_km(origin, hood), hood['id']))[:limit]


def _words(text: str) -> str:
    return ' '.join(re.findall(r'[a-z0-9]+', text.lower()))


def resolve(text: str, extra: dict[str, dict] | None = None) -> dict | None:
    """Match free text such as a character's `location` ("Fells Point, Baltimore") to a city and neighborhood.

    Returns `{"city": id, "neighborhood": id | None}` or `None` when no shipped city matches.
    """
    words = f' {_words(text)} '
    if not words.strip():
        return None
    for data in [*cities().values(), *(extra or {}).values()]:
        names = [data['name'], data['id'].replace('-', ' '), *data['aliases']]
        if any(f' {_words(name)} ' in words for name in names if _words(name)):
            hood = next((item['id'] for item in data['neighborhoods'] if f' {_words(item["name"])} ' in words), None)
            return {'city': data['id'], 'neighborhood': hood}
    return None


def sources(data: dict) -> list[dict]:
    """Every source the city's records cite, for attribution screens."""
    return [{'id': key} | value for key, value in data['sources'].items()]


@cache
def _featured() -> dict:
    return Featured.model_validate_json(FEATURED.read_text(encoding='utf-8')).model_dump()


def featured(extra: dict[str, dict] | None = None) -> dict:
    """The release's featured cities that load, in its order. While the app is on that release `new` is true,
    and so is each city's own `new` when it first shipped in it."""
    data = _featured()
    known = cities() | (extra or {})
    current = '.'.join(VERSION.split('.')[:2]) == data['release']
    return {'release': data['release'], 'title': data['title'], 'note': data['note'], 'new': current,
            'cities': [summary(known[city_id]) | {'new': current and city_id in data['new_cities']}
                       for city_id in data['cities'] if city_id in known]}
