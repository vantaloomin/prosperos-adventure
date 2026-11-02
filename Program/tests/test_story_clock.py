"""The story clock (dungeon/story_clock.py): once a campaign starts, the story keeps its own time."""
from datetime import UTC, datetime, timedelta

from conftest import Chunk

from dungeon import story_clock
from dungeon.story import local_moment


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def at(story):
    return datetime.fromisoformat(story['scene']['local_time'])


def test_how_long_a_line_takes():
    assert story_clock.minutes_for('I ask her name.', rolled=False) == 5
    assert story_clock.minutes_for('I punch him.', rolled=True) == 10
    assert story_clock.minutes_for('I wait two hours by the door.', rolled=False) == 120
    assert story_clock.minutes_for('I wait 20 minutes.', rolled=False) == 20
    assert story_clock.minutes_for('We bed down by the fire and sleep.', rolled=False) == 480
    assert story_clock.minutes_for('I walk to the mill.', rolled=False) == 30
    # A stretch of the day spent at something takes it.
    assert story_clock.minutes_for('I spend the day felling trees and come back at dusk.', rolled=True) == 600
    assert story_clock.minutes_for('I work the morning at the saws.', rolled=False) == 240
    assert story_clock.minutes_for('I mend nets for two hours.', rolled=False) == 120


def test_the_story_keeps_its_own_time_once_it_starts(client, connected, clock, provider):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood'}))
    ok(client.delete('/api/story'))
    started = at(ok(client.post('/api/story/start', json={'premade_id': 'tobin-pell'})))
    # The app clock moving on does not move the story.
    clock.instant = clock.now() + timedelta(hours=5)
    assert at(ok(client.get('/api/story'))) == started

    provider.replies = [[Chunk('Fine.'), Chunk('', 'stop')]] * 3
    ok(client.post('/api/story/messages', json={'text': 'I ask the baker for bread.', 'client_id': 'story-0001'}))
    assert at(ok(client.get('/api/story'))) == started + timedelta(minutes=5)
    first = ok(client.post('/api/story/messages', json={'text': 'I wait three hours.', 'client_id': 'story-0002'}))
    assert at(ok(client.get('/api/story'))) == started + timedelta(minutes=185)
    # Out of character takes no time, and moving across town does.
    ok(client.post('/api/story/messages', json={'text': 'OOC: what time is it?', 'client_id': 'story-0003'}))
    places = ok(client.get('/api/story'))['scene']['places']
    moved = ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': places[-1]['id']}))
    assert at(moved) == started + timedelta(minutes=205)

    # Going back puts the clock back too.
    went = ok(client.post('/api/story/back', json={'message_id': first['message']['id']}))
    assert at(went) == started + timedelta(minutes=5)
    # A new story runs on the app clock until it starts again.
    assert at(ok(client.delete('/api/story'))) != started + timedelta(minutes=5)


def test_a_fantasy_city_keeps_no_daylight_saving_and_a_modern_one_does():
    # Playtest m6b: on 25 October Kingswood's clock ran back from 01:54 to 01:04.
    fantasy = {'timezone': 'Europe/London', 'era': 'fantasy'}
    modern = {'timezone': 'America/New_York', 'era': 'modern'}
    before, after = datetime(2026, 10, 25, 0, 54, tzinfo=UTC), datetime(2026, 10, 25, 1, 4, tzinfo=UTC)
    assert local_moment(fantasy, before) < local_moment(fantasy, after)
    assert local_moment(fantasy, datetime(2026, 7, 1, 12, tzinfo=UTC)).hour == 12  # no summer time either
    assert local_moment(modern, datetime(2009, 7, 1, 12, tzinfo=UTC)).hour == 8  # EDT
    assert local_moment(modern, datetime(2009, 12, 1, 12, tzinfo=UTC)).hour == 7  # EST
