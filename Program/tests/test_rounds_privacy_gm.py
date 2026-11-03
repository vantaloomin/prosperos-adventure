"""The GM view in round play (adventure/gm.py `open_round`; docs/spec.md "Waiting and pauses"): it asks first in Play,
remembers the answer for the campaign when asked to, marks every turn it was open on, and shows everything."""
import asyncio

from conftest import ok

from adventure import table, timeline
from adventure.rounds import engine, seats
from adventure.rounds.contract import Declaration, Mind, State, Whisper

MOTIVE = 'SENTINEL-MOTIVE-sell-the-party'
WHISPER = 'SENTINEL-WHISPER-the-weir'


def play_turn(app, seq: int, declare: bool = True):
    """One committed turn with Hesk's declaration and motive in it."""
    async def going():
        turn = await engine.begin(app.state, timeline.ROOT, seq)
        if declare:
            turn.draft.declare(Declaration('hesk', 'Lead the way.', motive=MOTIVE, whispers=[Whisper(WHISPER, ['mira'])]))
            turn.draft.learn('hesk', 'motive', MOTIVE)
        assert await engine.run(turn) == State.COMMITTED
        return turn.id
    return asyncio.run(going())


def sit(app, mode: str = 'play'):
    database = app.state.database
    with database.connect(write=True) as connection:
        seats.set_seat(connection, 'hesk', 'Hesk', database.now(), mind=Mind.AGENT)
        seats.set_seat(connection, 'mira', 'Mira', database.now(), mind=Mind.AGENT)
        seats.set_seat(connection, 'you', 'You', database.now(), mind=Mind.HUMAN)
        seats.change(connection, {'mode': mode}, False)


def test_in_play_it_asks_first_then_shows_everything_and_marks_the_turn(client, app):
    sit(app)
    first = play_turn(app, 1)
    asked = client.post('/api/gm/round', json={})
    assert asked.status_code == 409 and asked.json() == {'detail': 'This shows every secret and motive. Open anyway?',
                                                         'code': 'gm_view_asks_first'}
    assert ok(client.get('/api/gm/round/marks')) == {'marked': []}
    shown = ok(client.post('/api/gm/round', json={'confirmed': True}))
    assert shown['turn']['id'] == first and shown['turn']['marks'] == ['gm_view']
    hesk = next(row for row in shown['minds'] if row['key'] == 'hesk')
    assert hesk['motive'] == MOTIVE and hesk['whispers'] == [{'text': WHISPER, 'to': ['mira']}]
    assert {'holder': 'hesk', 'kind': 'motive', 'text': MOTIVE}.items() <= shown['knowledge'][0].items()
    assert MOTIVE in [row['text'] for row in shown['memories']['hesk']]
    assert shown['marked'] == [first]
    assert shown['shown']['hesk'] == [] and shown['drafted'] == []
    # Not remembered: the next look asks again, and a turn played with it closed stays unmarked.
    second = play_turn(app, 2)
    assert client.post('/api/gm/round', json={}).status_code == 409
    assert ok(client.get('/api/gm/round/marks'))['marked'] == [first]
    assert second not in ok(client.get('/api/gm/round/marks'))['marked']


def test_remembered_it_stops_asking_until_a_new_story(client, app):
    sit(app)
    play_turn(app, 1)
    ok(client.post('/api/gm/round', json={'confirmed': True, 'remember': True}))
    assert client.post('/api/gm/round', json={}).status_code == 200
    from adventure import story
    story.clear(app.state.database)
    sit(app)
    assert client.post('/api/gm/round', json={}).status_code == 409


def test_turns_played_with_the_gm_view_on_are_marked_at_gather(client, app):
    sit(app)
    with app.state.database.connect(write=True) as connection:
        table.change(connection, {'gm_view': True})
    turn = play_turn(app, 1, declare=False)
    assert ok(client.get('/api/gm/round/marks'))['marked'] == [turn]


def test_author_and_watch_have_no_gate_and_mark_nothing(client, app):
    for mode in ('author', 'watch'):
        sit(app, mode)
        turn = play_turn(app, 1 if mode == 'author' else 2)
        shown = ok(client.post('/api/gm/round', json={}))
        assert shown['turn']['id'] == turn and shown['turn']['marks'] == []
    assert ok(client.get('/api/gm/round/marks'))['marked'] == []


def test_with_no_turn_yet_it_shows_nothing(client, app):
    sit(app, 'watch')
    assert ok(client.post('/api/gm/round', json={})) == {'turn': None, 'marked': []}


def test_the_minds_panel_shows_motives_in_watch_and_only_status_in_play(client, app):
    assert ok(client.get('/api/minds'))['minds'] == []
    sit(app)
    turn = play_turn(app, 1)
    play = ok(client.get('/api/minds'))
    hesk = next(row for row in play['minds'] if row['key'] == 'hesk')
    assert play['turn'] == turn and play['mode'] == 'play'
    assert hesk == {'key': 'hesk', 'name': 'Hesk', 'mind': 'agent', 'status': 'decided'}
    # Looking at the panel is not opening the GM view: nothing is marked.
    assert ok(client.get('/api/gm/round/marks'))['marked'] == []
    sit(app, 'watch')
    play_turn(app, 2)
    hesk = next(row for row in ok(client.get('/api/minds'))['minds'] if row['key'] == 'hesk')
    assert hesk['motive'] == MOTIVE and hesk['intent'] == 'Lead the way.'


def test_leaving_play_asks_once_and_missed_motives_stay_hidden_until_shown(client, app):
    sit(app)
    turn = play_turn(app, 1)
    assert ok(client.get('/api/minds'))['reveal_missed'] is None
    sit(app, 'author')

    def hesk():
        return next(row for row in ok(client.get('/api/minds'))['minds'] if row['key'] == 'hesk')

    def reported():
        return [item['motive'] for item in ok(client.get(f'/api/story/turns/{turn}/report'))['motives']]
    # Not answered, or Keep hidden: the Play turn keeps Play's visibility in the panel and the turn report.
    assert 'motive' not in hesk() and MOTIVE not in reported()
    shown = ok(client.put('/api/minds/reveal_missed', json={'reveal': False}))
    assert shown['reveal_missed'] is False and 'motive' not in hesk() and MOTIVE not in reported()
    ok(client.put('/api/minds/reveal_missed', json={'reveal': True}))
    assert hesk()['motive'] == MOTIVE and MOTIVE in reported()
    # Back in Play, Play's own rules hold again; a new story asks again.
    sit(app)
    assert 'motive' not in hesk()
    from adventure import story
    story.clear(app.state.database)
    assert ok(client.get('/api/minds'))['reveal_missed'] is None
