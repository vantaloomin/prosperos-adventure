"""Everyone gets older (from Companion, Hit List #67): townsfolk ages move on with the calendar.

A townsperson is rebuilt from a seed, so nothing is stored for them; their seeded age is their age on the day the
town started getting older (the town row in `birth_dates`, written when the world is first opened), and they turn a
year older on each seeded birthday after it. Nothing here calls a model.
"""
from calendar import isleap, monthrange
from datetime import date, timedelta

from dungeon.database import optional
from dungeon.world import generators

# --- Dates ---

def seeded_birthday(seed: str) -> str:
    """A birthday as "MM-DD" seeded by an id (never 29 February)."""
    return (date(2001, 1, 1) + timedelta(days=int(generators.unit(seed, 'birthday') * 365))).strftime('%m-%d')


def birthday_in(year: int, birthday: str) -> date:
    """The day a "MM-DD" birthday falls in a year; 29 February falls on the 28th in other years."""
    month, day = map(int, birthday.split('-'))
    if month == 2 and day == 29 and not isleap(year):
        day = 28
    return date(year, month, min(day, monthrange(year, month)[1]))


def born_from(age: int, birthday: str, today: date) -> date:
    """The birth date that makes someone `age` today with this birthday."""
    year = today.year - age - (birthday_in(today.year, birthday) > today)
    return birthday_in(year, birthday)


def age_on(born: date, birthday: str, day: date) -> int:
    return day.year - born.year - (birthday_in(day.year, birthday) > day)


# --- Stored dates ---

def stored(connection, kind: str, key: str) -> dict | None:
    return optional(connection, 'SELECT * FROM birth_dates WHERE kind=? AND person_key=?', (kind, key))


# --- The town ---

def town_began(connection) -> date | None:
    row = stored(connection, 'town', '')
    return date.fromisoformat(row['anchored_on']) if row else None


def town_age(connection, sheet: dict, day: date) -> int:
    """A townsperson's age on a day: their seeded age on the day the town started getting older, a year more for each
    of their seeded birthdays since."""
    return aged(sheet, day, town_began(connection))


def aged(sheet: dict, day: date, began: date | None) -> int:
    """A townsperson's age on a day, from the day the town started getting older (`town_began`): for the paper and
    town couples (dungeon/world/paper.py, couples.py), which have that day but no connection."""
    # A newcomer (dungeon/world/turnover.py) was their seeded age the day they arrived in town.
    if began is not None and sheet.get('arrived'):
        began = max(began, date.fromisoformat(sheet['arrived']))
    if began is None or day <= began:
        return sheet['age']
    born = born_from(sheet['age'], seeded_birthday(sheet['seed']), began)
    return max(sheet['age'], age_on(born, seeded_birthday(sheet['seed']), day))


def start_town(connection, timestamp: str) -> None:
    """The day the town starts getting older: the first time the world is opened."""
    day = timestamp[:10]
    connection.execute("INSERT OR IGNORE INTO birth_dates (kind, person_key, born_on, birthday, from_age, "
                       "anchored_on, created_at, updated_at) VALUES ('town', '', ?, '', 0, ?, ?, ?)",
                       (day, day, timestamp, timestamp))
