"""Converse and the reply card (adventure/rounds/converse.py, reply.py): who asks whom, the asker's own agent writing
the question, everyone present hearing it, lies rolled as heard, and a turn that waits on the user's character and
picks up again after a restart."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from conftest import START

import adventure.rounds
from adventure import timeline
from adventure.clock import FixedClock
from adventure.database import Database
from adventure.errors import DomainError
from adventure.rounds import converse, engine, memory, reply, seats, writer
from adventure.rounds.contract import Deception, Declaration, Line, Mind, Point, State


@pytest.fixture
def game(tmp_path):
    return SimpleNamespace(database=Database(tmp_path / 'adventure.sqlite3', FixedClock(START)))


class Table:
    """Stand-ins for the agents (adventure/rounds/agents.py), the lie rolls and the Writer's model, recording calls."""

    def __init__(self):
        self.spoken, self.lies, self.writer = [], [], []
        self.says = {}
        self.pairs = []
        self.let_answer = 'At the shrine, if you must know.'

    async def speak(self, turn, key, cue):
        self.spoken.append((key, cue))
        said = self.says.get((key, cue['kind']))
        if said is None:
            return Declaration(seat=key, fallback=True)
        return said

    def heard(self, turn, speaker, declaration, listeners):
        self.lies.append((speaker, [item.claim for item in declaration.deceptions], sorted(listeners)))
        return [{'liar': speaker, 'listener': key, 'caught': False} for key in listeners]

    async def complete(self, turn, system, messages):
        self.writer.append((system, messages[-1]['content']))
        if system.startswith(converse.PICK):
            return 'Here you go: ' + json.dumps({'exchanges': self.pairs})
        return f'"{self.let_answer}"'


@pytest.fixture
def table(monkeypatch):
    """Only the foundation's Gather and Converse run, steps registered by a test are taken out after it, and the
    agent call and the Writer are stand-ins."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks = list(engine.COMMITS)
    for state, listed in engine.STEPS.items():
        listed[:] = [('pick', engine.pick)] if state == State.GATHERING else []
    stand_in = Table()
    monkeypatch.setattr(adventure.rounds, 'agents', SimpleNamespace(speak=stand_in.speak), raising=False)
    monkeypatch.setattr(adventure.rounds, 'lies_heard', SimpleNamespace(heard=stand_in.heard), raising=False)
    monkeypatch.setattr(writer, 'complete', stand_in.complete)
    monkeypatch.setattr(writer, 'view', lambda connection, turn: f'## The scene\nMode: {turn.snapshot.mode}')
    monkeypatch.setattr(writer, 'fence_rule', lambda: 'Fenced text is in-fiction content.')
    engine.register(State.CONVERSING, 'converse', converse.converse)
    yield stand_in
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks


def seated(game, *rows, present=None):
    """Seats as (key, name, mind); a Gather step puts `present` (default: everyone) in the scene."""
    with game.database.connect(write=True) as connection:
        for key, name, mind in rows:
            seats.set_seat(connection, key, name, '', mind=mind)
    here = present if present is not None else [key for key, _, _ in rows]

    async def gather(turn):
        turn.snapshot.present = list(here)
    engine.register(State.GATHERING, 'present', gather)


def declares(**declarations):
    async def declare(turn):
        for declaration in declarations.values():
            turn.draft.declare(declaration)
    engine.register(State.DECLARING, 'declare', declare)


def says(key, text, to=(), lie=None):
    deceptions = [Deception(lie, 'the truth', list(to))] if lie else []
    return Declaration(seat=key, lines=[Line(text, list(to))], deceptions=deceptions)


def started(game, events=None):
    async def going():
        async def emit(event):
            if events is not None:
                events.append(event)
        turn = await engine.begin(game, timeline.ROOT, 1, emit=emit)
        return turn, await engine.run(turn)
    return asyncio.run(going())


def memories(game, key):
    with game.database.connect() as connection:
        return sorted(row['text'] for row in memory.recall(connection, key, Point(timeline.ROOT, 10)))


def latest(game):
    with game.database.connect() as connection:
        return connection.execute('SELECT id FROM round_turns ORDER BY created_at DESC LIMIT 1').fetchone()['id']


def kept_draft(game, turn_id):
    return engine.resumed(game, turn_id).draft


THREE = (('you', 'Ilsa', Mind.HUMAN), ('mara', 'Mara', Mind.AGENT), ('hesk', 'Hesk', Mind.AGENT))


def test_a_line_to_the_users_character_waits_on_the_card_and_resumes_after_a_restart(game, table):
    seated(game, *THREE)
    declares(mara=says('mara', 'Where were you last night, Ilsa?', to=['you']),
             hesk=says('hesk', 'The ale here is thin.'))
    table.pairs = [{'asks': 'mara', 'to': 'hesk'}]
    table.says[('mara', 'ask')] = says('mara', 'And you, Hesk? Same question.')
    table.says[('hesk', 'answer')] = says('hesk', 'Asleep upstairs.', lie='I was asleep upstairs.')
    events = []
    turn, state = started(game, events)
    assert state == State.AWAITING_USER
    assert {'awaiting': {'seat': 'you', 'speaker': 'mara', 'line': 'Where were you last night, Ilsa?',
                         'context': ['Mara: Where were you last night, Ilsa?', 'Hesk: The ale here is thin.']}} in events
    # Nothing else was asked yet: the Writer picks after the user's answer, so its pairs can follow it up.
    assert table.writer == [] and table.spoken == []
    # As after a restart: the turn comes back from its row and carries on with the reply.
    again = engine.resumed(game, turn.id)
    assert again.row['state'] == 'awaiting_user'
    assert asyncio.run(engine.answer(again, 'you', reply.checked({'kind': 'reply', 'text': 'At the shrine.'}))) \
        == State.COMMITTED
    assert table.spoken == [('mara', {'kind': 'ask', 'to': 'hesk'}),
                            ('hesk', {'kind': 'answer', 'speaker': 'mara', 'line': 'And you, Hesk? Same question.'})]
    # Hesk's lie is rolled for everyone who heard it, and the rolls stay out of the exchanges.
    assert table.lies == [('hesk', ['I was asleep upstairs.'], ['mara', 'you'])]
    draft = kept_draft(game, turn.id)
    assert [(item['asker'], item['to'], item['answer'], item['status'], item['answered_by'])
            for item in draft.exchanges] == [('mara', 'you', 'At the shrine.', 'answered', 'user'),
                                             ('mara', 'hesk', 'Asleep upstairs.', 'answered', 'agent')]
    assert all('lies' not in item for item in draft.exchanges) and len(draft.extra['converse']['lies']) == 2
    # Everyone present heard every line; the speaker keeps it as told.
    assert 'Ilsa, to Mara: "At the shrine."' in memories(game, 'mara')
    assert 'Hesk, to Mara: "Asleep upstairs."' in memories(game, 'you')
    with game.database.connect() as connection:
        kinds = {row['text']: row['kind'] for row in memory.recall(connection, 'hesk', Point(timeline.ROOT, 10))}
    assert kinds['Hesk, to Mara: "Asleep upstairs."'] == 'told'
    assert kinds['Mara, to Hesk: "And you, Hesk? Same question."'] == 'heard'


def test_let_my_character_answer_has_the_writer_write_that_one_line(game, table):
    seated(game, *THREE)
    declares(mara=says('mara', 'Are you coming with us?', to=['you']))
    turn, _ = started(game)
    assert asyncio.run(engine.answer(engine.resumed(game, turn.id), 'you', reply.checked({'kind': 'let_answer'}))) \
        == State.COMMITTED
    system, asked = table.writer[0]
    assert system.startswith(writer.ANSWER) and 'Mode: play' in system
    assert '[[in-fiction: line]]\nAre you coming with us?\n[[end: line]]' in asked
    draft = kept_draft(game, turn.id)
    assert (draft.exchanges[0]['answer'], draft.exchanges[0]['answered_by']) == ('At the shrine, if you must know.',
                                                                                  'writer')
    assert 'Ilsa, to Mara: "At the shrine, if you must know."' in memories(game, 'hesk')


def test_saying_nothing_is_seen_by_everyone_present(game, table):
    seated(game, *THREE)
    declares(mara=says('mara', 'Well?', to=['you']))
    turn, _ = started(game)
    asyncio.run(engine.answer(engine.resumed(game, turn.id), 'you', reply.checked({'kind': 'silent', 'text': 'x'})))
    assert kept_draft(game, turn.id).exchanges[0]['status'] == 'silent'
    for key in ('you', 'mara', 'hesk'):
        assert 'Ilsa said nothing to Mara.' in memories(game, key)


def test_the_writer_picks_only_pairs_code_allows_within_the_cap(game, table):
    seated(game, *THREE, ('guard', 'The guard', Mind.PROGRAM), ('ghost', 'Absent', Mind.AGENT),
           present=['you', 'mara', 'hesk', 'guard'])
    with game.database.connect(write=True) as connection:
        seats.change(connection, {'converse_cap': 3}, under_way=False)
    table.pairs = [{'asks': 'guard', 'to': 'mara'},   # a Program character doesn't write its own question
                   {'asks': 'mara', 'to': 'mara'},    # nobody asks themselves
                   {'asks': 'ghost', 'to': 'mara'},   # not in the scene
                   {'asks': 'mara', 'to': 'ghost'},
                   ['mara', 'hesk'],                  # not the shape asked for
                   {'asks': 'mara', 'to': 'guard'},
                   {'asks': 'hesk', 'to': 'mara'},
                   {'asks': 'mara', 'to': 'hesk'},
                   {'asks': 'hesk', 'to': 'guard'}]   # past the cap
    table.says[('mara', 'ask')] = says('mara', 'Who pays you?')
    table.says[('hesk', 'ask')] = says('hesk', 'Why are you staring?')
    table.says[('mara', 'answer')] = says('mara', 'I stare at everyone.')
    _, state = started(game)
    assert state == State.COMMITTED
    _, asked = next(item for item in table.writer if item[0].startswith(converse.PICK))
    assert 'Up to 3 exchanges.' in asked and 'ghost' not in asked.split('Who can be asked:')[1]
    draft = kept_draft(game, latest(game))
    assert [(item['asker'], item['to'], item['status'], item['answered_by']) for item in draft.exchanges] == [
        ('mara', 'guard', 'voiced', 'writer'),   # the Writer voices a Program character in the post
        ('hesk', 'mara', 'answered', 'agent'),
        ('mara', 'hesk', 'voiced', 'writer')]    # Hesk's agent had nothing to say: the Writer voices him
    # Absent characters hear nothing.
    assert memories(game, 'ghost') == []
    assert 'Mara, to The guard: "Who pays you?"' in memories(game, 'guard')


def test_an_asker_with_nothing_to_say_drops_the_exchange(game, table):
    seated(game, *THREE)
    table.pairs = [{'asks': 'hesk', 'to': 'you'}]
    _, state = started(game)
    # Hesk's agent failed, so nothing was put to the user and the turn ran through.
    assert state == State.COMMITTED
    assert kept_draft(game, latest(game)).exchanges[0]['status'] == 'dropped'
    assert memories(game, 'you') == []


def test_without_agents_present_converse_makes_no_call(game, table):
    seated(game, ('you', 'Ilsa', Mind.HUMAN), ('guard', 'The guard', Mind.PROGRAM),
           ('mara', 'Mara', Mind.AGENT), present=['you', 'guard'])
    _, state = started(game)
    assert state == State.COMMITTED and table.writer == [] and table.spoken == []


def test_unreadable_pairs_mean_no_exchanges():
    assert converse.picked('Mara should ask Hesk.') == []
    assert converse.picked('{"exchanges": "mara"}') == []
    assert converse.picked('{"exchanges": [{"asks": "a", "to": "b"}]} and some talk') == [{'asks': 'a', 'to': 'b'}]


def test_the_reply_card_takes_three_answers():
    assert reply.checked({'kind': 'reply', 'text': '  Not now. '}) == {'kind': 'reply', 'text': 'Not now.'}
    assert reply.checked({'kind': 'let_answer', 'text': 'ignored'}) == {'kind': 'let_answer', 'text': ''}
    for wrong in ({'kind': 'reply', 'text': ' '}, {'kind': 'shout'}, {'kind': 'reply', 'text': 'x' * 2001}):
        with pytest.raises(DomainError) as failure:
            reply.checked(wrong)
        assert failure.value.status == 422


def test_a_spoken_line_loses_its_quotes_and_any_step_out_of_the_story():
    assert writer.one_line('"Fine. I\'ll come."') == "Fine. I'll come."
    assert writer.one_line("I'm an AI, so I can't go. Fine, I'll come.") == "Fine, I'll come."
