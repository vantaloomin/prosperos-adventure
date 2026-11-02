"""Automatic backups of every world (dungeon/auto_backup.py)."""
from datetime import datetime, timedelta

from dungeon import auto_backup


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_seven_days_then_four_weeks_are_kept():
    start = datetime(2026, 10, 9, 3, 0)
    entries = [(start - timedelta(days=day), f'auto-{day}') for day in range(60)]
    kept = auto_backup.kept(entries)
    assert {f'auto-{day}' for day in range(7)} <= kept
    assert len(kept) == 7 + 4
    assert 'auto-59' not in kept
    # The weeklies are whole weeks before the dailies' oldest week, so they reach back past a month.
    weekly = sorted(int(name.split('-')[1]) for name in kept - {f'auto-{day}' for day in range(7)})
    oldest_daily_week = (start - timedelta(days=6)).isocalendar()[:2]
    assert all((start - timedelta(days=day)).isocalendar()[:2] != oldest_daily_week for day in weekly)
    assert weekly[-1] >= 28


def test_a_world_nobody_opened_is_not_backed_up_again(tmp_path):
    folder = tmp_path / 'backups'
    folder.mkdir()
    database = tmp_path / 'dungeon.sqlite3'
    database.write_bytes(b'')
    later = datetime.now() + timedelta(days=3)
    (folder / f"auto-{later.strftime('%Y%m%dT%H%M%S')}.zip").write_bytes(b'')
    assert not auto_backup.due(database, later + timedelta(days=2), 'daily')
    assert auto_backup.due(tmp_path / 'other' / 'dungeon.sqlite3', later, 'daily')
