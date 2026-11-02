"""Fixes from the dice, haggling and bonds playtest (2026-10-23): a friendly contest starts no fight, spending the
day somewhere goes there, the day ends with the evening, and sleep from the small hours wakes in the morning."""
from datetime import datetime

from conftest import Chunk, tell
from test_combat import roll
from test_lies import begin

from dungeon import combat, labour, rest, story, story_clock


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_an_arm_wrestle_is_no_fight():
    contest = roll('I arm-wrestle the biggest logger in the place for a round of drinks', 'failure')
    assert combat.stand_in([contest]) is None
    assert combat.stand_in([roll('I punch the biggest logger', 'failure')])['name'] == 'the biggest logger'
    assert not combat.fighting_words('I race the lad to the mill for a coin')


def test_the_day_runs_to_the_evening():
    afternoon = datetime(2026, 10, 1, 16, 10)
    assert story_clock.minutes_for('I spend the day around the Felled Oak', False, afternoon) == 170
    assert story_clock.minutes_for('I spend the day around the Felled Oak', False, datetime(2026, 10, 1, 8)) == 600
    # Begun in the evening, the day is done: an hour passes, not the night.
    assert story_clock.minutes_for('I spend the day around the Felled Oak', False, datetime(2026, 10, 1, 21)) == 60
    assert story_clock.minutes_for('I spend the whole day hauling logs', False, datetime(2026, 10, 1, 18, 50)) == 60
    # Work is paid for no more than the time it took.
    assert labour.minutes('I spend the day hauling logs for the yard.', 170) == 170


def test_sleep_from_the_small_hours_wakes_in_the_morning():
    assert rest.first_night(datetime(2026, 10, 1, 3, 59), morning=True) == 181
    assert rest.first_night(datetime(2026, 10, 1, 3, 59)) == rest.NIGHT_MINUTES
    assert rest.UNTIL_MORNING.search('I sleep until morning.')
    assert rest.first_night(datetime(2026, 10, 1, 22)) == 9 * 60
    assert rest.first_night(datetime(2026, 10, 1, 12)) == rest.NIGHT_MINUTES
    # Real-time pass: "until morning" at 14:59 slept to 22:59. It runs to the next morning from any hour, and at
    # 06:59 or mid-morning it is morning already.
    assert rest.first_night(datetime(2026, 10, 1, 14, 59), morning=True) == 16 * 60 + 1
    assert rest.awake(datetime(2026, 10, 1, 6, 59)) and rest.awake(datetime(2026, 10, 1, 9))
    assert not rest.awake(datetime(2026, 10, 1, 14, 59)) and not rest.awake(datetime(2026, 10, 1, 3, 59))


def test_spending_the_day_somewhere_goes_there(client, connected, provider, app):
    begin(client)
    provider.replies = [[Chunk('The market is loud.'), Chunk('', 'stop')]]
    tell(client, 'I spend the day at the Crossroads market.', 'story-0001')
    assert ok(client.get('/api/story'))['scene']['place']['id'] == 'crossroads-market'
    line = next(item for item in ok(client.get('/api/story'))['messages'] if item['role'] == 'user')
    with app.state.database.connect() as connection:
        assert story.line_minutes(connection, line['id']) > story_clock.ACROSS_TOWN_MINUTES
