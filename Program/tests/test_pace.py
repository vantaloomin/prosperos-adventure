"""Turn speed (dungeon/pace.py): the budget, timed steps, streaming and extraction after the reply."""
import json

from conftest import Chunk, tell

from dungeon import pace, record


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def route(client, job):
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': job, 'profile_id': profiles[0]['id']}))


def test_plain_lines_are_obvious_and_anything_uncertain_or_commanding_is_not():
    assert pace.obvious('I walk to the bar. "Evening," I say.')
    assert pace.obvious('I ask the barkeep about rooms and order a drink.')
    assert not pace.obvious('I tell the guard to stand aside.')
    assert not pace.obvious('I look around and pick the lock.')
    assert not pace.obvious('I punch him.')
    # Playtest M4b: picking someone out is looking; watching for watchers is a roll.
    assert pace.obvious('I pick out the loudest thug in the room.')
    assert not pace.obvious('I look about the square for anyone watching me.')


def test_the_budget_is_automatic_by_where_the_model_runs(app):
    with app.state.database.connect() as connection:
        assert pace.budget_for(connection, {'provider': 'local', 'base_url': ''}) == 90
        assert pace.budget_for(connection, {'provider': 'compatible', 'base_url': 'http://127.0.0.1:8080/v1'}) == 90
        assert pace.budget_for(connection, {'provider': 'anthropic', 'base_url': 'https://api.anthropic.com/v1'}) == 30


def test_an_obvious_line_skips_the_referee_model(client, connected, provider):
    route(client, 'referee')
    provider.replies = [reply('The barman nods.')]
    tell(client, 'I sit down at the bar.', 'story-0001')
    assert len(provider.requests) == 1 and 'Referee' not in provider.requests[0]['system']


class Slow:
    """A clock that moves a minute every time it is read: every turn is over any budget."""

    def __init__(self):
        self.now = 0

    def __call__(self):
        self.now += 60
        return self.now


def test_over_budget_the_rewrite_and_the_contradiction_check_give_way(client, connected, provider, app):
    ok(client.put('/api/settings', json={'turn_budget': 30, 'show_odds': True}))
    app.state.pace_clock = Slow()
    with app.state.database.connect(write=True) as connection:
        record.add(connection, 'death', 'Old Tom', 'Old Tom drowned off the pier.', app.state.database.now())
    # Old Tom is named and the prose has a strong tell, but no time is left: one call, the narrator's.
    provider.replies = [reply('Old Tom waves from the door -- a testament to the night.')]
    tell(client, 'I sit down at the bar.', 'story-0001')
    assert len(provider.requests) == 1
    line = ok(client.get('/api/story'))['messages'][-2]
    assert line['pace']['skipped'] == ['rewrite', 'contradiction'] and line['pace']['budget'] == 30
    assert not {'rewrite', 'contradiction'} & set(line['pace']['steps'])
    # The dash fix costs nothing and always runs.
    assert '--' not in ok(client.get('/api/story'))['messages'][-1]['text']


def test_the_narration_streams_and_facts_land_after_it(client, connected, provider, app):
    route(client, 'continuity')
    provider.replies = [[Chunk('The bouncer swings. '), Chunk('He breaks your nose.'), Chunk('', 'stop')],
                        reply('{"facts": [{"kind": "wound", "subject": "you", "text": "Your nose is broken."}]}')]
    with client.stream('POST', '/api/story/messages/stream',
                       json={'text': 'I shove the bouncer.', 'client_id': 'story-0001'}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line]
    # A sentence at a time, as the in-character guard passes them on.
    assert [event['text'] for event in events if 'text' in event] == ['The bouncer swings. ', 'He breaks your nose.']
    done = events[-1]['done']
    assert done['reply']['text'] == 'The bouncer swings. He breaks your nose.' and done['message']['text'] == 'I shove the bouncer.'
    assert [entry['text'] for entry in ok(client.get('/api/story/journal'))['entries']] == ['Your nose is broken.']
    with app.state.database.connect() as connection:
        steps = json.loads(pace.saved(connection, done['message']['id']))['steps']
    assert {'narrator', 'extraction', 'summary'} <= set(steps)


def test_a_streamed_turn_without_a_model_says_why(client):
    with client.stream('POST', '/api/story/messages/stream',
                       json={'text': 'Hello.', 'client_id': 'story-0001'}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line]
    assert events == [{'error': 'Add a text model in Settings > Models to tell the story.', 'code': 'no_connection',
                       'status': 409}]


def test_only_a_name_counts_as_a_first_name_for_the_dead():
    assert pace.named_dead({'Old Tom'}, 'Old Tom waves.') == ['Old Tom']
    assert pace.named_dead({'Hesk Varro'}, 'Hesk waves.') == ['Hesk Varro']
    # A record subject that is not a name is matched whole, never by its first word.
    assert pace.named_dead({'five fresh graves by the road'}, 'It is five, maybe six.') == []
    assert pace.named_dead({'the warden'}, 'A warden waits.') == []
