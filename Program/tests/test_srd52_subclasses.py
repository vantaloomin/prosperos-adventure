"""5E subclasses and more of the spells (dungeon/rules/srd52.py, dungeon/combat5e.py): the SRD's one subclass a
class at its subclass level, the subclass's spells, upcasting, conditions laid by a failed save, Magic Missile."""
from test_combat import ok
from test_combat5e import Always, swing
from test_rulesets import start

from dungeon import combat, combat5e, sheet
from dungeon.rules import srd52


def built(class_id, background_id, level=1):
    quick = srd52.suggested(class_id, background_id)
    found = srd52.build(class_id, 'human', background_id, quick['scores'], quick['picks'])
    gained = []
    while found['level'] < level:
        found, gained = srd52.advance(found)
    return found, gained


def begin(client, app, class_id, background_id, level=1):
    quick = srd52.suggested(class_id, background_id)
    ok(start(client, persona={'name': 'Wenna'}, ruleset='srd52', build={
        'class_id': class_id, 'species_id': 'human', 'background_id': background_id, 'scores': quick['scores'],
        'skills': quick['picks']}))
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        while found['level'] < level:
            found, _ = srd52.advance(found)
        sheet.set_native(connection, found, '')


def test_the_subclass_comes_at_its_level_with_its_features():
    fighter, gained = built('fighter', 'soldier', 3)
    assert fighter['subclass'] == 'champion' and 'Champion' in gained and 'Improved Critical' in gained
    assert 'Fighter Subclass' not in fighter['features'] and srd52.critical_from(fighter) == 19
    assert srd52.view(fighter)['names']['subclass'] == 'Champion' and ', Champion' in srd52.described(fighter)
    assert srd52.critical_from(built('fighter', 'soldier', 2)[0]) == 20
    assert srd52.critical_from(built('fighter', 'soldier', 15)[0]) == 18


def test_the_subclass_spells_are_always_prepared():
    cleric, _ = built('cleric', 'acolyte', 3)
    assert cleric['subclass'] == 'life-domain'
    assert {'aid', 'bless', 'cure-wounds', 'lesser-restoration'} <= set(cleric['spells']['prepared'])
    assert not set(srd52.subclass_spells(built('cleric', 'acolyte', 2)[0]))


def test_a_line_can_cast_with_a_higher_slot():
    assert srd52.upcast('I cast Burning Hands at 2nd level') == 2
    assert srd52.upcast('Cure Wounds with a 3rd-level slot') == 3 and srd52.upcast('I cast Burning Hands') is None
    burning = srd52.spells()['burning-hands']
    assert srd52.scaled('3d6', burning, 2) == '4d6' and srd52.scaled('3d6', burning, 1) == '3d6'


def test_an_upcast_spell_spends_that_slot_and_hits_harder(client, app):
    begin(client, app, 'wizard', 'sage', 3)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'spells': found['spells'] | {'prepared': ['burning-hands',
                                                                                       'magic-missile']}}, '')
        cast = sheet.check(connection, 'Essence', 'normal', 'I cast Burning Hands at 2nd level at the bandit',
                           Always(15))
        assert cast['skill'] == 'Burning Hands (spell) (2nd-level slot)'
        assert sheet.native(connection)['spells']['used'][:2] == [0, 1]
        foe = combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(20))[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [foe]}
        rolled = {'id': 'r', 'action': 'I cast Burning Hands at 2nd level at the bandit', 'band': 'success',
                  'stat': 'Essence', 'natural': 10, 'skill': cast['skill']}
        _, lines, _ = combat.play_round(connection, state, [rolled], [], Always(1))
        # 4d6 at 1 a die on a failed save.
        assert lines[0].startswith("The player's character casts Burning Hands at the bandit: 4 fire damage")
        # Magic Missile's three darts always hit: 1d4 + 1 each.
        rolled = {'id': 'r2', 'action': 'I cast Magic Missile at the bandit', 'band': 'success', 'stat': 'Essence',
                  'natural': 2, 'skill': 'Magic Missile (spell)'}
        _, lines, _ = combat.play_round(connection, state, [rolled], [], Always(4))
        assert lines[0].startswith("The player's character casts Magic Missile: 3 darts strike the bandit for 15 "
                                   'force damage')


def test_a_failed_save_lays_its_condition(client, app):
    begin(client, app, 'wizard', 'sage', 3)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'spells': found['spells'] | {'prepared': ['hold-person', 'sleep']}}, '')
        foe = combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(20))[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [foe]}
        rolled = {'id': 'r', 'action': 'I cast Hold Person on the bandit', 'band': 'success', 'stat': 'Essence',
                  'natural': 10, 'skill': 'Hold Person (spell)'}
        state, lines, _ = combat.play_round(connection, state, [rolled], [], Always(1))
        assert lines[0] == "The player's character casts Hold Person at the bandit: paralyzed, they can't act."
        assert 'The bandit is paralyzed and can\'t act.' in lines and state['foes'][0]['held']
        # A blow on the paralyzed is a critical hit.
        state, lines, _ = combat.play_round(connection, state, [swing(12, 'I hit the bandit with my staff')], [],
                                            Always(20))
        assert any('lands a critical hit on the bandit' in line for line in lines)


def test_disciple_of_life_heals_more(client, app):
    begin(client, app, 'cleric', 'acolyte', 3)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'hp': 1}, '')
        healed = sheet.check(connection, 'Essence', 'hard', 'I cast Cure Wounds at 2nd level on myself', Always(1))
        wisdom = srd52.modifier(found['abilities']['wis'])
        # 2d8 and 2d8 more for the higher slot, at 1 a die; the Wisdom modifier; and 2 + the slot's level.
        assert healed['skill'] == f"Cure Wounds (2nd-level slot) (heals {4 + wisdom + 4})"
