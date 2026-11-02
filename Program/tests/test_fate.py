"""Fate (dungeon/rules/fate.py): aspects, approaches, 4dF against the ladder, Fate points spent by code."""
import random

import pytest
from conftest import Chunk, tell
from test_rulesets import start
from test_travel import ok

from dungeon import combat, growth, sheet, story
from dungeon.rules import fate

APPROACHES = {'Sneaky': 3, 'Clever': 2, 'Quick': 2, 'Careful': 1, 'Flashy': 1, 'Forceful': 0}


class Dice(random.Random):
    """Fate dice that come up as given, in order."""
    def __init__(self, faces):
        super().__init__(0)
        self.faces = list(faces)

    def choice(self, options):
        return self.faces.pop(0)


def made(client, **extra):
    body = {'high_concept': 'Dockside cutpurse with a conscience', 'trouble': 'Owes the Hollins gang',
            'aspects': ['Knows every alley in the river ward'], 'approaches': APPROACHES,
            'stunts': ['Because I grew up on the docks, I get +2 when I Sneakily slip through a crowd']} | extra
    return start(client, persona={'name': 'Wren'}, ruleset='fate', fate=body)


def test_a_made_fate_character_keeps_their_aspects_approaches_and_fate_points(client):
    ok(made(client))
    view = ok(client.get('/api/story/sheet'))
    assert (view['ruleset'], view['ruleset_name'], view['high_concept'], view['trouble']) == \
        ('fate', 'Fate', 'Dockside cutpurse with a conscience', 'Owes the Hollins gang')
    assert view['approaches'] == APPROACHES and (view['fate_points'], view['refresh']) == (3, 3)
    assert view['stress'] == [False, False, False] and 'Evil Hat' in view['attribution']
    choices = ok(client.get('/api/story/start'))
    assert choices['fate']['approaches'] == list(fate.APPROACHES) and choices['fate']['array'] == [3, 2, 2, 1, 1, 0]


def test_a_fate_character_needs_a_high_concept_and_the_array(client):
    assert made(client, high_concept='  ').status_code == 422
    assert made(client, approaches=APPROACHES | {'Forceful': 3}).status_code == 422
    assert start(client, persona={'name': 'Wren'}, ruleset='fate').status_code == 422


def test_a_premade_takes_their_description_as_high_concept(client):
    ok(start(client, premade_id='agna-holt', ruleset='fate'))
    view = ok(client.get('/api/story/sheet'))
    assert view['high_concept'] and sorted(view['approaches'].values(), reverse=True) == [3, 2, 2, 1, 1, 0]


@pytest.mark.parametrize(('shifts', 'band'), [(-1, 'failure'), (0, 'success_cost'), (2, 'success'),
                                              (3, 'critical_success')])
def test_shifts_land_on_the_shared_ladder(shifts, band):
    assert fate.outcome(shifts) == band


def sheet_of(**extra):
    return fate.build('Dockside cutpurse with a conscience', 'Owes the Hollins gang',
                      ['Knows every alley in the river ward'], APPROACHES,
                      ['Because I grew up on the docks, I get +2 when I Sneakily slip through a crowd']) | extra


def test_the_words_pick_the_approach_and_a_fitting_stunt_adds_two():
    found = fate.roll(sheet_of(), 'Mind', 'normal', 'I slip through the crowd at the market', Dice([0, 0, 0, 0]))
    # Sneaky +3, the docks stunt +2, against Fair (+2): succeeding by 3 is success with style.
    assert (found['ability'], found['bonus'], found['total'], found['target'], found['band']) == \
        ('Sneaky', 5, 5, 2, 'critical_success')
    assert 'stunt +2' in found['skill'] and found['fate_points'] == 3
    plain = fate.roll(sheet_of(), 'Vitality', 'hard', 'I put my shoulder to the gate', Dice([1, 0, 0, -1]))
    assert (plain['ability'], plain['total'], plain['band']) == ('Forceful', 0, 'failure')


def test_a_fitting_aspect_is_invoked_only_when_two_more_changes_the_outcome():
    found = fate.roll(sheet_of(), 'Mind', 'hard', 'I lose them in an alley of the river ward', Dice([-1, 0, 0, 0]))
    # Clever +2 - 1 = 1 against Good (+3); invoking the alleys makes it 3, a tie: a Fate point spent.
    assert found['fate_points'] == 2 and found['band'] == 'success_cost'
    assert 'invoked “Knows every alley in the river ward”' in found['skill']
    hopeless = fate.roll(sheet_of(), 'Mind', 'hard', 'I lose them in an alley of the river ward', Dice([-1, -1, -1, 0]))
    assert hopeless['fate_points'] == 3 and 'invoked' not in hopeless['skill']
    nothing = fate.roll(sheet_of(fate_points=0), 'Mind', 'hard', 'I lose them in an alley of the river ward',
                        Dice([-1, 0, 0, 0]))
    assert nothing['fate_points'] == 0 and 'invoked' not in nothing['skill']


def test_one_shared_name_or_filler_does_not_fit_an_aspect_or_a_stunt():
    found = fate.roll(sheet_of(), 'Allure', 'hard', 'I make a speech to the river guild about the price of timber',
                      Dice([-1, 0, 0, 0]))
    assert 'invoked' not in found['skill'] and 'stunt' not in found['skill']
    assert not fate.stunt_fits('Because I grew up on the docks, I get +2 when I survey land', 'I pay a debt I owe')


def test_the_trouble_compels_whenever_the_action_is_about_it():
    found = fate.roll(sheet_of(), 'Allure', 'very_hard', 'I try to talk the Hollins gang out of my debt',
                      Dice([-1, 0, 0, 0]))
    assert found['band'] == 'failure' and found['fate_points'] == 4 and 'compelled' in found['skill']
    paid = fate.roll(sheet_of(), 'Allure', 'easy', 'I pay the Hollins gang what I owe, whatever it costs',
                     Dice([1, 1, 0, 0]))
    assert paid['band'] == 'success_cost' and paid['fate_points'] == 4


def test_a_premade_gets_a_trouble_from_their_description():
    found = fate.premade('Half-elf, born at Low Ford. Too human for Brynwyr. They owe the wrong people on both sides.',
                         'Mind')
    assert (found['high_concept'], found['trouble']) == ('Half-elf, born at Low Ford', 'They owe the wrong people on both sides')


def test_a_check_saves_the_fate_points_and_a_night_refreshes_them(client, app):
    ok(made(client))
    with app.state.database.connect(write=True) as connection:
        sheet.set_native(connection, sheet.native(connection) | {'fate_points': 1}, '')
        found = sheet.check(connection, 'Mind', 'hard', 'I lose them in an alley of the river ward', Dice([-1, 0, 0, 0]))
        assert found['ruleset'] == 'fate' and sheet.native(connection)['fate_points'] == 0
        # The sheet keeps the bookkeeping; the narrator is told nothing of it.
        assert combat.mend(connection, 1) == []
        assert sheet.native(connection)['fate_points'] == 3


def test_a_milestone_raises_the_weakest_approach(client, app):
    ok(made(client))
    with app.state.database.connect(write=True) as connection:
        assert growth.milestone(connection, 'the gang paid off', '') == 'The character has grown: Forceful rises to +1.'
        assert sheet.native(connection)['approaches']['Forceful'] == 1


def test_the_narrator_reads_the_aspects(client, app):
    ok(made(client))
    with app.state.database.connect() as connection:
        described = story.persona_text(connection)[0]
    assert 'Dockside cutpurse' in described and 'Owes the Hollins gang' in described


def test_a_line_acting_on_the_trouble_earns_a_fate_point_with_nothing_rolled(client, connected, provider, app):
    ok(made(client, trouble='I always pay my debts, whatever they cost'))
    provider.respond = lambda system, messages: [Chunk('He takes your coin and nods.'), Chunk('', 'stop')]
    tell(client, 'A creditor demands I settle a debt. I agree to pay it whatever it costs me.', 'fate-0001')
    with app.state.database.connect() as connection:
        assert sheet.native(connection)['fate_points'] == 4


# Stress and consequences (dungeon/combat_fate.py) -------------------------------------------------------------

from dungeon import combat_fate  # noqa: E402


def fresh():
    return fate.build('Dockside cutpurse', approaches=APPROACHES)


@pytest.mark.parametrize(('shifts', 'way'), [
    (1, (0, [])), (3, (2, [])), (4, (1, ['mild'])), (6, (1, ['moderate'])), (13, (2, ['moderate', 'severe'])), (15, (2, ['mild', 'moderate', 'severe'])),
    (16, None)])
def test_a_hit_is_absorbed_as_cheaply_as_covers_it(shifts, way):
    assert combat_fate.absorb(fresh(), shifts) == way


def test_a_foes_blow_marks_stress_and_a_consequence_and_rest_heals_it(client, app):
    ok(made(client))
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'kill', 'foes': [{'id': 'f', 'name': 'the bandit', 'vitality': 10, 'resolve': 90,
                                                         'weapon': 0, 'wound': 0, 'zone': 'engaged', 'broken': False}]}
        # The bandit (Average +1) rolls ++++ for 5; the character's Quick +2 defends with ---- for -2: 7 shifts.
        state, lines, ending = combat.play_round(connection, state, [], [], Dice([1, 1, 1, 1, -1, -1, -1, -1]))
        assert "The bandit hits the player's character for 7 shifts: absorbed with 3-shift stress and a moderate " \
               'consequence, “Badly cut by the bandit”.' in lines
        assert ending == '' and combat.condition(connection)['level'] == 3
        assert sheet.native(connection)['stress'] == [False, False, True]
        assert 'Carrying: Badly cut by the bandit.' in fate.described(sheet.native(connection))
        combat.save_fight(connection, None)
        # A night clears stress; the moderate consequence takes three.
        assert combat.mend(connection, 1) == [] and sheet.native(connection)['stress'] == [False] * 3
        assert combat.condition(connection)['level'] == 3
        assert combat.mend(connection, 2) == ["Rest heals the character's consequence: Badly cut by the bandit."]
        assert combat.condition(connection)['level'] == 0


def test_more_than_the_character_can_absorb_takes_them_out(client, app):
    ok(made(client))
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        found['consequences'] = {'mild': 'Sprained ankle', 'moderate': 'Cracked rib', 'severe': ''}
        found['stress'] = [True, True, True]
        sheet.set_native(connection, found, '')
        state = {'round': 0, 'wants': 'kill', 'foes': [{'id': 'f', 'name': 'the bandit', 'vitality': 10, 'resolve': 90,
                                                         'weapon': 1, 'wound': 0, 'zone': 'engaged', 'broken': False}]}
        state, lines, ending = combat.play_round(connection, state, [], [], Dice([1, 1, 1, 1, -1, -1, -1, -1]))
        assert lines[-1].endswith('more than they can take: taken out.') and ending == 'dying'


def test_a_wound_from_outside_a_fight_marks_its_consequence(client, app):
    ok(made(client))
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 2)
        assert sheet.native(connection)['consequences']['mild'] == 'Bruised and sore'
        combat.set_condition(connection, 1)
        assert sheet.native(connection)['consequences']['mild'] == ''
        combat.set_condition(connection, 0)
        assert sheet.native(connection)['consequences'] == {'mild': '', 'moderate': '', 'severe': ''}
