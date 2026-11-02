"""Magic under BRP (dungeon/rules/brp.py cast, dungeon/combat_brp.py cast): Chapter 4's spells, power points and
levels; a wizard or a priest begins as a magician."""
from test_brp import Faces, made
from test_rulesets import start
from test_travel import ok

from dungeon import combat, combat_brp, sheet
from dungeon.rules import brp

MAGE = {'str': 10, 'con': 10, 'siz': 10, 'int': 14, 'pow': 14, 'dex': 10, 'cha': 10}


def wizard(client):
    ok(start(client, persona={'name': 'Orla'}, ruleset='brp', brp=made(MAGE, 'wizard', 'cunning')))


def test_a_wizard_begins_with_four_spells_and_the_rest_with_none():
    built = brp.build(MAGE, 'wizard', 'cunning')
    assert set(built['spells']) == {'blast', 'protection', 'light', 'perception'}
    # INT x1 and their share of the points.
    assert all(14 < value <= 75 for value in built['spells'].values())
    assert 'blast' not in built['skills'] and brp.view(built)['most_level'] == 7
    assert 'spells' not in brp.build(MAGE, 'warrior', 'brutal')
    assert set(brp.build(MAGE, 'priest', 'charming')['spells']) == {'heal', 'protection', 'light', 'dispel'}
    assert 'A magician: Blast' in brp.described(built)


def test_a_spell_is_cast_at_a_level_for_its_power_points():
    built = brp.build(MAGE, 'wizard', 'cunning')
    assert brp.known_spell(built, 'I cast Blast 2 at the thug') == 'blast'
    assert brp.known_spell(built, 'I light a torch') is None and brp.known_spell(built, 'I cast a Light spell') == 'light'
    rolled = brp.cast(built, 'blast', 'I cast Blast 2 at the thug', 'normal', Faces(10))
    assert rolled['skill'].startswith('Blast 2 ') and rolled['skill'].endswith(', 6 power points')
    assert built['pp'] == 8 and rolled['band'] == 'success'
    # A failure costs 1; never the last point.
    rolled = brp.cast(built, 'blast', 'I cast Blast 3 at the thug', 'normal', Faces(90))
    assert built['pp'] == 7 and rolled['skill'].endswith(', 1 power point')
    built['pp'] = 3
    assert brp.cast(built, 'blast', 'I cast Blast', 'normal', Faces(10))['skill'] == 'Blast (not enough power points)'
    assert brp.recover(built, 1) == 8 and built['pp'] == 11


def test_spells_in_a_fight(client, app):
    wizard(client)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        found['spells'] |= {'blast': 60, 'protection': 60}
        sheet.set_native(connection, found, '')
        rolled = sheet.check(connection, 'Essence', 'normal', 'I cast Blast 2 at the thug', Faces(10))
        thug = combat_brp.foes_from({'name': 'the thug'}, 'engaged')[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [thug]}
        # The thug's dodge fails (90); 2D6 (6 + 6) less 1 armour.
        state, lines, _ = combat.play_round(connection, state, [rolled | {'id': 'r', 'stat': 'Essence',
                                                                         'action': 'I cast Blast 2 at the thug'}],
                                            [], Faces(90, 6, 6, 90, 90, rest=99))
        assert lines[0] == "The player's character casts Blast 2 at the thug for 11 damage: now badly hurt."
        assert sheet.native(connection)['pp'] == 8
        rolled = sheet.check(connection, 'Essence', 'normal', 'I cast Protection 2 on myself', Faces(10))
        state, lines, _ = combat.play_round(connection, state, [rolled | {'id': 'r2', 'stat': 'Essence',
                                                                         'action': 'I cast Protection 2 on myself'}],
                                            [], Faces(rest=99))
        assert lines[0] == ("The player's character casts Protection 2: 2 more armour against blows for the rest of "
                            'the fight.') and state['protection'] == 2


def test_heal_heals_the_character(client, app):
    ok(start(client, persona={'name': 'Orla'}, ruleset='brp', brp=made(MAGE, 'priest', 'charming')))
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'hp': 2, 'spells': found['spells'] | {'heal': 60}}, '')
        healed = sheet.check(connection, 'Essence', 'normal', 'I cast Heal on myself', Faces(10, 4))
        assert healed['skill'].endswith('(heals 4)') and sheet.native(connection)['hp'] == 6
        # A night brings back the power points.
        combat.mend(connection, 1)
        assert sheet.native(connection)['pp'] == sheet.native(connection)['max_pp']
