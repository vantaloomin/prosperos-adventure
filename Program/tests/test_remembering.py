"""What the narrator is reminded of and what the characters still remember (dungeon/remembering.py)."""
import json

from conftest import tell
from test_travel import Road, ok, reply

from dungeon import record, remembering

NOW = '2026-10-22T00:00:00+00:00'


def fact(connection, kind, subject, text, truth='both'):
    return record.add(connection, kind, subject, text, NOW, truth=truth)


def test_facts_are_chosen_by_relevance_after_every_death_and_promise(app):
    with app.state.database.connect(write=True) as connection:
        fact(connection, 'death', 'Old Tom', 'Old Tom drowned.')
        fact(connection, 'item', 'the ferryman', 'The ferryman keeps a brass bell.')
        for number in range(5):
            fact(connection, 'fact', f'stranger {number}', 'A stranger passed through.')
        text = record.prompt_text(connection, 'I wave to the ferryman.', 3)
    lines = text.splitlines()[1:]
    assert lines[0].startswith('- death, Old Tom') and lines[1].startswith('- item, the ferryman')
    assert lines[2].startswith('- fact, stranger 4') and len(lines) == 3


def test_small_things_fade_big_ones_and_strong_feelings_stay_and_mention_refreshes(app, monkeypatch):
    with app.state.database.connect(write=True) as connection:
        bell = fact(connection, 'item', 'the ferryman', 'The ferryman keeps a brass bell.')
        debt = fact(connection, 'fact', 'Gus', 'You owe Gus forty crowns.')
        hidden = fact(connection, 'secret', 'the bouncer', 'He works for the co-op.', 'world')
        assert (bell['weight'], debt['weight']) == (1, 3)
        monkeypatch.setattr(remembering, 'turn_now', lambda _connection: remembering.FADE[1] + 1)
        assert remembering.faded_ids(connection) == {bell['id']}
        assert 'brass bell. (faded: the character remembers this only vaguely' in record.prompt_text(connection)
        assert 'co-op. (hidden' in record.prompt_text(connection) and hidden['id'] not in remembering.faded_ids(connection)
        # Someone the character feels strongly about stays sharp.
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, "
                           "meetings, notes, fear) VALUES ('f', 'kingswood', 'Hob the ferryman', ?, ?, '1290-05-01', 1, "
                           "'[]', 4)", (NOW, NOW))
        assert remembering.faded_ids(connection) == set()
        connection.execute("DELETE FROM story_people")
        remembering.refresh(connection, 'The ferryman rings his bell.')
        assert remembering.faded_ids(connection) == set()


def test_a_roll_brings_a_faded_detail_back(client, connected, provider, app, monkeypatch):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    with app.state.database.connect(write=True) as connection:
        bell = fact(connection, 'item', 'the ferryman', 'The ferryman keeps a brass bell.')
    monkeypatch.setattr(remembering, 'turn_now', lambda _connection: 100)
    assert ok(client.get('/api/story/journal'))['entries'][0]['faded'] is True
    app.state.dice = Road(95)
    reply(provider, 'It comes back to you: the bell.')
    tell(client, 'I try to remember the ferryman.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert 'The character remembers what they knew of the ferryman clearly again.' in narrator
    with app.state.database.connect() as connection:
        roll = connection.execute('SELECT action, stat FROM story_rolls').fetchone()
        assert (roll['action'], roll['stat']) == ('Recall what they knew of the ferryman', 'Mind')
        assert connection.execute('SELECT turn FROM record_entries WHERE id=?', (bell['id'],)).fetchone()['turn'] == 100


def test_the_contradiction_check_can_be_turned_off_and_the_context_capped(client, connected, provider, app):
    with app.state.database.connect(write=True) as connection:
        fact(connection, 'death', 'Old Tom', 'Old Tom drowned off the pier.')
    ok(client.put('/api/settings', json={'contradiction_check': False, 'context_cap': 4000}))
    reply(provider, 'Old Tom waves from the door.')
    sent = tell(client, 'I look around.', 'story-0001')
    # No rewrite was asked for; the passage is marked for the player instead.
    assert len(provider.requests) == 1
    assert json.loads(sent['reply']['flags'])[0]['dead'] == {'old tom': 'The record says Old Tom is dead.'}
    with app.state.database.connect() as connection:
        assert remembering.room(connection, {'context_tokens': 128000}) == 4000
        assert remembering.room(connection, {'context_tokens': 2000}) == 2000
