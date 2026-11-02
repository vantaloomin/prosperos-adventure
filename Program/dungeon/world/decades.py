"""Decades: a modern world that runs in a past year keeps to that year (ported from Prospero Companion's Back when).

Havenbrooke is autumn 2009. There, by rule and with no model call:

- careers and pastimes with `years` (`[from, until]`, either may be null) are only offered in those years: nobody
  drives for a ride-hailing app in 2009, and a video store clerk is a job then but not today (catalog.careers_for);
- the narrator is told the year (`prompt_text`): the decade's phones, computers and media, the slang of the year,
  a few books, shows and songs out by then (world/data/media/modern.json), prices in that year's money, and the
  things that don't exist yet;
- narration that names one of those later things anyway (Instagram in 2009) is caught (`anachronisms`): the story
  asks the model for one rewrite, and a passage that still names it is flagged for the player (dungeon/story.py);
- pictures are told the year, so clothes, phones and cars are of it (dungeon/art.py).

Which year: a modern city's own year is its `names.year` (the year its people's ages count back from; Haven's is
2009), and in play the story clock's year. Either counts only when it is before this year: a world in the present
changes nothing. A city of another era (fantasy, 1895) is never dated here.
"""
import hashlib
import json
import re
from datetime import date, datetime
from functools import cache
from pathlib import Path

DATA = Path(__file__).parent / 'data'
MODERN_ERAS = ('modern',)
PARTS = ((3, 'early'), (6, 'mid'), (9, 'late'))
# Media for the narrator: shows that started within this many years, books and songs within these.
SHOW_YEARS, BOOK_YEARS, SONG_YEARS = 4, 2, 1
SHOWS, BOOKS, SONGS = 5, 3, 5
PRICES = 6
# Country names to the media banks' region tags.
REGIONS = {'us': ('us', 'usa', 'united states'), 'uk': ('uk', 'gb', 'united kingdom', 'england', 'scotland', 'wales'),
           'jp': ('jp', 'japan'), 'kr': ('kr', 'korea', 'south korea')}


@cache
def table() -> dict:
    return json.loads((DATA / 'decades.json').read_text(encoding='utf-8'))


@cache
def media_bank() -> dict:
    return json.loads((DATA / 'media' / 'modern.json').read_text(encoding='utf-8'))


@cache
def pastime_bank() -> list[dict]:
    return json.loads((DATA / 'hobbies' / 'catalogue.json').read_text(encoding='utf-8'))['hobbies']


def this_year() -> int:
    """The real year: a world before it is in the past."""
    return date.today().year


# --- The year and its decade ---

def modern(city: dict | None) -> bool:
    return ((city or {}).get('era') or 'modern') in MODERN_ERAS


def city_year(city: dict | None) -> int | None:
    """A modern city's own year (its names.year), or None."""
    return ((city or {}).get('names') or {}).get('year') if modern(city) else None


def year_of(city: dict | None, moment: datetime | date | None = None, present: int | None = None) -> int | None:
    """The past year a modern city is in: the story's (`moment`) when given, else the city's own; None in the present
    and in a city of another era."""
    if not modern(city):
        return None
    year = moment.year if moment else city_year(city)
    return year if year and year < (present or this_year()) else None


def decade(year: int) -> str:
    """'2000s' for 2009."""
    return f'{year // 10 * 10}s'


def part(year: int) -> str:
    """Early, mid or late in its decade."""
    return next(word for last, word in PARTS if year % 10 <= last)


def rules(year: int) -> dict:
    """The decade's own rules; {} for one the table has none for."""
    return table()['decades'].get(decade(year)) or {}


# --- Years on careers and pastimes ---

def in_years(item: dict, year: int) -> bool:
    """Whether something with optional `years` ([from, until], either null) exists in `year`."""
    years = item.get('years')
    if not years:
        return True
    start, until = years
    return (start is None or start <= year) and (until is None or year <= until)


def offered_year(city: dict | None) -> int | None:
    """The year a modern city's careers are offered for: its own past year, else this one (so work that ended, a
    video store clerk, isn't offered today either). None for a city of another era."""
    return (year_of(city) or this_year()) if modern(city) else None


def current(items, city: dict | None) -> list:
    """The items that exist in the city's year; all of them in a city of another era."""
    year = offered_year(city)
    return [item for item in items if year is None or in_years(item, year)]


# --- Prices ---

def level(code: str, year: int) -> float:
    """The currency's price level in `year`: the listed year's, or a steady rate between the two nearest."""
    prices = table()['prices']
    levels = {int(key): value for key, value in (prices['levels'].get(code) or
                                                 prices['levels'][prices['fallback']]).items()}
    year = min(max(year, min(levels)), max(levels))
    if year in levels:
        return levels[year]
    before = max(key for key in levels if key < year)
    after = min(key for key in levels if key > year)
    return levels[before] * (levels[after] / levels[before]) ** ((year - before) / (after - before))


def share(city: dict, year: int) -> float:
    """What the city's written prices come to in `year`: they are in its own year's money (names.year), else
    today's. 0.65 for a city written in today's dollars, in 2009."""
    code = (city.get('currency') or {}).get('code') or 'USD'
    written = city_year(city) or table()['prices']['base']
    return level(code, year) / level(code, written)


def figure(value: float) -> str:
    return f'{value:,.0f}' if value >= 10 else f'{value:,.2f}'


def prices_text(city: dict, year: int) -> str:
    """A few of the city's typical prices in `year`'s money."""
    found = (city.get('prices') or [])[:PRICES]
    if not found or (city.get('currency') or {}).get('code') == 'none':
        return ''
    rate, symbol = share(city, year), (city.get('currency') or {}).get('symbol') or '$'
    return '; '.join(f"{item['item']} {symbol}{figure(item['low'] * rate)}–{symbol}{figure(item['high'] * rate)}"
                     for item in found)


# --- What the year has ---

def slang(year: int) -> list[str]:
    """Slang people say aloud in `year`."""
    return [word['say'] for word in table()['slang']['words'] if in_years(word, year)]


def pastimes(year: int) -> list[str]:
    """Pastimes particular to their years (LAN parties, scrapbooking), out of those with `years`."""
    return [item['label'] for item in pastime_bank() if item.get('years') and in_years(item, year)
            and 'modern' in item.get('eras', ())]


def region(city: dict | None) -> str | None:
    country = ((city or {}).get('country') or '').casefold()
    return next((tag for tag, names in REGIONS.items() if country in names), None)


def rank(seed: str, title: str) -> str:
    return hashlib.sha1(f'{seed}|{title}'.encode()).hexdigest()


def media(city: dict | None, year: int, seed: str = '') -> dict[str, list[str]]:
    """A few real books, shows and songs out by `year` and new then, from the city's country where the bank tags
    one: what's on TV, on the radio and in the shops. The same ones all year, for the same seed."""
    tag, bank = region(city), media_bank()

    def chosen(kind: str, back: int, count: int) -> list[str]:
        pool = [entry for entry in bank[kind] if year - back <= entry[2] <= year]
        local = [entry for entry in pool if tag and tag in entry[3].split()]
        pool = local if len(local) >= count else pool
        pool = sorted(pool, key=lambda entry: rank(f'{seed}|{year}|{kind}', entry[0]))[:count]
        return [f'{entry[0]} ({entry[1]})' for entry in sorted(pool, key=lambda entry: entry[2])]

    return {'shows': chosen('show', SHOW_YEARS, SHOWS), 'books': chosen('book', BOOK_YEARS, BOOKS),
            'songs': chosen('music', SONG_YEARS, SONGS)}


# --- Things from a later year ---

@cache
def later_patterns() -> tuple[tuple[re.Pattern, int, str], ...]:
    named = [(pattern, first, label) for pattern, first, label in table()['later']['named']]
    named += [(word['check'], word['years'][0], f"the slang \"{word['say']}\"")
              for word in table()['slang']['words'] if word.get('check')]
    return tuple((re.compile(pattern, re.IGNORECASE), first, label) for pattern, first, label in named)


def to_come(year: int) -> list[str]:
    """What doesn't exist yet in `year`, soonest first."""
    found = sorted((first, label) for _pattern, first, label in later_patterns() if first > year)
    return list(dict.fromkeys(label for _first, label in found))


def anachronisms(text: str, year: int | None) -> list[dict]:
    """Each thing `text` names from after `year`: {'text', 'label', 'first'}; none when there is no past year."""
    if not year or not text:
        return []
    found = {}
    for pattern, first, label in later_patterns():
        if first > year and (match := pattern.search(text)):
            found.setdefault(label, {'text': match[0], 'label': label, 'first': first})
    return list(found.values())


def why(finding: dict, year: int) -> str:
    return (f"\"{finding['text']}\": the story is in {year}, and {finding['label']} only came in {finding['first']}. "
            'Use what people had then.')


# --- The narrator's and the pictures' words ---

def prompt_text(city: dict | None, moment: datetime | date | None, seed: str = '', present: int | None = None) -> str:
    """The year for the narrator, in a modern world that runs in a past year; '' otherwise."""
    year = year_of(city, moment, present)
    if not year:
        return ''
    found = rules(year)
    lines = [f"## The year: {year}",
             f"The story is set in {year}, the {part(year)} {decade(year)}. Everything people have, say, wear, watch "
             f"and pay is of {year}: nothing from a later year."]
    if found.get('things'):
        lines.append(found['things'])
    if words := slang(year):
        lines.append(f"Slang of {year}, for dialogue and sparingly: {', '.join(words)}.")
    shown = media(city, year, seed)
    for label, key in (('On TV', 'shows'), ('On the radio', 'songs'), ('In the bookshops', 'books')):
        if shown[key]:
            lines.append(f"{label} around now (real titles, name them only in passing): {'; '.join(shown[key])}.")
    if hobbies := pastimes(year):
        lines.append(f"Pastimes of the time: {', '.join(hobbies)}.")
    if money := prices_text(city or {}, year):
        lines.append(f"Money is {year} money. Typical prices: {money}.")
    if later := to_come(year):
        lines.append(f"Not yet invented or not yet common in {year}, so never named: {', '.join(later)}.")
    return '\n'.join(lines)


def picture_text(city: dict | None, moment: datetime | date | None, present: int | None = None) -> str:
    """How a picture shows the year; '' in the present and in a city of another era."""
    year = year_of(city, moment, present)
    if not year:
        return ''
    return (rules(year).get('picture') or '').replace('{year}', str(year)).replace('{part}', part(year))
