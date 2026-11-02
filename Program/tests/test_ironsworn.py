"""Ironsworn (dungeon/rules/ironsworn.py): the character, moves read from the words, the action roll and momentum."""
import random
from collections import Counter

import pytest
from conftest import tell
from test_rulesets import reply, start
from test_travel import ok

from dungeon import bonds, quests, record, sheet, stress, travel
from dungeon import sworn as sworn_tracks
from dungeon.rules import ironsworn


class Dice:
    """The action die shows `action`, the two challenge dice `first` and `second`."""

    def __init__(self, action, first, second):
        self.faces = iter([action, first, second])

    def randint(self, low, high):
        return next(self.faces)


def made(stats=None, assets=('path/veteran', 'combat_talent/swordmaster', 'companion/hound')):
    return {'stats': stats or {'iron': 3, 'heart': 2, 'wits': 2, 'edge': 1, 'shadow': 1}, 'assets': list(assets)}


def test_an_ironsworn_character_takes_the_array_and_three_assets(client):
    choices = ok(client.get('/api/story/start'))['ironsworn']
    assert choices['array'] == [3, 2, 2, 1, 1] and 'Shawn Tomkin' in choices['attribution']
    assert {'path/veteran', 'ritual/divination', 'companion/hound'} <= {asset['id'] for asset in choices['assets']}
    ok(start(client, persona={'name': 'Kara'}, ruleset='ironsworn', ironsworn=made()))
    view = ok(client.get('/api/story/sheet'))
    assert view['ruleset'] == 'ironsworn' and view['stats']['iron'] == 3
    assert (view['health'], view['spirit'], view['supply'], view['momentum'], view['momentum_max']) == (5, 5, 5, 2, 10)
    assert [asset['name'] for asset in view['asset_list']] == ['Veteran', 'Swordmaster', 'Hound']
    assert client.put('/api/story/sheet', json={'stats': {'Mind': 12}}).status_code == 409


@pytest.mark.parametrize(('build', 'detail'), [
    (made(stats={'iron': 3, 'heart': 3, 'wits': 1, 'edge': 1, 'shadow': 1}), '3, 2, 2, 1 and 1'),
    (made(assets=('path/veteran',)), 'Choose 3 assets'),
])
def test_an_ironsworn_build_must_be_one_the_rules_allow(client, build, detail):
    response = start(client, persona={'name': 'Kara'}, ruleset='ironsworn', ironsworn=build)
    assert response.status_code == 422 and detail in response.json()['detail']


def test_a_premade_plays_ironsworn_from_its_strongest_stat(client):
    ok(start(client, premade_id='agna-holt', ruleset='ironsworn'))
    view = ok(client.get('/api/story/sheet'))
    assert view['ruleset'] == 'ironsworn' and max(view['stats'].values()) == 3 and len(view['assets']) == 3


def test_moves_are_read_from_the_words():
    assert ironsworn.read('Luck', 'I sneak past the guard') == ('face_danger', 'shadow')
    assert ironsworn.read('Allure', 'I threaten him until he talks') == ('compel', 'iron')
    assert ironsworn.read('Allure', 'I try to convince her') == ('compel', 'heart')
    assert ironsworn.read('Mind', 'I search the camp') == ('gather_information', 'wits')
    assert ironsworn.read('Vitality', 'I climb the cliff') == ('face_danger', 'iron')
    # Playtest M4, finding 6: talking someone round is Compel; a vow is Swear an Iron Vow.
    assert ironsworn.read('Allure', 'I talk the factor round to telling me the truth') == ('compel', 'heart')
    assert ironsworn.read('Resolve', 'I swear an iron vow to find her') == ('swear_an_iron_vow', 'heart')


def test_the_action_roll_beats_the_challenge_dice_and_burns_momentum_when_it_helps():
    built = ironsworn.build(*made().values())
    # 4 + iron 3 = 7 beats 5 and 6: a strong hit, and Face Danger takes +1 momentum.
    rolled = ironsworn.roll(built, 'Vitality', 'normal', 'I climb', Dice(4, 5, 6))
    assert (rolled['band'], rolled['total'], rolled['momentum']) == ('success', 7, 3)
    assert rolled['skill'] == 'Face Danger +iron vs 5 and 6'
    # 7 against 6 and 9: a weak hit; against 9 and 9 a miss with a match.
    assert ironsworn.roll(built, 'Vitality', 'normal', 'I climb', Dice(4, 6, 9))['band'] == 'success_cost'
    assert ironsworn.roll(built, 'Vitality', 'normal', 'I climb', Dice(4, 9, 9))['band'] == 'critical_failure'
    # Momentum 8 beats what the roll did not: burned, the result improves and momentum resets to 2.
    burned = ironsworn.roll(built | {'momentum': 8}, 'Vitality', 'normal', 'I climb', Dice(1, 5, 7))
    assert burned['band'] == 'success' and burned['momentum'] == 3 and 'momentum burned' in burned['skill']
    # A hard action rolls at -1; negative momentum cancels an action die that equals it.
    assert ironsworn.roll(built, 'Vitality', 'hard', 'I climb', Dice(4, 1, 1))['bonus'] == 2
    assert ironsworn.roll(built | {'momentum': -4}, 'Vitality', 'normal', 'I climb', Dice(4, 2, 3))['total'] == 3
    bands = Counter(ironsworn.roll(built, 'Vitality', 'normal', 'I climb', random.Random(seed))['band']
                    for seed in range(300))
    assert set(bands) == {'success', 'success_cost', 'failure', 'critical_success', 'critical_failure'}


def test_a_turn_under_ironsworn_rolls_a_move_and_keeps_momentum(client, connected, provider, app):
    ok(start(client, persona={'name': 'Kara'}, ruleset='ironsworn', ironsworn=made()))
    ok(client.put('/api/settings', json={'show_odds': True}))
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('You climb.')
    tell(client, 'I climb the wall.', 'story-0001')
    story = ok(client.get('/api/story'))
    rolled = next(message for message in story['messages'] if message['role'] == 'user')['rolls'][0]
    assert rolled['ruleset'] == 'ironsworn' and rolled['die'] == 6 and rolled['skill'].startswith('Face Danger +iron')
    assert story['bands'] is None
    with app.state.database.connect() as connection:
        assert sheet.ruleset(connection) == 'ironsworn' and 'Swordmaster' in sheet.full_view(connection)['asset_list'][1]['name']


# Fights -------------------------------------------------------------------------------------------

from dungeon import combat, combat_iron  # noqa: E402


class Always:
    def __init__(self, face):
        self.face = face

    def randint(self, low, high):
        return max(low, min(high, self.face))


def sworn(client):
    ok(start(client, persona={'name': 'Kara'}, ruleset='ironsworn', ironsworn=made()))


def attack(band, action='I hit the raider with my sword'):
    return {'id': 'r', 'action': action, 'band': band, 'stat': 'Vitality', 'natural': 4,
            'skill': 'Face Danger +iron vs 2 and 3'}


def test_foes_are_the_packs_npcs_with_progress_tracks():
    assert combat_iron.npc_for({'name': 'ley-mad boar'}) == 'animals/boar'
    assert combat_iron.npc_for({'name': 'warden of Brynwyr'}) == 'ironlanders/hunter'
    assert combat_iron.npc_for({'name': 'the drunk', 'vitality': 6}) == 'ironlanders/common_folk'
    raider = combat_iron.foes_from({'name': 'the raider'}, 'engaged')[0]
    assert raider['rank'] == 2
    combat_iron.inflict(raider, 2)  # Dangerous: 2 boxes a harm.
    assert combat_iron.boxes(raider) == 4 and not raider['out']


def test_strike_with_initiative_clash_without_and_end_the_fight(client, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        assert combat.sworn(connection) and combat.word(connection, 0) == 'unharmed'
        raider = combat_iron.foes_from({'name': 'the raider'}, 'engaged')[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [raider], 'initiative': 'player'}
        # A strong hit with initiative and a sword: 2 harm +1, 6 boxes, and the upper hand kept.
        rolled = attack('success')
        state, lines, ending = combat.play_round(connection, state, [rolled], [{'item_id': 'sword'}], Always(10))
        assert lines[0].startswith("The player's character strikes the raider: 3 harm, 6 of 10 boxes")
        assert rolled['skill'].startswith('Strike +iron') and state['initiative'] == 'player' and ending == ''
        # A punch is 1 harm, +1 on a strong hit: from 4 boxes to 8, and End the Fight against the challenge dice.
        state['foes'][0] |= {'ticks': 16, 'out': False, 'wound': 1}
        state, lines, ending = combat.play_round(connection, state, [attack('success', 'I punch the raider')],
                                                 [{'item_id': 'sword'}], Always(1))
        assert 'ends the fight with the raider' in ' '.join(lines) and ending == 'won'


def test_a_foe_with_the_upper_hand_makes_the_character_endure_harm(client, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        raider = combat_iron.foes_from({'name': 'the raider'}, 'engaged')[0]
        state = {'round': 0, 'wants': 'rob', 'foes': [raider], 'initiative': 'foe'}
        # A miss without initiative: the raider (rank 2) hits for 2 harm.
        state, lines, _ = combat.play_round(connection, state, [attack('failure')], [], Always(10))
        assert "hits the player's character for 2 harm: health 3 of 5" in ' '.join(lines)
        assert combat_iron.health(connection) == 3 and combat.view(connection, True)['condition'] == 'hurt'
        assert 'health 3 of 5' in combat.condition_text(connection)
        # Rest: +1 health a night.
        assert combat.mend(connection, 2) == ['Rest restores the character: health 5 of 5.']
        assert combat.condition(connection)['level'] == 0


def test_at_0_health_a_miss_on_endure_harm_means_facing_death(client, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        combat_iron.set_health(connection, 1)
        bear = combat_iron.foes_from({'name': 'the bear'}, 'engaged')[0]
        state = {'round': 1, 'wants': 'kill', 'foes': [bear], 'initiative': 'foe'}
        # Every die high: the action die 6 + iron 3 = 9 never beats two 10s, so Endure Harm misses at 0 health.
        state, lines, ending = combat.play_round(connection, state, [], [], Always(10))
        assert ending == 'dying'
        events = []
        combat.fall(connection, state, Always(10), 'now', lines, events)
        assert events[0][0] == 'death' and combat.condition(connection)['dead']
        # The fight's own rolls are roll cards: Endure Harm, then Face Death.
        assert [card['action'] for card in state['cards']] == ['Endure Harm from the bear', 'Face Death']


def test_a_brawl_to_drive_the_character_off_ends_in_a_beating_not_a_death(client, app):
    # Playtest M4, finding 4: a thug who wants the character gone does not kill them.
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        combat_iron.set_health(connection, 1)
        thug = combat_iron.foes_from({'name': 'the thug'}, 'engaged')[0]
        state = {'round': 1, 'wants': 'drive_off', 'foes': [thug], 'initiative': 'foe'}
        state, lines, ending = combat.play_round(connection, state, [], [], Always(10))
        events = []
        combat.fall(connection, state, Always(1), 'now', lines, events)
        assert events[0][0] in ('thrown_out', 'rescued') and not combat.condition(connection)['dead']
        assert not any('faces it' in line for line in lines)


def test_supply_feeds_the_road_and_resupply_brings_it_back(client, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        # Two days on the road: two supply, not a food from the pack.
        assert travel.eat(connection, ['bread'], 2) == (['2 supply (3 left)'], 0)
        assert travel.eat(connection, ['bread'], 5) == (['3 supply (0 left)'], 2)
        # Resupply: a strong hit (6 + wits 2 beats 1 and 2) brings back 2 supply.
        rolled = sheet.check(connection, 'Mind', text='I forage for roots and berries', rng=Dice(6, 1, 2))
        assert rolled['move'] == 'resupply' and rolled['skill'].endswith('(+2 supply)')
        assert sheet.native(connection)['supply'] == 2


def test_spirit_follows_the_stress_track(client, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        stress.save(connection, 5)
        assert sheet.native(connection)['spirit'] == 2
        stress.save(connection, 0)
        assert sheet.native(connection)['spirit'] == 5


def test_a_vow_fulfilled_gives_experience_spent_on_assets():
    character = ironsworn.build({'iron': 3, 'heart': 2, 'wits': 2, 'edge': 1, 'shadow': 1}, made()['assets'])
    character['xp'] = ironsworn.vow_xp(ironsworn.rank_of(2))
    assert ironsworn.rank_of(2) == 'formidable' and character['xp'] == 3
    # 2 upgrades the veteran (its second ability); 1 is left.
    grown = ironsworn.spend(character)
    assert grown[0].startswith('Veteran grows') and character['xp'] == 1
    assert len(ironsworn.view(character)['asset_list'][0]['abilities']) == 2


def test_a_quest_done_under_ironsworn_is_a_vow_fulfilled(client, app, monkeypatch):
    sworn(client)
    rolled = ironsworn.progress_roll
    monkeypatch.setattr(ironsworn, 'progress_roll', lambda ticks, rng=None: rolled(ticks, Faces(1, 1)))
    with app.state.database.connect(write=True) as connection:
        quest_id = quests.create(connection, 'oath', 'kingswood', 'An oath to Tamsin', 'Find her brother.', '', '',
                                 None, giver='Tamsin')
        lines = quests.end(connection, quest_id, 'done', 'Found him.', 'now')
        # The deed that ends it is a milestone: 8 ticks, 2 boxes, beat 1 and 1.
        assert any(line.startswith('Fulfill Your Vow, dangerous (An oath to Tamsin), progress 2 vs 1 and 1, a strong '
                                   'hit: 2 experience') for line in lines)
        assert sheet.native(connection)['upgrades'] == {'path/veteran': 1}


class Faces:
    def __init__(self, *faces):
        self.faces = iter(faces)

    def randint(self, low, high):
        return next(self.faces)


def test_progress_tracks_mark_by_rank_and_roll_against_the_challenge_dice():
    assert ironsworn.mark(0, 'troublesome') == 12 and ironsworn.mark(36, 'troublesome') == 40
    assert ironsworn.mark(0, 'epic') == 1
    assert ironsworn.progress_roll(24, Faces(5, 4))['band'] == 'success'
    assert ironsworn.progress_roll(24, Faces(5, 7))['band'] == 'success_cost'
    assert ironsworn.progress_roll(24, Faces(8, 9))['band'] == 'failure'
    assert ironsworn.progress_roll(0, Faces(3, 3))['band'] == 'critical_failure'
    assert ironsworn.vow_xp('formidable', weak=True) == 2


def test_pursuing_a_vow_reaches_a_milestone_once_a_day_and_bonds_tick(client, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        quests.create(connection, 'job', 'kingswood', 'The Millpond bargain', 'Drag the pond.', '', '', None,
                      tier=2)
        landed, missed = [{'band': 'success'}], [{'band': 'failure'}]
        assert sworn_tracks.pursued(connection, 'I head to the Millpond.', missed, '2026-10-01') == []
        assert sworn_tracks.pursued(connection, 'I ask about the weather.', landed, '2026-10-01') == []
        assert sworn_tracks.pursued(connection, 'I drag the Millpond for the bargain\'s token.', landed,
                                    '2026-10-01') == ['Reach a Milestone on the vow The Millpond bargain: progress 1 '
                                                      'of 10.']
        assert sworn_tracks.pursued(connection, 'Deeper to the Millpond.', landed, '2026-10-01') == []
        assert sworn_tracks.pursued(connection, 'Deeper to the Millpond.', landed, '2026-10-02') != []
        bonds.forge(connection, 'hesk', 'Hesk Aldane', 'sworn', 'now')
        shown = ironsworn.view(sheet.native(connection))['progress']
        assert shown == [{'name': 'The Millpond bargain', 'rank': 'formidable', 'ticks': 8, 'boxes': 2, 'of': 10},
                         {'name': 'Bonds', 'rank': None, 'ticks': 1, 'boxes': 0, 'of': 10}]


def test_a_vow_milestone_reaches_the_narrator(client, connected, provider, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        quests.create(connection, 'oath', 'kingswood', 'An oath to Tamsin', 'Find her brother.', '', '', None)
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('You ask around.')
    app.state.dice = Always(6)
    tell(client, 'I climb the mill wall to look for Tamsin\'s brother.', 'story-0001')
    assert any('## Vows (decided by the game)\n- Reach a Milestone on the vow An oath to Tamsin: progress 2 of 10.'
               in request['system'] for request in provider.requests)

def test_a_line_swears_an_iron_vow_pursues_it_by_its_words_and_calls_it_kept(client, connected, provider, app):
    # E2E vows pass: an iron vow sworn in so many words made no quest, and "The vow is done" did nothing.
    sworn(client)
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('The mill is quiet.')
    app.state.dice = Always(6)
    tell(client, 'I swear an iron vow to find whoever is breaking the saws at the mill, whatever it costs.',
         'story-0001')
    with app.state.database.connect() as connection:
        vow = next(quest for quest in quests.rows(connection, 'open') if quest['kind'] == 'oath')
        assert vow['title'] == 'Vow: find whoever is breaking the saws at the mill' and vow['due_at'] is None
        assert ironsworn.view(sheet.native(connection))['progress'][0] == {
            'name': vow['title'], 'rank': 'dangerous', 'ticks': 0, 'boxes': 0, 'of': 10}
    tell(client, 'I climb into the saw pit and look for tool marks.', 'story-0003')
    assert any('Reach a Milestone on the vow Vow: find whoever is breaking the saws at the mill: progress 2 of 10.'
               in request['system'] for request in provider.requests)
    tell(client, 'The vow is done.', 'story-0005')
    assert any('Fulfill Your Vow, dangerous (Vow: find whoever is breaking the saws at the mill)' in request['system']
               for request in provider.requests)
    with app.state.database.connect() as connection:
        assert not [quest for quest in quests.rows(connection, 'open') if quest['kind'] == 'oath']
        assert [track['name'] for track in ironsworn.view(sheet.native(connection))['progress']] == ['Bonds']


def test_an_oath_sworn_to_someone_is_a_vow_track_on_the_sheet(client, app):
    sworn(client)
    with app.state.database.connect(write=True) as connection:
        quests.swear(connection, 'kingswood', {'to': 'Corin', 'text': 'Stand by Corin.', 'days': 7},
                     quests.datetime(2026, 10, 1))
        assert ironsworn.view(sheet.native(connection))['progress'][0]['name'] == 'An oath to Corin'
