"""The town's mix (Worlds > Townsfolk mix): the shares the townsfolk rolls use for how people look and who
they are drawn to, shown to the user and, for advanced users, changed for a new world.

Each world keeps its own mix (table `townsfolk_mix`; no row is the built-in one) and a new world starts from the
mix of the world it was made from, so Become a townsperson keeps the same people. Changing the mix never touches
the open world: Debug makes a new world with it and switches there, so everyone already met stays who they were.

The rolls (dungeon/world/dating.py, generators.name, dungeon/world/intimacy.py) read `current()`, which is the
open world's mix; `using` holds another one while a new world's starter companion is drawn. Every value equal to
the built-in one leaves its roll exactly as it was, so a world with no mix of its own never changes.

Ages, and every check that keeps the adult side for adults, are not part of the mix and never change here.
"""
import json
from contextlib import contextmanager

from dungeon.database import optional

# The built-in mix, as the rolls had it before the mix could change.
DEFAULTS = {
    'nonbinary': 6,         # Percent of people in modern worlds; a third of it in older eras (generators.name).
    'women': 50,            # Percent of the rest who are women; the others are men.
    'height_woman': 162,    # Average height in centimetres (dating.HEIGHT); nonbinary people sit between.
    'height_man': 176,
    'slender': 37.5,        # Shares of builds: slender, in between and heavier (dating.BUILD_GROUPS).
    'middle': 37.5,
    'heavier': 25,
    'beard': 35,            # Percent of men with facial hair.
    'gay': 2.6,             # Percent of adults who are gay or lesbian, about, across the town's ages.
    'bisexual': 3.0,        # Percent of adult women and men who are bisexual, about.
    'bolder': 0,            # Adult side: -2 much tamer .. 2 much bolder.
    'drive': 0,             # Adult side: -2 much lower .. 2 much higher.
}
LIMITS = {
    'nonbinary': (0, 40, 1), 'women': (0, 100, 1), 'height_woman': (145, 185, 1), 'height_man': (155, 200, 1),
    'slender': (0, 100, 0.5), 'middle': (0, 100, 0.5), 'heavier': (0, 100, 0.5), 'beard': (0, 100, 1),
    'gay': (0, 40, 0.1), 'bisexual': (0, 60, 0.1), 'bolder': (-2, 2, 1), 'drive': (-2, 2, 1),
}
# How far each step of the adult-side sliders moves the roll.
BOLDER_STEP = 0.12
DRIVE_STEP = 0.1
# The highest share of one age band who are gay, lesbian or bisexual together, however far the sliders go.
MOST_QUEER = 0.95

_active: dict = dict(DEFAULTS)


def clean(values: dict | None) -> dict:
    """A whole mix from what was sent or saved: every value inside its limits, anything missing built in."""
    found = dict(DEFAULTS)
    for key, (low, high, _step) in LIMITS.items():
        value = (values or {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            found[key] = min(max(float(value), low), high)
    if found['slender'] + found['middle'] + found['heavier'] <= 0:
        found |= {key: DEFAULTS[key] for key in ('slender', 'middle', 'heavier')}
    return {key: int(value) if float(value).is_integer() and isinstance(DEFAULTS[key], int) else value
            for key, value in found.items()}


def current() -> dict:
    return _active


def changed(key: str) -> bool:
    return _active[key] != DEFAULTS[key]


def fingerprint() -> str:
    """For caches of drawn people (dungeon/dating.py pool): '' for the built-in mix."""
    return '' if _active == DEFAULTS else json.dumps(_active, sort_keys=True)


def read(connection) -> dict:
    row = optional(connection, 'SELECT mix FROM townsfolk_mix WHERE id=1')
    return clean(json.loads(row['mix'])) if row else dict(DEFAULTS)


def write(connection, values: dict, timestamp: str):
    connection.execute('INSERT OR REPLACE INTO townsfolk_mix (id, mix, updated_at) VALUES (1, ?, ?)',
                       (json.dumps(clean(values), sort_keys=True), timestamp))


def load(database):
    """The open world's mix, read when the app starts or switches world."""
    global _active
    with database.connect() as connection:
        _active = read(connection)


@contextmanager
def using(values: dict):
    global _active
    before, _active = _active, clean(values)
    try:
        yield
    finally:
        _active = before


# What the rolls ask -------------------------------------------------------------------------------------------

def pronoun_weights(modern: bool) -> list[float]:
    """She, he and they, for generators.name: 47, 47 and 6 in modern worlds and 2 in older eras, built in."""
    nonbinary = _active['nonbinary'] if modern else _active['nonbinary'] / 3
    rest = 100 - _active['nonbinary']
    return [rest * _active['women'] / 100, rest * (100 - _active['women']) / 100, nonbinary]


def height_mean(who: str, built_in: float) -> float:
    if who == 'woman':
        return _active['height_woman'] if changed('height_woman') else built_in
    if who == 'man':
        return _active['height_man'] if changed('height_man') else built_in
    if not (changed('height_woman') or changed('height_man')):
        return built_in
    return (_active['height_woman'] + _active['height_man']) / 2


def builds_changed() -> bool:
    return any(changed(key) for key in ('slender', 'middle', 'heavier'))


def beard_share() -> float:
    return _active['beard'] / 100


# Who they're drawn to: the built-in rates go by age band (dating.ORIENTATION_RATES), and the sliders scale every
# band alike so younger people stay more often bisexual than older ones.

def age_shares() -> list[tuple[int, float]]:
    """How the town's adults spread over the age bands: most townsfolk are residents, 18 + the mean of two
    draws times 66 (dungeon/world/townsfolk.py)."""
    from dungeon.world import dating
    steps, counts = 400, {}
    for a in range(steps):
        for b in range(steps):
            age = 18 + round(((a + 0.5) / steps + (b + 0.5) / steps) / 2 * 66)
            upper = next(band[0] for band in dating.ORIENTATION_RATES if age <= band[0])
            counts[upper] = counts.get(upper, 0) + 1
    return [(upper, counts.get(upper, 0) / steps ** 2) for upper, *_rest in dating.ORIENTATION_RATES]


_SHARES: list = []


def band_shares() -> list[tuple[int, float]]:
    if not _SHARES:
        _SHARES.extend(age_shares())
    return _SHARES


def built_in_share(kind: str) -> float:
    """Percent of adults, built in: gay or lesbian, or bisexual (women and men alike); DEFAULTS rounds them."""
    from dungeon.world import dating
    weights = dict(band_shares())
    if kind == 'gay':
        return 100 * sum(weights[band[0]] * band[1] for band in dating.ORIENTATION_RATES)
    return 100 * sum(weights[band[0]] * (band[2] + band[3]) / 2 for band in dating.ORIENTATION_RATES)


def orientation_band(band: tuple) -> tuple:
    """An age band's (upper age, gay, bisexual women, bisexual men) under the open world's mix."""
    if not (changed('gay') or changed('bisexual')):
        return band
    upper, gay, bi_woman, bi_man = band
    gay = min(gay * _active['gay'] / DEFAULTS['gay'], MOST_QUEER)
    scale = _active['bisexual'] / DEFAULTS['bisexual']
    return upper, gay, min(bi_woman * scale, MOST_QUEER - gay), min(bi_man * scale, MOST_QUEER - gay)


def bolder_shift() -> float:
    return _active['bolder'] * BOLDER_STEP


def drive_weights(built_in: dict) -> dict:
    if not changed('drive'):
        return built_in
    shift = _active['drive'] * DRIVE_STEP * sum(built_in.values())
    return {'low': max(built_in['low'] - shift, 0.0), 'average': built_in['average'],
            'high': max(built_in['high'] + shift, 0.0)}
