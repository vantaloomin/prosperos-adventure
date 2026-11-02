"""Agent minds in the round loop (adventure/rounds/agents.py, declare.py, lies_heard.py, react.py): what an agent
gives back is validated by code, agents are picked within the cap, everyone declares at once, lies are rolled as
heard, each agent reacts once, feelings move from rolls, and a broken, slow or refusing model falls back to the
character's Program mind without losing the turn. The model is a stub provider throughout."""
import asyncio
import json
import random
from types import SimpleNamespace

import pytest
from conftest import START, FakeProvider

from adventure import feelings, pace, text_models, timeline
from adventure.clock import FixedClock
from adventure.database import Database
from adventure.providers.chat import Chunk
from adventure.providers.config import ProfileCreate
from adventure.providers.scheduling import RequestScheduler
from adventure.providers.vault import MemoryVault
from adventure.rounds import agents, declare, engine, lies_heard, memory, react, seats
from adventure.rounds.contract import Mind, Mode, Point, Seat, Snapshot, State, TurnResult

MODEL = {'provider': 'compatible', 'model': 'stub', 'base_url': 'https://models.example/v1'}


@pytest.fixture
def game(tmp_path):
    database = Database(tmp_path / 'adventure.sqlite3', FixedClock(START))
    app = SimpleNamespace(database=database, provider=FakeProvider(), vault=MemoryVault(),
                          scheduler=RequestScheduler(), dice=random.Random(7))
    text_models.create(database, app.vault, ProfileCreate(name='Stub', config=MODEL, api_key='key'))
    pace.SPENDS.pop(str(database.path), None)
    return app


@pytest.fixture
def steps():
    """The agents' steps, and only theirs (plus the foundation's), for each test; put back as they were after."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks = list(engine.COMMITS)
    for state in engine.STEPS:
        engine.STEPS[state][:] = []
    engine.register(State.GATHERING, 'pick', declare.pick)
    engine.register(State.DECLARING, 'declare', declare.declare)
    engine.register(State.DECLARING, 'lies', lies_heard.step)
    engine.register(State.REACTING, 'react', react.react)
    engine.register(State.WRITING, 'feelings', react.felt)
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks


def seat_up(game, *table):
    with game.database.connect(write=True) as connection:
        for order, (key, name, mind) in enumerate(table):
            seats.set_seat(connection, key, name, game.database.now(), mind=mind, order=order)


def answer(data) -> list[Chunk]:
    return [Chunk(data if isinstance(data, str) else json.dumps(data)), Chunk('', 'stop')]


def playing(system: str) -> str:
    """Which character a call is for, from the fenced name in its system prompt."""
    return system.split('[[in-fiction: your character]]\n', 1)[1].split('\n', 1)[0]


def scripted(game, script: dict):
    """The stub answers each character's calls in turn from `script[name]` (a list of answers)."""
    def respond(system, messages):
        return answer(script[playing(system)].pop(0))
    game.provider.respond = respond


def turn_of(game, mode=Mode.PLAY, said='', resolve=None):
    events = []

    async def emit(event):
        events.append(event)

    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1, emit=emit, mode=mode)
        turn.snapshot.settings['said'] = said
        if resolve:
            engine.register(State.RESOLVING, 'resolve', resolve)
        state = await engine.run(turn)
        return turn, state
    turn, state = asyncio.run(going())
    return turn, state, events


def snapshot(*table, mode='play') -> Snapshot:
    return Snapshot(turn_id='t', mode=mode, point=Point(timeline.ROOT, 1), number=0,
                    seats=[Seat(key, name, mind, order) for order, (key, name, mind) in enumerate(table)])


# What an agent gives back ---------------------------------------------------------------------------------------------

def test_claims_are_cut_back_to_attempts_and_audiences_kept_to_who_is_here():
    shot = snapshot(('you', 'Vanta Reyes', Mind.HUMAN), ('mara', 'Mara Quill', Mind.AGENT),
                    ('hesk', 'Hesk', Mind.AGENT))
    shot.present = ['you', 'mara', 'hesk']
    made = agents.checked({
        'intent': 'draws steel and lunges at Hesk as my blade finds his heart, and he falls',
        'lines': [{'text': '*grins* You should have run. (quietly)', 'to': ['Hesk', 'Nobody']},
                  {'text': 'Stay back, Vanta.', 'to': ['vanta']}, {'text': '*only an action*', 'to': []}],
        'motive': 'He sold my brother to the wardens.',
        'deceptions': [{'claim': 'I was at the shrine all night.', 'believed': 'I was at the docks.',
                        'aimed_at': ['Mara Quill', 'you']}, {'claim': '', 'believed': 'x'}],
        'whispers': [{'text': 'Now.', 'to': []}, {'text': 'Take the left door.', 'to': ['you']}]},
        'mara', shot)
    assert made.intent == 'draws steel and lunges at Hesk'
    assert [(line.text, line.to) for line in made.lines] == [('You should have run.', ['hesk']),
                                                             ('Stay back, Vanta.', ['you'])]
    # Never aimed at the speaker herself; a whisper with nobody to hear it is dropped.
    assert [(item.claim, item.aimed_at) for item in made.deceptions] == [('I was at the shrine all night.', ['you'])]
    assert [(item.text, item.to) for item in made.whispers] == [('Take the left door.', ['you'])]
    assert agents.attempt('I manage to successfully pick the lock, which works') == 'I try to pick the lock'
    assert agents.attempt('manages to pick the lock before the guard notices') == 'tries to pick the lock before the ' \
                                                                               'guard notices'
    assert agents.attempt('I kill the guard') == 'tries to kill the guard'


def test_what_the_story_keeps_off_the_page_is_cut_from_every_field_hidden_ones_too():
    shot = snapshot(('mara', 'Mara', Mind.AGENT), ('hesk', 'Hesk', Mind.AGENT))
    levels = {'violence': 0, 'sex': 2, 'horror': 2, 'cruelty': 2, 'drugs': 2}
    made = agents.checked({'intent': 'waits by the door', 'motive': 'I want him gone. I will stab him in his sleep.',
                           'whispers': [{'text': 'Slit his throat tonight.', 'to': ['hesk']}],
                           'lines': [{'text': 'Good evening.'}]}, 'mara', shot, levels)
    assert made.motive == 'I want him gone.'
    assert made.whispers == []
    assert made.lines[0].text == 'Good evening.'


def test_a_refusal_and_broken_json_are_told_apart():
    assert agents.refused("I'm sorry, but I can't help with that.", 'stop')
    assert agents.refused('', 'content_filter')
    assert not agents.refused('{"intent": "I am sorry for nothing"}', 'stop')
    assert agents.parsed('Sure! {"intent": "waits"}')[0] == {'intent': 'waits'}
    assert agents.parsed('{"intent": "waits",}')[0] is None
    assert agents.parsed('{"lines": "hello"}')[1] == '"lines" must be a list'


# Gather -------------------------------------------------------------------------------------------------------------

def test_agents_are_picked_within_the_cap_party_first_then_nemeses_and_promoted_then_by_role(game, steps):
    seat_up(game, ('you', 'Vanta', Mind.HUMAN), ('ilsa', 'Ilsa', Mind.AGENT), ('bram', 'Bram', Mind.AGENT),
            ('cole', 'Cole Varn', Mind.AGENT), ('dov', 'Dov', Mind.AGENT), ('hesk', 'Hesk', Mind.AGENT))
    with game.database.connect(write=True) as connection:
        seats.change(connection, {'agent_cap': 3}, under_way=False)
        seats.set_seat(connection, 'dov', 'Dov', game.database.now(), promoted=True)
        connection.execute("INSERT INTO story_party (key, name, city_id, sheet, joined) VALUES ('hesk', 'Hesk', 'c', '{}', '')")
        connection.execute("INSERT INTO story_nemeses (id, name, grudge, remembers, status, since) VALUES "
                           "('n1', 'Cole Varn', 'x', 'Mind', 'alive', '')")

    async def nothing(turn):
        pass
    engine.register(State.DECLARING, 'declare', nothing)
    turn, _, _ = turn_of(game, said='I ask Bram about the ford.')
    minds = {seat.key: seat.mind for seat in turn.snapshot.seats}
    # Hesk (party), then Cole (a nemesis) and Dov (promoted) by seat order; Bram is named but the cap is reached.
    assert [key for key, mind in minds.items() if mind == Mind.AGENT] == ['cole', 'dov', 'hesk']
    assert turn.snapshot.settings['dropped'] == ['bram', 'ilsa']
    assert turn.snapshot.settings['agents']['preset'] == 'balanced'
    # Outside Play the human's character runs on its Program mind.
    turn, _, _ = turn_of(game, mode=Mode.WATCH)
    assert turn.snapshot.seat('you').mind == Mind.PROGRAM


# A whole round ------------------------------------------------------------------------------------------------------

def mara_declares():
    return {'intent': 'tries to talk Hesk into leaving the ford unguarded', 'motive': 'The wardens pay me for him.',
            'lines': [{'text': 'The bridge is watched, Hesk. Take the ford.', 'to': ['Hesk']}],
            'deceptions': [{'claim': 'The bridge is watched.', 'believed': 'The bridge is empty tonight.',
                            'aimed_at': ['Hesk']}],
            'whispers': [{'text': 'Keep Vanta busy.', 'to': ['Ilsa']}]}


def test_two_agents_and_the_user_declare_roll_lies_react_and_resolve(game, steps):
    seat_up(game, ('you', 'Vanta', Mind.HUMAN), ('mara', 'Mara', Mind.AGENT), ('hesk', 'Hesk', Mind.AGENT),
            ('ilsa', 'Ilsa', Mind.PROGRAM))
    scripted(game, {
        'Mara': [mara_declares(), {'change': False}],
        'Hesk': [{'intent': 'studies Mara', 'motive': 'She is hiding something.', 'lines': [{'text': 'Is it now?'}]},
                 {'change': True, 'intent': 'heads for the bridge anyway', 'lines': [{'text': 'I will see.'}]}],
    })

    async def resolve(turn):
        turn.draft.result = TurnResult(rolls=[{'actor': 'hesk', 'target': 'mara', 'kind': 'threaten',
                                               'stat': 'Resolve', 'band': 'success', 'action': 'stares Mara down'}])
    turn, state, events = turn_of(game, said='I watch the road. "Quiet, both of you."', resolve=resolve)
    assert state == State.COMMITTED
    draft = turn.draft
    # Merged in seat order, whatever order the answers came in; the human's line split into attempt and speech.
    assert list(draft.declarations) == ['you', 'mara', 'hesk', 'ilsa']
    assert draft.declarations['you'].intent == 'I watch the road'
    assert [line.text for line in draft.declarations['you'].lines] == ['Quiet, both of you.']
    assert draft.declarations['ilsa'].intent == 'goes about their own business'
    # Hesk changed course in React; his first move is kept for the minds panel and re-asking.
    assert draft.declarations['hesk'].intent == 'heads for the bridge anyway'
    assert draft.declared['hesk'].intent == 'studies Mara'
    # The lie was rolled for everyone who heard it aloud: Hesk it was aimed at, and the user, who overheard.
    lies = draft.extra['agents']['lies']
    assert sorted(item['listener'] for item in lies) == ['hesk', 'ilsa', 'you']
    for item in lies:
        kinds = {known.kind for known in draft.known_to(item['listener']) if known.source == 'mara'}
        assert ('belief' in kinds) == (item['read'] == 'believed')
        assert ('tell' in kinds) == (item['read'] != 'believed')

    def known(key):
        return ' | '.join(item.text for item in draft.known_to(key))
    # Motives reach nobody but their owner; the whisper only Ilsa; nobody else learns what Mara holds true.
    assert 'wardens pay' in known('mara') and not any('wardens pay' in known(key) for key in ('you', 'hesk', 'ilsa'))
    assert 'Keep Vanta busy' in known('ilsa') and 'Keep Vanta busy' not in known('you') + known('hesk')
    assert 'bridge is empty' in known('mara') and not any('bridge is empty' in known(key)
                                                          for key in ('you', 'hesk', 'ilsa'))
    assert 'Hesk: heads for the bridge anyway' in known('mara')
    # The Program character and the human never got a model call: two for Mara, two for Hesk.
    assert len(game.provider.requests) == 4
    statuses = [(event['seat']['key'], event['seat']['status']) for event in events if 'seat' in event]
    assert statuses == [('mara', 'thinking'), ('hesk', 'thinking'), ('mara', 'declared'), ('hesk', 'declared'),
                        ('mara', 'reacting'), ('hesk', 'reacting'), ('mara', 'done'), ('hesk', 'done')]
    # In Play the round timeline never shows an intent.
    assert not any('intent' in event['seat'] for event in events if 'seat' in event)
    with game.database.connect() as connection:
        later = Point(timeline.ROOT, 10)
        assert any('wardens pay' in row['text'] for row in memory.recall(connection, 'mara', later))
        assert not any('wardens pay' in row['text'] for row in memory.recall(connection, 'hesk', later))
        # Hesk's threat landed: Mara fears and respects him a little more.
        felt = memory.toward(connection, 'mara', 'hesk', later)
        assert (felt['fear'], felt['respect']) == (1, 1)


def test_what_an_agent_reads_holds_only_what_it_could_see_and_hear(game, steps):
    seat_up(game, ('mara', 'Mara', Mind.AGENT), ('hesk', 'Hesk', Mind.AGENT), ('ilsa', 'Ilsa', Mind.AGENT))
    scripted(game, {
        'Mara': [mara_declares() | {'intent': 'quietly pockets the map'}, {'change': False}],
        'Hesk': [{'intent': 'waits', 'motive': 'SENTINEL-MOTIVE-HESK'}, {'change': False}],
        'Ilsa': [{'intent': 'waits'}, {'change': False}],
    })
    turn_of(game, mode=Mode.AUTHOR)
    reacts = {playing(request['system']): request['messages'][0]['content']
              for request in game.provider.requests if 'may react once' in request['system']}
    assert 'Keep Vanta busy' in reacts['Ilsa'] and 'Keep Vanta busy' not in reacts['Hesk']
    # Hesk's motive is his alone; Mara's covert act is seen by nobody (whether it is noticed is Resolve's roll).
    assert 'SENTINEL-MOTIVE-HESK' in reacts['Hesk']
    assert not any('SENTINEL-MOTIVE-HESK' in reacts[name] for name in ('Mara', 'Ilsa'))
    assert not any('pockets the map' in reacts[name] for name in ('Hesk', 'Ilsa'))
    assert 'The bridge is empty' not in reacts['Hesk'] + reacts['Ilsa']


# Failures -----------------------------------------------------------------------------------------------------------

def test_broken_output_is_asked_again_once_with_what_was_wrong(game, steps):
    seat_up(game, ('mara', 'Mara', Mind.AGENT))
    scripted(game, {'Mara': ['{"intent": "waits",}', {'intent': 'waits by the fire'}, {'change': False}]})
    turn, state, _ = turn_of(game)
    assert state == State.COMMITTED
    assert turn.draft.declarations['mara'].intent == 'waits by the fire'
    retry = game.provider.requests[1]['messages']
    assert retry[1] == {'role': 'assistant', 'content': '{"intent": "waits",}'}
    assert 'the JSON did not parse' in retry[2]['content']


def test_a_refusing_broken_or_slow_model_falls_back_to_the_program_mind_without_losing_the_turn(game, steps,
                                                                                                monkeypatch):
    seat_up(game, ('mara', 'Mara', Mind.AGENT), ('hesk', 'Hesk', Mind.AGENT))
    scripted(game, {'Mara': ["I'm sorry, but I can't play this character."], 'Hesk': ['no json', 'still none']})
    turn, state, events = turn_of(game)
    assert state == State.COMMITTED
    assert turn.draft.declarations['mara'].fallback and turn.draft.declarations['hesk'].fallback
    assert turn.draft.declarations['mara'].intent == 'goes about their own business'
    assert turn.draft.extra['agents']['fallbacks'] == {'mara': 'refused', 'hesk': 'unparsed'}
    # A refusal is not asked again; broken output is, once.
    assert len(game.provider.requests) == 3
    assert ('mara', 'fallback') in [(event['seat']['key'], event['seat']['status']) for event in events if
                                    'seat' in event]
    # A model that never answers in time: one retry, then the Program mind.
    monkeypatch.setattr(agents, 'FLOOR', 0.05)
    monkeypatch.setattr(pace, 'budget_for', lambda connection, config: 0.1)
    game.provider.respond, game.provider.delay = None, 1
    with game.database.connect(write=True) as connection:
        seats.remove_seat(connection, 'hesk')
    turn, state, _ = turn_of(game)
    assert state == State.COMMITTED and turn.draft.extra['agents']['fallbacks'] == {'mara': 'failed'}


def test_with_no_model_or_over_the_session_cap_agents_run_on_their_program_minds(game, steps):
    seat_up(game, ('mara', 'Mara', Mind.AGENT))
    with game.database.connect(write=True) as connection:
        agents.change(connection, {'session_cap': 10}, game.database.now())
    turn, state, _ = turn_of(game)
    assert state == State.COMMITTED and turn.draft.extra['agents']['fallbacks'] == {'mara': 'capped'}
    assert game.provider.requests == []
    with game.database.connect(write=True) as connection:
        connection.execute('DELETE FROM model_routes')
    turn, _, _ = turn_of(game)
    assert turn.draft.extra['agents']['fallbacks'] == {'mara': 'no model'}


def test_converse_calls_speak_and_get_an_empty_fallback_when_the_agent_fails(game, steps):
    seat_up(game, ('you', 'Vanta', Mind.HUMAN), ('mara', 'Mara', Mind.AGENT))
    scripted(game, {'Mara': [{'lines': [{'text': 'Where were you last night?', 'to': ['Vanta']}]}, 'nonsense', 'no']})

    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1, mode=Mode.PLAY)
        asked = await agents.speak(turn, 'mara', {'kind': 'ask', 'to': 'you'})
        failed = await agents.speak(turn, 'mara', {'kind': 'answer', 'speaker': 'you', 'line': 'At the shrine.'})
        engine.discard(turn)
        return asked, failed
    asked, failed = asyncio.run(going())
    assert [(line.text, line.to) for line in asked.lines] == [('Where were you last night?', ['you'])]
    assert failed.fallback and not failed.lines
    assert '[[in-fiction: Vanta said]]\nAt the shrine.' in game.provider.requests[1]['messages'][0]['content']


# Budgets, feelings and settings -------------------------------------------------------------------------------------

def test_spend_holds_across_parallel_calls_and_the_cap_stops_play_only_at_idle(game):
    spend = pace.spend_for(game.database)
    first, second = spend.reserve(600, 1000), spend.reserve(600, 1000)
    assert first is not None and second is None
    # A call the turn needs is never refused; the cap is checked at Idle.
    needed = spend.reserve(600, 1000, required=True)
    spend.settle(first, 450)
    spend.settle(needed, None)
    assert spend.view(1000) == {'spent': 1050, 'held': 0, 'cap': 1000}
    assert pace.capped(game.database, 1000) and not pace.capped(game.database, 0)
    assert pace.used_tokens({'input_tokens': 10, 'output_tokens': 5}) == 15 and pace.used_tokens({}) is None


def test_rolls_move_feelings_between_any_two_characters_by_kind_and_loyalty():
    rolls = [{'actor': 'hesk', 'target': 'mara', 'kind': 'attack', 'stat': 'Vitality', 'band': 'critical_success',
              'action': 'swings at Mara'},
             {'actor': 'mara', 'target': 'hesk', 'kind': 'steal', 'stat': 'Luck', 'band': 'success', 'action': 'x'},
             {'actor': 'mara', 'target': 'you', 'kind': 'persuade', 'stat': 'Allure', 'band': 'success', 'action': 'y'},
             {'actor': 'mara', 'target': '', 'kind': 'referee', 'stat': 'Mind', 'band': 'success', 'action': 'z'}]
    moved = feelings.between(rolls, 1.0, {'you'})
    assert moved == [{'from': 'mara', 'to': 'hesk', 'changes': {'fear': 2, 'affection': -4, 'trust': -2},
                      'why': 'swings at Mara'}]
    assert feelings.scaled({'trust': -1, 'fear': 2}, 0.5) == {'fear': 1}
    assert feelings.scaled({'trust': -1, 'fear': 2}, 1.5) == {'trust': -2, 'fear': 3}


def test_presets_and_dials_are_settings_with_a_plain_estimate(game):
    with game.database.connect(write=True) as connection:
        assert agents.settings(connection) == agents.DEFAULTS
        agents.change(connection, {'preset': 'rich', 'scheming': 3, 'loyalty': 'fast'}, game.database.now())
        shown = agents.view(connection, agents=4)
        assert (shown['preset'], shown['scheming'], shown['loyalty']) == ('rich', 3, 'fast')
        with pytest.raises(Exception):
            agents.change(connection, {'scheming': 5}, game.database.now())
    quick, rich = agents.estimate('quick', 4, 4), agents.estimate('rich', 4, 4)
    assert quick['calls'] < rich['calls'] and quick['tokens'] < rich['tokens']
    assert rich['text'] == f"About {rich['calls']} model calls and {rich['tokens']:,} tokens a turn with 4 agents."


def test_a_character_with_its_own_model_uses_it_over_the_agents_job(game):
    other = text_models.create(game.database, game.vault, ProfileCreate(name='Villain', config=MODEL | {
        'model': 'big'}))
    with game.database.connect() as connection:
        assert text_models.character_config(connection, other['id'])['model'] == 'big'
        assert text_models.character_config(connection, None)['model'] == 'stub'
        assert text_models.character_config(connection, 'gone')['model'] == 'stub'


def test_the_agents_settings_api_shows_each_preset_with_its_estimate(client):
    shown = client.get('/api/agents').json()
    assert shown['preset'] == 'balanced' and [item['name'] for item in shown['presets']] == [
        'Quick and cheap', 'Balanced', 'Rich and slow']
    assert shown['spend'] == {'spent': 0, 'held': 0, 'cap': 0} and shown['capped'] is False
    changed = client.put('/api/agents', json={'preset': 'quick', 'loyalty': 'slow', 'session_cap': 50000}).json()
    assert (changed['preset'], changed['loyalty'], changed['spend']['cap']) == ('quick', 'slow', 50000)
    assert client.put('/api/agents', json={'scheming': 4}).status_code == 422
