"""Townsfolk couples (Hit List #65, v0.13 Life Together): the town's "seeing someone" and "married" become couples.

A townsperson's dating details (dungeon/world/dating.py) say whether they are single, seeing someone or married;
here someone who has a partner gets a named one, seeded like the rest of their sheet, and the couple moves on week by
week from the world's epoch (the same weeks townsfolk goals move in, dungeon/world/townsfolk.py): a couple seeing
each other may get engaged and, some months later, married, or split up; a married couple rarely splits; someone
single again may meet someone new. Nothing is stored: the same person on the same day is the same couple, every time.

Now and then a couple has a baby (`babies`), a week seeded the same way, from when the town started changing hands
(dungeon/world/turnover.py); the baby is only ever words in the paper.

The town paper reports engagements, weddings and babies (dungeon/world/paper.py), and a companion who knows a townsperson
well enough knows where their love life stands (dungeon/life/encounters.py).
"""
from datetime import date, timedelta
from functools import lru_cache

from dungeon.world import dating, generators, lifespans, townsfolk, turnover

# Each week's chance, from the epoch.
ENGAGE = 1 / 90  # Seeing someone, after `ENGAGE_AFTER` weeks together: they get engaged.
ENGAGE_AFTER = 20
SPLIT = 1 / 160  # Seeing someone or engaged: they split up.
DIVORCE = 1 / 2600  # Married: they split up.
MEET = 1 / 70  # Single again, after `MEET_AFTER` weeks: they meet someone new.
MEET_AFTER = 12
WEDDING = (20, 56)  # Weeks from an engagement to the wedding.
PARTNERED = ('seeing someone', 'married')
GENDER_PRONOUNS = {'woman': 'she', 'man': 'he', 'nonbinary': 'they'}
BABY = 0.1  # An engaged or married couple's chance of a baby each year, at the usual pace.
BABY_AGES = (24, 42)
EXPECTING_WEEKS = 30  # How long before a town baby arrives that the people who know the couple hear about it.


@lru_cache(maxsize=4096)
def history(seed: str, start: str, weeks: int) -> tuple:
    """(week, what happened, partner number) through `weeks`, from where they stood at the epoch."""
    state, number, since, wedding, result = start, 0, -ENGAGE_AFTER, None, []
    for week in range(weeks + 1):
        roll = generators.unit(seed, 'couple', week)
        if state == 'seeing someone' and roll < SPLIT or state == 'engaged' and roll < SPLIT / 2 or \
                state == 'married' and roll < DIVORCE:
            state, since = 'single', week
            result.append((week, 'split', number))
        elif state == 'seeing someone' and week - since >= ENGAGE_AFTER and roll > 1 - ENGAGE:
            state = 'engaged'
            wedding = week + WEDDING[0] + int(generators.unit(seed, 'wedding', week) * (WEDDING[1] - WEDDING[0]))
            result.append((week, 'engaged', number))
        elif state == 'engaged' and week >= wedding:
            state = 'married'
            result.append((week, 'married', number))
        elif state == 'single' and week - since >= MEET_AFTER and roll > 1 - MEET:
            state, number, since = 'seeing someone', number + 1, week
            result.append((week, 'met', number))
    return tuple(result)


def companion_sheet(sheet: dict, data: dict) -> bool:
    """A companion living in town (`cast`, or one of `data['companions']`, the townsfolk keys companions were made
    from): their love life is their own, never the seeded townsperson's."""
    return bool(sheet.get('cast')) or sheet.get('key') in data.get('companions', ())


def details_of(sheet: dict, data: dict) -> dict | None:
    if 'desire' not in sheet or 'age' not in sheet or companion_sheet(sheet, data):
        return None
    return dating.details(sheet, data)


def partner(sheet: dict, data: dict, number: int, found: dict) -> dict:
    """Their partner: a seeded name, someone they are drawn to, near their age in human terms (an elf of 300 and a
    human of 48 are a match, dungeon/world/lifespans.py)."""
    seed = f'{townsfolk.drawn(sheet)}:partner:{number}'
    gender = generators.pick(seed, 'gender', sorted(found['drawn_to'])) or 'woman'
    life = max(18, found.get('life', sheet['age']) + round(generators.unit(seed, 'age') * 10) - 5)
    folk = townsfolk.folk_of(data, seed)
    age = lifespans.real_age(life, lifespans.lifespan_of(folk, data))
    name = generators.name(data, seed=seed, pronouns=GENDER_PRONOUNS.get(gender, 'they'), age=life)
    made = {'name': name['given'], 'full': name['full'], 'pronouns': name['pronouns'], 'age': age}
    return made | ({'folk': folk} if folk != lifespans.HUMAN else {})


def couple(sheet: dict, data: dict, day: date) -> dict | None:
    """Where their love life stands on `day`: {status, partner, since, ex}, or None for someone who started single
    (or isn't a resident with dating details, or is a companion now)."""
    found = details_of(sheet, data)
    if not found or found['status'] not in PARTNERED:
        return None
    weeks = min(max(townsfolk.week_of(day), 0), townsfolk.MAX_WEEKS)
    state, number, since, ex = found['status'], 0, None, None
    for week, what, which in history(townsfolk.drawn(sheet), found['status'], weeks):
        number, since = which, week
        if what == 'split':
            state, ex = 'single', which
        else:
            state = 'seeing someone' if what == 'met' else what
    return {'status': state, 'partner': partner(sheet, data, number, found) if state != 'single' else None,
            'ex': partner(sheet, data, ex, found) if state == 'single' and ex is not None else None,
            'since': (townsfolk.EPOCH + timedelta(weeks=since)).isoformat() if since is not None else None}


def events(sheet: dict, data: dict, week_range: tuple[date, date]) -> list[dict]:
    """Engagements and weddings in a span of days: {what, partner, day}."""
    found = details_of(sheet, data)
    if not found or found['status'] not in PARTNERED:
        return []
    weeks = min(max(townsfolk.week_of(week_range[1]), 0), townsfolk.MAX_WEEKS)
    result = []
    for week, what, which in history(townsfolk.drawn(sheet), found['status'], weeks):
        when = townsfolk.EPOCH + timedelta(weeks=week, days=5)  # A Saturday.
        if what in ('engaged', 'married') and week_range[0] <= when <= week_range[1]:
            result.append({'what': what, 'partner': partner(sheet, data, which, found), 'day': when})
    return result


def babies(sheet: dict, data: dict, week_range: tuple[date, date]) -> list[dict]:
    """Babies born to them and their partner in a span of days: {partner, day}. Follows Growing families. Never for a
    companion living in town (`companion_sheet`): a companion's own baby waits for v0.15."""
    if not turnover.ACTIVE or companion_sheet(sheet, data):
        return []
    result = []
    for week in range(max(townsfolk.week_of(week_range[0]), turnover.START_WEEK), townsfolk.week_of(week_range[1]) + 1):
        age = dating.life_of({**sheet, 'age': age_on(sheet, data, turnover.week_day(week, 3))}, data)
        chance = BABY * turnover.PACE[turnover.levels_at(week)[2]] / turnover.YEAR
        if generators.unit(townsfolk.drawn(sheet), 'baby', week) >= chance or not BABY_AGES[0] <= age <= BABY_AGES[1]:
            continue
        day = turnover.week_day(week, 3)
        state = couple(sheet, data, day)
        if state and state['status'] in ('engaged', 'married') and week_range[0] <= day <= week_range[1]:
            result.append({'partner': state['partner'], 'day': day})
    return result


def age_on(sheet: dict, data: dict, day: date) -> int:
    """Their age on a day as Around town has it (dungeon/life/ages.py): from the day the town started getting older
    (`data['began']`, the paper's; else when it started changing hands) and their seeded birthday."""
    from dungeon.life import ages
    return ages.aged(sheet, day, data.get('began') or turnover.START)


def family_news(sheet: dict, data: dict, day: date) -> str | None:
    """'expecting a baby with Dana around March' for a baby on the way (the news is out about seven months before),
    'had a baby with Dana in June' for one in the last half year; None otherwise (Births and growing families)."""
    found = babies(sheet, data, (day - timedelta(weeks=26), day + timedelta(weeks=EXPECTING_WEEKS)))
    if not found:
        return None
    item = found[-1]
    with_whom = f" with {item['partner']['name']}" if item['partner'] else ''
    if item['day'] > day:
        return f"expecting a baby{with_whom} around {item['day'].strftime('%B')}"
    return f"had a baby{with_whom} in {item['day'].strftime('%B')}"


def text(state: dict | None) -> str | None:
    """'married to Dana Ruiz', 'seeing Dana', 'single again since splitting up with Dana'."""
    if not state:
        return None
    if state['status'] == 'single':
        return f"single again since splitting up with {state['ex']['name']}" if state['ex'] else None
    who = state['partner']
    return {'married': f"married to {who['full']}", 'engaged': f"engaged to {who['full']}"}.get(
        state['status'], f"seeing {who['full']}")
