"""Day labour is paid the town's day wage (dungeon/labour.py)."""
from conftest import Chunk, tell

from dungeon import happenings, labour, story, story_clock
from dungeon.world import catalog


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_hours_of_work_are_counted_and_other_lines_earn_nothing():
    assert labour.minutes('I spend the day hauling logs for the yard.') == labour.DAY_MINUTES
    assert labour.minutes('I take an all-day hauling job at the yard.') == labour.DAY_MINUTES
    assert labour.minutes('I work the saws for three hours.') == 3 * 60
    assert labour.minutes('I spend the afternoon stacking timber.') == 4 * 60
    assert labour.minutes('I work the saws for twenty minutes.') == 0
    assert labour.minutes('I spend the day sleeping off the ale.') == 0
    assert labour.minutes('I spend the afternoon working on my own sword.') == 0
    assert labour.minutes('I spend the evening on my coursework.') == 0
    assert story_clock.minutes_for('I take an all-day hauling job at the yard.', False) == 10 * 60


def test_a_day_hauling_pays_the_wage_once(client, connected, provider, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    before = ok(client.get('/api/story/gear'))['coins']
    wage = happenings.wage(catalog.city('kingswood'))
    provider.replies = [[Chunk('You haul.'), Chunk('', 'stop')]]
    tell(client, 'I spend the day hauling logs for the yard.', 'story-0001')
    assert '## Work for hire (decided by the game)' in provider.requests[-1]['system']
    # Paid for the day as long as it ran, to the evening (dungeon/story_clock.py day_left).
    line = next(item for item in ok(client.get('/api/story'))['messages'] if item['role'] == 'user')
    with app.state.database.connect() as connection:
        wage = wage * story.line_minutes(connection, line['id']) // labour.DAY_MINUTES
    assert ok(client.get('/api/story/gear'))['coins'] == before + wage
    # Telling the same line again pays nothing more.
    provider.replies = [[Chunk('You haul again.'), Chunk('', 'stop')]]
    ok(client.post('/api/story/retry'))
    assert ok(client.get('/api/story/gear'))['coins'] == before + wage
