"""The Percentile ruleset (dungeon/rules/brp.py, dungeon/combat_brp.py): BRP characters, d100 skill rolls, experience,
fights on the Attack and Defense Matrix, major wounds and slow healing."""
import pytest
from conftest import tell
from test_rulesets import reply, start
from test_travel import ok

from dungeon import combat, combat_brp, growth, record, sheet
from dungeon.rules import brp

WARRIOR = {'str': 15, 'con': 14, 'siz': 13, 'int': 10, 'pow': 10, 'dex': 14, 'cha': 10}


class Faces:
    """The given faces in order, then `rest`."""

    def __init__(self, *faces, rest=50):
        self.faces, self.rest = list(faces), rest

    def randint(self, low, high):
        return max(low, min(high, self.faces.pop(0) if self.faces else self.rest))


def made(characteristics=None, profession='warrior', personality='brutal'):
    return {'characteristics': characteristics or WARRIOR, 'profession': profession, 'personality': personality}


def played(client):
    ok(start(client, persona={'name': 'Kara'}, ruleset='brp', brp=made()))


def test_a_character_buys_characteristics_and_takes_a_profession_and_a_personality(client, app):
    choices = ok(client.get('/api/story/start'))['brp']
    assert choices['points'] == 24 and 'ORC License' in choices['attribution']
    assert any(item['id'] == 'warrior' for item in choices['professions'])
    played(client)
    with app.state.database.connect() as connection:
        view = sheet.full_view(connection)
    assert view['ruleset_name'] == 'Percentile' and view['max_hp'] == 14 and view['major_wound'] == 7
    assert view['damage_modifier'] == '+1D4' and view['rolls']['Effort'] == 75 and view['armor_name'] == 'Leather, Hard'
    # Brutal's 20s and the warrior's points, none past 75.
    assert view['skills']['brawl'] == 75 and view['skills']['sword'] > 15 and max(view['skills'].values()) <= 75
    assert view['skills']['dodge'] >= 28
    # A made warrior carries the broadsword their Sword skill covers (playtest M4b, finding 2).
    from dungeon import inventory
    with app.state.database.connect() as connection:
        assert 'sword' in {row['item_id'] for row in inventory.carried(connection, 'kingswood')}


def test_the_pack_has_no_modern_weapons():
    named = [attack['name'] for foe in brp.pack()['foes'] for attack in foe['attacks']]
    assert not [name for name in named if 'baseball' in name.lower()] and 'Cudgel' in named


@pytest.mark.parametrize(('build', 'detail'), [
    (made({**WARRIOR, 'dex': 18}), 'cost 24 points at most'),
    (made({**WARRIOR, 'str': 22}), 'from 3 to 21'),
    (made(profession='astronaut'), 'profession'),
])
def test_a_build_must_be_one_the_rules_allow(client, build, detail):
    response = start(client, persona={'name': 'Kara'}, ruleset='brp', brp=build)
    assert response.status_code == 422 and detail in response.text


def test_a_premade_plays_brp_from_its_strongest_stat():
    quick = brp.suggested('Luck')
    character = brp.build(quick['characteristics'], quick['profession'], quick['personality'])
    assert character['profession'] == 'thief' and brp.cost(character['characteristics']) <= 24


def test_success_levels_follow_the_skill_results_table():
    # 60%: critical 01-03, special 04-12, fumble 98-00.
    assert [brp.level(n, 60) for n in (3, 4, 12, 13, 60, 61, 97, 98)] == \
        ['critical', 'special', 'special', 'success', 'success', 'failure', 'failure', 'fumble']
    # 01-05 always succeeds, 96 always fails; 85% fumbles only on 00.
    assert brp.level(5, 2) == 'success' and brp.level(96, 99) == 'failure' and brp.level(99, 85) == 'failure'
    assert brp.chance_for(60, 'easy') == 120 and brp.chance_for(61, 'hard') == 31 and brp.chance_for(60, 'very_hard') == 10
    # The card never reads over 95% (96-00 always fails); the full 120% still sets the critical.
    assert brp.shown(120) == 95 and brp.shown(60) == 60 and brp.level(6, 120) == 'critical'


def test_a_roll_reads_its_skill_from_the_words_and_earns_an_experience_check(client, app):
    played(client)
    with app.state.database.connect(write=True) as connection:
        rolled = sheet.check(connection, 'Vitality', text='I climb the wall', rng=Faces(30))
        assert rolled['skill'] == 'Climb 75%' and rolled['band'] == 'success' and rolled['die'] == 100
        assert sheet.native(connection)['checks'] == ['climb']
        # No skill fits: a characteristic roll (Idea, INT x5).
        assert sheet.check(connection, 'Mind', text='I wonder', rng=Faces(30))['skill'] == 'Idea 50%'
        # After a rest, d100 + the experience bonus (5) over 75 raises Climb 1D6.
        assert growth.grow(connection, 'now', Faces(80, 4)) == [
            'What the character has been through has taught them: Climb grows from 75% to 79%.']
        assert sheet.native(connection)['checks'] == []


def test_a_turn_under_brp_rolls_a_d100_skill(client, connected, provider, app):
    played(client)
    ok(client.put('/api/settings', json={'show_odds': True}))
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('You climb.')
    tell(client, 'I climb the wall.', 'story-0001')
    story = ok(client.get('/api/story'))
    rolled = next(message for message in story['messages'] if message['role'] == 'user')['rolls'][0]
    assert rolled['ruleset'] == 'brp' and rolled['die'] == 100 and rolled['skill'].startswith('Climb')


# Fights -------------------------------------------------------------------------------------------

def attack(natural, action='I hit the thug with my sword'):
    return {'id': 'r', 'action': action, 'band': 'success', 'stat': 'Vitality', 'natural': natural,
            'skill': 'Effort 75%'}


def test_foes_are_the_packs_characters_and_animals():
    assert combat_brp.foe_for({'name': 'the bandit'})['id'] == 'thug'
    assert combat_brp.foe_for({'name': 'a grey wolf'})['id'] == 'wolf'
    assert combat_brp.foe_for({'name': 'the drunk', 'vitality': 6})['id'] == 'thug'
    # The matrix: a dodge at the attack's level stops it; a success takes a special down to a success.
    assert combat_brp.landed('special', 'special') is None and combat_brp.landed('special', 'success') == 'success'
    assert combat_brp.landed('critical', 'special') == 'success' and combat_brp.landed('success', 'failure') == 'success'


def test_the_characters_attack_uses_the_weapon_skill_and_the_foe_dodges(client, app):
    played(client)
    with app.state.database.connect(write=True) as connection:
        assert combat.basic(connection) and combat.word(connection, 0) == 'unhurt'
        thug = combat_brp.foes_from({'name': 'the thug'}, 'engaged')[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [thug]}
        rolled = attack(20)
        # The thug's dodge fails (90); the broadsword does 1D8+1 (8+1) + 1D4 (4) - 1 armour = 12; down to 3 of 15,
        # the thug fails Luck (90) and breaks.
        state, lines, ending = combat.play_round(connection, state, [rolled], [{'item_id': 'sword'}],
                                                 Faces(90, 8, 4, 90, 90))
        assert lines[0] == "The player's character hits the thug with a broad sword for 12 damage: now barely standing."
        assert rolled['skill'].startswith('Sword, Broad') and rolled['target'] == sheet.native(connection)['skills']['sword']
        assert 'sword' in sheet.native(connection)['checks'] and 'The thug breaks' in lines[1] and ending == 'won'


def test_a_major_wound_can_leave_its_mark_and_rest_heals_slowly(client, app):
    played(client)
    with app.state.database.connect(write=True) as connection:
        bear = combat_brp.foes_from({'name': 'the bear'}, 'engaged')[0]
        state = {'round': 1, 'wants': 'kill', 'foes': [bear]}
        # The claw lands (10), the dodge fails (99); 1D6 (6) + 2D6 (6, 6) - 2 armour = 16 of 14: a fatal wound.
        state, lines, ending = combat.play_round(connection, state, [], [], Faces(10, 99, 6, 6, 6))
        assert 'for 16 damage: 0 of 14 hit points left' in ' '.join(lines) and ending == 'dying'
        combat_brp.set_hp(connection, 14)
        state = {'round': 1, 'wants': 'kill', 'foes': [bear]}
        # 1D6 (5) + 2D6 (2, 2) - 2 = 7: a major wound; Luck fails (99) and the table (05) takes 1D3 (2) DEX.
        state, lines, _ = combat.play_round(connection, state, [], [], Faces(10, 99, 5, 2, 2, 99, 5, 2))
        assert 'It is a major wound.' in lines and sheet.native(connection)['characteristics']['dex'] == 12
        assert sheet.native(connection)['major_wounds'][0]['characteristic'] == 'dex'
        # Rest: a hit point every 7 / 1D3 nights (here 3 nights a point).
        assert combat_brp.rest(connection, 3, Faces(3, 3)) == ['Rest mends the character: 8 of 14 hit points.']


def test_first_aid_on_the_characters_own_wound_heals_once(client, app):
    played(client)
    with app.state.database.connect(write=True) as connection:
        combat_brp.set_hp(connection, 8)
        healed = sheet.check(connection, 'Mind', text='I bandage my arm', rng=Faces(10, 3))
        assert healed['skill'].endswith('(heals 3)') and combat_brp.hit_points(connection) == (11, 14)
        again = sheet.check(connection, 'Mind', text='I bandage my arm', rng=Faces(10, 3))
        assert 'heals' not in again['skill'] and combat_brp.hit_points(connection) == (11, 14)


@pytest.mark.parametrize('text', ['I bind my wounds with a strip of my shirt', 'I dress the wound', 'She binds up my leg',
                                  'I tie a tourniquet above the cut'])
def test_binding_a_wound_is_first_aid(text):
    assert brp.skill_for(text) == 'first_aid'


@pytest.mark.parametrize('synced', [True, False])
def test_binding_a_wound_on_a_turn_rolls_first_aid_and_heals(client, connected, provider, app, synced):
    # Playtest m5: at 9 of 14 hit points, "I bind my wounds…" rolled nothing.
    played(client)
    ok(client.put('/api/settings', json={'show_odds': True}))
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('You bind the cut.')
    with app.state.database.connect(write=True) as connection:
        level = combat_brp.set_hp(connection, 9)
        if synced:
            combat.set_condition(connection, level)
    tell(client, 'I bind my wounds with a strip of my shirt.', 'aid-0001')
    story = ok(client.get('/api/story'))
    rolls = next(message for message in story['messages'] if message['role'] == 'user')['rolls']
    assert [roll['skill'].split(' ')[:2] for roll in rolls] == [['First', 'Aid']]
    with app.state.database.connect() as connection:
        hp = combat_brp.hit_points(connection)[0]
    assert hp > 9 if rolls[0]['band'] in ('success', 'critical_success') else hp == 9
