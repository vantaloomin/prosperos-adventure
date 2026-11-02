"""Lasting injuries and treatment (dungeon/injuries.py), under the Injury persistence setting."""
from datetime import datetime, timedelta

from conftest import tell
from test_combat import Dice, foe
from test_inventory import begin
from test_travel import Road, ok, reply

from dungeon import combat, injuries, inventory

NOW = datetime(1290, 5, 1, 12)
ILSE = {'sheet': {'name': 'Ilse Rook', 'role': 'shrine keeper', 'about': 'Keeper of the shrine, healer and gravedigger.'}}
CROWNS = {'symbol': 'cr.'}


def persistence(client, value):
    ok(client.put('/api/settings', json={'injury_persistence': value}))


def test_a_lasting_injury_makes_its_actions_harder_and_people_notice(app):
    with app.state.database.connect(write=True) as connection:
        assert injuries.roll(connection, NOW, 'a raider', Road(5)) == 'It leaves a lasting injury: a lost eye.'
        assert injuries.view(connection, NOW) == ['a lost eye']
        assert [action['difficulty'] for action in injuries.adjust(connection, [
            {'action': 'shoot the lookout', 'stat': 'Vitality', 'difficulty': 'normal'},
            {'action': 'ask the way', 'stat': 'Allure', 'difficulty': 'normal'}], NOW)] == ['hard', 'normal']
        assert 'Strangers' not in injuries.prompt_text(connection, NOW)
        assert 'A lost eye: An empty socket' in injuries.prompt_text(connection, NOW)
        # The same injury twice is never rolled: the next is another.
        assert injuries.roll(connection, NOW, 'a raider', Road(5)) == 'It leaves a lasting injury: a limp from a leg ' \
                                                                       'that knit badly.'
        assert "Left with a lost eye by a raider." in [row['text'] for row in connection.execute(
            'SELECT text FROM record_entries').fetchall()]


def test_injury_persistence_keeps_fades_or_rules_them_out(client, app):
    with app.state.database.connect(write=True) as connection:
        injuries.roll(connection, NOW, 'a raider', Road(5))
    later = NOW + timedelta(days=41)
    persistence(client, 'temporary')
    with app.state.database.connect() as connection:
        assert injuries.view(connection, NOW + timedelta(days=39)) == ['a lost eye']
        assert injuries.view(connection, later) == []
    persistence(client, 'none')
    with app.state.database.connect(write=True) as connection:
        assert injuries.view(connection, NOW) == [] and injuries.roll(connection, NOW, 'a raider', Road(5)) is None
    persistence(client, 'permanent')
    with app.state.database.connect() as connection:
        assert injuries.view(connection, later) == ['a lost eye']


def test_a_critical_hit_that_only_hurts_leaves_no_lasting_injury(app):
    # E2E vows pass: a warden archer's critical hit left the character Hurt, and a lost eye with it.
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(weapon=0)]}
        assert combat.foes_move(connection, state, False, Dice(95, 'low'), []) == 2
        assert 'hurt_by' not in state


def test_a_critical_hit_in_a_fight_leaves_a_lasting_injury(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        # Already grazed, the critical hit leaves the character Wounded.
        combat.set_condition(connection, 1)
        combat.save_fight(connection, {'round': 0, 'wants': 'kill', 'foes': [foe(weapon=0)]})
    app.state.dice = Dice(95, 'low')
    reply(provider, 'The blade finds bone.')
    tell(client, 'I stand there.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert len(story['fight']['injuries']) == 1 and story['fight']['fight'] is not None
    narrator = provider.requests[-1]['system']
    assert 'It leaves a lasting injury:' in narrator and "lasting injuries (kept by the game" in narrator
    with app.state.database.connect() as connection:
        assert 'hurt_by' not in combat.fight(connection)


def test_bandages_from_the_pack_treat_a_wound_once(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 3)
        connection.execute("DELETE FROM story_inventory WHERE item_id IN ('bandages', 'poultice')")
        connection.execute("INSERT INTO story_inventory (id, city_id, item_id, qty) VALUES ('b', 'kingswood', "
                           "'bandages', 1)")
    # Wounded is hard to treat: 85 and the Mind die, less 10, is a success.
    app.state.dice = Road(85)
    reply(provider, 'Linen and patience.')
    tell(client, 'I clean the wound and bandage it.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert story['fight']['condition'] == 'hurt'
    narrator = provider.requests[-1]['system']
    assert '## The treatment' in narrator and 'from wounded to hurt' in narrator
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT qty FROM story_inventory WHERE id='b'").fetchone()[0] == 0
        assert tuple(connection.execute("SELECT stat, difficulty FROM story_rolls WHERE action='treat the wound'"
                                  ).fetchone()) == ('Mind', 'hard')
    reply(provider, 'Again.')
    tell(client, 'I bandage it again.', 'story-0002')
    assert 'treated already' in provider.requests[-1]['system']


def test_a_healer_treats_for_a_fee_and_a_bad_treatment_goes_bad(app):
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 2)
        inventory.set_purse(connection, 100)
        assert 'cannot pay' in injuries.treat(connection, 'Mother Rook, can you tend my wound?', [ILSE], [], CROWNS)[0]
        inventory.set_purse(connection, 500)
        lines = injuries.treat(connection, 'Mother Rook, can you tend my wound?', [ILSE], [], CROWNS, Road(80))
        assert lines[0] == 'Ilse Rook is paid 2.00 cr. to treat the wound.' and 'from hurt to unhurt' in lines[1]
        assert inventory.purse(connection) == 300
        # A fresh wound can be treated again; a critical failure turns it bad.
        combat.set_condition(connection, 3)
        lines = injuries.treat(connection, 'I bandage it.', [], [{'action': 'treat the wound', 'band':
                                                                   'critical_failure'}], CROWNS)
        assert 'nothing in the pack' in lines[0]
        connection.execute("INSERT INTO story_inventory (id, city_id, item_id, qty) VALUES ('p', 'kingswood', "
                           "'poultice', 1)")
        lines = injuries.treat(connection, 'I bandage it.', [], [{'action': 'treat the wound', 'band':
                                                                   'critical_failure'}], CROWNS)
        assert 'goes bad' in lines[0] and combat.condition(connection)['level'] == 4


def test_treating_a_wound_the_character_does_not_have_rolls_nothing(client, connected, provider, app):
    begin(client)
    reply(provider, 'Nothing to bind.')
    tell(client, 'I bind my wounds.', 'story-0001')
    assert 'The character has no wound to treat.' in provider.requests[-1]['system']
    with app.state.database.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM story_rolls').fetchone()[0] == 0
    assert injuries.untreated([{'action': 'bind my wounds'}, {'action': 'look around'}]) == [{'action': 'look around'}]
