"""Real-time living worlds (dungeon/story_clock.py caught_up): a world can keep moving while the app is closed."""
from datetime import timedelta

from test_lies import begin
from test_travel import ok

from dungeon import story, story_clock, tiers


def test_havenbrooke_lives_in_real_time_and_vallarith_on_story_time():
    assert tiers.clock('havenbrooke') == 'real_time' and tiers.clock('vallarith') == 'story'


def passed(app, clock, text, client_id, hours=0):
    database = app.state.database
    clock.advance(timedelta(hours=hours))
    with database.connect() as connection:
        before = story_clock.now(connection, database.clock)
    user, _ = story.received(database, text, client_id)
    with database.connect() as connection:
        return int((story_clock.now(connection, database.clock) - before).total_seconds() // 60), user


def test_story_time_ignores_the_hours_away(client, app, clock):
    begin(client)
    passed(app, clock, 'I look around.', 'c1')
    assert passed(app, clock, 'I look around again.', 'c2', hours=5)[0] == story_clock.TALK_MINUTES


def test_real_time_passes_the_hours_away_and_tells_the_narrator(client, app, clock):
    begin(client)
    ok(client.put('/api/story/table', json={'clock': 'real_time'}))
    passed(app, clock, 'I look around.', 'c1')
    minutes, user = passed(app, clock, 'I look around again.', 'c2', hours=29)
    assert minutes == 29 * 60 + story_clock.TALK_MINUTES
    with app.state.database.connect() as connection:
        assert story.away_text(connection, user['id']).startswith(
            "## While the player was away (decided by the game)\n- 1 day and 5 hours passed in the world")
    # A few real minutes between lines pass too, with nothing said of them.
    minutes, user = passed(app, clock, 'I sit down.', 'c3', hours=0.05)
    assert minutes == 3 + story_clock.TALK_MINUTES
    with app.state.database.connect() as connection:
        assert story.away_text(connection, user['id']) == ''
    # However long the app was closed, at most thirty days pass.
    assert passed(app, clock, 'I stand up.', 'c4', hours=24 * 90)[0] == story_clock.MOST_AWAY + story_clock.TALK_MINUTES


def test_turning_real_time_on_later_starts_from_then(client, app, clock):
    begin(client)
    passed(app, clock, 'I look around.', 'c1')
    clock.advance(timedelta(hours=10))
    passed(app, clock, 'I look around again.', 'c2')
    ok(client.put('/api/story/table', json={'clock': 'real_time'}))
    assert passed(app, clock, 'I wave.', 'c3', hours=1)[0] == 60 + story_clock.TALK_MINUTES
