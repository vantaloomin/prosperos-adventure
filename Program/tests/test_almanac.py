"""The built-in calendar (dungeon/almanac/): observances, seasons, daylight and the chat context section."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from dungeon.almanac import days, sky
from dungeon.world import catalog
from dungeon.world.source import CatalogWorld

EASTERN = ZoneInfo('America/New_York')


def local(moment):
    return moment.astimezone(EASTERN).strftime('%H:%M') if moment else None


def test_sun_times_match_published_tables_within_a_few_minutes():
    def near(moment, expected):
        hours, minutes = map(int, expected.split(':'))
        actual = moment.astimezone(EASTERN)
        return abs(actual.hour * 60 + actual.minute - hours * 60 - minutes) <= 4
    rise, set_ = sky.sun(date(2026, 6, 21), 39.29, -76.61)  # Baltimore, longest day: 5:39 and 8:37 EDT
    assert near(rise, '05:39') and near(set_, '20:37')
    rise, set_ = sky.sun(date(2026, 12, 21), 40.71, -74.0)  # New York, shortest day: 7:16 and 4:32 EST
    assert near(rise, '07:16') and near(set_, '16:32')
    assert sky.sun(date(2026, 6, 21), 70.0, 20.0) == (None, None)  # midnight sun


def test_moon_phases_on_known_dates():
    assert sky.moon(datetime(2026, 10, 26, 12, tzinfo=timezone.utc)) == 'full moon'
    assert sky.moon(datetime(2026, 11, 9, 12, tzinfo=timezone.utc)) == 'new moon'
    assert sky.moon(datetime(2026, 10, 5, 12, tzinfo=timezone.utc)) == 'waning crescent'


def test_observances_and_seasons_for_a_modern_us_city():
    baltimore = catalog.city('baltimore', {})
    assert days.applies(baltimore) and not days.applies(catalog.city('london-1895', {}))
    found = {item['id']: item['date'] for item in days.days_between(baltimore, date(2026, 10, 1), date(2027, 3, 1))}
    assert found['indigenous-peoples-day'] == date(2026, 10, 12)
    assert found['dst-ends'] == date(2026, 11, 1)
    assert found['black-friday'] == date(2026, 11, 27)  # from the world's Thanksgiving
    assert found['super-bowl-sunday'] == date(2027, 2, 14)
    assert found['lunar-new-year'] == date(2027, 2, 6)
    assert found['election-day'] == date(2026, 11, 3)
    # A season that runs past New Year counts from the autumn before it.
    january = {item['id'] for item in days.spans_on(baltimore, date(2027, 1, 5))}
    assert {'nfl-season', 'nba-season', 'nhl-season'} <= january and 'mlb-season' not in january
    assert 'pride-month' in {item['id'] for item in days.spans_on(baltimore, date(2026, 6, 10))}


def test_parties_join_the_days_happenings_in_modern_us_cities_only():
    world = CatalogWorld()
    assert [item['name'] for item in world.happenings('baltimore', date(2026, 10, 31))] == ['Halloween parties']
    assert world.happenings('baltimore', date(2026, 10, 30)) == []
    assert not any(item['id'].startswith('gathering-') for item in world.happenings('london-1895', date(1895, 12, 31)))
