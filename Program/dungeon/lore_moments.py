"""Lore that fits the moment: a lore entry can say when it applies (dungeon/lore.py), not only which words bring it.

Ported from Prospero's Companion 1.0 (companion/lore_moments.py). A "when" is a list of conditions, each `kind:value`:
the weather (rain, snow, heat, fog), the season, the time of day, a weekday or the weekend, one of the city's
holidays, and a place or neighbourhood. Conditions of one kind are alternatives and different kinds all have to hold,
so ["weather:rain", "time:night"] is a rainy night and ["season:winter", "season:fall"] is either. The moment is the
story's scene (dungeon/story.py): its town's weather and calendar at the scene's local time, and where the player
is. Rules only: no model picks anything.

Imported lorebooks get a "when" by rule only from a keyword that is itself a season, weather, time of day or one of
the city's holidays (`guessed`), and the player can change or clear it.
"""
import re
from datetime import datetime

from dungeon.world import catalog, generators

WEATHER = {'rain': 'Rain', 'snow': 'Snow', 'heat': 'Heat', 'fog': 'Fog'}
SEASONS = {'spring': 'Spring', 'summer': 'Summer', 'fall': 'Fall', 'winter': 'Winter'}
TIMES = {'morning': 'Morning', 'afternoon': 'Afternoon', 'evening': 'Evening', 'night': 'Night'}
DAYS = {'weekday': 'Weekdays', 'weekend': 'Weekends'}
# The hour each part of the day starts, local time; night runs on to morning.
TIME_STARTS = ((5, 'morning'), (12, 'afternoon'), (17, 'evening'), (21, 'night'))
KINDS = ('weather', 'season', 'time', 'day', 'holiday', 'place')
# Heat from this high (°F) up, snow on a wet day this cold or colder at night.
HOT_F, SNOW_F = 88, 30
FOGGY = re.compile(r'\b(fog|fogs|foggy|mist|misty|haar|smog)\b', re.I)
SNOWY = re.compile(r'\b(snow\w*|sleet|blizzard)\b', re.I)
# Keywords of an imported entry that are themselves a moment (`guessed`). "Fall" is left out: it is a verb too.
WORDS = {'rain': 'weather:rain', 'rainy': 'weather:rain', 'snow': 'weather:snow', 'snowy': 'weather:snow',
         'heatwave': 'weather:heat', 'heat wave': 'weather:heat', 'fog': 'weather:fog', 'foggy': 'weather:fog',
         'spring': 'season:spring', 'summer': 'season:summer', 'autumn': 'season:fall', 'winter': 'season:winter',
         'morning': 'time:morning', 'afternoon': 'time:afternoon', 'evening': 'time:evening', 'night': 'time:night',
         'nighttime': 'time:night', 'weekend': 'day:weekend', 'weekday': 'day:weekday'}


# Reading the moment ----------------------------------------------------------------------------------------

def part_of_day(hour: int) -> str:
    found = 'night'
    for start, name in TIME_STARTS:
        if hour >= start:
            found = name
    return found


def weather_keys(conditions: dict | None) -> set[str]:
    """What the day's weather (dungeon/world/generators.py conditions) counts as."""
    if not conditions:
        return set()
    note = conditions.get('note') or ''
    found = set()
    if conditions.get('rain'):
        snowing = conditions.get('low_f', 99) <= SNOW_F or bool(SNOWY.search(note))
        found.add('weather:snow' if snowing else 'weather:rain')
    elif FOGGY.search(note):
        found.add('weather:fog')
    if conditions.get('high_f', 0) >= HOT_F:
        found.add('weather:heat')
    return found


def place_keys(city: dict, place_id: str) -> set[str]:
    """The place the scene is at and its neighbourhood, by the city's ids."""
    place = catalog.find(city, place_id)
    if not place:  # Somewhere off the map, or a place the city no longer has: no place conditions hold.
        return set()
    hood = place.get('neighborhood')
    return {f'place:{place_id}'} | ({f'place:{hood}'} if hood else set())


def holiday_keys(city: dict, day) -> set[str]:
    return {f"holiday:{item['name'].casefold()}" for item in generators.holidays(city, day)}


def now_keys(city: dict, place_id: str, local: datetime) -> set[str]:
    """Every condition that holds in the scene: the town at its local time, and where the player is."""
    found = {f'time:{part_of_day(local.hour)}', 'day:weekend' if local.weekday() >= 5 else 'day:weekday'}
    if city.get('climate'):
        found.add(f'season:{generators.SEASONS[local.month]}')
    found |= weather_keys(generators.conditions(city, local.date()))
    return found | holiday_keys(city, local.date()) | place_keys(city, place_id)


def matches(when: list[str], keys: set[str]) -> bool:
    """Whether a "when" holds: one condition of each kind it names. An empty "when" never does."""
    wanted: dict[str, set[str]] = {}
    for condition in when:
        kind, _, value = condition.partition(':')
        wanted.setdefault(kind, set()).add(f'{kind}:{value.casefold()}')
    return bool(wanted) and all(options & keys for options in wanted.values())


# What an entry's "when" says ----------------------------------------------------------------------------------

def holiday_names(city: dict | None) -> list[str]:
    """The city's holidays by name, for the picker and for guessing."""
    if not city:
        return []
    return sorted(dict.fromkeys(item['name'] for item in generators.city_holidays(city)), key=str.casefold)


def guessed(keywords: list[str], holidays: list[str]) -> list[str]:
    """A "when" for an imported entry from keywords that are themselves a moment, of one kind only (the first found),
    so an entry keyed "winter" and "rain" switches on in winter, not only on wet winter days."""
    named = {name.casefold(): name for name in holidays}
    found = []
    for word in keywords:
        key = word.strip().casefold()
        condition = WORDS.get(key) or (f'holiday:{named[key]}' if key in named else None)
        if condition and (not found or condition.partition(':')[0] == found[0].partition(':')[0]):
            found.append(condition)
    return list(dict.fromkeys(found))


def choices(city: dict | None) -> dict:
    """What a "when" picker offers, as [{key, label}] by kind: places are the city's neighbourhoods and places."""
    def listed(kind, labels):
        return [{'key': f'{kind}:{key}', 'label': label} for key, label in labels.items()]
    spots = {item['id']: item['name'] for item in [*(city or {}).get('neighborhoods', []),
                                                    *(city or {}).get('places', [])]}
    return {'weather': listed('weather', WEATHER), 'season': listed('season', SEASONS), 'time': listed('time', TIMES),
            'day': listed('day', DAYS),
            'holiday': [{'key': f'holiday:{name}', 'label': name} for name in holiday_names(city)],
            'place': listed('place', dict(sorted(spots.items(), key=lambda item: item[1].casefold())))}


def label(condition: str, city: dict | None) -> str:
    kind, _, value = condition.partition(':')
    if kind == 'place':
        known = {item['id']: item['name'] for item in [*(city or {}).get('neighborhoods', []),
                                                         *(city or {}).get('places', [])]}
        return known.get(value, value.replace('-', ' ').capitalize())
    if kind == 'holiday':
        return value
    return {**WEATHER, **SEASONS, **TIMES, **DAYS}.get(value, value)


def tidy(when: list[str]) -> list[str]:
    """A "when" from the player, kept to known kinds and in a steady order."""
    kept = []
    for condition in when:
        kind, _, value = condition.partition(':')
        if kind in KINDS and value.strip() and condition not in kept:
            kept.append(f'{kind}:{value.strip()[:120]}')
    return sorted(kept, key=lambda item: KINDS.index(item.partition(':')[0]))[:40]
