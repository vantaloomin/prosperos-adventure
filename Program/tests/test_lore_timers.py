"""Lore timing (dungeon/lore.py "Timing"): entries that linger, rest, wait, fire on a chance or come one of a group,
counted in story lines, rewound with the story."""
import base64
import json

from conftest import Chunk

from dungeon import lore


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def tavern_book(entries: list[dict]) -> dict:
    """A SillyTavern world info file: entries keyed by uid."""
    book = {'entries': {str(number): {'uid': number, **entry} for number, entry in enumerate(entries)}}
    return {'filename': 'harbour.json', 'data': base64.b64encode(json.dumps(book).encode()).decode('ascii')}


def start(client, entries: list[dict]) -> list[dict]:
    ok(client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'}))
    ok(client.post('/api/import/lorebook', json=tavern_book(entries)))
    return ok(client.get('/api/lore'))['books'][0]['entries']


def said(client, provider, text: str, number: int) -> str:
    """One line told; the narrator's system prompt for it."""
    provider.replies = [[Chunk('The tide turns.'), Chunk('', 'stop')]]
    ok(client.post('/api/story/messages', json={'text': text, 'client_id': f'timer-{number:04d}'}))
    return next(request['system'] for request in reversed(provider.requests) if '## Scene' in request['system'])


def test_an_entry_with_no_timing_fires_as_before(client, provider):
    start(client, [{'key': ['Pellam'], 'content': 'Pellam owes the tide-wardens.'}])
    assert 'Pellam owes' in said(client, provider, 'I ask after Pellam.', 1)
    assert 'Pellam owes' in said(client, provider, 'Pellam again.', 2)


def test_a_lingering_entry_stays_for_its_lines_after_the_keyword_is_gone(client, provider):
    start(client, [{'key': ['Pellam'], 'content': 'Pellam owes the tide-wardens.', 'sticky': 2}])
    told = [said(client, provider, text, number) for number, text in enumerate(
        ['I ask after Pellam.', 'I wait.', 'I wait some more.', 'I order fish.', 'I eat.', 'I pay.'], 1)]
    # Fired on line 1, it lingers through line 3; by line 4 the keyword has left the last few messages too.
    assert ['Pellam owes' in system for system in told] == [True, True, True, False, False, False]


def test_a_resting_entry_is_left_out_for_its_lines(client, provider):
    start(client, [{'key': ['bell'], 'content': 'The bell rings for the drowned.', 'cooldown': 2}])
    told = [said(client, provider, f'I hear the bell, time {number}.', number) for number in range(1, 5)]
    assert ['rings for the drowned' in system for system in told] == [True, False, False, True]


def test_a_waiting_entry_cannot_fire_before_its_line(client, provider):
    start(client, [{'key': ['bell'], 'content': 'The bell rings for the drowned.', 'delay': 3}])
    told = [said(client, provider, f'I hear the bell, time {number}.', number) for number in range(1, 4)]
    assert ['rings for the drowned' in system for system in told] == [False, False, True]


def test_chance_rolls_the_same_for_the_same_line_and_branch_and_anew_on_another():
    rolls = [lore.dice('first', line, 'e1').randrange(100) for line in range(1, 40)]
    assert rolls == [lore.dice('first', line, 'e1').randrange(100) for line in range(1, 40)]
    assert any(roll < 50 for roll in rolls) and any(roll >= 50 for roll in rolls)
    assert rolls != [lore.dice('other', line, 'e1').randrange(100) for line in range(1, 40)]


def test_chance_zero_never_fires(client, provider):
    start(client, [{'key': ['gulls'], 'content': 'Gulls cry over the slate roofs.', 'useProbability': True,
                    'probability': 0}])
    assert all('Gulls cry' not in said(client, provider, 'I watch the gulls.', number) for number in range(1, 4))


def test_one_entry_of_a_group_goes_in(client, provider):
    start(client, [{'key': ['harbour'], 'content': f'Harbour mood {number}.', 'group': 'mood', 'groupWeight': 10}
                   for number in range(3)])
    for number in range(1, 5):
        system = said(client, provider, f'I walk the harbour, time {number}.', number)
        assert sum(f'Harbour mood {mood}.' in system for mood in range(3)) == 1


def test_going_back_rewinds_the_timers(client, provider):
    start(client, [{'key': ['bell'], 'content': 'The bell rings for the drowned.', 'cooldown': 5}])
    said(client, provider, 'I wait.', 1)
    assert 'rings for the drowned' in said(client, provider, 'I hear the bell.', 2)
    assert 'rings for the drowned' not in said(client, provider, 'The bell again.', 3)
    line_two = [row for row in ok(client.get('/api/story'))['messages'] if row['role'] == 'user'][1]
    ok(client.post('/api/story/back', json={'message_id': line_two['id']}))
    said(client, provider, 'I wait some more.', 4)
    assert 'rings for the drowned' in said(client, provider, 'I hear the bell.', 5)


def test_the_importer_reads_timing_and_the_editor_sets_it_within_range(client):
    entries = start(client, [{'key': ['bell'], 'content': 'The bell.', 'sticky': 3, 'cooldown': 4, 'delay': 2,
                              'useProbability': True, 'probability': 40, 'group': 'sounds', 'groupWeight': 7},
                             {'key': ['gulls'], 'content': 'Gulls.', 'probability': 10},
                             {'key': ['x'], 'content': 'Always.', 'constant': True}])
    assert entries[0]['timing'] == {'sticky': 3, 'cooldown': 4, 'delay': 2, 'chance': 40, 'group_weight': 7,
                                    'group': 'sounds'}
    # Probability counts only with useProbability on, as in SillyTavern.
    assert entries[1]['timing']['chance'] == 100
    changed = ok(client.put(f"/api/lore/entries/{entries[1]['id']}/timing", json={'sticky': 1, 'group': ' birds '}))
    assert changed['books'][0]['entries'][1]['timing'] | {} == {'sticky': 1, 'cooldown': 0, 'delay': 0, 'chance': 100,
                                                                'group_weight': 100, 'group': 'birds'}
    assert client.put(f"/api/lore/entries/{entries[1]['id']}/timing", json={'chance': 101}).status_code == 422
    assert client.put(f"/api/lore/entries/{entries[2]['id']}/timing", json={'sticky': 1}).status_code == 422


def test_the_lore_list_shows_where_each_timed_entry_stands(client, provider):
    entries = start(client, [{'key': ['bell'], 'content': 'The bell.', 'cooldown': 3},
                             {'key': ['gulls'], 'content': 'Gulls.', 'delay': 5}])
    assert entries[0]['timer'] == {'state': 'ready', 'lines': 0} and entries[1]['timer']['state'] == 'waiting'
    said(client, provider, 'I hear the bell.', 1)
    listed = ok(client.get('/api/lore'))['books'][0]['entries']
    assert listed[0]['timer'] == {'state': 'resting', 'lines': 3}
