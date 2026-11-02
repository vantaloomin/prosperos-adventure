"""Prospero dice (dungeon/rules/marvel.py), checked against rolls from Mabry Curve's roll log."""
import random

import pytest

from dungeon.rules import ladder, marvel


@pytest.mark.parametrize(('natural', 'total', 'band'), [
    (10, 0, 'critical_failure'),     # T001 Rachel: a natural 10 at +10.
    (6, 27, 'critical_failure'),     # T020 Grant: a natural 6 is critical whatever the die adds.
    (24, 4, 'failure'),              # T003 Rachel: low, but not a natural 10 or less.
    (13, 3, 'failure'),
    (55, 45, 'failure_upside'),      # T004
    (41, 50, 'failure_upside'),
    (51, 51, 'success_cost'),
    (75, 65, 'success_cost'),        # T001 Grant
    (72, 71, 'success'),
    (97, 87, 'success'),             # A natural 97 at +10 is a plain success.
    (76, 90, 'critical_success'),    # T007 Grant: 76 + 4 at -10.
    (100, 90, 'critical_success'),
])
def test_bands_match_the_mabry_curve_log(natural, total, band):
    assert marvel.band(natural, total) == band


def test_the_stat_die_grows_with_the_stat():
    assert [marvel.die_for(value) for value in (None, 1, 7, 8, 10, 12, 14, 30)] == [None, 4, 4, 6, 8, 10, 12, 12]


def test_a_roll_adds_the_die_and_takes_off_the_shift():
    result = marvel.roll(14, 'hard', random.Random(3))
    assert result['die'] == 12 and 1 <= result['bonus'] <= 12 and result['shift'] == 10
    assert result['total'] == result['natural'] + result['bonus'] - 10
    assert result['band'] == marvel.band(result['natural'], result['total']) and result['band'] in ladder.BANDS
    # No stats, no die.
    bare = marvel.roll(None, 'normal', random.Random(3))
    assert bare['die'] is None and bare['bonus'] == 0


def test_harder_tasks_fail_more_often():
    rng = random.Random(7)
    def wins(difficulty):
        return sum(ladder.succeeded(marvel.roll(10, difficulty, rng)['band']) for _ in range(4000))
    assert wins('easy') > wins('normal') > wins('extreme')
