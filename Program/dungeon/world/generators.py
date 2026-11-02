"""Deterministic generators that assemble everyday life from the shipped city data.

The same city data, seed and arguments always give the same result, on any machine and Python
version: choices come from SHA-256 of the seed, never from `random`. Callers pass a seed that is
stable for the moment being simulated (a slot key, for example), so a resumed or repeated batch
picks the same outing. Results are plain dictionaries with `refs`, the ids of every record used,
and `sources`, so an event can record exactly which facts it was built from. The model only
phrases these facts; it never has to invent a place, employer, rent or commute.
"""
import copy
import functools
import hashlib
from datetime import date, timedelta

from dungeon.errors import DomainError
from dungeon.world import catalog, lifespans, naming
from dungeon.world import mix as town_mix
from dungeon.world.schema import HEARSAY_KINDS

COSTS = ['free', '$', '$$', '$$$', '$$$$']
SEASONS = {12: 'winter', 1: 'winter', 2: 'winter', 3: 'spring', 4: 'spring', 5: 'spring', 6: 'summer',
           7: 'summer', 8: 'summer', 9: 'fall', 10: 'fall', 11: 'fall'}
MEALS = {'breakfast': 'morning', 'brunch': 'morning', 'lunch': 'afternoon', 'dinner': 'evening', 'late': 'late'}
FOOD = ('restaurant', 'cafe', 'market', 'tavern', 'inn')
BEDROOMS = ('studio', 'one_bedroom', 'two_bedroom')
# Where a career with no named employer in the data can plausibly work.
WORKPLACE_KINDS = {
    'barista': ('cafe',), 'baker': ('cafe', 'market'), 'line-cook': ('restaurant',), 'server': ('restaurant',),
    'bartender': ('bar', 'nightlife', 'tavern', 'inn'), 'retail-associate': ('shopping',), 'tour-guide': ('attraction', 'landmark'),
    'performer': ('venue',), 'musician': ('venue', 'bar'), 'fitness-trainer': ('fitness',),
    'lifeguard': ('beach',), 'surf-instructor': ('beach',),
    'exotic-dancer': ('nightlife', 'bar'), 'burlesque-performer': ('venue', 'nightlife', 'bar'),
    'adult-store-clerk': ('shopping',),
    # The 1920s (jazz-age careers).
    'speakeasy-bartender': ('bar', 'nightlife'), 'jazz-musician': ('nightlife', 'venue', 'bar'),
    'chorus-dancer': ('venue', 'nightlife'), 'hatcheck-attendant': ('nightlife', 'restaurant'),
    'soda-jerk': ('cafe',), 'department-store-clerk': ('shopping',), 'grocer': ('market', 'shopping'),
    'druggist': ('shopping',), 'antiquarian-bookseller': ('shopping',), 'librarian': ('library',),
    'museum-curator': ('museum',), 'minister': ('temple',), 'burlesque-dancer': ('venue', 'nightlife'),
}
# Where any career in a sector can plausibly work, for cities that name no employer for it.
SECTOR_KINDS = {
    'food': ('cafe', 'market', 'restaurant'), 'hospitality': ('restaurant', 'bar', 'tavern', 'inn', 'cafe'),
    'entertainment': ('venue',), 'tourism': ('attraction', 'landmark'), 'retail': ('shopping', 'market'),
    'religion': ('temple',), 'trade': ('market', 'guildhall', 'workshop'), 'crafts': ('workshop',),
    'fitness': ('fitness',), 'recreation': ('beach', 'park'), 'logistics': ('docks',),
}
# Places people go to on an errand, never for an outing (a vet clinic); asked for only by kind.
ERRAND_KINDS = {'vet'}
RAIL = {'subway', 'light-rail', 'commuter-rail', 'streetcar', 'monorail', 'tram'}
# Shared lines other than rail, and private ways to travel, fastest first.
LINES = {'bus', 'ferry', 'water-taxi', 'boat', 'airship', 'stagecoach'}
PRIVATE = ('car', 'carriage', 'horse', 'bike-share')
DEFAULT_SPEEDS = {'walk': 4.5, 'car': 25, 'rideshare': 25, 'bus': 13, 'carriage': 10, 'horse': 12, 'tram': 15}
# Modes held up by road works (dungeon/world/changes.py marks a neighborhood's `works`).
ROAD = {'car', 'rideshare', 'bus', 'bike-share', 'carriage', 'horse', 'stagecoach', 'streetcar', 'tram'}
OVERHEAD = {'walk': 0, 'car': 6, 'rideshare': 8, 'bus': 9, 'ferry': 10, 'water-taxi': 10, 'bike-share': 3}


def detached(function):
    """Return a deep copy, so a caller that edits a result can't change the cached city data."""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        return copy.deepcopy(function(*args, **kwargs))
    return wrapper


def unit(seed: str, *parts) -> float:
    """A stable number in [0, 1) for this seed and label."""
    digest = hashlib.sha256('\x1f'.join(map(str, (seed, *parts))).encode()).digest()
    return int.from_bytes(digest[:8], 'big') / 2 ** 64


def pick(seed: str, label: str, items: list, weights: list[float] | None = None):
    """Weighted choice that depends only on the seed, the label and the order of `items`."""
    if not items:
        return None
    weights = weights or [1.0] * len(items)
    total = sum(weights)
    target, running = unit(seed, label) * total, 0.0
    for item, weight in zip(items, weights, strict=True):
        running += weight
        if target < running:
            return item
    return items[-1]


def provenance(data: dict, refs: list[str]) -> dict:
    records = [catalog.find(data, ref) for ref in refs]
    cited = sorted({record['source'] for record in records if record})
    return {'city': data['id'], 'data_version': data['data_version'], 'refs': refs, 'sources': cited}


def rank_pick(seed: str, label: str, weights: dict):
    """Weighted choice that is stable per item: each item draws its own number, so adding or dropping one
    item (or changing its weight) moves only the people who had it or now get it, never everyone else."""
    if not weights:
        return None
    return max(sorted(weights), key=lambda item: unit(seed, label, item) ** (1 / weights[item]))


# How much more often people in a city work a career the city itself is built around. Every career the era
# offers counts 1; a career of the city's own counts CITY_CAREER more; each employer hiring it adds by its size;
# each career hub of its sector adds HUB_SECTOR; each place it works at (a cafe for a soda jerk) adds PLACE_JOB,
# up to PLACE_CAP places. So a fishing town is mostly fishermen and cannery hands, while a big city with dozens
# of employers stays varied.
CITY_CAREER = 3.0
EMPLOYER_SIZES = {'small': 4.0, 'medium': 10.0, 'large': 20.0}
HUB_SECTOR = 0.5
PLACE_JOB = 0.25
PLACE_CAP = 4


def career_weights(data: dict, offered: dict[str, dict]) -> dict[str, float]:
    """How often residents work each offered career in this city: its own industries count far more."""
    return dict(_career_weights(
        tuple((key, career['sector']) for key, career in offered.items()),
        tuple(career['id'] for career in data.get('careers', [])),
        tuple((tuple(employer['careers']), employer.get('size')) for employer in data.get('employers', [])),
        tuple(sector for hub in data.get('career_hubs', []) for sector in hub.get('sectors', [])),
        tuple(place['kind'] for place in data.get('places', []))))


@functools.lru_cache(maxsize=64)
def _career_weights(offered: tuple, own: tuple, employers: tuple, sectors: tuple, kinds: tuple) -> tuple:
    # Read for every townsperson the city draws, so a city's weights are worked out once.
    weights = dict.fromkeys((key for key, _ in offered), 1.0)
    for career in own:
        if career in weights:
            weights[career] += CITY_CAREER
    for careers, size in employers:
        hires = set(careers) & set(weights)
        for career in hires:
            weights[career] += EMPLOYER_SIZES.get(size, EMPLOYER_SIZES['small']) / len(hires)
    for key, sector in offered:
        workplaces = sum(kinds.count(kind) for kind in WORKPLACE_KINDS.get(key, ()))
        weights[key] += HUB_SECTOR * sectors.count(sector) + PLACE_JOB * min(workplaces, PLACE_CAP)
    return tuple(weights.items())


# Eras whose work custom kept to men or to women (a careers' `worked_by`), unless the city says otherwise.
GENDERED_ERAS = {'victorian', 'medieval', 'steampunk', 'frontier'}
SIDES = {'she': 'women', 'he': 'men'}


def by_gender(data: dict) -> bool:
    """Whether this city's townsfolk work the jobs their era kept to their side (City.work_by_gender)."""
    rule = data.get('work_by_gender')
    return data.get('era', 'modern') in GENDERED_ERAS if rule is None else bool(rule)


def fits_side(data: dict, pronouns: str | None):
    """`fits(career)` for someone with these pronouns: in a city that keeps work by gender, a woman is never a
    cabman nor a man a governess; anyone else (they/them, or a city that doesn't) fits every career."""
    side = SIDES.get((pronouns or '').split('/')[0])
    if not side or not by_gender(data):
        return None
    return lambda career: career.get('worked_by') in (None, side)


def own_side(data: dict, pronouns: str | None, offered: dict[str, dict]) -> dict[str, dict]:
    """The offered careers (by id) someone with these pronouns works in this city's era (fits_side); all of them when
    the era leaves work open or none would fit."""
    if not (side := fits_side(data, pronouns)):
        return offered
    return {key: career for key, career in offered.items() if side(career)} or offered


def town_career(data: dict, seed: str, label: str = 'career', fits=None, pronouns: str | None = None,
                age: int | None = None) -> dict | None:
    """A career for someone living in this city, weighted towards the city's own industries (career_weights).
    `fits(career_id)` keeps only careers that suit them; `pronouns` keeps to the work their era gave their side
    (fits_side), and `age` (in human terms) to the work done at that age (fits_age: never a 55-year-old squire)."""
    offered = own_side(data, pronouns, catalog.everyday(catalog.careers_for(data)))
    weights = {key: weight for key, weight in career_weights(data, offered).items()
               if (not fits or fits(key)) and (age is None or fits_age(offered[key], age))}
    chosen = rank_pick(seed, label, weights)
    return offered[chosen] if chosen else None


# --- Climate and the calendar ---

def conditions(data: dict, day: date, seed: str = '') -> dict | None:
    """Typical weather for the date from monthly climate, with a seeded chance of rain; None without a climate."""
    if not data['climate']:
        return None
    month = data['climate']['months'][day.month - 1]
    wet = unit(seed or day.isoformat(), data['id'], 'rain') < month['rain_days'] / 30
    return {'season': SEASONS[day.month], 'month': day.month, 'high_f': month['high_f'], 'low_f': month['low_f'],
            'rain': wet, 'note': month['note'], 'typical': True}


@detached
def annual_events(data: dict, day: date) -> list[dict]:
    """Recurring events usually held in this month. Exact dates vary year to year."""
    return [event for event in data['annual_events'] if day.month in event['months']]


def easter(year: int) -> date:
    """Western (Gregorian) Easter Sunday, by the anonymous Gregorian computus."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def holiday_date(holiday: dict, year: int) -> date | None:
    """The date a holiday falls on in this year, or None when its rule names no such day (31 June, a 5th Monday, a
    year its table of dates lacks)."""
    if holiday.get('dates'):
        found = holiday['dates'].get(str(year))
        return date.fromisoformat(f'{year}-{found}') if found else None
    if holiday['easter'] is not None:
        return easter(year) + timedelta(days=holiday['easter'])
    month = holiday['month']
    if holiday['day'] is not None:
        try:
            return date(year, month, holiday['day'])
        except ValueError:
            return None
    following = date(year + month // 12, month % 12 + 1, 1)
    if holiday['nth'] > 0:
        first = date(year, month, 1)
        found = first + timedelta(days=(holiday['weekday'] - first.weekday()) % 7 + 7 * (holiday['nth'] - 1))
        return found if found < following else None
    last = following - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - holiday['weekday']) % 7)


def city_holidays(data: dict) -> list[dict]:
    """The city's shared calendar's holidays, then its own (which win on a shared id)."""
    shared = catalog.holiday_calendars().get(catalog.calendar_id(data) or '', {}).get('holidays', [])
    return list(({item['id']: item for item in shared} | {item['id']: item for item in data['holidays']}).values())


def holidays(data: dict, start: date, end: date | None = None) -> list[dict]:
    """Holidays from `start` to `end` inclusive (just `start` when no end is given), in date order.

    Each item is the holiday record plus its `date`. `public` holidays close most offices and schools.
    """
    end = end or start
    if end < start or (end - start).days > 400:
        raise DomainError('A holiday range runs forward and spans at most 400 days.', 422)
    found = []
    for item in city_holidays(data):
        for year in range(start.year, end.year + 1):
            day = holiday_date(item, year)
            if day and start <= day <= end:
                found.append(item | {'date': day.isoformat()})
    return sorted(found, key=lambda item: (item['date'], item['id']))


# --- Getting around ---

def commute(data: dict, origin: str, destination: str, mode: str | None = None) -> dict:
    """An estimated trip between two neighborhoods, by the given mode or the likeliest one.

    The likeliest is walking when it is close, else a line both ends share (rail first), else two lines that meet
    at a neighborhood both serve with one change between them (`change`), else a private way to travel."""
    start, end = catalog.neighborhood(data, origin), catalog.neighborhood(data, destination)
    km = round(catalog.distance_km(start, end) * 1.3 + 0.4, 1)
    shared = [line for line in data['transit'] if line['id'] in start['transit'] and line['id'] in end['transit']]
    change = None
    if mode is None:
        mode, line, change = _likeliest(data, start, end, km, shared)
    else:
        line = next((item for item in shared if item['kind'] == mode), None) if mode in RAIL or mode in LINES else None
    speed = data['speeds'].get(mode) or DEFAULT_SPEEDS.get(mode, 4.5)
    works = _works(start, end, mode)
    minutes = round(km / speed * 60 + OVERHEAD.get(mode, 8)) + sum(item['delay'] for item in works)
    trip = {'from': origin, 'to': destination, 'mode': mode, 'line': line['name'] if line else None,
            'distance_km': km, 'minutes': max(minutes, 3), 'estimate': True}
    if change:
        first, second, hub = change
        trip |= {'line': f"{first['name']}, then {second['name']}", 'change': {'at': hub['id'], 'name': hub['name'],
                 'lines': [first['name'], second['name']]}, 'minutes': trip['minutes'] + TRANSFER_WAIT}
    return trip | ({'works': [item['summary'] for item in works]} if works else {})


# Minutes added for changing lines on the way: the walk across the platform and the wait for the next train.
TRANSFER_WAIT = 7


def _likeliest(data: dict, start: dict, end: dict, km: float, shared: list[dict]) -> tuple:
    """(mode, line, change) for the likeliest way to make a trip; change is (first line, second line, where)."""
    rail = next((line for line in shared if line['kind'] in RAIL), None)
    bus = next((line for line in shared if line['kind'] in LINES), None)
    bus_ok = start['walkability'] != 'low' and km <= 8
    if km <= 1.6:
        return 'walk', None, None
    if rail:
        return rail['kind'], rail, None
    if bus and bus_ok:
        return bus['kind'], bus, None
    change = _change(data, start, end, bus_ok)
    if change:
        return change[0]['kind'], None, change
    return next((kind for kind in PRIVATE if kind in data['speeds']), 'walk'), None, None


def _change(data: dict, start: dict, end: dict, bus_ok: bool) -> tuple | None:
    """Two lines, one from each end, that meet at a neighborhood both serve: rail to rail first, then the shortest
    way round. Buses and boats count only where a direct bus would (bus_ok). Deterministic: ties keep data order."""
    lines = {line['id']: line for line in data['transit'] if line['kind'] in RAIL or (bus_ok and line['kind'] in LINES)}
    firsts = [lines[key] for key in start['transit'] if key in lines]
    seconds = [lines[key] for key in end['transit'] if key in lines]
    options = []
    for hub in data['neighborhoods']:
        for first in firsts:
            for second in seconds:
                if first['id'] != second['id'] and {first['id'], second['id']} <= set(hub['transit']):
                    railless = (first['kind'] not in RAIL) + (second['kind'] not in RAIL)
                    around = catalog.distance_km(start, hub) + catalog.distance_km(hub, end)
                    options.append((railless, round(around, 3), len(options), (first, second, hub)))
    return min(options)[3] if options else None


def _works(start: dict, end: dict, mode: str) -> list[dict]:
    """Road works at either end of a trip by road, once each."""
    if mode not in ROAD:
        return []
    found = {hood['works']['id']: hood['works'] for hood in (start, end) if hood.get('works')}
    return list(found.values())


# --- Outings and meals ---

def _affordable(place: dict, budget: str | None) -> bool:
    return budget is None or COSTS.index(place['cost']) <= COSTS.index(budget)


def _weight(data: dict, place: dict, around: dict | None, weather: dict | None) -> float:
    weight = 1.0
    if around:
        if place['neighborhood'] == around['id']:
            weight *= 6
        else:
            km = catalog.distance_km(around, catalog.neighborhood(data, place['neighborhood']))
            weight *= 3 if km <= 2.5 else 1.5 if km <= 6 else 0.6
    if weather:
        harsh = weather['rain'] or weather['high_f'] >= 93 or weather['high_f'] <= 38
        if harsh:
            weight *= {'indoor': 3, 'mixed': 1, 'outdoor': 0.15}[place['setting']]
    return weight


@detached
def outing(data: dict, *, seed: str, day: date | None = None, day_part: str = 'afternoon', company: str = 'solo',
           neighborhood: str | None = None, home: str | None = None, budget: str | None = None,
           kinds: list[str] | None = None, exclude: list[str] | tuple = ()) -> dict | None:
    """A plausible place to spend part of a day, near `neighborhood` when given.

    Constraints relax in order (day part, then company) rather than failing; `None` only when the
    city has no place of the requested kinds at all. Pass recently used place ids in `exclude` for
    variety.
    """
    around = catalog.neighborhood(data, neighborhood) if neighborhood else None
    weather = conditions(data, day, seed) if day else None
    pool = [place for place in data['places'] if place['id'] not in exclude and _affordable(place, budget)
            and (place['kind'] in kinds if kinds else place['kind'] not in ERRAND_KINDS)]
    season = weather['season'] if weather else None
    attempts = (
        lambda p: day_part in p['day_parts'] and company in p['good_for'],
        lambda p: company in p['good_for'],
        lambda p: True,
    )
    for test in attempts:
        options = [p for p in pool if test(p) and (not season or not p['seasons'] or season in p['seasons'])]
        if options:
            break
    else:
        return None
    chosen = pick(seed, 'outing', options, [_weight(data, p, around, weather) for p in options])
    refs = [chosen['id'], chosen['neighborhood']]
    result = {'place': chosen, 'neighborhood': catalog.neighborhood(data, chosen['neighborhood']),
              'day_part': day_part, 'company': company, 'weather': weather, 'travel': None}
    origin = home or neighborhood
    if origin:
        result['travel'] = commute(data, origin, chosen['neighborhood'])
        refs.append(origin)
    return result | provenance(data, refs)


@detached
def meal(data: dict, *, seed: str, meal: str = 'dinner', **options) -> dict | None:
    """Somewhere to eat: an outing limited to restaurants, cafes and markets (bars for a late bite)."""
    if meal not in MEALS:
        raise DomainError(f'Meal is one of {", ".join(MEALS)}.', 422)
    kinds = [*FOOD, 'bar'] if meal == 'late' else list(FOOD)
    result = outing(data, seed=seed, day_part=MEALS[meal], kinds=kinds, **options)
    return result | {'meal': meal} if result else None


# --- Work and routine ---

WEEKDAYS = [0, 1, 2, 3, 4]
# Each schedule kind lists variants of (possible work days, work start, work end, bedtime, waking time).
PATTERNS = {
    'office': [([WEEKDAYS], '08:30', '17:00', '23:00', '07:00'), ([WEEKDAYS], '09:00', '17:30', '23:00', '07:00'),
               ([WEEKDAYS], '09:30', '18:00', '23:30', '07:30')],
    'shift-day': [([[0, 2, 4], [1, 3, 5], [0, 1, 3], [2, 4, 6]], '07:00', '19:30', '21:30', '05:45')],
    'shift-night': [([[0, 1, 2], [3, 4, 5], [1, 3, 5]], '19:00', '07:30', '09:00', '16:00')],
    'rotating': [([[0, 1, 2, 3, 4], [2, 3, 4, 5, 6], [0, 3, 4, 5, 6]], '07:00', '15:30', '22:30', '06:00'),
                 ([[0, 1, 2, 3, 4], [2, 3, 4, 5, 6], [0, 3, 4, 5, 6]], '15:00', '23:30', '01:00', '09:00')],
    'evening': [([[1, 2, 3, 4, 5], [2, 3, 4, 5, 6]], '16:00', '23:30', '01:30', '09:30')],
    'early': [([WEEKDAYS, [1, 2, 3, 4, 5]], '05:30', '13:30', '21:30', '05:00')],
    'academic': [([WEEKDAYS], '08:00', '15:30', '22:30', '06:30')],
    'flexible': [([WEEKDAYS], '10:00', '16:00', '00:00', '08:00')],
}
STUDY = {'undergraduate', 'graduate-student'}


def schedule(career: dict, seed: str, workplace: str = '') -> list[dict]:
    """A weekly routine for this career, in the character `schedule` shape the life simulation reads."""
    day_options, start, end, bed, wake = pick(seed, 'variant', PATTERNS[career['schedule']])
    days = pick(seed, 'days', day_options)
    themes = career['themes'][:5] + ([workplace] if workplace else [])
    return week(career['name'], 'study' if career['id'] in STUDY else 'work', days, start, end, bed, wake, themes)


def week(label: str, kind: str, days, start: str, end: str, bed: str, wake: str, themes: list[str]) -> list[dict]:
    """Work (or study) on `days` from `start` to `end`, sleep every night, free time after work and days off."""
    blocks = [{'key': 'work', 'label': label, 'kind': kind,
               'days': list(days), 'start': start, 'end': end, 'themes': themes},
              {'key': 'sleep', 'label': 'Asleep', 'kind': 'sleep', 'days': list(range(7)), 'start': bed,
               'end': wake, 'themes': []}]
    free = _free_time(start, end, bed)
    if free:
        blocks.append({'key': 'after-work', 'label': 'Free time after work', 'kind': 'leisure', 'days': list(days),
                       'start': free[0], 'end': free[1], 'themes': []})
    off = [day for day in range(7) if day not in days]
    if off:
        rest = _minutes(wake) + 120
        blocks.append({'key': 'day-off', 'label': 'Day off', 'kind': 'leisure', 'days': off,
                       'start': _clock(rest), 'end': _clock(rest + 6 * 60), 'themes': []})
    return blocks


def _minutes(value: str) -> int:
    hours, minutes = value.split(':')
    return int(hours) * 60 + int(minutes)


def _clock(total: int) -> str:
    total %= 24 * 60
    return f'{total // 60:02d}:{total % 60:02d}'


def _free_time(start: str, end: str, bed: str) -> tuple[str, str] | None:
    """The waking stretch between the end of a daytime shift and bedtime, when it is at least two hours."""
    if _minutes(end) < _minutes(start):
        return None
    begin, sleep = _minutes(end) + 60, _minutes(bed)
    if sleep <= _minutes(end):
        sleep += 24 * 60
    if sleep - begin < 120:
        return None
    return _clock(begin), _clock(min(sleep, begin + 4 * 60))


@detached
def job(data: dict, career_id: str, *, seed: str, home: str | None = None, employer: str | None = None,
        avoid: list[str] | tuple = ()) -> dict:
    """An employer, workplace neighborhood, weekly schedule and commute for a career in this city.

    Named employers come from the data. Careers the data has no employer for work at a fitting place
    (a cafe for a barista) or at an unnamed employer in a matching career hub, so nothing is invented.
    `employer` names a record (employer, college or place) to work at, such as a coworker's. Workplaces in
    `avoid` (ids already taken by others in a circle, say) are much less likely to be chosen.
    """
    career = catalog.careers_for(data).get(career_id)
    if not career:
        raise DomainError(f'{data["name"]} has no career {career_id!r}.', 404, 'unknown_career')
    chosen, hood, refs = _workplace(data, career, seed, employer, avoid)
    refs = [*refs, hood]
    result = {'career': career, 'employer': chosen, 'neighborhood': catalog.neighborhood(data, hood),
              'schedule': schedule(career, seed, chosen['name'] if chosen['named'] else ''), 'commute': None}
    if home:
        result['commute'] = commute(data, home, hood)
        refs.append(home)
    return result | provenance(data, refs)


def _named(record: dict, fit: str, summary: str | None = None) -> tuple[dict, str, list[str]]:
    employer = {'id': record['id'], 'name': record['name'], 'named': True,
                'summary': record['summary'] if summary is None else summary, 'fit': fit}
    return employer, record['neighborhood'], [record['id']]


def _spread(seed: str, label: str, items: list[dict], avoid) -> dict:
    return pick(seed, label, items, [0.15 if item['id'] in avoid else 1.0 for item in items])


def _workplace(data: dict, career: dict, seed: str, given: str | None, avoid=()) -> tuple[dict, str, list[str]]:
    record = catalog.find(data, given) if given else None
    if given and not (record and 'neighborhood' in record):
        raise DomainError(f'{data["name"]} has no workplace {given!r}.', 404, 'unknown_workplace')
    if record:
        summary = record.get('summary') or f'Known for {", ".join(record["known_for"][:3]).replace("-", " ")}.'
        return _named(record, 'given', summary)
    if employers := [item for item in data['employers'] if career['id'] in item['careers']]:
        return _named(_spread(seed, 'employer', employers, avoid), 'employer')
    if career['id'] in STUDY and data['colleges']:
        chosen = _spread(seed, 'college', data['colleges'], avoid)
        return _named(chosen, 'college', f'Known for {", ".join(chosen["known_for"][:3]).replace("-", " ")}.')
    if places := [place for place in data['places'] if place['kind'] in
                  WORKPLACE_KINDS.get(career['id'], SECTOR_KINDS.get(career['sector'], ()))]:
        return _named(_spread(seed, 'workplace', places, avoid), 'workplace')
    matching = [hub for hub in data['career_hubs'] if career['sector'] in hub['sectors']]
    hub = pick(seed, 'hub', matching or data['career_hubs'])
    hood = pick(seed, 'hub-neighborhood', hub['neighborhoods'] if hub else
                [item['id'] for item in data['neighborhoods']])
    place_name = catalog.neighborhood(data, hood)['name']
    employer = {'id': None, 'name': f'a workplace in {place_name}' + (f' ({hub["name"]})' if hub else ''),
                'named': False, 'summary': hub['summary'] if hub else '', 'fit': 'hub' if matching else 'weak'}
    return employer, hood, [hub['id']] if hub else []


# --- Housing ---

def rent_step(rent: float) -> int:
    """What to round a rent to, by its size, so it suits the currency: yen and won by the thousand, dollars and
    pounds by 25, shillings or pennies by 5 or 1."""
    return 1000 if rent >= 40_000 else 25 if rent >= 400 else 5 if rent >= 40 else 1


@detached
def home(data: dict, *, seed: str, bedrooms: str = 'one_bedroom', budget: int | None = None,
         vibe: str | None = None, near: str | None = None) -> dict:
    """A neighborhood, housing type and rent within that neighborhood's typical range.

    `budget` is a maximum in the city's currency per its `rent_period`; when nothing fits, the cheapest
    neighborhoods are used. `rent` is None in settings without rents.
    """
    if bedrooms not in BEDROOMS:
        raise DomainError(f'Bedrooms is one of {", ".join(BEDROOMS)}.', 422)
    hoods = data['neighborhoods']
    priced = [hood for hood in hoods if hood['rent']]
    fits = [hood for hood in priced if budget is None or hood['rent'][bedrooms][0] <= budget]
    if priced and not fits:
        fits = sorted(priced, key=lambda hood: hood['rent'][bedrooms][0])[:3]
    fits = fits or hoods
    anchor = catalog.neighborhood(data, near) if near else None
    weights = []
    for hood in fits:
        weight = 3.0 if vibe and vibe in hood['vibe'] else 1.0
        if anchor:
            km = catalog.distance_km(anchor, hood)
            weight *= 4 if km <= 2 else 2 if km <= 5 else 1
        weights.append(weight)
    chosen = pick(seed, 'home', fits, weights)
    result = {'neighborhood': chosen, 'housing': pick(seed, 'housing', chosen['housing']), 'bedrooms': bedrooms,
              'rent': None, 'rent_range': None, 'currency': data['currency'], 'rent_period': data['rent_period'],
              'estimate': True}
    if chosen['rent']:
        low, high = chosen['rent'][bedrooms]
        top = max(low, min(high, budget)) if budget is not None else high
        step = rent_step(high)
        result |= {'rent': low + round(unit(seed, 'rent') * (top - low) / step) * step, 'rent_range': [low, high]}
    return result | provenance(data, [chosen['id']])


# --- People ---

PRONOUNS = {'she': 'she/her', 'he': 'he/him', 'they': 'they/them'}
GIVEN = {'she': 'feminine', 'he': 'masculine'}
HAUNTS = ('cafe', 'bar', 'tavern', 'inn', 'restaurant', 'park', 'garden', 'fitness', 'library', 'market',
          'beach', 'square', 'trail')
RETIRED_AT = 67
ROLES = {
    # Role: (closeness, age offset range from the companion, shares the family name)
    'close-friend': ('close', (-4, 4), False), 'friend': ('regular', (-7, 7), False),
    'coworker': ('regular', (-12, 12), False), 'neighbor': ('occasional', (-20, 25), False),
    'old-classmate': ('occasional', (-1, 1), False), 'mentor': ('occasional', (12, 30), False),
    'longtime-friend': ('close', (-3, 3), False), 'new-friend': ('regular', (-8, 8), False),
    'sibling': ('close', (-8, 8), True), 'parent': ('close', (24, 36), True), 'cousin': ('occasional', (-10, 10), None),
}
# The order a circle fills in, so a small circle has the closest people.
CIRCLE = ('close-friend', 'coworker', 'sibling', 'friend', 'parent', 'neighbor', 'friend', 'cousin', 'old-classmate',
          'friend', 'mentor', 'coworker')
# A sociable companion's bigger circle: friends old and new, more than one coworker and both parents.
SOCIAL = ('close-friend', 'longtime-friend', 'coworker', 'sibling', 'parent', 'new-friend', 'coworker', 'friend',
          'parent', 'new-friend', 'cousin', 'friend')
RETIRED_SCHEDULE = [
    {'key': 'sleep', 'label': 'Asleep', 'kind': 'sleep', 'days': list(range(7)), 'start': '22:30', 'end': '06:30',
     'themes': []},
    {'key': 'day', 'label': 'Retired', 'kind': 'leisure', 'days': list(range(7)), 'start': '09:00', 'end': '17:00',
     'themes': []},
]


def seeded_pronouns(data: dict, seed: str) -> str:
    """The pronouns `name` gives this seed when none are asked for: 'she', 'he' or 'they'."""
    modern = data['era'] in ('modern', 'future', 'other')
    return pick(seed, 'pronouns', ['she', 'he', 'they'], town_mix.pronoun_weights(modern))


def name(data: dict, *, seed: str, pronouns: str | None = None, group: str | None = None,
         family: str | None = None, age: int | None = None, avoid=()) -> dict:
    """A resident's name from the city's name groups. `family` keeps a relative's family name.

    In modern settings a group linked to cultures takes the given name from what babies were called around
    the person's birth year (`age` years before the data's present year; a seeded adult age without one),
    and the family name from that culture when it lists its own.

    Someone unrelated (no `family`) never gets a family name in `avoid` or in the city's `kin` (the
    companion's own and their relatives', set by dungeon/life/network.py): only that family name is drawn
    again, from the same seed, so everyone else's name stays as it was.
    """
    groups, mix = catalog.name_groups(data)
    group = group_of(data, seed, group)
    names = groups[group]
    if pronouns not in PRONOUNS:
        pronouns = seeded_pronouns(data, seed)
    links = naming.links(names, data)
    if family and not names.get('own_family'):
        # A relative's given name comes from a culture that fits the family name they share.
        links = {key: weight for key, weight in links.items() if not naming.culture(key)['surnames']
                 or naming.base_family(key, family) in naming.culture_surnames(key)}
    culture = pick(seed, 'culture', list(links), list(links.values())) if links else None
    if culture:
        age = age if age is not None else 22 + round(unit(seed, 'name-age') * 42)
        given = _given_for(seed, culture, naming.present_year(data) - age, pronouns)
    else:
        pools = [names[GIVEN[pronouns]]] if pronouns in GIVEN else [names['neutral']]
        if names['neutral'] and unit(seed, 'neutral-name') < 0.12:
            pools.insert(0, names['neutral'])
        pools += [names['feminine'] + names['masculine'] + names['neutral']]
        given = pick(seed, 'given', next(pool for pool in pools if pool))
    if family:
        family = naming.gendered(culture, naming.base_family(culture, family), pronouns) if culture else family
    else:
        avoid = {item.casefold() for item in (*avoid, *data.get('kin', ()))}
        family = _family(seed, culture, pronouns, names, groups, mix)
        for attempt in range(1, 9):
            if not family or not avoid & {family.casefold(), naming.base_family(culture, family).casefold()}:
                break
            family = _family(f'{seed}:family:{attempt}', culture, pronouns, names, groups, mix)
    if pronouns == 'she':
        family = _feminine_family(family, names)
    return {'given': given, 'family': family, 'full': f'{given} {family}', 'pronouns': PRONOUNS[pronouns],
            'group': group, 'culture': culture}


def group_of(data: dict, seed: str, group: str | None = None) -> str:
    """The name group a resident's name comes from (`name`): `group` when the city has it, else drawn by the seed
    from the groups their kind is named from (`kind_of`)."""
    return drawn(data, seed, group)[0]


def kind_of(data: dict, seed: str, group: str | None = None) -> str:
    """A resident's kind (dungeon/world/lifespans.py): `group`'s when given, else rolled from the shares the city's
    `kinds` block gives each kind (humans the rest), else their drawn name group's."""
    return drawn(data, seed, group)[1]


def drawn(data: dict, seed: str, group: str | None = None) -> tuple[str, str]:
    """(name group, kind) for a seed. A city without kind shares draws the group from the whole mix, as before shares
    existed; with them, the kind comes first and the group from that kind's own (a human keeps the group they had
    when the mix has no kind-tied groups)."""
    groups, mix = catalog.name_groups(data)
    if group in groups:
        return group, lifespans.of_group(data, group)
    shares = lifespans.shares(data)
    if not shares:
        group = pick(seed, 'name-group', list(mix), list(mix.values()))
        return group, lifespans.of_group(data, group)
    kind, mark = lifespans.HUMAN, unit(seed, 'folk-kind')
    for key, share in shares.items():
        if mark < share:
            kind = key
            break
        mark -= share
    weights = lifespans.groups_for(data, kind)
    return pick(seed, 'name-group', list(weights), list(weights.values())), kind


def _feminine_family(family: str, names: dict) -> str:
    for ending, feminine in (names.get('feminine_family') or {}).items():
        if family.endswith(ending):
            return family[:-len(ending)] + feminine
    return family


def _family(seed: str, culture: str | None, pronouns: str, names: dict, groups: dict, mix: dict) -> str:
    surnames = naming.culture(culture)['surnames'] if culture and not names.get('own_family') else []
    if surnames:
        family = pick(seed, 'family', surnames, naming.rank_weights(surnames))
        return naming.gendered(culture, naming.base_family(culture, family), pronouns)
    # Most residents' family names come from the same heritage group; some from anywhere in the city.
    # From people of their own kind: a human isn't a Hrívë Court elf's namesake.
    same = {key: weight for key, weight in mix.items() if groups[key].get('kind') == names.get('kind')}
    if not same and names.get('kind'):  # A people outside the mix (the peoples bank's dwarves): their own names.
        same = {key: 1.0 for key, group in groups.items() if group is names}
    same = same or mix
    other = pick(seed, 'family-group', list(same), list(same.values()))
    return pick(seed, 'family', names['family'] if unit(seed, 'mixed') >= 0.2 else groups[other]['family'])


def _given_for(seed: str, culture: str, born: int, pronouns: str) -> str:
    """A given name popular within a few years of `born`, ranked by popularity."""
    year = born + round((unit(seed, 'birth-year') * 2 - 1) * naming.SPREAD)
    found = naming.cohort(culture, year)
    if pronouns in GIVEN:
        pool = found[GIVEN[pronouns]]
    else:
        # Names given to both girls and boys that year, else the name they were given at birth from either list.
        shared = [item for item in found['feminine'] if item in set(found['masculine'])]
        pool = shared or found[pick(seed, 'neutral-list', ['feminine', 'masculine'])]
    return pick(seed, 'given', pool, naming.rank_weights(pool))


def fits_age(career: dict | None, age: int) -> bool:
    """Whether someone this age (in human terms) works this career: a squire is young (Career.ages)."""
    low, high = (career or {}).get('ages') or (0, 999)
    return low <= age <= high


def _age(data: dict, seed: str, career: str | None, around: int | None, role: str) -> int:
    offsets = ROLES[role][1]
    if around is None and role in ('parent', 'sibling', 'cousin', 'mentor', 'old-classmate'):
        # Relatives and mentors are placed relative to someone; without an age, assume a companion of 33.
        around = 33
    ages = (catalog.careers_for(data, needs_met=False).get(career) or {}).get('ages') if career else None
    if ages:
        low, high = ages
    elif around is not None:
        low, high = max(18, around + offsets[0]), max(18, around + offsets[1])
    else:
        low, high = 22, 64
    # Two draws averaged lean towards the middle of the range.
    return low + round((unit(seed, 'age-a') + unit(seed, 'age-b')) / 2 * (high - low))


def _career_for(data: dict, seed: str, age: int, employer: str | None, pronouns: str | None = None) -> str | None:
    if age >= RETIRED_AT:
        return None
    record = catalog.find(data, employer) if employer else None
    if record and record.get('careers'):
        offered = catalog.everyday(catalog.careers_for(data))
        options = [career for career in record['careers'] if career in offered]
        if (side := fits_side(data, pronouns)) and (fitting := [career for career in options if side(offered[career])]):
            options = fitting
        options = [career for career in options if fits_age(offered[career], age)] or options
        return pick(seed, 'career', sorted(options)) if options else None
    found = town_career(data, seed, pronouns=pronouns, age=age)
    return found['id'] if found else None


def _haunts(data: dict, seed: str, hood: str, count: int = 3) -> list[dict]:
    """Regular spots near home: in the neighborhood or the closest ones, favouring the nearest."""
    near = [hood] + [item['id'] for item in catalog.nearby(data, hood, 3)]
    scored = []
    for place in data['places']:
        if place['kind'] in HAUNTS and place['neighborhood'] in near and place['cost'] in ('free', '$', '$$'):
            weight = 3.0 if place['neighborhood'] == hood else 1.0
            scored.append((-(unit(seed, 'haunt', place['id']) ** (1 / weight)), place['id'], place))
    return [{'id': place['id'], 'name': place['name'], 'kind': place['kind'], 'neighborhood': place['neighborhood']}
            for _, _, place in sorted(scored)[:count]]


@detached
def resident(data: dict, *, seed: str, role: str = 'friend', career: str | None = None, age: int | None = None,
             near: str | None = None, employer: str | None = None, family: str | None = None,
             group: str | None = None, around_age: int | None = None, local: bool = True,
             avoid: list[str] | tuple = (), folk: str | None = None, pronouns: str | None = None) -> dict:
    """One person in the city: name, age, home, job with commute, weekly schedule and regular haunts.

    `near` puts their home close to a neighborhood (a neighbor's is the same one); `employer` makes them
    work at that record; `family` and `group` keep a relative's family name and heritage. `local=False`
    gives someone who lives out of town, with no home, job or schedule here. `avoid` lists workplaces to
    steer away from, so a circle doesn't all work in one place.

    Ages are drawn in human terms (`age` and `around_age` too) and their real age follows their kind
    (dungeon/world/lifespans.py): `folk`, else their name group's, so a relative of an elf is an elf and an
    elven resident is often centuries old. Their job and retiring follow the age in human terms.

    Their job fits the work their era gave their side (fits_side): `pronouns`, else their name's.
    """
    if role not in ROLES:
        raise DomainError(f'Role is one of {", ".join(ROLES)}.', 422)
    life = age or _age(data, seed, career, around_age, role)
    named = name(data, seed=seed, group=group, family=family, age=life)
    folk = folk or kind_of(data, seed, group)
    person = {'id': f'{role}-{hashlib.sha256(seed.encode()).hexdigest()[:8]}', 'role': role,
              'closeness': ROLES[role][0], 'name': named,
              'age': lifespans.real_age(life, lifespans.lifespan_of(folk, data)), 'local': local,
              'home': None, 'job': None, 'schedule': None, 'haunts': []}
    person |= {'folk': folk} if folk != lifespans.HUMAN else {}
    if not local:
        return person | provenance(data, [])
    age = life
    career = career or _career_for(data, seed, age, employer, pronouns or named['pronouns'])
    bedrooms = pick(seed, 'bedrooms', list(BEDROOMS), [3, 5, 2] if age < 35 else [1, 4, 5])
    if role == 'neighbor' and near:
        place = home(data, seed=seed, bedrooms=bedrooms, near=near)
        place = place if place['neighborhood']['id'] == near else _home_in(data, seed, bedrooms, near)
    else:
        place = home(data, seed=seed, bedrooms=bedrooms, near=near)
    hood = place['neighborhood']['id']
    person |= {'home': place, 'haunts': _haunts(data, seed, hood)}
    refs = [hood, *[spot['id'] for spot in person['haunts']]]
    if career:
        work = job(data, career, seed=seed, home=hood, employer=employer, avoid=avoid)
        person |= {'job': work, 'schedule': work['schedule']}
        refs += work['refs']
    else:
        person['schedule'] = RETIRED_SCHEDULE if age >= RETIRED_AT else []
    return person | provenance(data, list(dict.fromkeys(refs)))


def _home_in(data: dict, seed: str, bedrooms: str, hood_id: str) -> dict:
    """A home in exactly this neighborhood, for a next-door neighbor."""
    single = data | {'neighborhoods': [catalog.neighborhood(data, hood_id)]}
    return home(single, seed=seed, bedrooms=bedrooms)


@detached
def circle(data: dict, *, seed: str, size: int = 6, home: str | None = None, age: int | None = None,
           career: str | None = None, employer: str | None = None, family: str | None = None,
           group: str | None = None, order: tuple[str, ...] = CIRCLE, coworkers: bool = False,
           folk: str | None = None) -> dict:
    """The people around a companion: friends, coworkers, family and neighbors, closest first.

    Pass what is known about the companion (home neighborhood, age, career, workplace, family name and
    heritage group) so coworkers share their workplace (or their career, when only that is known),
    neighbors live nearby and relatives share a name. Without a career or workplace there are no coworkers.
    `order` is the order roles fill in (SOCIAL for a sociable companion); `coworkers` keeps coworkers
    when the caller places them at the companion's work itself. `folk` is the companion's kind, which their
    relatives share (dungeon/world/lifespans.py); `age` is theirs in human terms.
    """
    if not 1 <= size <= len(order):
        raise DomainError(f'A circle has 1 to {len(order)} people.', 422)
    roles = [role for role in order if role != 'coworker' or employer or career or coworkers]
    if not (employer or career or coworkers):
        roles = [*roles, 'friend', 'friend']
    if not family:
        chosen = name(data, seed=f'{seed}:family', group=group)
        family, group = naming.base_family(chosen['culture'], chosen['family']), group or chosen['group']
    people, used, taken = [], set(), {employer} - {None}
    # Friends, coworkers and neighbors never carry the family's name; only relatives do.
    others = data | {'kin': [*data.get('kin', ()), family]}
    for index, role in enumerate(roles[:size]):
        member_seed, related = f'{seed}:{role}:{index}', ROLES[role][2]
        if related is None:
            related = unit(member_seed, 'shares-name') < 0.5
        local = role not in ('parent', 'sibling', 'cousin') or unit(member_seed, 'local') < 0.6
        person = resident(data if related else others, seed=member_seed, role=role, around_age=age, local=local,
                          near=home if role in ('neighbor', 'parent', 'sibling') else None,
                          employer=employer if role == 'coworker' else None,
                          career=career if role == 'coworker' and not employer else None,
                          family=family if related else None, group=group if role in ('parent', 'sibling') else None,
                          avoid=sorted(taken), folk=folk if related else None)
        if person['job'] and person['job']['employer']['id']:
            taken.add(person['job']['employer']['id'])
        retry = 0
        while person['name']['full'] in used and retry < 5:
            retry += 1
            person['name'] = name(data if related else others, seed=f'{member_seed}:{retry}',
                                  family=family if related else None, group=person['name']['group'], age=person['age'])
        used.add(person['name']['full'])
        people.append(person)
    refs = list(dict.fromkeys(ref for person in people for ref in person['refs']))
    return {'family': family, 'people': people} | provenance(data, refs)


# --- Grounding text ---

@detached
def price(data: dict, item: str, *, seed: str) -> dict:
    """One plausible price for an everyday purchase, within the city's typical range."""
    found = next((entry for entry in data['prices'] if entry['id'] == item), None)
    if not found:
        raise DomainError(f'{data["name"]} has no price for {item!r}.', 404, 'unknown_price')
    low, high = found['low'], found['high']
    # Prices under ten keep two decimals (cents, or pence written as fractions of a shilling); larger ones
    # round to whole units.
    amount = low + unit(seed, 'price', item) * (high - low)
    amount = round(amount, 2) if high < 10 else round(amount)
    return {'price': found, 'amount': amount, 'currency': data['currency'], 'estimate': True,
            'city': data['id'], 'data_version': data['data_version'], 'refs': [item], 'sources': [found['source']]}


@detached
def local_color(data: dict, *, seed: str, kinds: list[str] | None = None, day: date | None = None,
                count: int = 3) -> list[dict]:
    """A few things locals eat, drink, say, do or tell, for flavour. Seasonal items appear only in season on `day`.
    Each is marked `hearsay` when it is a legend or rumour: something people say, never confirmed fact."""
    season = SEASONS[day.month] if day else None
    pool = [item for item in data['local_color'] if (not kinds or item['kind'] in kinds)
            and (not season or not item['seasons'] or season in item['seasons'])]
    return [item | {'hearsay': item['kind'] in HEARSAY_KINDS}
            for item in sorted(pool, key=lambda item: unit(seed, 'color', item['id']))[:count]]


def figure(value: float) -> str:
    """A price as people write it: 4.5, 12, 1,200 or 850,000 (never 8.5e+05, which `:g` gives for won)."""
    return f'{value:,.0f}' if value == int(value) else f'{value:,.2f}'.rstrip('0').rstrip('.')


def facts(data: dict, neighborhood: str | None = None, limit: int = 8) -> list[str]:
    """Short factual lines for a prompt, so the model describes real places instead of inventing them."""
    lines = [f'{data["name"]}, {data["region"]}: {data["summary"]}']
    if neighborhood:
        hood = catalog.neighborhood(data, neighborhood)
        lines.append(f'{hood["name"]}: {hood["summary"]}')
        for place in catalog.places(data, neighborhood=neighborhood)[:limit]:
            lines.append(f'{place["name"]} ({place["kind"]}): {place["summary"]}')
    if data['prices']:
        symbol = data['currency']['symbol']
        lines.append('Typical prices: ' + '; '.join(
            f'{item["item"]} {symbol}{figure(item["low"])}–{symbol}{figure(item["high"])}' +
            (f' {item["per"]}' if item['per'] else '')
            for item in data['prices'][:limit]))
    for item in data['local_color'][:limit]:
        lines.append(color_line(item))
    return lines


def color_line(item: dict) -> str:
    """One local colour item for a prompt; a legend or rumour is marked as hearsay, so it is never told as fact."""
    if item['kind'] in HEARSAY_KINDS:
        return f'Local {item["kind"]} (hearsay locals tell, not confirmed fact): {item["name"]}: {item["summary"]}'
    return f'Local {item["kind"]}: {item["name"]}: {item["summary"]}'
