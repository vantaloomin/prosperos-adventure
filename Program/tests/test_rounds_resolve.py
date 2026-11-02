"""Resolve for a party (adventure/rounds/resolve.py): code classifies and rolls every character's risky acts, the
Referee sees only the bare intent, the one an act is aimed at resists, Narrative Only gives code's verdict, and the
TurnResult, its brief and the dice log carry who acted, at whom and what was at stake."""
import asyncio
from types import SimpleNamespace

import pytest
from conftest import START

from adventure import referee, timeline
from adventure.clock import FixedClock
from adventure.database import Database
from adventure.rounds import engine, resolve, seats
from adventure.rounds.contract import Deception, Declaration, Line, Mind, Mode, State
from adventure.rules import narrative


class Dice:
    """Rolls that come up as listed, in order (d100 first, then the stat die, for each roll)."""

    def __init__(self, *values):
        self.values = list(values)

    def randint(self, low, high):
        return max(low, min(high, self.values.pop(0)))


@pytest.fixture
def steps():
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks = list(engine.COMMITS)
    engine.register(State.RESOLVING, 'ambiguity', resolve.ambiguity)
    engine.register(State.RESOLVING, 'resolve', resolve.resolve)
    engine.on_commit('rolls', resolve.kept_rolls)
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks


@pytest.fixture
def game(tmp_path, steps):
    game = SimpleNamespace(database=Database(tmp_path / 'adventure.sqlite3', FixedClock(START)), dice=None)
    with game.database.connect(write=True) as connection:
        seats.set_seat(connection, 'you', 'Wren Ash', '', mind=Mind.HUMAN)
        seats.set_seat(connection, 'hesk', 'Hesk', '', mind=Mind.AGENT)
        seats.set_seat(connection, 'mara', 'Mara Quill', '', mind=Mind.AGENT)
    return game


def resolved(game, *declarations, extra=None, settings=None):
    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1)
        turn.snapshot.settings |= {'when': 'Evening', 'where': 'The Lantern, Kingswood'} | (settings or {})
        for declaration in declarations:
            turn.draft.declare(declaration)
        turn.draft.extra |= extra or {}
        assert await engine.run(turn) == State.COMMITTED
        return turn
    return asyncio.run(going())


def test_each_actor_risky_acts_are_rolled_by_code_and_labelled(game):
    # Hesk's blow: d100 60 + d8 4 against Mara's resist d100 20 + d8 1. Mara's threat: d100 80 + d8 8, unopposed.
    game.dice = Dice(60, 4, 20, 1, 80, 8)
    turn = resolved(game, Declaration('hesk', intent='I stab Mara in the arm.'),
                    Declaration('mara', intent='I threaten the innkeeper.'),
                    Declaration('you', intent='I punch Hesk.'))
    rolls = turn.draft.result.rolls
    assert [(roll['actor'], roll['kind'], roll['target'], roll['stat']) for roll in rolls] == [
        ('hesk', 'attack', 'mara', 'Vitality'), ('mara', 'threaten', '', 'Resolve')]
    assert rolls[0]['stake'] == 'hurting Mara Quill' and rolls[0]['opposed']['stat'] == 'Vitality'
    assert rolls[0]['band'] == 'success_cost' and rolls[1]['band'] == 'success'
    brief = turn.draft.result.brief
    assert brief.outcomes[0] == ('Hesk: "I stab Mara in the arm" (Vitality, against Mara Quill\'s Vitality; at stake: '
                                 'hurting Mara Quill): Success at a cost.')
    assert brief.math[1] == 'Mara Quill: d100 80 + d8 8 = 88: Success.'
    assert brief.when == 'Evening' and brief.stop_point == "Before Wren Ash's next real decision."
    # The human's own line is rolled by today's turn in Play, not here.
    assert 'you' not in {roll['actor'] for roll in rolls}


def test_the_target_doing_better_makes_the_act_land_a_step_worse(game):
    # Hesk's theft: d100 62 + d8 3 = 65 (success at a cost); Mara's notice: d100 80 + d8 2 = 82 (success).
    game.dice = Dice(62, 3, 80, 2)
    turn = resolved(game, Declaration('hesk', intent="I pickpocket Mara's purse."))
    roll = turn.draft.result.rolls[0]
    assert (roll['kind'], roll['target'], roll['opposed']['band']) == ('steal', 'mara', 'success')
    assert roll['band'] == 'failure_upside'


def test_the_referee_rules_on_the_rest_from_the_bare_intent(game, monkeypatch):
    asked = []

    async def decide(state, text, config, decisions=None, fight=None):
        asked.append(text)
        return [{'action': 'climb the wall', 'roll': True, 'stat': 'Vitality', 'difficulty': 'hard'}]
    monkeypatch.setattr(referee, 'decide', decide)
    game.dice = Dice(50, 4)
    turn = resolved(game, Declaration('hesk', intent='I climb the wall.', motive='Get to the vault before Mara.',
                                      lines=[Line('Trust me, I know a way in.', ['mara'])]))
    assert asked == ['I climb the wall']
    assert (turn.draft.result.rolls[0]['kind'], turn.draft.result.rolls[0]['difficulty']) == ('referee', 'hard')


def test_narrative_only_gives_codes_verdict_and_no_judge(game, monkeypatch):
    monkeypatch.setattr('adventure.sheet.ruleset', lambda connection: narrative.ID)
    turn = resolved(game, Declaration('hesk', intent='I persuade Mara to open the gate.'))
    roll = turn.draft.result.rolls[0]
    assert (roll['ruleset'], roll['verdict'], roll['band'], roll['die']) == ('narrative', 'yes_but', 'success_cost', 0)
    assert turn.draft.result.brief.math == ['Hesk: normal on its face, so Yes, but.']


def test_a_declared_lie_is_not_rolled_again_and_its_hearing_is_in_the_brief(game):
    lies = {'agents': {'lies': [{'liar': 'hesk', 'listener': 'mara', 'claim': 'the bridge is guarded',
                                 'band': 'failure', 'caught': True}]}}
    turn = resolved(game, Declaration('hesk', intent='I lie to Mara about the bridge.',
                                      deceptions=[Deception('the bridge is guarded', 'it is not', ['mara'])]),
                    extra=lies)
    assert turn.draft.result.rolls == []
    assert turn.draft.result.brief.outcomes == [
        'Hesk lies to Mara Quill (the bridge is guarded): the listener sees through it.']


def test_out_of_play_everyone_is_resolved_and_the_stop_point_is_the_next_break(game):
    with game.database.connect(write=True) as connection:
        seats.change(connection, {'mode': Mode.WATCH.value}, False)
    game.dice = Dice(70, 4)
    turn = resolved(game, Declaration('you', intent='I kick the door.'))
    assert [roll['actor'] for roll in turn.draft.result.rolls] == ['you']
    assert turn.draft.result.brief.stop_point == 'At the next natural break or big moment.'


def test_commit_keeps_the_rolls_for_the_dice_log(game):
    game.dice = Dice(60, 4, 20, 1)
    turn = resolved(game, Declaration('hesk', intent='I stab Mara.'), settings={'message_id': 'line-1'})
    with game.database.connect() as connection:
        rows = resolve.saved(connection, 'line-1')
        names = {seat.key: seat.name for seat in seats.seats(connection)}
    assert [(row['turn_id'], row['actor'], row['target'], row['against']) for row in rows] == [
        (turn.id, 'hesk', 'mara', 'failure')]
    shown = resolve.shown(rows[0], names)
    assert (shown['actor'], shown['against'], shown['label']) == ('Hesk', 'Mara Quill', 'Success at a cost')


def test_an_ambiguous_risky_move_asks_one_question_before_resolve(game):
    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1)
        turn.snapshot.present = ['you', 'hesk', 'mara']
        turn.snapshot.settings |= {'said': 'I draw my knife and stab him.', 'when': 'Evening', 'where': 'Inn'}
        assert await engine.run(turn) == State.AWAITING_USER
        assert turn.draft.awaiting['line'] == 'Who do you mean: Hesk or Mara Quill?'
        assert turn.draft.result is None
        assert await engine.answer(turn, 'you', {'kind': 'reply', 'text': 'Hesk'}) == State.COMMITTED
        return turn
    turn = asyncio.run(going())
    assert turn.draft.extra['resolve']['meant'] == 'Hesk'
    assert resolve.meant('I stab him.', turn) == 'I stab him. (meaning Hesk)'
    assert turn.draft.result is not None


def test_a_clear_move_or_one_other_person_asks_nothing(game):
    seated = [seats.Seat('you', 'Wren Ash', Mind.HUMAN), seats.Seat('hesk', 'Hesk'), seats.Seat('mara', 'Mara Quill')]
    assert resolve.question('I stab Hesk.', seated, ['you', 'hesk', 'mara'], 'you') is None
    assert resolve.question('I stab him.', seated, ['you', 'hesk'], 'you') is None
    assert resolve.question('I wave at them.', seated, ['you', 'hesk', 'mara'], 'you') is None
    assert resolve.question('I rob them both.', seated, ['you', 'hesk', 'mara'], 'you') is not None


def test_agent_allies_moves_come_from_their_own_declarations(game):
    async def going():
        turn = await engine.begin(game, timeline.ROOT, 1)
        turn.draft.declare(Declaration('hesk', intent='I go for the archer.'))
        turn.draft.declare(Declaration('mara', intent='I hold back.', fallback=True))
        turn.draft.declare(Declaration('you', intent='I swing at the bandit.'))
        return resolve.ally_moves(turn)
    assert asyncio.run(going()) == {'hesk': 'I go for the archer.'}
