"""The director in a round (adventure/rounds/directing.py): warning signs before a betrayal, given to the Writer as
the sign itself; signs come first; and a nemesis given an agent of its own."""
import copy
import json
from datetime import datetime

import pytest
from test_rounds_modes import head_of, played, snapshot_of
from test_rounds_play import ok, rows, seated

from adventure import director
from adventure.rounds import declare, directing, engine, memory, writer
from adventure.rounds.contract import Declaration, Mind, State


@pytest.fixture
def steps():
    """The agents' 'pick', the memory hook, and the director's steps and hook, whatever else registered."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks, after = list(engine.COMMITS), dict(engine.AFTER)
    for listed in engine.STEPS.values():
        listed[:] = []
    engine.STEPS[State.GATHERING][:] = [('pick', declare.pick), ('director', directing.brewing)]
    engine.STEPS[State.REACTING][:] = [('signs_first', directing.signs_first)]
    engine.COMMITS[:] = [('memory', engine.committed_memory), ('director', directing.committed)]
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks
    engine.AFTER.clear()
    engine.AFTER.update(after)


def declares(*declarations):
    async def step(turn):
        for declaration in map(copy.deepcopy, declarations):
            turn.draft.declare(declaration)
            if declaration.motive:
                turn.draft.learn(declaration.seat, 'motive', declaration.motive, source=declaration.seat)
    return step


def party_of(client, *keys):
    with client.app.state.database.connect(write=True) as connection:
        for key in keys:
            connection.execute("INSERT INTO story_party (key, name, city_id, sheet, joined) VALUES "
                               "(?, ?, 'kingswood', '{}', 'x')", (key, key.title()))


def draft_of(client, turn_id):
    return json.loads(rows(client, 'SELECT draft FROM round_turns WHERE id=?', (turn_id,))[0]['draft'])


def test_a_party_member_turning_is_shown_by_a_sign_never_the_secret(client, steps):
    seated(client, 'hesk', human='you')
    party_of(client, 'hesk')
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    engine.register(State.DECLARING, 'declare', declares(Declaration('hesk', 'keeps watch by the fire',
                                                                     motive='Take the coin purse and run.')))
    first = played(client)['turn']
    assert snapshot_of(client, first['id'])['settings'].get('director', {}).get('signs', []) == []
    engine.register(State.DECLARING, 'declare', declares(Declaration('hesk', 'keeps watch by the fire')))
    second = played(client, against=first['id'])['turn']
    held = snapshot_of(client, second['id'])['settings']['director']
    [sign] = held['signs']
    assert sign in [text.format(name='Hesk') for text in directing.SIGNS['steal']]
    assert 'coin purse' not in sign and held['behind'] == [{'key': 'hesk', 'kind': 'steal', 'sign': sign}]
    assert [row['kind'] for row in rows(client, 'SELECT kind FROM betrayal_signs')] == ['steal']


def test_soured_feelings_toward_the_user_are_a_betrayal_brewing(client, steps):
    seated(client, 'hesk', human='you')
    party_of(client, 'hesk')
    with client.app.state.database.connect(write=True) as connection:
        memory.feel(connection, {'id': 'start', 'branch_id': 'first', 'seq': 0, 'number': 0}, 'hesk', 'you',
                    {'trust': -3, 'affection': -3}, 'An old wrong.', 'x')
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    turn = played(client)['turn']
    assert snapshot_of(client, turn['id'])['settings']['director']['behind'][0]['kind'] == 'turn'


def test_signs_come_first_a_betrayal_with_none_before_is_held_a_turn(client, steps):
    seated(client, 'hesk', 'mara', human='you')
    party_of(client, 'hesk', 'mara')
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    engine.register(State.DECLARING, 'declare', declares(
        Declaration('hesk', 'stabs Mara in the back', motive='She knows too much.'),
        Declaration('mara', 'studies the map')))
    first = played(client)['turn']
    draft = draft_of(client, first['id'])
    assert draft['declarations']['hesk']['intent'] == directing.HELD['attack'].format(name='Hesk')
    assert draft['declarations']['hesk']['motive'] == 'She knows too much.'
    assert draft['extra']['director']['held'] == {'hesk': 'stabs Mara in the back'}
    [sign] = directing.signs(engine.resumed(client.app.state, first['id']))
    assert sign in [text.format(name='Hesk') for text in directing.SIGNS['attack']]
    # The round Writer is given the sign to place (adventure/rounds/writer.py).
    with client.app.state.database.connect() as connection:
        assert sign in writer.context_for(connection, engine.resumed(client.app.state, first['id']), '')
    # Someone outside the party, or a betrayal with its sign placed before, goes through.
    second = played(client, against=first['id'])['turn']
    assert draft_of(client, second['id'])['declarations']['hesk']['intent'] == 'stabs Mara in the back'
    assert draft_of(client, second['id'])['extra']['moments'] == [{'kind': 'betrayal',
                                                                  'text': 'Hesk turned on the party.'}]
    # Going back to before the sign forgets it: the betrayal is held again.
    with client.app.state.database.connect() as connection:
        assert directing.signed_before(connection, engine.resumed(client.app.state, second['id']).point) == {'hesk'}
        assert directing.signed_before(connection, engine.resumed(client.app.state, first['id']).point) == set()


def test_slipping_away_is_held_too_and_mara_studying_the_map_is_not(client, steps):
    seated(client, 'hesk', 'mara', human='you')
    party_of(client, 'hesk', 'mara')
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    engine.register(State.DECLARING, 'declare', declares(Declaration('hesk', 'slips away in the night'),
                                                         Declaration('mara', 'studies the map')))
    turn = played(client)['turn']
    declarations = draft_of(client, turn['id'])['declarations']
    assert declarations['hesk']['intent'] == directing.HELD['desert'].format(name='Hesk')
    assert declarations['mara']['intent'] == 'studies the map'


def test_a_nemesis_gets_an_agent_once_in_a_campaign_that_plays_with_agents(client):
    now = datetime(1290, 5, 1, 12)
    with client.app.state.database.connect(write=True) as connection:
        director.promote(connection, 'Vark', 'fled', now, 'x')
        # No agents at the table: the campaign plays as Dungeon does.
        assert connection.execute('SELECT * FROM round_seats').fetchall() == []
    seated(client, 'mara')
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE story_nemeses SET status='dead'")
        director.promote(connection, 'Grell', 'robbed', now, 'x')
    table = {seat['key']: seat for seat in ok(client.get('/api/rounds'))['seats']}
    assert table['nemesis-grell']['mind'] == Mind.AGENT and table['nemesis-grell']['name'] == 'Grell'
    # Demoted by hand, a later grudge leaves it be.
    ok(client.put('/api/rounds/seats/nemesis-grell', json={'name': 'Grell', 'mind': 'program'}))
    with client.app.state.database.connect(write=True) as connection:
        assert directing.seat_nemesis(connection, 'Grell', 'x') is None
    assert {seat['key']: seat['mind'] for seat in ok(client.get('/api/rounds'))['seats']}['nemesis-grell'] == 'program'
    assert head_of(client) is None
