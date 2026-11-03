"""Author, Watch and switching modes (adventure/rounds/author.py, watch.py, modes.py, adventure/mode_routes.py): nudges
and their feedback, the beat board, the nudge box in Play, Watch's timer and its pauses, the session cap, and who
plays the user's character outside Play."""
import asyncio
import json

import pytest
from test_director import start
from test_rounds_play import ok, rows, seated, streamed

from adventure import director, pace, plotting, record
from adventure.rounds import author, declare, engine, modes, play, watch
from adventure.rounds.contract import Declaration, Line, Mind, State, TurnResult
from adventure.rounds.queue import head


@pytest.fixture
def steps():
    """The agents' 'pick', the foundation's memory hook, and this workstream's steps and hooks, whatever else registered."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks, after = list(engine.COMMITS), dict(engine.AFTER)
    for listed in engine.STEPS.values():
        listed[:] = []
    engine.STEPS[State.GATHERING][:] = [('pick', declare.pick), ('stand_in', modes.stand_in), ('author', author.taken),
                                        ('watch', watch.frozen)]
    engine.COMMITS[:] = [('memory', engine.committed_memory), ('author', author.committed)]
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks
    engine.AFTER.clear()
    engine.AFTER.update(after)


def writes(text, declarations=()):
    """A Writing step that declares what it is given and writes `text` as the turn's post."""
    async def step(turn):
        for declaration in declarations:
            turn.draft.declare(declaration)
        turn.draft.post = text
    return step


def snapshot_of(client, turn_id):
    return json.loads(rows(client, 'SELECT snapshot FROM round_turns WHERE id=?', (turn_id,))[0]['snapshot'])


def played(client, path='/api/rounds/turns/stream', **body):
    events, end = streamed(client, path, body)
    assert 'done' in end, end
    return end['done']


# Author ---------------------------------------------------------------------------------------------------------------

def test_author_nudges_get_feedback_used_or_not_yet(client, steps):
    seated(client, 'mara', 'hesk')
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    engine.register(State.WRITING, 'write', writes('Rain hammers the roof.', [
        Declaration('mara', 'goes north along the river road', [Line('We go north, now.')])]))
    first = played(client, nudge='Someone should go north along the river.')
    assert snapshot_of(client, first['turn']['id'])['settings']['author']['nudges'] == [
        'Someone should go north along the river.']
    assert ok(client.get('/api/rounds/author'))['feedback'] == [
        {'nudge': 'Someone should go north along the river.', 'status': 'used', 'why': 'Used: Mara took it up.'}]
    engine.register(State.WRITING, 'write', writes('A storm breaks over the harbour.'))
    played(client, nudge='A storm breaks.', against=first['turn']['id'])
    assert ok(client.get('/api/rounds/author'))['feedback'][0]['why'] == 'Used: it reached the page.'
    third = played(client, nudge='The baker confesses.', against=head_of(client))
    assert ok(client.get('/api/rounds/author'))['feedback'] == [
        {'nudge': 'The baker confesses.', 'status': 'not_yet', 'why': 'Not yet: no one took it up this turn.'}]
    # Watch turns take no nudge.
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    fourth = played(client, against=third['turn']['id'])
    assert 'author' not in snapshot_of(client, fourth['turn']['id'])['settings']
    assert ok(client.get('/api/rounds/author'))['feedback'] == []


def head_of(client):
    with client.app.state.database.connect() as connection:
        return head(connection)


def test_the_beat_board_is_the_directors_plan_and_the_author_edits_it(client, app, steps):
    start(client)
    with app.state.database.connect(write=True) as connection:
        plotting.store(connection, 'the-eight-pieces', 0, ['A courier arrives with sealed orders.',
                                                           'The grove goes quiet.'], 'world')
    # Outside Author the plan takes the GM view, as in Dungeon.
    assert client.post('/api/rounds/author/beats', json={'arc_id': 'the-eight-pieces', 'text': 'x'}).status_code == 409
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    view = ok(client.post('/api/rounds/author/beats', json={'arc_id': 'the-eight-pieces',
                                                            'text': 'A wolf howls at the gate.'}))
    [arc] = [item for item in view['board'] if item['arc_id'] == 'the-eight-pieces']
    assert [(beat['text'], beat['source']) for beat in arc['beats']] == [
        ('A courier arrives with sealed orders.', 'world'), ('The grove goes quiet.', 'world'),
        ('A wolf howls at the gate.', 'author')]
    grove = arc['beats'][1]['id']
    view = ok(client.patch(f'/api/rounds/author/beats/{grove}', json={'cut': True, 'position': 0}))
    [arc] = [item for item in view['board'] if item['arc_id'] == 'the-eight-pieces']
    assert [(beat['text'], beat['cut']) for beat in arc['beats']][0] == ('The grove goes quiet.', True)
    assert client.post('/api/rounds/author/beats', json={'arc_id': 'no-such-arc', 'text': 'x'}).status_code == 404
    # A nudge that names a planned beat moves it to the front of the plan.
    engine.register(State.WRITING, 'write', writes('Nothing much happens.'))
    played(client, nudge='Bring in that wolf howling at the gate.')
    [arc] = [item for item in ok(client.get('/api/rounds/author'))['board'] if item['arc_id'] == 'the-eight-pieces']
    assert arc['beats'][0]['text'] == 'A wolf howls at the gate.'
    assert ok(client.get('/api/rounds/author'))['feedback'][0]['why'] == (
        'Used: the director moved “A wolf howls at the gate.” up its plan.')
    # Once the note has given a beat, its reaching the page marks it landed.
    with app.state.database.connect(write=True) as connection:
        assert plotting.next_beat(connection, 'the-eight-pieces', 0) == 'A wolf howls at the gate.'
    engine.register(State.WRITING, 'write', writes('Somewhere past the gate a wolf howls, long and low.'))
    played(client, against=head_of(client))
    [arc] = [item for item in ok(client.get('/api/rounds/author'))['board'] if item['arc_id'] == 'the-eight-pieces']
    assert [beat['text'] for beat in arc['beats'] if beat['landed']] == ['A wolf howls at the gate.']


def test_beats_written_beside_a_play_line_are_nudges_for_the_next_turn(client, app, steps):
    start(client)
    assert ok(client.post('/api/rounds/author/box', json={'text': 'A stranger arrives in a red cloak.'}))['box']
    with app.state.database.connect() as connection:
        director_lines = director.asked(connection)
    assert director_lines == ['Asked for by the player, if it fits (the characters still choose for themselves): '
                              'A stranger arrives in a red cloak.']
    engine.register(State.WRITING, 'write', writes('The door opens on a stranger in a red cloak.'))
    seated(client, 'mara')
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    # In Author the box waits: the nudge comes with Next.
    assert client.post('/api/rounds/author/box', json={'text': 'More.'}).status_code == 409
    turn = played(client, nudge='')['turn']
    assert 'beats' not in snapshot_of(client, turn['id'])['settings']
    assert len(ok(client.get('/api/rounds/author'))['box']) == 1
    # A Play turn takes the box as the user-set beats of its brief, and empties it once committed.
    ok(client.put('/api/rounds/mode', json={'mode': 'play'}))
    row = asyncio.run(play.next_turn(app.state))
    assert snapshot_of(client, row['id'])['settings']['beats'] == ['A stranger arrives in a red cloak.']
    view = ok(client.get('/api/rounds/author'))
    assert view['box'] == [] and view['feedback'][0]['why'] == 'Used: it reached the page.'


# Watch ----------------------------------------------------------------------------------------------------------------

def test_watch_runs_on_its_timer_and_pauses_at_a_death_until_the_user_goes_on(client, app, steps):
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    ok(client.put('/api/rounds/mode/settings', json={'watch_seconds': 5}))
    assert ok(client.get('/api/rounds/watch')) == {'seconds': 5, 'paused': None}
    quiet = played(client, '/api/rounds/watch/next/stream', against=None)
    assert quiet['turn']['state'] == 'committed'

    async def dies(turn):
        with turn.database.connect(write=True) as connection:
            record.add(connection, 'death', 'Old Tam', 'Old Tam fell from the wall.', turn.database.now())
    engine.register(State.RESOLVING, 'dies', dies)
    deadly = played(client, '/api/rounds/watch/next/stream', against=quiet['turn']['id'])
    engine.unregister(State.RESOLVING, 'dies')
    paused = ok(client.get('/api/rounds/watch'))['paused']
    assert paused == {'kind': 'death', 'text': 'Old Tam died.', 'turn_id': deadly['turn']['id']}
    _, end = streamed(client, '/api/rounds/watch/next/stream', {'against': deadly['turn']['id']})
    assert end['status'] == 409 and end['code'] == 'paused' and end['error'] == 'Paused: Old Tam died.'
    # Continue lets the timer run again.
    assert client.post('/api/rounds/watch/continue', json={'against': None}).status_code == 409
    assert ok(client.post('/api/rounds/watch/continue', json={'against': deadly['turn']['id']}))['paused'] is None
    assert played(client, '/api/rounds/watch/next/stream', against=deadly['turn']['id'])['turn']['state'] == 'committed'


def test_watch_pauses_at_a_betrayal_a_flagged_moment_and_the_session_cap(client, app, steps):
    seated(client, 'mara', 'hesk', human='you')
    with app.state.database.connect(write=True) as connection:
        for key in ('mara', 'hesk'):
            connection.execute("INSERT INTO story_party (key, name, city_id, sheet, joined) VALUES "
                               "(?, ?, 'kingswood', '{}', 'x')", (key, key.title()))
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))

    async def turns_on(turn):
        turn.draft.result = TurnResult(rolls=[{'actor': 'hesk', 'target': 'mara', 'kind': 'attack',
                                               'band': 'success'}])
    engine.register(State.RESOLVING, 'resolve', turns_on)
    turned = played(client, '/api/rounds/watch/next/stream', against=None)
    assert ok(client.get('/api/rounds/watch'))['paused']['text'] == 'Hesk betrayed the party.'
    engine.unregister(State.RESOLVING, 'resolve')

    # Next by hand always plays, and leaves the pause behind with its turn.
    async def flags(turn):
        turn.draft.extra['moments'] = [{'kind': 'reveal', 'text': 'The letter was forged.'}]
    engine.register(State.RESOLVING, 'flags', flags)
    flagged = played(client, against=turned['turn']['id'])
    engine.unregister(State.RESOLVING, 'flags')
    assert ok(client.get('/api/rounds/watch'))['paused'] == {'kind': 'reveal', 'text': 'The letter was forged.',
                                                             'turn_id': flagged['turn']['id']}
    ok(client.post('/api/rounds/watch/continue', json={'against': flagged['turn']['id']}))
    ok(client.put('/api/agents', json={'session_cap': 100}))
    pace.spend_for(app.state.database).settle(None, 100)
    assert ok(client.get('/api/rounds/watch'))['paused']['kind'] == 'cap'
    _, end = streamed(client, '/api/rounds/watch/next/stream', {'against': flagged['turn']['id']})
    assert end['code'] == 'paused' and end['error'] == 'Paused: This session reached its cap.'


def test_the_timer_runs_only_in_watch(client, steps):
    _, end = streamed(client, '/api/rounds/watch/next/stream', {'against': None})
    assert end['status'] == 409 and end['code'] == 'not_watch'
    assert client.put('/api/rounds/mode/settings', json={'watch_seconds': 4000}).status_code == 422


# Switching modes ------------------------------------------------------------------------------------------------------

async def everyone(turn):
    """Everyone at the table is in the scene, as a 'present' step before 'pick' would say."""
    turn.snapshot.present = [seat.key for seat in turn.snapshot.seats]


def test_outside_play_the_users_character_runs_on_the_mind_they_picked(client, steps):
    engine.STEPS[State.GATHERING].insert(0, ('present', everyone))
    seated(client, 'mara', 'hesk', human='you')
    ok(client.put('/api/rounds/settings', json={'agent_cap': 2}))
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    first = played(client)['turn']
    minds = {seat['key']: seat['mind'] for seat in snapshot_of(client, first['id'])['seats']}
    assert minds == {'you': Mind.PROGRAM, 'mara': Mind.AGENT, 'hesk': Mind.AGENT}
    assert snapshot_of(client, first['id'])['settings']['stand_in'] == {'key': 'you', 'mind': 'program'}
    # As an agent, it is promoted by hand and the cap applies with it in: the last seat drops to its Program mind.
    view = ok(client.put('/api/rounds/mode', json={'mode': 'watch', 'stand_in': 'agent'}))
    assert view['settings']['stand_in'] == 'agent'
    second = played(client, against=first['id'])['turn']
    snapshot = snapshot_of(client, second['id'])
    minds = {seat['key']: seat['mind'] for seat in snapshot['seats']}
    assert minds == {'you': Mind.AGENT, 'mara': Mind.AGENT, 'hesk': Mind.PROGRAM}
    assert snapshot['settings']['dropped'] == ['hesk']
    # The user's seat is still the human's, so going back to Play needs nothing undone.
    table = ok(client.get('/api/rounds'))
    assert {seat['key']: seat['mind'] for seat in table['seats']}['you'] == Mind.HUMAN


def test_leaving_play_asks_whether_to_see_the_motives_missed(client, app, steps):
    seated(client, 'mara', human='you')
    engine.register(State.WRITING, 'write', writes('', [Declaration('mara', 'smiles', motive='Rob them blind.')]))
    play_turn = asyncio.run(play.next_turn(app.state))
    with app.state.database.connect() as connection:
        assert not modes.revealed(connection, play_turn)
    # Hidden by default.
    view = ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    assert view['switches'][0] == {'from': 'play', 'to': 'author', 'reveal': False, 'at': view['switches'][0]['at']}
    author_turn = played(client, nudge='', against=play_turn['id'])['turn']
    with app.state.database.connect() as connection:
        assert not modes.revealed(connection, play_turn)
        assert modes.revealed(connection, {'id': author_turn['id'], 'mode': 'author'})
    ok(client.put('/api/rounds/mode', json={'mode': 'play'}))
    ok(client.put('/api/rounds/mode', json={'mode': 'watch', 'reveal': True}))
    with app.state.database.connect() as connection:
        assert modes.revealed(connection, play_turn)


def test_a_switch_asked_for_during_a_turn_waits_for_idle(client, steps):
    seated(client, 'mara', human='you')
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))

    async def asks(turn):
        if 'you' not in turn.draft.replies:
            turn.draft.wait_for('you', 'mara', 'Well?', [])
    engine.register(State.CONVERSING, 'asks', asks)
    turn = played(client, nudge='')['turn']
    assert turn['state'] == 'awaiting_user'
    view = ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    assert view['coming'] == 'watch' and view['table']['settings']['mode'] == 'author'
    done = played(client, f"/api/rounds/turns/{turn['id']}/reply/stream", seat='you', kind='silent', against=turn['id'])
    assert done['turn']['mode'] == 'author' and done['settings']['mode'] == 'watch'
