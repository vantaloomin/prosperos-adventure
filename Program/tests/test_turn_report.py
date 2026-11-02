"""The checks in a round's Writing step and the turn report (adventure/rounds/report.py): the house rules frozen at
Gather, the Reviewer and the scan after the Writer, the settled post committed, and the report read back by mode."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from conftest import START

from adventure import table, timeline
from adventure.clock import FixedClock
from adventure.database import Database, decode
from adventure.rounds import engine, house_rules, report, seats, turns
from adventure.rounds.contract import Brief, Declaration, Line, Mind, Mode, State, TurnResult
from adventure.rounds.draft import Draft

POST = ('Mara worked the pick — slow. Suddenly the lock gave.\n\n"Hold the lamp steady," Mara said.\n\n'
        '"And then we take the whole ledger and burn the counting house down," Mara added.')


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


def seated(game, mode=Mode.PLAY):
    database = game.database
    with database.connect(write=True) as connection:
        seats.set_seat(connection, 'mara', 'Mara Quell', database.now(), mind=Mind.HUMAN)
        seats.set_seat(connection, 'hesk', 'Hesk', database.now(), mind=Mind.AGENT)
        seats.change(connection, {'mode': str(mode)}, False)
        table.change(connection, {'pov': 'third', 'tense': 'past'})
        house_rules.change(connection, {'words': ['suddenly']}, database.now())
        house_rules.rule(connection, 'Hesk never drinks.', database.now())


async def write(turn):
    """A Writer that leaves an em dash, an outlawed word and a line Mara never declared."""
    turn.draft.declare(Declaration('mara', 'I pick the lock.', [Line('Hold the lamp steady.')], 'Get the ledger.'))
    turn.draft.declare(Declaration('hesk', 'Hesk holds the lamp.', [], 'Sell Mara out at dawn.'))
    turn.draft.result = TurnResult(
        declarations=list(turn.draft.declarations.values()),
        rolls=[{'actor': 'Mara', 'action': 'pick the lock', 'stat': 'Luck', 'band': 'success_cost', 'natural': 14,
                'total': 16, 'difficulty': 15}],
        brief=Brief(beats=['The storm breaks.'], math=['The pick snaps: one fewer in the kit.'],
                    stop_point='Mara decides what to do with the ledger.'))
    turn.draft.post = POST
    turn.draft.extra['w4'] = {'inventions': ['The counting house has a back stair.']}


def played(game):
    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1)
        assert await engine.run(turn) == State.COMMITTED
        return turn
    return asyncio.run(going())


def test_the_post_is_checked_after_the_writer_and_committed_settled(game, steps):
    seated(game)
    engine.register(State.WRITING, 'write', write)  # registered after the checks: they still run last
    turn = played(game)
    with game.database.connect() as connection:
        row = turns.get(connection, turn.id)
    snapshot, draft = decode(row['snapshot']), Draft.of(decode(row['draft']))
    frozen = snapshot['settings']['house_rules']
    assert 'suddenly' in frozen['words'] and frozen['rulings'] == ['Hesk never drinks.']
    assert snapshot['settings']['reviewer'] is False
    # No model, so no rewrite: code fixed the dash and cut the sentence with the outlawed word.
    assert '—' not in draft.post and 'Suddenly' not in draft.post
    assert draft.post.startswith('Mara worked the pick, slow.')
    staged = draft.extra['w5']
    assert staged['cut'] == ['Suddenly the lock gave.'] and staged['rewrites'] == 0
    kinds = {item['kind'] for item in staged['scan']['findings']}
    assert 'past-stop' in kinds and 'outlawed-word' not in kinds


def test_the_report_shows_what_the_mode_allows(game, steps):
    seated(game)
    engine.register(State.WRITING, 'write', write)
    turn = played(game)
    with game.database.connect() as connection:
        found = report.report(connection, turn.id)
        gm = report.report(connection, turn.id, gm_view=True)
        line = report.status(connection)
    assert found['set'] == {'intent': 'I pick the lock.', 'lines': ['Hold the lamp steady.'],
                            'beats': ['The storm breaks.']}
    assert found['rolls'] == [{'actor': 'Mara', 'action': 'pick the lock', 'stat': 'Luck',
                               'result': 'succeeds, at a real cost'}]
    assert found['numbers'] == ['The pick snaps: one fewer in the kit.']
    assert found['inventions'] == ['The counting house has a back stair.']
    assert found['checks']['cut'] == ['Suddenly the lock gave.']
    assert found['next'] == 'Mara decides what to do with the ledger.'
    # In Play the user sees only their own character's motive; the GM view shows everyone's.
    assert found['motives'] == [{'seat': 'mara', 'motive': 'Get the ledger.'}]
    assert {item['seat'] for item in gm['motives']} == {'mara', 'hesk'}
    assert line['last'] == {'turn_id': turn.id, 'number': 1} and line['pending'] is None
    assert line['offpage_within'] >= 1


def test_rolls_show_their_numbers_when_the_table_shows_odds(game, steps):
    seated(game, Mode.WATCH)
    engine.register(State.WRITING, 'write', write)
    with game.database.connect(write=True) as connection:
        connection.execute('INSERT INTO story_campaign (id, show_odds) VALUES (1, 1) ON CONFLICT(id) DO UPDATE SET '
                           'show_odds=1')
    turn = played(game)
    with game.database.connect() as connection:
        found = report.report(connection, turn.id)
    assert found['rolls'][0]['natural'] == 14 and found['rolls'][0]['total'] == 16
    assert {item['seat'] for item in found['motives']} == {'mara', 'hesk'}


def test_the_reviewer_runs_when_it_is_on(game, steps, monkeypatch):
    seated(game)
    with game.database.connect(write=True) as connection:
        house_rules.change(connection, {'reviewer': 'on'}, game.database.now())
    engine.register(State.WRITING, 'write', write)
    asked = []

    async def complete(system, messages):
        asked.append(system)
        if system.startswith(report.reviewer.SYSTEM):
            return json.dumps({'notes': [{'quote': 'Hold the lamp steady', 'problem': 'Flat.', 'fix': 'Sharper.'}]})
        if system.startswith(report.reviewer.APPLY):
            return json.dumps({'text': POST.replace('Hold the lamp steady', 'Keep that lamp still'), 'declined': []})
        return messages[0]['content'].split('Narration:\n\n')[1].split('\n\nFix these:')[0]

    monkeypatch.setattr(report, 'model', lambda turn: complete)
    turn = played(game)
    with game.database.connect() as connection:
        draft = Draft.of(decode(turns.get(connection, turn.id)['draft']))
    assert 'Keep that lamp still' in draft.post
    assert draft.extra['w5']['review'][0]['applied'] is True
    assert draft.extra['w5']['rewrites'] == 2 and '—' not in draft.post


def test_a_turn_with_no_post_is_left_alone(game, steps):
    turn = played(game)
    with game.database.connect() as connection:
        draft = Draft.of(decode(turns.get(connection, turn.id)['draft']))
    assert draft.post == '' and 'w5' not in draft.extra


def test_the_report_and_status_line_over_the_api(client, app, steps):
    seated(app.state)
    engine.register(State.WRITING, 'write', write)
    turn = played(app.state)
    found = client.get(f'/api/story/turns/{turn.id}/report')
    assert found.status_code == 200 and found.json()['marks'] == []
    assert [item['seat'] for item in found.json()['motives']] == ['mara']
    assert client.get('/api/story/turns/nope/report').status_code == 404
    assert client.get('/api/story/status-line').json()['last']['turn_id'] == turn.id


def test_todays_single_player_turn_keeps_its_own_checks(game, steps):
    async def solo_write(turn):
        turn.draft.post = 'She ran — hard.'

    engine.register(State.WRITING, 'write', solo_write)

    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1)
        turn.draft.extra['solo'] = {'user': {}, 'reply': {}}
        assert await engine.run(turn) == State.COMMITTED
        return turn
    turn = asyncio.run(going())
    with game.database.connect() as connection:
        row = turns.get(connection, turn.id)
    assert 'house_rules' not in decode(row['snapshot'])['settings']
    assert Draft.of(decode(row['draft'])).post == 'She ran — hard.'
