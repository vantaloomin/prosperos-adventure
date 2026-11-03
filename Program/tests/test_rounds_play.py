"""Playing rounds (adventure/rounds/play.py, queue.py, solo.py, adventure/round_routes.py): today's turn through the
round loop, one writer at a time, stale commands refused, the reply card, cancelling, re-asking and restarts."""
import asyncio
import json

import pytest
from conftest import tell

from adventure import story, timeline
from adventure.rounds import engine, memory, play, queue, resolve, solo, telling, turns
from adventure.rounds.contract import Declaration, Mind, Point, State


@pytest.fixture
def steps():
    """Each test starts from the foundation's own steps (picking seats), today's turn as steps with the party's
    Resolve, and their hooks (memory, the story, the rolls), whatever other parts of the loop registered; everything
    is put back after it."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks = list(engine.COMMITS)
    for listed in engine.STEPS.values():
        listed[:] = [(name, step) for name, step in listed if step in (
            engine.pick, telling.gather, telling.line, telling.write, resolve.ambiguity, resolve.resolve)]
    # Another part may have replaced 'pick' under its name: the foundation's own is put back for these tests.
    engine.STEPS[State.GATHERING][:] = [('pick', engine.pick), ('line', telling.gather)]
    engine.COMMITS[:] = [(name, hook) for name, hook in engine.COMMITS
                         if hook in (engine.committed_memory, telling.committed, resolve.kept_rolls)]
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def streamed(client, path, body):
    """A streamed command's events, and what it ended with."""
    with client.stream('POST', path, json=body) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]
    return events, next((event for event in events if 'done' in event or 'error' in event), None)


def rows(client, sql, values=()):
    with client.app.state.database.connect() as connection:
        return [dict(row) for row in connection.execute(sql, values).fetchall()]


def seated(client, *agents, human=None):
    if human:
        ok(client.put(f'/api/rounds/seats/{human}', json={'name': human.title(), 'mind': 'human'}))
    for key in agents:
        ok(client.put(f'/api/rounds/seats/{key}', json={'name': key.title(), 'mind': 'agent'}))


def declaring(seen):
    """A Declare step for every agent without a declaration yet; each one learns what it chose."""
    async def declare(turn):
        for seat in turn.snapshot.agents():
            if seat.key not in turn.draft.declarations:
                seen.append(seat.key)
                choice = f'{seat.key} choice {len(seen)}'
                turn.draft.declare(Declaration(seat.key, choice))
                turn.draft.learn(seat.key, 'motive', choice)
    return declare


def test_a_players_line_is_a_turn_of_the_round_loop(client, connected):
    first = tell(client, 'I look around the market.', 'client-one-1')
    assert first['reply']['status'] == 'complete'
    played = rows(client, 'SELECT * FROM round_turns')
    assert [(row['anchor_id'], row['state'], row['mode']) for row in played] == [
        (first['message']['id'], 'committed', 'play')]
    # Each line says which turn it belongs to, for its report.
    assert first['turn_id'] == played[0]['id']
    lines = {row['id']: row['turn_id'] for row in ok(client.get('/api/story'))['messages']}
    assert lines[first['message']['id']] == lines[first['reply']['id']] == played[0]['id']
    # The same line sent again (a retried request) is answered from what was kept, with no second turn.
    assert tell(client, 'I look around the market.', 'client-one-1')['reply']['id'] == first['reply']['id']
    assert len(rows(client, 'SELECT * FROM round_turns')) == 1
    # Telling it again retires the turn that told it.
    ok(client.post('/api/story/retry'))
    assert [row['state'] for row in rows(client, 'SELECT * FROM round_turns ORDER BY created_at, rowid')] == [
        'discarded', 'committed']
    told_again = rows(client, "SELECT id FROM round_turns WHERE state='committed'")[0]['id']
    assert {row['turn_id'] for row in ok(client.get('/api/story'))['messages']} == {told_again}


def test_a_solo_turns_stream_is_as_it_always_was(client, connected):
    events, end = streamed(client, '/api/story/messages/stream', {'text': 'I wait.', 'client_id': 'client-two-1'})
    assert 'done' in end
    assert not any({'round', 'seat', 'awaiting'} & event.keys() for event in events)
    assert rows(client, 'SELECT state FROM round_turns') == [{'state': 'committed'}]


def test_with_agents_a_players_line_shows_the_round_and_can_stop_on_the_reply_card(client, connected, steps):
    async def converse(turn):
        if 'you' not in turn.draft.replies:
            turn.draft.wait_for('you', 'mara', 'Who sent you?', [])
    engine.register(State.CONVERSING, 'converse', converse)
    seated(client, 'mara', human='you')
    line = {'text': 'I ask Mara for the key.', 'client_id': 'client-five-1'}
    events, end = streamed(client, '/api/story/messages/stream', line)
    # The round timeline is in the story's stream, and the line ends on the card with no reply yet.
    assert {'round': {'turn_id': end['done']['awaiting']['id'], 'state': 'declaring'}} in events
    assert {'awaiting': {'seat': 'you', 'speaker': 'mara', 'line': 'Who sent you?', 'context': []}} in events
    waiting = end['done']['awaiting']
    assert end['done']['reply'] is None and waiting['state'] == 'awaiting_user'
    # The same line sent again is shown the card again; a new line waits for the card.
    assert tell(client, line['text'], line['client_id'])['awaiting']['id'] == waiting['id']
    refused = client.post('/api/story/messages', json={'text': 'I leave.', 'client_id': 'client-five-2'})
    assert (refused.status_code, refused.json()['code']) == (409, 'awaiting')
    assert len(rows(client, "SELECT * FROM story_messages WHERE role='user'")) == 1
    # Answered through the round loop, the line is told there, and that stream ends with the reply.
    _, end = streamed(client, f"/api/rounds/turns/{waiting['id']}/reply/stream",
                      {'seat': 'you', 'kind': 'reply', 'text': 'Nobody.', 'against': waiting['id']})
    assert 'done' in end, end
    assert end['done']['turn']['state'] == 'committed'
    assert end['done']['reply']['status'] == 'complete'
    assert [row['id'] for row in rows(client, "SELECT id FROM story_messages WHERE role='narrator'")] == [
        end['done']['reply']['id']]


def test_gather_seats_only_who_is_in_the_scene(client, steps, monkeypatch):
    engine.STEPS[State.GATHERING][:] = [('present', engine.present), ('pick', engine.pick)]
    scene = story.scene
    monkeypatch.setattr(story, 'scene', lambda connection, now: scene(connection, now) | {
        'people': [{'sheet': {'key': 'mara'}}, {'sheet': {'key': 'innkeeper'}}]})
    seated(client, 'mara', 'elsewhere', human='you')
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))
    _, end = streamed(client, '/api/rounds/turns/stream', {})
    snapshot = json.loads(rows(client, 'SELECT snapshot FROM round_turns WHERE id=?', (end['done']['turn']['id'],))[0][
        'snapshot'])
    # The human's character is always in their own scene; an agent who is elsewhere sits this turn out.
    assert snapshot['present'] == ['you', 'mara', 'innkeeper']
    assert {seat['key']: seat['mind'] for seat in snapshot['seats']} == {
        'mara': 'agent', 'elsewhere': 'program', 'you': 'program'}


def test_one_writer_at_a_time(client):
    state = client.app.state
    log = []

    async def work(name):
        log.append(f'{name} starts')
        await asyncio.sleep(0.01)
        log.append(f'{name} ends')
        return name

    async def both():
        return await asyncio.gather(queue.play(state, lambda: work('a')), queue.play(state, lambda: work('b')))
    assert asyncio.run(both()) == ['a', 'b']
    assert log == ['a starts', 'a ends', 'b starts', 'b ends']


def test_watch_turns_refuse_a_stale_command_and_settings_wait_for_idle(client, steps):
    assert client.post('/api/rounds/turns/stream', json={}).status_code == 409  # Play starts with your line.
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))
    _, end = streamed(client, '/api/rounds/turns/stream', {'against': None})
    assert end['done']['turn']['state'] == 'committed' and end['done']['turn']['mode'] == 'watch'
    head = end['done']['head']
    # A second tab still thinking no turn was played is refused; one that knows the newest turn goes on.
    _, end = streamed(client, '/api/rounds/turns/stream', {'against': None})
    assert end['status'] == 409 and end['code'] == 'stale'
    _, end = streamed(client, '/api/rounds/turns/stream', {'against': head})
    assert end['done']['turn']['state'] == 'committed'
    # Watch turns open on a line of their own, a save point like a player's line.
    lines = rows(client, "SELECT * FROM story_messages WHERE role='user' ORDER BY seq")
    assert [(line['mode'], line['text']) for line in lines] == [('watch', ''), ('watch', '')]
    assert len(rows(client, 'SELECT * FROM story_saves')) == 2


def test_a_turn_waits_on_the_reply_card_then_runs_on_with_the_answer(client, steps):
    async def converse(turn):
        if 'you' in turn.draft.replies:
            turn.draft.learn('mara', 'heard', f"Ilsa said: {turn.draft.replies['you']['text']}", source='you')
            return
        turn.draft.wait_for('you', 'mara', 'Where were you last night?', ['Mara leans in.'])
    engine.register(State.CONVERSING, 'converse', converse)
    seated(client, 'mara', human='you')
    ok(client.put('/api/rounds/settings', json={'mode': 'author'}))
    events, end = streamed(client, '/api/rounds/turns/stream', {'nudge': 'A storm comes in.'})
    turn = end['done']['turn']
    assert turn['state'] == 'awaiting_user'
    assert {'awaiting': {'seat': 'you', 'speaker': 'mara', 'line': 'Where were you last night?',
                         'context': ['Mara leans in.']}} in events
    # Settings asked for meanwhile wait for Idle.
    assert ok(client.put('/api/rounds/settings', json={'agent_cap': 2}))['settings']['queued'] == {'agent_cap': 2}
    assert client.post(f"/api/rounds/turns/{turn['id']}/reply/stream",
                       json={'seat': 'you', 'kind': 'reply', 'text': ''}).status_code == 422
    _, end = streamed(client, f"/api/rounds/turns/{turn['id']}/reply/stream",
                      {'seat': 'you', 'kind': 'reply', 'text': 'At the shrine.', 'against': turn['id']})
    assert end['done']['turn']['state'] == 'committed'
    assert end['done']['settings']['agent_cap'] == 2 and end['done']['settings']['queued'] == {}
    with client.app.state.database.connect() as connection:
        known = memory.recall(connection, 'mara', Point(timeline.active(connection), 10 ** 9))
    assert [row['text'] for row in known] == ['Ilsa said: At the shrine.']
    # The Author's nudge was kept with the snapshot.
    snapshot = json.loads(rows(client, 'SELECT snapshot FROM round_turns')[0]['snapshot'])
    assert snapshot['settings']['nudge'] == 'A storm comes in.'


def test_cancelling_a_waiting_turn_keeps_nothing(client, steps):
    async def asks(turn):
        turn.draft.learn('mara', 'witnessed', 'Something that will not be kept.')
        if 'you' not in turn.draft.replies:
            turn.draft.wait_for('you', 'mara', 'Well?', [])
    engine.register(State.CONVERSING, 'asks', asks)
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))
    _, end = streamed(client, '/api/rounds/turns/stream', {})
    turn_id = end['done']['turn']['id']
    assert ok(client.post(f'/api/rounds/turns/{turn_id}/cancel'))['under_way'] is None
    assert client.post(f'/api/rounds/turns/{turn_id}/cancel').status_code == 409
    assert rows(client, 'SELECT state FROM round_turns') == [{'state': 'discarded'}]
    assert rows(client, 'SELECT * FROM character_memories') == []


def test_reasking_an_agent_keeps_everyone_elses_choice_on_a_new_branch(client, steps):
    seen = []
    engine.register(State.DECLARING, 'declare', declaring(seen))
    seated(client, 'mara', 'hesk')
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))
    _, end = streamed(client, '/api/rounds/turns/stream', {})
    first = end['done']['turn']['id']
    assert seen == ['mara', 'hesk']
    assert client.post(f'/api/rounds/turns/{first}/reask/stream', json={'seat': 'nobody'}).status_code == 200
    _, end = streamed(client, f'/api/rounds/turns/{first}/reask/stream', {'seat': 'mara', 'against': first})
    again = end['done']['turn']
    assert again['state'] == 'committed' and again['reask_of'] == first and again['reask_seat'] == 'mara'
    assert seen == ['mara', 'hesk', 'mara']
    draft = json.loads(rows(client, 'SELECT draft FROM round_turns WHERE id=?', (again['id'],))[0]['draft'])
    assert {key: value['intent'] for key, value in draft['declarations'].items()} == {
        'hesk': 'hesk choice 2', 'mara': 'mara choice 3'}
    with client.app.state.database.connect() as connection:
        branch = timeline.active(connection)
        assert branch != timeline.ROOT
        here = Point(branch, 10 ** 9)
        # The new branch remembers only its own telling; the first branch keeps its own.
        assert [row['text'] for row in memory.recall(connection, 'mara', here)] == ['mara choice 3']
        assert [row['text'] for row in memory.recall(connection, 'mara', Point(timeline.ROOT, 10 ** 9))] == [
            'mara choice 1']
        assert queue.head(connection) == again['id']


def test_a_restart_throws_away_an_open_turn_and_plays_a_round_turn_again(client, steps):
    seen = []
    engine.register(State.DECLARING, 'declare', declaring(seen))
    seated(client, 'mara')
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))
    state = client.app.state

    async def stopped():
        line = None
        with state.database.connect(write=True) as connection:
            line = play.opening_line(connection, state.database.now(), 'watch', '')
        turn = await engine.begin(state, line['branch_id'], line['seq'], anchor_id=line['id'], mode='watch')
        await engine.enter(turn, State.GATHERING)
        engine.kept(turn, snapshot=True)
        return turn.id
    turn_id = asyncio.run(stopped())
    assert play.recover(state) == turn_id
    with state.database.connect() as connection:
        assert turns.get(connection, turn_id)['state'] == 'discarded'
    assert asyncio.run(play.replay(state, turn_id))['state'] == 'committed'
    assert seen == ['mara']
    assert play.recover(state) is None


def test_a_restart_leaves_a_waiting_turn_waiting_and_a_solo_turn_for_retry(client, steps):
    state = client.app.state

    async def opened(solo_turn):
        with state.database.connect(write=True) as connection:
            line = play.opening_line(connection, state.database.now(), 'play', 'I wait.')
        turn = await engine.begin(state, line['branch_id'], line['seq'], anchor_id=line['id'])
        if solo_turn:
            turn.draft.extra[solo.SOLO] = {'user': line}
        else:
            turn.draft.wait_for('you', 'mara', 'Well?', [])
            await engine.pause(turn, State.CONVERSING, 'converse')
        engine.kept(turn)
        return turn.id
    waiting = asyncio.run(opened(False))
    assert play.recover(state) is None
    with state.database.connect(write=True) as connection:
        assert turns.under_way(connection)['id'] == waiting
        turns.discard(connection, waiting)
    asyncio.run(opened(True))
    assert play.recover(state) is None
    assert [row['state'] for row in rows(client, 'SELECT state FROM round_turns')] == ['discarded', 'discarded']


def test_one_human_seat_and_its_mind_is_kept_across_going_back(client):
    seated(client, 'mara', human='you')
    table = ok(client.put('/api/rounds/seats/hesk', json={'name': 'Hesk', 'mind': 'human', 'notes': 'Quiet.'}))
    assert {seat['key']: seat['mind'] for seat in table['seats']} == {'you': Mind.PROGRAM, 'mara': Mind.AGENT,
                                                                      'hesk': Mind.HUMAN}
    assert client.put('/api/rounds/settings', json={'agent_cap': 7}).status_code == 422
    assert ok(client.delete('/api/rounds/seats/hesk'))['seats'][-1]['key'] == 'mara'


def test_cancelling_a_running_turn_stops_it_at_once(client, steps):
    state = client.app.state
    started = asyncio.Event()

    async def slow(turn):
        turn.draft.learn('mara', 'witnessed', 'Half a thought.')
        started.set()
        await asyncio.sleep(30)
    engine.register(State.DECLARING, 'slow', slow)
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))

    async def going():
        playing = asyncio.ensure_future(queue.play(state, lambda: play.next_turn(state)))
        await started.wait()
        with state.database.connect() as connection:
            turn_id = turns.under_way(connection)['id']
        assert queue.cancel(state, turn_id)
        with pytest.raises(Exception) as failure:
            await playing
        return failure.value
    failure = asyncio.run(going())
    assert getattr(failure, 'code', None) == 'cancelled'
    assert rows(client, 'SELECT state, error FROM round_turns') == [{'state': 'discarded', 'error': 'CancelledError'}]
    assert rows(client, 'SELECT * FROM character_memories') == []
