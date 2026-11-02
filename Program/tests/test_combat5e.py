"""Fights under 5E (dungeon/combat5e.py through dungeon/combat.py): SRD foes, attacks on AC, hit points, death saves."""
from conftest import tell
from test_combat import Dice, ok, reply
from test_rulesets import made, start

from dungeon import combat, combat5e, record, sheet
from dungeon.rules import srd52


class Always:
    """Every die shows `face` (held to the die's own range)."""

    def __init__(self, face):
        self.face = face

    def randint(self, low, high):
        return max(low, min(high, self.face))

    def choice(self, items):
        return items[0]


def fighter(client):
    # A level 1 dwarf fighter: Str 17 (+3), 12 hit points, AC 11.
    ok(start(client, persona={'name': 'Brann'}, ruleset='srd52', build=made()))


def swing(natural, action='I swing my sword at the bandit'):
    return {'id': 'roll-1', 'action': action, 'band': 'failure', 'stat': 'Vitality', 'natural': natural}


def test_hit_points_read_as_the_wound_words_and_dice_roll_as_written():
    assert [combat5e.level_for(hp, 20) for hp in (20, 19, 12, 7, 4, 0)] == [0, 1, 2, 3, 4, 5]
    assert all(combat5e.level_for(combat5e.hp_for(level, 20), 20) == level for level in range(6))
    assert combat5e.roll_dice('2d8+2', Always(8)) == 18 and combat5e.roll_dice('2d8+2', Always(8), twice=True) == 34
    assert combat5e.roll_dice('1', Always(8)) == 1
    assert combat5e.death_saves(Always(20)) == (True, True, [20])
    assert combat5e.death_saves(Always(1)) == (False, False, [1, 1])
    assert combat5e.death_saves(Always(10)) == (True, False, [10, 10, 10])


def test_foes_are_srd_stat_blocks_by_their_spec_their_name_or_how_tough_they_are():
    rng = Always(8)
    bandit = combat5e.foes_from({'name': 'road bandit'}, 'near', rng)[0]
    assert (bandit['monster'], bandit['ac'], bandit['hp'], bandit['attack']['bonus']) == ('bandit', 12, 18, 3)
    assert combat5e.foes_from({'name': 'ley-mad boar', 'srd52': 'giant-boar'}, 'near', rng)[0]['monster'] == \
        'giant-boar'
    assert combat5e.foes_from({'name': 'the drunk', 'vitality': 6}, 'near', rng)[0]['monster'] == 'commoner'
    pair = combat5e.foes_from({'name': 'warden of Brynwyr', 'count': 2}, 'near', rng)
    assert [foe['name'] for foe in pair] == ['warden of Brynwyr 1', 'warden of Brynwyr 2'] and \
        pair[0]['monster'] == 'scout'


def test_an_attack_rolls_against_ac_and_a_natural_20_doubles_the_dice(client, app):
    fighter(client)
    with app.state.database.connect(write=True) as connection:
        foe = combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(4))[0]  # 2d8+2: 10 hit points.
        state = {'round': 0, 'wants': 'rob', 'foes': [foe]}
        # A natural 20 with a longsword: 2d8 + 3, every die high, drops the bandit.
        rolled = swing(20)
        state, lines, ending = combat.play_round(connection, state, [rolled], [{'item_id': 'sword'}], Always(8))
        assert ending == 'won' and 'critical hit on the bandit for 19 damage: now down, dead' in lines[0]
        # The roll's card now shows the attack: +3 Str, +2 proficiency, against the bandit's AC.
        assert (rolled['skill'], rolled['bonus'], rolled['total'], rolled['target'], rolled['band']) == \
            ('Attack (Longsword)', 5, 25, 12, 'critical_success')
        # A 6 + 5 misses AC 12; a natural 1 always misses.
        state = {'round': 0, 'wants': 'rob', 'foes': [combat5e.foes_from({'name': 'the bandit'}, 'engaged',
                                                                       Always(4))[0]]}
        _, lines, _ = combat.play_round(connection, state, [swing(6)], [{'item_id': 'sword'}], Always(1))
        assert 'attack on the bandit misses' in lines[0]


def test_foes_hit_the_characters_hit_points_and_a_dodge_needs_no_roll(client, app):
    fighter(client)
    with app.state.database.connect(write=True) as connection:
        foe = combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(4))[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [foe]}
        # Every die high: the bandit's 20 is a critical hit, 2d6+1 = 13, more than Brann's 12.
        _, lines, ending = combat.play_round(connection, state, [], [], Always(20))
        assert 'critical hit on the player\'s character for 13 damage: 0 of 12 hit points left' in lines[0]
        assert ending == 'dying' and combat5e.hit_points(connection) == (0, 12)
        assert combat.condition(connection)['level'] == combat.DYING
        combat5e.set_hp(connection, 12)
        combat.set_condition(connection, 0)
        # A dodge (no roll needed) gives the foes disadvantage: the lower of a 1 and a 20 misses.
        dice = iter([1, 20, 1, 20])
        rng = type('Pair', (), {'randint': lambda self, low, high: next(dice)})()
        dodge = {'id': 'roll-2', 'action': 'I dodge', 'band': 'failure', 'stat': 'Luck', 'natural': 3}
        _, lines, ending = combat.play_round(connection, state, [dodge], [], rng)
        assert lines == ['The bandit attacks and misses.'] and ending == ''


def test_at_0_hit_points_the_death_saves_decide(client, app):
    fighter(client)
    with app.state.database.connect(write=True) as connection:
        foe = combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(4))[0]
        state = {'round': 1, 'wants': 'rob', 'foes': [foe]}
        lines, events = [], []
        # A natural 20: back on their feet with 1 hit point, still fighting.
        assert combat.fall(connection, state, Always(20), 'now', lines, events) == '' and not events
        assert combat5e.hit_points(connection) == (1, 12) and 'back on their feet with 1 hit point' in lines[0]
        # Stable: the defeat table without death, and 1 hit point.
        lines = []
        assert combat.fall(connection, state, Always(10), 'now', lines, events) == 'dying'
        assert 'Death saves: 10, 10, 10: stable' in lines[0] and events[0][0] != 'death'
        assert combat5e.hit_points(connection) == (1, 12) and not combat.condition(connection)['dead']
        # Three failures: dead.
        lines, events = [], []
        combat.fall(connection, state, Always(1), 'now', lines, events)
        assert events == [('death', 'the bandit')] and combat.condition(connection)['dead']
        assert combat5e.hit_points(connection) == (0, 12)
        assert any(row['kind'] == 'death' for row in record.entries(connection))


def test_with_defeat_by_aim_foes_who_want_a_prisoner_take_one(client, app):
    fighter(client)
    ok(client.put('/api/story/table', json={'defeat': 'by_aim'}))
    with app.state.database.connect(write=True) as connection:
        wardens = {'round': 1, 'wants': 'capture', 'foes': combat5e.foes_from({'name': 'the warden'}, 'engaged',
                                                                             Always(4))}
        lines, events = [], []
        # No death saves: the wardens' table decides, and its low roll is a capture.
        combat.fall(connection, wardens, Always(1), 'now', lines, events)
        assert 'Death saves' not in lines[0] and events == [('captured', 'the warden')]
        # Foes out to kill still bring the death saves.
        killers = wardens | {'wants': 'kill'}
        lines = []
        combat.fall(connection, killers, Always(10), 'now', lines, [])
        assert 'Death saves: 10, 10, 10' in lines[0]


def test_wounds_outside_a_fight_move_the_hit_points_and_a_long_rest_restores_them(client, app):
    fighter(client)
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 3)
        assert combat5e.hit_points(connection) == (5, 12) and 'badly hurt, 5 of 12 hit points' in \
            combat.condition_text(connection)
        # No wound penalties under 5E.
        actions = [{'action': 'I climb', 'stat': 'Vitality', 'difficulty': 'normal'}]
        assert combat.adjust(connection, actions) == actions
        assert combat.mend(connection, 1) == ["A long rest restores the character's hit points: 12 of 12."]
        assert combat5e.hit_points(connection) == (12, 12) and combat.condition(connection)['level'] == 0
        assert sheet.ruleset(connection) == 'srd52'


def test_a_danger_under_5e_brings_an_srd_foe_with_hit_points(client, connected, provider, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'the-heartwood'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt', 'ruleset': 'srd52'}))
    ok(client.put('/api/settings', json={'show_odds': True}))
    app.state.dice = Dice(20, 'low')
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('Something heavy in the brush.')
    tell(client, 'I look around.', 'story-0001')
    fight = ok(client.get('/api/story'))['fight']
    boar = fight['fight']['foes'][0]
    assert boar['name'] == 'ley-mad boar' and boar['max_hp'] == 20 and boar['hp'] == 20  # 5d10+15, every die 1.
    assert (fight['hp'], fight['max_hp']) == (ok(client.get('/api/story/sheet'))['max_hp'],) * 2


# Levels, XP and spells -----------------------------------------------------------------------------

def wizard(client):
    # A level 1 elf wizard (Int 17 after the Sage's +2): spell attack +5, save DC 13, two level 1 slots.
    quick = srd52.suggested('wizard', 'sage')
    ok(start(client, persona={'name': 'Ilse'}, ruleset='srd52', build={
        'class_id': 'wizard', 'species_id': 'elf', 'background_id': 'sage', 'scores': quick['scores'],
        'skills': quick['picks']}))


def test_levels_follow_the_advancement_table_and_add_what_the_class_gains():
    quick = srd52.suggested('wizard', 'sage')
    built = srd52.build('wizard', 'elf', 'sage', quick['scores'], quick['picks'])
    assert built['spells']['cantrips'] == ['acid-splash', 'chill-touch', 'fire-bolt']
    assert len(built['spells']['prepared']) == 4 and built['spells']['slots'][:2] == [2, 0]
    assert (srd52.xp_for(2), srd52.level_for_xp(899), srd52.level_for_xp(900)) == (300, 2, 3)
    grown = built
    for _ in range(3):
        grown, gained = srd52.advance(grown)
    # Level 4: d6 hit die, fixed 4 + Con +2 a level; Ability Score Improvement: Int 17 to 19.
    assert grown['level'] == 4 and grown['max_hp'] == built['max_hp'] + 18 and grown['abilities']['int'] == 19
    assert gained == ['6 more hit points', 'Intelligence +2'] and 'Scholar' in grown['features']
    # Spells are kept as they grow: the old picks stay, level 2 spells come in with the slots.
    assert set(built['spells']['prepared']) <= set(grown['spells']['prepared'])
    assert grown['spells']['slots'][:2] == [4, 3] and len(grown['spells']['cantrips']) == 4


def test_a_won_fight_and_a_milestone_give_xp_and_levels(client, app):
    fighter(client)
    with app.state.database.connect(write=True) as connection:
        foe = combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(1))[0]  # 2d8+2: 4 hit points.
        state = {'round': 0, 'wants': 'rob', 'foes': [foe]}
        state, _, ending = combat.play_round(connection, state, [swing(20)], [{'item_id': 'sword'}], Always(8))
        assert ending == 'won' and combat5e.fight_xp(state) == 25
        assert combat5e.gain(connection, 25, 'the fight won') == ['The character gains 25 XP (the fight won): 25 in all.']
        from dungeon import growth
        said = growth.milestone(connection, 'The Heartwood contract', 'now')
        assert 'gains 100 XP (a milestone: The Heartwood contract)' in said
        said = ' '.join(combat5e.gain(connection, 200, 'a test'))
        assert 'reaches level 2: 8 more hit points, Action Surge' in said and sheet.native(connection)['max_hp'] == 20


def test_spells_spend_slots_hit_foes_heal_and_come_back_with_a_long_rest(client, app):
    wizard(client)
    with app.state.database.connect(write=True) as connection:
        # Out of a fight a spell is a check with the spellcasting ability; a levelled one spends a slot.
        cast = sheet.check(connection, 'Essence', 'normal', 'I cast Burning Hands at the web', Always(15))
        assert cast['skill'] == 'Burning Hands (spell)' and cast['bonus'] == 5 and cast['band'] == 'success'
        sheet.check(connection, 'Essence', 'normal', 'I cast Thunderwave', Always(15))
        empty = sheet.check(connection, 'Essence', 'normal', 'I cast Ice Knife', Always(15))
        # With no slot left it just fails: no dice (playtest M4, finding 3).
        assert empty['band'] == 'failure' and 'no spell slot left' in empty['skill'] and empty['natural'] == 0
        # A cantrip costs nothing: Fire Bolt is a spell attack on AC, 1d10 fire.
        foe = combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(4))[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [foe]}
        rolled = {'id': 'r', 'action': 'I cast Fire Bolt at the bandit', 'band': 'success', 'stat': 'Essence',
                  'natural': 10, 'skill': 'Fire Bolt (spell)'}
        _, lines, _ = combat.play_round(connection, state, [rolled], [], Always(6))
        assert lines[0] == "The player's character casts Fire Bolt at the bandit: 6 fire damage, now badly hurt."
        assert (rolled['skill'], rolled['total'], rolled['target']) == ('Fire Bolt (spell attack)', 15, 12)
        # A save spell: the foe's Dex save against DC 13; a cantrip on a made save does nothing.
        state = {'round': 0, 'wants': 'rob', 'foes': [combat5e.foes_from({'name': 'the bandit'}, 'engaged', Always(4))[0]]}
        rolled = {'id': 'r2', 'action': 'I cast Acid Splash on the bandit', 'band': 'success', 'stat': 'Essence',
                  'natural': 3, 'skill': 'Acid Splash (spell)'}
        _, lines, _ = combat.play_round(connection, state, [rolled], [], Always(20))
        assert 'and it does no harm' in lines[0] and rolled['skill'].startswith("Acid Splash (the bandit's Dexterity")
        combat.set_condition(connection, 0)  # The bandit's blows aside.
        assert combat.mend(connection, 1) == ['A long rest gives the character back their spell slots.']
        assert sheet.native(connection)['spells']['used'][0] == 0


def test_a_healing_spell_heals_the_character(client, app):
    quick = srd52.suggested('cleric', 'acolyte')
    ok(start(client, persona={'name': 'Wenna'}, ruleset='srd52', build={
        'class_id': 'cleric', 'species_id': 'human', 'background_id': 'acolyte', 'scores': quick['scores'],
        'skills': quick['picks']}))
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 3)
        before = combat5e.hit_points(connection)[0]
        healed = sheet.check(connection, 'Essence', 'hard', 'I cast Cure Wounds on myself', Always(1))
        assert healed['band'] == 'success' and healed['skill'].startswith('Cure Wounds (heals')
        assert combat5e.hit_points(connection)[0] > before and combat.condition(connection)['level'] < 3


def test_a_punch_is_an_unarmed_strike_and_starting_armour_counts():
    # Playtest 5E findings 1 and 3: a fighter starts in Chain Mail; "I punch him" is no longsword.
    quick = srd52.suggested('fighter', 'soldier')
    built = srd52.build('fighter', 'human', 'soldier', quick['scores'], quick['picks'])
    assert built['armor'] == ['chain-mail'] and built['ac'] == 16
    assert srd52.starting_armor('ranger') == ['studded-leather-armor']
    assert combat5e.weapon_of([{'item_id': 'sword'}], 'I punch him in the jaw') is None
    assert combat5e.weapon_of([{'item_id': 'sword'}, {'item_id': 'knife'}], 'I stab him with my knife')['name'] == \
        'Dagger'


def test_under_5e_the_condition_reads_as_hit_points_not_marvel_wounds(client, app):
    # Playtest 5E finding 5.
    fighter(client)
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 4)
        assert combat.view(connection, True)['condition'] == 'barely standing'
        assert 'maimed' not in combat.condition_text(connection)
