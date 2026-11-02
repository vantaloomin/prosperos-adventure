"""The turn loop (dungeon/turn.py): the Referee's actions are rolled on the persona's stats before the narrator
writes, and the narrator is told how each landed."""
import json
import random

from conftest import Chunk, tell

from dungeon.rules import marvel


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_an_uncertain_action_is_rolled_once_and_the_narrator_is_told(client, connected, provider, app):
    app.state.dice = random.Random(5)
    sent = tell(client, 'I try to persuade the barista to give me a free coffee.', 'turn-0001')
    prompt = provider.requests[-1]['system']
    assert '## This turn (decided by the game)' in prompt
    assert 'The player\'s character, on "I try to persuade the barista to give me a free coffee"' in prompt
    assert 'Rolls are hidden' in prompt
    with app.state.database.connect() as connection:
        rolls = [dict(row) for row in connection.execute('SELECT * FROM story_rolls')]
    assert len(rolls) == 1 and rolls[0]['stat'] == 'Allure' and rolls[0]['die'] == 8
    assert rolls[0]['message_id'] == sent['message']['id']
    # Hidden dice never leave the app.
    story = ok(client.get('/api/story'))
    assert story['dice_shown'] is False and 'rolls' not in story['messages'][0]
    # Telling it again keeps the dice.
    ok(client.post('/api/story/retry'))
    with app.state.database.connect() as connection:
        assert [dict(row) for row in connection.execute('SELECT * FROM story_rolls')] == rolls


def test_shown_dice_come_with_the_players_line(client, connected, provider, app):
    ok(client.put('/api/settings', json={'show_odds': True}))
    tell(client, 'I attack the man at the bar.', 'turn-0002')
    assert 'Rolls are shown to the player' in provider.requests[-1]['system']
    line = ok(client.get('/api/story'))['messages'][0]
    roll = line['rolls'][0]
    assert roll['stat'] == 'Vitality' and roll['label'] and roll['total'] == roll['natural'] + roll['bonus'] - roll['shift']


def test_talk_and_out_of_character_lines_roll_nothing(client, connected, app):
    tell(client, 'I sit down and look around.', 'turn-0003')
    tell(client, 'OOC: can I attack anyone here?', 'turn-0004')
    with app.state.database.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM story_rolls').fetchone()[0] == 0


def test_the_referee_model_is_asked_only_when_chosen(client, connected, provider, app):
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': 'referee', 'profile_id': profiles[0]['id']}))
    provider.replies = [
        [Chunk('{"actions": [{"action": "talk the guard down", "roll": true, "stat": "Resolve", '
               '"difficulty": "hard"}]}'), Chunk('', 'stop')],
        [Chunk('The guard lowers his spear.'), Chunk('', 'stop')]]
    tell(client, 'I tell the guard to stand aside.', 'turn-0005')
    assert len(provider.requests) == 2 and 'You are the Referee' in provider.requests[0]['system']
    assert "The player's character tries to talk the guard down:" in provider.requests[1]['system']
    with app.state.database.connect() as connection:
        row = connection.execute('SELECT stat, difficulty, shift FROM story_rolls').fetchone()
    assert tuple(row) == ('Resolve', 'hard', 10)


def test_the_sheet_holds_the_personas_stats(client):
    sheet = ok(client.get('/api/story/sheet'))
    assert sheet['stats'] == dict.fromkeys(marvel.STATS, 10) and sheet['dice']['Mind'] == 8
    changed = ok(client.put('/api/story/sheet', json={'stats': {'Mind': 15, 'Luck': 7}}))
    assert changed['stats']['Mind'] == 15 and changed['dice']['Mind'] == 12 and changed['dice']['Luck'] == 4
    assert client.put('/api/story/sheet', json={'stats': {'Strength': 12}}).status_code == 422
    assert client.put('/api/story/sheet', json={'stats': {'Mind': 31}}).status_code == 422


def streamed_events(client, text, client_id):
    with client.stream('POST', '/api/story/messages/stream', json={'text': text, 'client_id': client_id}) as response:
        return [json.loads(line) for line in response.iter_lines() if line]


def test_a_streamed_turn_shows_its_stages_and_rolls_before_the_narration(client, connected, app):
    ok(client.put('/api/settings', json={'show_odds': True}))
    events = streamed_events(client, 'I attack the man at the bar.', 'turn-0005')
    kinds = [next(iter(event)) for event in events]
    first_text = kinds.index('text')
    assert kinds[:4] == ['stage', 'actions', 'roll', 'stage'] and first_text == 4
    assert events[0] == {'stage': 'reading'} and events[3] == {'stage': 'writing'} and kinds[-1] == 'done'
    action, = events[1]['actions']
    assert action['stat'] == 'Vitality' and action['difficulty']
    assert [band['band'] for band in events[1]['bands']] == ['failure', 'failure_upside', 'success_cost', 'success',
                                                            'critical_success']
    assert events[1]['bands'][-1]['ceiling'] is None
    roll = events[2]['roll']
    assert roll['total'] == roll['natural'] + roll['bonus'] - roll['shift'] and roll['label']
    # The roll streamed is the one kept with the line.
    assert ok(client.get('/api/story'))['messages'][0]['rolls'] == [roll]
    # Telling it again streams the same dice again.
    with client.stream('POST', '/api/story/retry/stream', json={}) as response:
        again = [json.loads(line) for line in response.iter_lines() if line]
    assert [event['roll'] for event in again if 'roll' in event] == [roll]


def test_hidden_dice_stream_only_what_was_tried_and_the_stat(client, connected, app):
    events = streamed_events(client, 'I attack the man at the bar.', 'turn-0006')
    actions = next(event for event in events if 'actions' in event)
    assert actions == {'actions': [{'action': actions['actions'][0]['action'], 'stat': 'Vitality'}]}
    assert [event['roll'] for event in events if 'roll' in event] == [
        {'action': actions['actions'][0]['action'], 'stat': 'Vitality'}]
    assert ok(client.get('/api/story'))['bands'] is None


def test_a_line_with_nothing_to_roll_streams_no_actions(client, connected):
    kinds = [next(iter(event)) for event in streamed_events(client, 'I sit down and look around.', 'turn-0007')]
    assert 'actions' not in kinds and 'roll' not in kinds and kinds[:2] == ['stage', 'stage']


def test_rolling_dice_is_an_off_by_default_setting(client):
    assert ok(client.get('/api/settings'))['roll_dice'] is False
    assert ok(client.put('/api/settings', json={'roll_dice': True}))['roll_dice'] is True
    assert ok(client.get('/api/settings'))['roll_dice'] is True


def test_the_dice_log_keeps_every_roll_while_the_dice_are_shown(client, connected, app):
    assert ok(client.get('/api/story/dice-log')) == {'shown': False, 'turns': [], 'tally': None}
    ok(client.put('/api/settings', json={'show_odds': True}))
    tell(client, 'I attack the man at the bar.', 'turn-0010')
    tell(client, 'I sit down and look around.', 'turn-0011')
    log = ok(client.get('/api/story/dice-log'))
    rolled = [item for item in log['turns'] if item['rolls']]
    assert rolled[0]['line'] == 'I attack the man at the bar.' and rolled[0]['rolls'][0]['stat'] == 'Vitality'
    assert all(item['pace'] for item in log['turns'])
    assert log['tally']['rolls'] == sum(len(item['rolls']) for item in log['turns'])
    assert sum(log['tally']['bands'].values()) == log['tally']['rolls']
