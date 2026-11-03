"""Corrections and struck inventions (adventure/rounds/corrections.py): turn-keyed patches every later read sees,
in one transaction, with the later turns that named what changed."""
import asyncio
from types import SimpleNamespace

import pytest
from conftest import START, ok

from adventure import sheet, timeline
from adventure.clock import FixedClock
from adventure.database import Database
from adventure.errors import DomainError
from adventure.rounds import corrections, engine, memory, report
from adventure.rounds.contract import Point, State


@pytest.fixture
def game(tmp_path):
    return SimpleNamespace(database=Database(tmp_path / 'adventure.sqlite3', FixedClock(START)))


@pytest.fixture
def steps():
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks = list(engine.COMMITS)
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks


def play(app, seq, post='', learn=(), inventions=()):
    async def write(turn):
        for holder, text in learn:
            turn.draft.learn(holder, 'witnessed', text, importance=2)
        turn.draft.post = post
        if inventions:
            turn.draft.extra['w4'] = {'inventions': list(inventions)}

    engine.register(State.WRITING, 'write', write)

    async def going():
        turn = await engine.begin(app, timeline.ROOT, seq)
        assert await engine.run(turn) == State.COMMITTED
        return turn
    return asyncio.run(going())


def recalled(app, key, seq=100):
    with app.database.connect() as connection:
        return [row['text'] for row in memory.recall(connection, key, Point(timeline.ROOT, seq))]


def test_a_memory_struck_or_reworded_is_read_that_way_from_then_on(game, steps):
    first = play(game, 1, learn=[('hesk', 'Mara took the ledger from the desk.'), ('hesk', 'The lamp was out.')])
    play(game, 3, post='Hesk watched the ledger burn.')
    with game.database.connect(write=True) as connection:
        rows = {row['text']: row['id'] for row in memory.recall(connection, 'hesk', Point(timeline.ROOT, 100))}
        done = corrections.correct(connection, first.id, [
            {'kind': 'memory', 'memory_id': rows['Mara took the ledger from the desk.']},
            {'kind': 'memory', 'memory_id': rows['The lamp was out.'], 'text': 'The lamp was low.'}],
            'Hesk was asleep and could not have seen it.', game.database.now())
    assert recalled(game, 'hesk') == ['The lamp was low.']
    # A read from before the corrected turn never had the memory in the first place.
    assert recalled(game, 'hesk', seq=1) == []
    assert [item['number'] for item in done['later']] == [2]
    with game.database.connect() as connection:
        listed = corrections.of_turn(connection, first.id)
    assert [(item['kind'], item['after']) for item in listed] == [('memory', None), ('memory', 'The lamp was low.')]
    assert listed[0]['why'] == 'Hesk was asleep and could not have seen it.'


def test_feelings_and_stats_are_corrected_in_one_go(game, steps):
    turn = play(game, 1)
    with game.database.connect(write=True) as connection:
        corrections.correct(connection, turn.id, [
            {'kind': 'feeling', 'from': 'hesk', 'to': 'mara', 'changes': {'trust': -2, 'nonsense': 5}},
            {'kind': 'stat', 'stat': 'Vitality', 'value': 14}], 'The fight went the other way.', game.database.now())
    with game.database.connect() as connection:
        assert memory.toward(connection, 'hesk', 'mara', Point(timeline.ROOT, 100))['trust'] == -2
        assert sheet.stats(connection)['Vitality'] == 14
        stat = [item for item in corrections.of_turn(connection, turn.id) if item['kind'] == 'stat'][0]
    assert (stat['before'], stat['after']) == (10, 14)


def test_a_bad_change_undoes_the_whole_correction(game, steps):
    turn = play(game, 1)
    with pytest.raises(DomainError):
        with game.database.connect(write=True) as connection:
            corrections.correct(connection, turn.id, [{'kind': 'stat', 'stat': 'Vitality', 'value': 14},
                                                      {'kind': 'memory', 'memory_id': 'nope'}], '', game.database.now())
    with game.database.connect() as connection:
        assert sheet.stats(connection)['Vitality'] == 10 and corrections.of_turn(connection, turn.id) == []


def test_striking_an_invention_takes_it_out_of_memory_and_hands_back_the_passage(game, steps):
    invented = {'name': 'Varn', 'text': 'A man called Varn waited by the gate.'}
    turn = play(game, 1, post='A man called Varn waited by the gate. The rain kept on.',
                learn=[('hesk', 'Varn waited by the gate.'), ('hesk', 'The rain kept on.')], inventions=[invented])
    play(game, 3, post='Varn was gone by morning.')
    with game.database.connect(write=True) as connection:
        struck = corrections.strike(connection, turn.id, 'varn', game.database.now())
        with pytest.raises(DomainError):
            corrections.strike(connection, turn.id, 'Nobody', game.database.now())
    assert struck['passage'] == invented['text'] and [item['number'] for item in struck['later']] == [2]
    assert recalled(game, 'hesk') == ['The rain kept on.']
    with game.database.connect() as connection:
        shown = report.report(connection, turn.id)
    assert shown['inventions'] == [invented | {'struck': True}]
    assert [item['kind'] for item in shown['corrections']] == ['memory', 'invention']


def test_corrections_need_the_gm_view_over_the_api(client, app, steps):
    turn = play(app.state, 1)
    body = {'changes': [{'kind': 'stat', 'stat': 'Luck', 'value': 12}], 'why': 'Misread.'}
    assert client.post(f'/api/story/turns/{turn.id}/corrections', json=body).status_code == 403
    ok(client.put('/api/story/table', json={'gm_view': True}))
    done = ok(client.post(f'/api/story/turns/{turn.id}/corrections', json=body))
    assert len(done['corrections']) == 1 and done['later'] == []
    assert ok(client.get(f'/api/story/turns/{turn.id}/corrections'))[0]['after'] == 12
    assert client.get('/api/story/turns/nope/corrections').status_code == 404


def test_the_committed_reply_is_found_where_either_writer_left_it():
    assert corrections.reply_of({'extra': {'telling': {'reply': {'id': 'm1'}}}}) == 'm1'
    assert corrections.reply_of({'extra': {'w4': {'reply': {'id': 'm2'}, 'inventions': []}}}) == 'm2'
    assert corrections.reply_of({'extra': {}}) is None
