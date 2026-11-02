"""Worlds > Townsfolk mix (dungeon/world/mix.py): what the open world's town is made of, counted from its
people, and a new world made with a changed mix.

The count reads every townsperson in the story's city (people at its places and its residents), the
same sheets the rest of the app draws, so it is what the town is rather than what the rates promise. It is worked
out once per city, town and mix. Nothing here calls a model.
"""
import functools
from collections import Counter

from dungeon import story, worlds
from dungeon.database import settings
from dungeon.errors import require
from dungeon.world import dating, intimacy, mix, townsfolk

BAND_LABELS = ('18 to 29', '30 to 44', '45 to 59', '60 and over')
LEVELS = ('reserved', 'conventional', 'curious', 'adventurous', 'wild')
_COUNTS: dict[tuple, dict] = {}


def town_of(connection) -> dict:
    """The story's city; one with no places has no townsfolk to count."""
    return story.city_data(connection, story.scene_row(connection)['city_id'])


def everyone(data: dict) -> list[dict]:
    people = [sheet for place in data['places'] for sheet in townsfolk.at_place(data, place['id'])]
    for hood in data['neighborhoods']:
        where = townsfolk.area(data, hood['id'])
        people += townsfolk.not_you(data, [townsfolk.resident(data, hood['id'], index, where)
                                           for index in range(townsfolk.resident_count(data, hood['id']))])
    return [sheet for sheet in people if intimacy.adult(sheet.get('age'))]


def percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def count(data: dict) -> dict:
    """The town's adults by gender, height, build, facial hair, orientation and adult side."""
    key = (data['id'], data.get('town', ''), data.get('you', ''), mix.fingerprint())
    if key in _COUNTS:
        return _COUNTS[key]
    people = everyone(data)
    found = [(sheet, dating.details(sheet, data)) for sheet in people]
    genders = Counter(item['gender'] for _sheet, item in found)
    men = [item for _sheet, item in found if item['gender'] == 'man']
    group_of = {build: group for group, builds in dating.BUILD_GROUPS.items() for build in builds}
    builds = Counter(group_of.get(item['looks']['build'], 'middle') for _sheet, item in found)
    binary = [item for _sheet, item in found if item['gender'] != 'nonbinary']
    orientations = Counter(item['orientation'] for item in binary)
    sides = [intimacy.for_sheet(sheet) for sheet in people]
    levels = Counter(side['level'] for side in sides if side)
    drives = Counter(side['drive'] for side in sides if side)
    total = len(found)
    result = {
        'city': data['name'], 'people': total,
        'genders': {gender: percent(genders[gender], total) for gender in dating.GENDERS},
        'heights': {gender: round(sum(item['looks']['height_cm'] for _sheet, item in found if item['gender'] == gender)
                                  / genders[gender]) if genders[gender] else None for gender in dating.GENDERS},
        'builds': {group: percent(builds[group], total) for group in dating.BUILD_GROUPS},
        'beard': percent(sum(1 for item in men if item['looks'].get('beard')), len(men)),
        'gay': percent(orientations['gay'] + orientations['lesbian'], len(binary)),
        'bisexual': percent(orientations['bisexual'], len(binary)),
        'levels': {level: percent(levels[level], sum(levels.values())) for level in LEVELS},
        'drives': {drive: percent(drives[drive], sum(drives.values())) for drive in ('low', 'average', 'high')},
    }
    if len(_COUNTS) > 8:
        _COUNTS.clear()
    _COUNTS[key] = result
    return result


@functools.cache
def level_shares(step: int) -> dict:
    """The share of each adult-side level a step of the "bolder" slider gives: the mean of two draws, moved."""
    steps, counts = 200, Counter()
    for a in range(steps):
        for b in range(steps):
            middle = min(max(((a + 0.5) / steps + (b + 0.5) / steps) / 2 + step * mix.BOLDER_STEP, 0.0), 0.999)
            counts[LEVELS[min(len(LEVELS) - 1, int(middle * len(LEVELS)))]] += 1
    return {level: percent(counts[level], steps ** 2) for level in LEVELS}


def drive_shares(step: int) -> dict:
    with mix.using(mix.current() | {'drive': step}):
        weights = mix.drive_weights(intimacy.DRIVES)
    total = sum(weights.values())
    return {drive: round(100 * weight / total, 1) for drive, weight in weights.items()}


def view(database) -> dict:
    with database.connect() as connection:
        data = town_of(connection)
        saved = mix.read(connection)
        adult_side = bool((settings(connection) or {}).get('adult_side'))
    low, high, _step = mix.LIMITS['bolder']
    return {'mix': saved, 'defaults': mix.DEFAULTS, 'limits': {key: list(value) for key, value in mix.LIMITS.items()},
            'bands': [{'ages': label, 'gay': band[1], 'bisexual_women': band[2], 'bisexual_men': band[3]}
                      for label, band in zip(BAND_LABELS, dating.ORIENTATION_RATES, strict=True)],
            'levels': {step: level_shares(step) for step in range(int(low), int(high) + 1)},
            'drives': {step: drive_shares(step) for step in range(int(low), int(high) + 1)},
            'adult_side': adult_side, 'town': count(data) if data.get('places') else None}


def new_world(state, values: dict) -> dict:
    """A new world in the same city for the same persona, made with this mix, and switch to it. The world being left
    keeps its own mix and everyone in it."""
    reason = worlds.busy(state)
    require(reason is None, reason or '', 409)
    world = worlds.create_world(state.database, town_mix=mix.clean(values))
    return worlds.switch(state, world['id'])
