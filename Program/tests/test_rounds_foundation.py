"""The round loop's foundation (adventure/rounds/): turns as transactions, steps plugged into the state machine, the
reply card pause, seats and settings, and memory and feelings that follow branches."""
import asyncio
from types import SimpleNamespace

import pytest
from conftest import START

from adventure import timeline
from adventure.clock import FixedClock
from adventure.database import Database
from adventure.errors import DomainError
from adventure.rounds import engine, memory, seats, turns
from adventure.rounds.contract import (
    Deception,
    Declaration,
    Line,
    Mind,
    Point,
    Snapshot,
    State,
    TurnResult,
    Whisper,
    plain,
)
from adventure.rounds.draft import Draft


@pytest.fixture
def game(tmp_path):
    return SimpleNamespace(database=Database(tmp_path / 'adventure.sqlite3', FixedClock(START)))


@pytest.fixture
def steps():
    """Only the foundation's own steps run in these tests (other parts' modules may have registered theirs), and
    steps registered by a test are taken out again after it."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks = list(engine.COMMITS)
    for listed in engine.STEPS.values():
        listed[:] = [(name, step) for name, step in listed if step is engine.pick]
    # Another part may have replaced 'pick' under its name: the foundation's own is put back for these tests.
    engine.STEPS[State.GATHERING][:] = [('pick', engine.pick)]
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks


def play(game, seq, branch=timeline.ROOT, learn=(), feel=()):
    """One committed turn at (branch, seq) whose draft holds the given knowledge and feelings."""
    async def going():
        turn = await engine.begin(game, branch, seq)
        for holder, kind, text, weight, about in learn:
            turn.draft.learn(holder, kind, text, importance=weight, about=about)
        for from_key, to_key, changes in feel:
            turn.draft.feel(from_key, to_key, changes, 'because')
        assert await engine.run(turn) == State.COMMITTED
        return turn
    return asyncio.run(going())


def branch_from(game, parent, fork_seq, name):
    with game.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_branches (id, parent_id, fork_seq, tip, created_at) VALUES (?, ?, ?, NULL, '')",
                           (name, parent, fork_seq))


def texts(game, key, point, focus=''):
    with game.database.connect() as connection:
        return [row['text'] for row in memory.recall(connection, key, point, focus)]


def test_memory_follows_branches(game, steps):
    play(game, 1, learn=[('hesk', 'witnessed', 'Mara drew a knife at the inn.', 1, 'mara')])
    play(game, 2, learn=[('hesk', 'heard', 'Mara says the bridge is guarded.', 1, 'mara')])
    play(game, 3, learn=[('mara', 'motive', 'I will sell Hesk to the wardens.', 2, 'hesk')])
    # Going back to before the second turn: a branch from there sees only the first.
    branch_from(game, timeline.ROOT, 2, 'b2')
    assert texts(game, 'hesk', Point('b2', 10)) == ['Mara drew a knife at the inn.']
    assert texts(game, 'hesk', Point(timeline.ROOT, 10)) == ['Mara says the bridge is guarded.',
                                                            'Mara drew a knife at the inn.']
    # What the new branch learns is its own; the old branch never sees it.
    play(game, 4, branch='b2', learn=[('hesk', 'heard', 'Mara says the ford is safe.', 1, 'mara')])
    assert texts(game, 'hesk', Point('b2', 10)) == ['Mara says the ford is safe.', 'Mara drew a knife at the inn.']
    assert 'Mara says the ford is safe.' not in texts(game, 'hesk', Point(timeline.ROOT, 10))
    # A memory is only ever its holder's: Mara's motive is not Hesk's.
    assert not any('wardens' in text for text in texts(game, 'hesk', Point(timeline.ROOT, 10)))
    assert texts(game, 'mara', Point(timeline.ROOT, 10)) == ['I will sell Hesk to the wardens.']


def test_memory_fades_as_it_is_read_but_what_matters_stays_sharp(game, steps):
    play(game, 1, learn=[('hesk', 'witnessed', 'The innkeeper wore a green apron.', 1, 'innkeeper'),
                        ('hesk', 'witnessed', 'Mara owes the wardens forty crowns.', 1, 'mara'),
                        ('hesk', 'witnessed', 'Ilsa sang by the fire.', 1, 'ilsa')],
         feel=[('hesk', 'ilsa', {'affection': 2})])
    play(game, 2, feel=[('hesk', 'ilsa', {'affection': 2})])
    for seq in range(3, 30):
        play(game, seq)

    def faded(point):
        with game.database.connect() as connection:
            return {row['text']: row['faded'] for row in memory.recall(connection, 'hesk', point)}
    later = faded(Point(timeline.ROOT, 100))
    assert later['The innkeeper wore a green apron.'] is True
    # A debt is important whatever the step that found it said, and someone Hesk is fond of stays sharp.
    assert later['Mara owes the wardens forty crowns.'] is False
    assert later['Ilsa sang by the fire.'] is False
    # Read from early on, nothing has faded: fading never rewrote a row.
    assert not any(faded(Point(timeline.ROOT, 5)).values())


def test_bringing_a_memory_back_refreshes_it_on_that_branch_only(game, steps):
    play(game, 1, learn=[('hesk', 'witnessed', 'The innkeeper wore a green apron.', 1, 'innkeeper')])
    for seq in range(2, 28):
        play(game, seq)
    with game.database.connect() as connection:
        memory_id = memory.recall(connection, 'hesk', Point(timeline.ROOT, 100))[0]['id']
    branch_from(game, timeline.ROOT, 27, 'b2')

    async def mention():
        turn = await engine.begin(game, timeline.ROOT, 40)
        turn.draft.bring_back('hesk', memory_id)
        await engine.run(turn)
    asyncio.run(mention())
    with game.database.connect() as connection:
        assert memory.recall(connection, 'hesk', Point(timeline.ROOT, 100))[0]['faded'] is False
        assert memory.recall(connection, 'hesk', Point('b2', 100))[0]['faded'] is True


def test_feelings_toward_anyone_add_up_within_their_ranges(game, steps):
    with game.database.connect(write=True) as connection:
        # A campaign's starting feelings, seen from every branch.
        memory.feel(connection, {'branch_id': timeline.ROOT, 'seq': 0}, 'mara', 'hesk', {'trust': 2}, 'Old friends.')
    play(game, 1, feel=[('mara', 'hesk', {'trust': -9, 'fear': 1})])
    play(game, 2, feel=[('mara', 'hesk', {'trust': -2, 'fear': 2}), ('mara', 'ilsa', {'desire': 1})])
    branch_from(game, timeline.ROOT, 2, 'b2')
    with game.database.connect() as connection:
        now = memory.feelings(connection, 'mara', Point(timeline.ROOT, 10))
        assert {axis: now['hesk'][axis] for axis in ('trust', 'fear')} == {'trust': -2, 'fear': 3}
        assert now['ilsa']['desire'] == 1
        assert now['hesk']['impressions'] == ['Old friends.', 'because']
        back = memory.toward(connection, 'mara', 'hesk', Point('b2', 10))
        assert (back['trust'], back['fear']) == (0, 1)
        assert memory.toward(connection, 'hesk', 'mara', Point(timeline.ROOT, 10))['trust'] == 0


def test_steps_run_in_order_and_a_name_registered_again_replaces_its_step(game, steps):
    ran = []

    def step(name):
        async def run(turn):
            ran.append(name)
        return run
    engine.register(State.DECLARING, 'declare', step('declare'))
    engine.register(State.RESOLVING, 'resolve', step('resolve'))
    engine.register(State.DECLARING, 'whispers', step('whispers'))
    engine.register(State.DECLARING, 'declare', step('declare again'))
    events = []

    async def emit(event):
        events.append(event)

    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1, emit=emit)
        return await engine.run(turn)
    assert asyncio.run(going()) == State.COMMITTED
    assert ran == ['declare again', 'whispers', 'resolve']
    states = [event['round']['state'] for event in events if 'round' in event]
    assert states == ['gathering', 'declaring', 'reacting', 'conversing', 'resolving', 'writing', 'committing', 'idle']


def test_a_turn_waits_on_the_reply_card_and_runs_on_from_the_step_that_asked(game, steps):
    asked = []

    async def converse(turn):
        reply = turn.draft.replies.get('you')
        if reply is None:
            asked.append('asked')
            turn.draft.wait_for('you', 'mara', 'Where were you last night?', ['a', 'b', 'c'])
            return
        turn.draft.learn('mara', 'heard', f"You said: {reply['text']}", source='you')

    async def before(turn):
        asked.append('before')
    engine.register(State.CONVERSING, 'before', before)
    engine.register(State.CONVERSING, 'converse', converse)
    events = []

    async def emit(event):
        events.append(event)

    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1, emit=emit)
        assert await engine.run(turn) == State.AWAITING_USER
        return turn.id
    turn_id = asyncio.run(going())
    assert {'awaiting': {'seat': 'you', 'speaker': 'mara', 'line': 'Where were you last night?',
                         'context': ['b', 'c']}} in events
    # Read back from its row, as after a restart, it carries on with the reply.
    turn = engine.resumed(game, turn_id)
    assert turn.row['state'] == 'awaiting_user'
    assert asyncio.run(engine.answer(turn, 'you', {'kind': 'reply', 'text': 'At the shrine.'})) == State.COMMITTED
    assert asked == ['before', 'asked']
    assert texts(game, 'mara', Point(timeline.ROOT, 10)) == ['You said: At the shrine.']


def test_a_failed_step_discards_the_turn_and_keeps_nothing(game, steps):
    async def learns(turn):
        turn.draft.learn('hesk', 'witnessed', 'Something that never happened.')

    async def breaks(turn):
        raise RuntimeError('the model fell over')
    engine.register(State.DECLARING, 'learns', learns)
    engine.register(State.RESOLVING, 'breaks', breaks)

    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1)
        await engine.run(turn)
    with pytest.raises(RuntimeError):
        asyncio.run(going())
    with game.database.connect() as connection:
        row = connection.execute('SELECT state, error FROM round_turns').fetchone()
        assert (row['state'], row['error']) == ('discarded', 'the model fell over')
        assert turns.under_way(connection) is None
    assert texts(game, 'hesk', Point(timeline.ROOT, 10)) == []


def test_a_commit_hook_that_fails_keeps_nothing_of_the_turn(game, steps):
    def broken(connection, turn):
        raise RuntimeError('no room')
    engine.on_commit('broken', broken)
    with pytest.raises(RuntimeError):
        play(game, 1, learn=[('hesk', 'witnessed', 'A fact that must not be kept.', 1, '')])
    assert texts(game, 'hesk', Point(timeline.ROOT, 10)) == []


def test_only_one_turn_is_played_at_a_time(game, steps):
    async def going():
        await engine.begin(game, timeline.ROOT, 1)
        await engine.begin(game, timeline.ROOT, 2)
    with pytest.raises(DomainError) as failure:
        asyncio.run(going())
    assert failure.value.status == 409


def test_seats_settings_and_who_decides_this_turn(game, steps):
    database = game.database
    with database.connect(write=True) as connection:
        seats.set_seat(connection, 'you', 'Ilsa', database.now(), mind=Mind.HUMAN)
        for index, key in enumerate(('mara', 'hesk', 'orrin')):
            seats.set_seat(connection, key, key.title(), database.now(), mind=Mind.AGENT, notes='Keeps her word.')
        # One human sits at a time.
        seats.set_seat(connection, 'orrin', 'Orrin', database.now(), mind=Mind.HUMAN)
        assert [seat.mind for seat in seats.seats(connection)] == ['program', 'agent', 'agent', 'human']
        seats.set_seat(connection, 'you', 'Ilsa', database.now(), mind=Mind.HUMAN)
        seats.set_seat(connection, 'orrin', 'Orrin', database.now(), mind=Mind.AGENT)
        seats.change(connection, {'agent_cap': 2}, under_way=False)
        with pytest.raises(DomainError):
            seats.change(connection, {'converse_cap': 13}, under_way=False)
        with pytest.raises(DomainError):
            seats.change(connection, {'mode': 'director'}, under_way=False)

    async def going(mode=None):
        turn = await engine.begin(game, timeline.ROOT, 1 if mode is None else 2, mode=mode)
        if mode is None:
            with database.connect(write=True) as connection:
                # Asked for mid-turn: waits for Idle, so the turn finishes as it started.
                seats.change(connection, {'mode': 'watch', 'agent_cap': 3}, under_way=True)
                assert seats.settings(connection)['mode'] == 'play'
        await engine.run(turn)
        return turn
    turn = asyncio.run(going())
    assert [(seat.key, seat.mind) for seat in turn.snapshot.seats] == [
        ('you', 'human'), ('mara', 'agent'), ('hesk', 'agent'), ('orrin', 'program')]
    with database.connect() as connection:
        assert seats.settings(connection) | {'queued': None} == {'mode': 'watch', 'agent_cap': 3, 'converse_cap': 4,
                                                                 'queued': None}
    # Outside Play the user's character is not theirs to declare for.
    watched = asyncio.run(going('watch'))
    assert watched.snapshot.human() is None and watched.snapshot.seat('you').mind == 'program'
    assert [seat.key for seat in watched.snapshot.agents()] == ['mara', 'hesk', 'orrin']


def test_the_snapshot_and_draft_come_back_from_json_as_they_were(game):
    declaration = Declaration('mara', 'I slip the purse from his belt.', [Line('Lovely night.', ['hesk'])],
                              'He owes me.', [Deception('I was at the shrine.', 'I was at the docks.', ['hesk'])],
                              [Whisper('Tonight, by the well.', ['orrin'])])
    draft = Draft()
    draft.declare(declaration)
    draft.learn('hesk', 'belief', 'Mara was at the shrine.', source='mara', about='mara', importance=2)
    draft.result = TurnResult(declarations=[declaration], rolls=[{'actor': 'mara', 'band': 'success'}])
    assert Draft.of(draft.data()).data() == draft.data()
    assert Draft.of(draft.data()).declarations['mara'] == declaration
    snapshot = Snapshot('t1', 'play', Point('first', 3), 2)
    assert Snapshot.of(plain(snapshot)) == snapshot
    # A key the code doesn't know yet (a newer draft) is ignored, not an error.
    assert Declaration.of(plain(declaration) | {'mood': 'sly'}) == declaration


def test_a_new_story_forgets_every_character_and_turn(client):
    game = client.app.state
    play(game, 1, learn=[('hesk', 'witnessed', 'The well is dry.', 1, '')])
    assert client.delete('/api/story').status_code == 200
    with game.database.connect() as connection:
        assert turns.count(connection) == 0
    assert texts(game, 'hesk', Point(timeline.ROOT, 10)) == []


def test_a_step_can_ask_to_run_straight_after_another_whichever_comes_first(steps):
    async def nothing(turn):
        pass
    engine.register(State.WRITING, 'checks', nothing, after='write')
    engine.register(State.WRITING, 'report', nothing)
    assert [name for name, _ in engine.STEPS[State.WRITING]] == ['checks', 'report']
    engine.register(State.WRITING, 'write', nothing)
    engine.register(State.WRITING, 'tidy', nothing, after='write')
    assert [name for name, _ in engine.STEPS[State.WRITING]] == ['report', 'write', 'checks', 'tidy']
    engine.unregister(State.WRITING, 'write')
    assert [name for name, _ in engine.STEPS[State.WRITING]] == ['report', 'checks', 'tidy']


def test_a_turn_knows_the_line_it_opens_on(game, steps):
    database = game.database
    with database.connect(write=True) as connection:
        for seq, mode in ((1, 'play'), (2, 'author')):
            connection.execute("INSERT INTO story_messages (id, seq, role, text, city_id, place_id, created_at, mode) "
                               "VALUES (?, ?, 'user', ?, 'baltimore', 'p', '', ?)", (f'm{seq}', seq, f'text {seq}', mode))

    async def opened(seq, mode):
        turn = await engine.begin(game, timeline.ROOT, seq, anchor_id=f'm{seq}', mode=mode)
        await engine.run(turn)
        return turn.snapshot.settings
    assert asyncio.run(opened(1, 'play')) == {'message_id': 'm1', 'said': 'text 1'}
    assert asyncio.run(opened(2, 'author')) == {'message_id': 'm2', 'nudge': 'text 2'}
