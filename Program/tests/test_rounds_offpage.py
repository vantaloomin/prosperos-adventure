"""Off-page threads in a round (adventure/rounds/offpage.py): code draws the beats, an offscreen agent writes its own
lines, and nothing is written until the turn commits."""
import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from test_beats import dealt, know  # noqa: F401 - the Life Cards dealer fixture
from test_inventory import begin

import adventure.rounds
from adventure import beats, record, story_clock, timeline
from adventure.database import decode
from adventure.rounds import engine, memory, offpage, seats
from adventure.rounds.contract import Declaration, Line, Mind, Point, State


@pytest.fixture
def rounds(monkeypatch):
    """Only Gather's pick and the off-page step run; the agent call is a stand-in that records its cues."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks = list(engine.COMMITS)
    for state, listed in engine.STEPS.items():
        listed[:] = [('pick', engine.pick)] if state == State.GATHERING else []
    engine.register(State.RESOLVING, 'offpage', offpage.offpage)
    engine.on_commit('offpage', offpage.committed)
    cues = []

    async def speak(turn, key, cue):
        cues.append((key, cue))
        if key == 'silent':
            return Declaration(seat=key, fallback=True)
        return Declaration(seat=key, lines=[Line('"Tell my sister the boots were never mine."'), Line('  ')])
    monkeypatch.setattr(adventure.rounds, 'agents', SimpleNamespace(speak=speak), raising=False)
    yield cues
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks


def a_day_ago(app):
    """The off-page clock last looked a day ago, so this round may bring a beat."""
    database = app.state.database
    with database.connect(write=True) as connection:
        now = story_clock.now(connection, database.clock)
        beats.keep_clock(connection, (now - timedelta(days=1)).isoformat(), 0)


def round_played(app, stop: State | None = None):
    async def going():
        turn = await engine.begin(app.state, timeline.ROOT, 1)
        if stop is None:
            await engine.run(turn)
            return turn
        engine.register(State.WRITING, 'stop', boom)
        try:
            await engine.run(turn)
        except RuntimeError:
            return turn

    async def boom(turn):
        raise RuntimeError('cancelled')
    return asyncio.run(going())


def seated(app, *rows):
    with app.state.database.connect(write=True) as connection:
        for key, name, mind in rows:
            seats.set_seat(connection, key, name, '', mind=mind)


def test_an_offscreen_agent_writes_its_lines_and_the_beat_lands_at_commit(client, app, dealt, rounds):  # noqa: F811
    begin(client)
    dealt.next = 'beat-boots'
    with app.state.database.connect(write=True) as connection:
        know(connection)
    seated(app, ('you', 'Ilsa', Mind.HUMAN), ('corin', 'Corin Ashby', Mind.AGENT))
    a_day_ago(app)
    turn = round_played(app)
    assert rounds == [('corin', {'kind': 'offpage', 'outcome': rounds[0][1]['outcome'], 'with': []})]
    assert 'Corin' in rounds[0][1]['outcome']
    database = app.state.database
    with database.connect() as connection:
        assert beats.gone(connection) == {'corin'}
        assert 'corin ashby' in record.dead(connection)
        row = connection.execute('SELECT key, card_id, lines FROM story_beats').fetchone()
        assert (row['key'], row['card_id']) == ('corin', 'beat-boots')
        assert decode(row['lines']) == ['Tell my sister the boots were never mine.']
        remembered = {item['kind']: item['text'] for item in memory.recall(connection, 'corin',
                                                                            Point(timeline.ROOT, 10))}
        stored = decode(connection.execute('SELECT draft FROM round_turns WHERE id=?', (turn.id,)).fetchone()['draft'])
    assert remembered['told'] == 'Corin Ashby, off the page: "Tell my sister the boots were never mine."'
    assert remembered['witnessed'][0].isupper()
    # Cutaways are off, so the Writer has none to place.
    assert stored['extra']['offpage']['cutaways'] == []
    # The turn report lists the thread, with what code decided and what the agent said.
    assert stored['extra']['w4']['offpage'] == [{'key': 'corin', 'name': 'Corin Ashby', 'card_id': 'beat-boots',
                                                 'truth': remembered['witnessed'],
                                                 'lines': ['Tell my sister the boots were never mine.']}]


def test_a_cancelled_round_leaves_no_beat_behind(client, app, dealt, rounds):  # noqa: F811
    begin(client)
    dealt.next = 'beat-boots'
    with app.state.database.connect(write=True) as connection:
        know(connection)
    seated(app, ('you', 'Ilsa', Mind.HUMAN), ('corin', 'Corin Ashby', Mind.AGENT))
    a_day_ago(app)
    round_played(app, stop=State.WRITING)
    with app.state.database.connect() as connection:
        assert beats.gone(connection) == set()
        assert connection.execute('SELECT COUNT(*) AS n FROM story_beats').fetchone()['n'] == 0


def test_a_program_characters_beat_is_code_only_and_without_agents_it_is_left_alone(
        client, app, dealt, rounds):  # noqa: F811
    begin(client)
    dealt.next = 'beat-boots'
    with app.state.database.connect(write=True) as connection:
        know(connection)
    # No agents at all: the round leaves off-page beats to today's telling.
    seated(app, ('you', 'Ilsa', Mind.HUMAN), ('corin', 'Corin Ashby', Mind.PROGRAM))
    a_day_ago(app)
    round_played(app)
    with app.state.database.connect() as connection:
        assert connection.execute('SELECT COUNT(*) AS n FROM story_beats').fetchone()['n'] == 0
    # With an agent elsewhere in the cast, Corin's beat runs in the round, written by code alone.
    seated(app, ('hesk', 'Hesk', Mind.AGENT))
    asyncio.run(_second_round(app))
    assert rounds == []
    with app.state.database.connect() as connection:
        row = connection.execute('SELECT key, lines FROM story_beats').fetchone()
    assert (row['key'], decode(row['lines'])) == ('corin', [])


async def _second_round(app):
    turn = await engine.begin(app.state, timeline.ROOT, 2)
    await engine.run(turn)


def test_a_players_line_with_an_offscreen_agent_brings_one_beat_with_its_lines(client, connected, provider, app,
                                                                               dealt, monkeypatch):  # noqa: F811
    from conftest import ok, tell
    from test_travel import reply

    from adventure.rounds import agents

    async def speak(turn, key, cue):
        return Declaration(seat=key, lines=[Line('Not my blood, mostly.')])
    monkeypatch.setattr(agents, 'speak', speak)
    begin(client)
    ok(client.put('/api/settings', json={'cutaways': True}))
    dealt.next = 'beat-knifed'
    with app.state.database.connect(write=True) as connection:
        know(connection)
    seated(app, ('corin', 'Corin Ashby', Mind.AGENT))
    for n in range(4):
        reply(provider, 'The shop is quiet.')
        tell(client, 'I wait.', f'story-000{n}')
    # Today's telling left the beat to the round, and the Writer was given it to cut away to.
    assert 'Corin Ashby took a knife in a tavern brawl' in provider.requests[-1]['messages'][-1]['content']
    with app.state.database.connect() as connection:
        rows = connection.execute('SELECT key, lines FROM story_beats').fetchall()
    assert [(row['key'], decode(row['lines'])) for row in rows] == [('corin', ['Not my blood, mostly.'])]
