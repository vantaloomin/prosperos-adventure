"""The director, full (dungeon/plotting.py): seeds and payoffs, adopted details and planned beats."""
import asyncio
import json

from conftest import Chunk
from test_director import NOW, directed, note, start  # noqa: F401, F811 - `directed` is a fixture
from test_travel import Road, ok

from dungeon import director, plotting, record


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def route(client, job):
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': job, 'profile_id': profiles[0]['id']}))


def test_a_planted_seed_is_logged_reaches_the_page_and_is_asked_back_then_paid(client, app, directed):  # noqa: F811
    start(client)
    with app.state.database.connect(write=True) as connection:
        director.touch(connection, 'vallarith', 'A fight.', 'crisis', 'm1', 'x')
        assert 'Seed, if it fits the scene: A root cut at the edge of the grove bleeds' in note(connection)
        [seed] = plotting.seeds(connection)
        assert seed['status'] == 'planted' and seed['truth'] and seed['arc_id'] == 'the-eight-pieces'
        plotting.after_line(connection, 'The ranger hacks a root at the grove edge and it bleeds red sap.', 'm2')
        assert plotting.seeds(connection)[0]['status'] == 'reached'
        # When its thread is hot it is asked to come back, once.
        for n in range(2):
            director.touch(connection, 'vallarith', 'The Heartwood again.', 'quiet', f'h{n}', 'x')
        assert 'Payoff: bring back what was planted earlier (A root cut' in note(connection)
        assert 'Payoff' not in note(connection)
        plotting.after_line(connection, 'You remember the root that bled at the grove edge.', 'm3')
        assert plotting.seeds(connection)[0]['status'] == 'paid'


def test_a_seed_that_never_paid_off_is_retired_and_the_gm_view_can_cash_one_in(client, app, directed):  # noqa: F811
    start(client)
    ok(client.put('/api/settings', json={'gm_view': True}))
    with app.state.database.connect(write=True) as connection:
        plotting.plant(connection, 'the-long-border', 'A deserter\'s boot in the ditch.', 'Bastion is emptying.')
        connection.execute("UPDATE story_director SET lines=?", (plotting.WINDOW + plotting.CLOSING + 1,))
        plotting.after_line(connection, 'Nothing of note.', 'm1')
        [seed] = plotting.seeds(connection)
    assert seed['status'] == 'retired'
    view = ok(client.post(f"/api/story/gm/seeds/{seed['id']}/cash-in"))
    assert view['seeds'][0]['status'] == 'reached'
    with app.state.database.connect(write=True) as connection:
        assert "Payoff: bring back what was planted earlier (A deserter's boot" in note(connection)


def test_a_detail_the_player_engaged_is_given_a_meaning_tied_to_a_thread(client, app, directed, connected, provider):  # noqa: F811
    start(client)
    route(client, 'director')
    provider.replies = [reply('{"truth": "The stranger in grey keeps watch for Gannet & Pryce."}')]
    asyncio.run(plotting.adopt(app.state, plotting.engaged('{"engaged": ["the stranger in grey"]}'), 'm1', Road(1)))
    assert provider.requests[-1]['system'] == plotting.MEANING
    with app.state.database.connect() as connection:
        [seed] = plotting.seeds(connection)
        assert (seed['text'], seed['status']) == ('the stranger in grey', 'reached')
        assert any(row['text'] == seed['truth'] and row['truth'] == 'world'
                   for row in record.entries(connection, known_only=False))
    # A detail the game already has a story for is left alone.
    asyncio.run(plotting.adopt(app.state, ['the stranger in grey'], 'm2', Road(1)))
    with app.state.database.connect() as connection:
        assert len(plotting.seeds(connection)) == 1


def test_each_arc_stage_gets_planned_beats_the_gm_can_cut_and_reorder(client, app, directed, connected, provider):  # noqa: F811
    start(client)
    # With no director model, the world's own beats.
    asyncio.run(plotting.plan(app.state))
    with app.state.database.connect() as connection:
        own = plotting.beats(connection, 'the-eight-pieces', 0)
        assert [beat['source'] for beat in own] == ['world', 'world']
    route(client, 'director')
    with app.state.database.connect(write=True) as connection:
        connection.execute('DELETE FROM story_arc_beats')
        record.add(connection, 'death', 'Hob', 'Hob drowned.', 'x')
    provider.replies = [reply(json.dumps({'beats': ['A Guild clerk asks after the character.', 'Hob comes back.',
                                                    'The grove goes quiet.']}))] * 3
    asyncio.run(plotting.plan(app.state))
    ok(client.put('/api/settings', json={'gm_view': True}))
    plan = next(item for item in ok(client.get('/api/story/gm'))['plans'] if item['arc_id'] == 'the-eight-pieces')
    assert [beat['text'] for beat in plan['beats']] == ['A Guild clerk asks after the character.',
                                                        'The grove goes quiet.']
    first, second = plan['beats']
    ok(client.patch(f"/api/story/gm/beats/{first['id']}", json={'cut': True}))
    view = ok(client.patch(f"/api/story/gm/beats/{second['id']}", json={'position': 0}))
    plan = next(item for item in view['plans'] if item['arc_id'] == 'the-eight-pieces')
    assert [(beat['text'], beat['cut']) for beat in plan['beats']] == [('The grove goes quiet.', False),
                                                                       ('A Guild clerk asks after the character.', True)]
    # When the arc is due, the note gives the next beat that is not cut.
    with app.state.database.connect(write=True) as connection:
        director.advance(connection, 'vallarith', NOW, NOW.replace(day=2), 'x', Road(1, 99, 99))
        connection.execute("UPDATE story_arcs SET stage=0 WHERE arc_id='the-eight-pieces'")
        assert 'Next beat (The Eight Pieces): The grove goes quiet.' in note(connection)


def test_a_drafted_beat_keeps_to_its_own_arc():
    # The Long Border's beats may not borrow the Eight Pieces' cast (playtest M3, finding 3).
    foreign = plotting.foreign_words('vallarith', 'the-long-border')
    assert {'gannet', 'pryce', 'heartwood'} <= foreign and 'cyrel' not in foreign
    beats = ['A Gannet & Pryce clerk rides up to the Bastion.', 'Murga sends a rider down from the passes.']
    asking = plotting.drafting(director.arc('vallarith', 'the-long-border'),
                               director.arc('vallarith', 'the-long-border')['stages'][0],
                               [{'arc_id': 'the-eight-pieces', 'title': 'The contract', 'truth': 'a cult'},
                                {'arc_id': None, 'title': "The Wardens' Eyes", 'truth': 'herb bundles'},
                                {'arc_id': 'the-long-border', 'title': 'The levy', 'truth': 'short of men'}])
    # A side quest tied to no arc is no arc's beat (playtest M4, finding 8).
    assert 'The levy' in asking and 'The contract' not in asking and 'herb bundles' not in asking
    assert [beat for beat in beats if not plotting.words_of(beat) & foreign] == beats[1:]
