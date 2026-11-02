"""Observance days and seasons for modern US cities, from dungeon/almanac/data/observances.json.

These add to the world's holiday calendars (dungeon/world/data/holidays.json): the world data
decides public holidays and days off; this adds the rest of what a person living there notices,
like Super Bowl Sunday, Pride Month, tax season, the NFL season or the clocks changing.
A rule is a world holiday rule (month and day; month, weekday and nth; or days from Easter), a
world holiday's id (`holiday`), or a table of dates by year (`dates`), plus an optional `days` offset.
"""
import json
from datetime import date, timedelta
from functools import cache
from pathlib import Path

from dungeon.world import catalog, generators

DATA = Path(__file__).with_name('data') / 'observances.json'
CALENDAR = 'us'


@cache
def data() -> dict:
    return json.loads(DATA.read_text(encoding='utf-8'))


def applies(city: dict | None) -> bool:
    """Observances are for cities that keep the modern US calendar."""
    return bool(city) and catalog.calendar_id(city) == CALENDAR


def on(rule: dict, year: int, city: dict) -> date | None:
    """The date a rule names in this year, or None when it names none (a year missing from a table)."""
    if 'dates' in rule:
        found = rule['dates'].get(str(year))
        day = date.fromisoformat(f'{year}-{found}') if found else None
    elif 'holiday' in rule:
        holiday = next((item for item in generators.city_holidays(city) if item['id'] == rule['holiday']), None)
        day = generators.holiday_date(holiday, year) if holiday else None
    else:
        day = generators.holiday_date({'easter': None, 'day': None, 'weekday': None, 'nth': None} | rule, year)
    return day + timedelta(days=rule.get('days', 0)) if day else None


def days_between(city: dict, start: date, end: date) -> list[dict]:
    """Observance days from `start` to `end` inclusive, in date order, each with its `date`."""
    found = []
    for item in data()['days']:
        for year in range(start.year, end.year + 1):
            day = on(item['on'], year, city)
            if day and start <= day <= end:
                found.append({'id': item['id'], 'name': item['name'], 'date': day})
    return sorted(found, key=lambda item: (item['date'], item['id']))


def spans_on(city: dict, day: date) -> list[dict]:
    """Seasons going on this date, each with the date it ends. A span that runs past New Year starts the
    year before it ends."""
    found = []
    for item in data()['spans']:
        for year in (day.year - 1, day.year):
            start = on(item['from'], year, city)
            end = start and (on(item['to'], year, city) if 'dates' in item['to'] else
                             next((found_end for found_end in (on(item['to'], year, city),
                                                               on(item['to'], year + 1, city))
                                   if found_end and found_end >= start), None))
            if start and end and start <= day <= end:
                found.append({'id': item['id'], 'name': item['name'], 'until': end})
    return found


def gatherings(city: dict, day: date) -> list[dict]:
    """Parties and nights out on this date (Halloween parties, Super Bowl watch parties), as the life
    simulation's annual happenings: a free evening can go to one, the way it can go to a festival."""
    if not applies(city):
        return []
    named = {item['id'] for item in generators.holidays(city, day)} | {item['id'] for item in
                                                                        days_between(city, day, day)}
    return [{'id': f"gathering-{item['on']}", 'name': item['name'], 'kind': 'event', 'city': city['name'],
             'neighborhood': '', 'summary': item['name']} for item in data()['gatherings'] if item['on'] in named]
