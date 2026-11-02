"""Every town's quests, dangers and finds (dungeon/world/data/adventures, finds; dungeon/quests.py, dungeon/finds.py)."""
import pytest
from test_table import ASH, STATS

from dungeon import combat5e, finds, inventory, packages, quests, world_data

TOWNS = ['kingswood', 'haven', 'the-concourse', 'hollin', 'the-gilded-bazaar']


@pytest.mark.parametrize('town', TOWNS)
def test_a_towns_adventure_names_its_own_places_and_fightable_foes(town):
    found = quests.adventure(town)
    places = {place['id'] for place in world_data.read('cities', town)['places']}
    assert found['quests'] and len({quest['id'] for quest in found['quests']}) == len(found['quests'])
    for quest in found['quests']:
        assert {'title', 'hook', 'truth', 'missed'} <= set(quest) and set(quest['places']) <= places, quest['id']
    for danger in found['dangers']:
        assert danger['place'] in places
        for threat in danger['threats']:
            spec = threat.get('foe') if isinstance(threat, dict) else None
            if spec:
                assert spec['wants'] in ('kill', 'rob', 'capture', 'drive_off')
                assert spec.get('srd52') is None or spec['srd52'] in combat5e.monsters()


def test_quest_ids_are_unique_across_towns():
    ids = [quest['id'] for town in TOWNS for quest in quests.adventure(town)['quests']]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize('town', TOWNS)
def test_a_towns_finds_name_only_its_own_items(town):
    tables = world_data.read('finds', town)['containers']
    for spec in tables.values():
        for entry in spec['table']:
            assert 'item' not in entry or inventory.item(town, entry['item']), (town, entry)
    assert finds.container(town, 'I search the chest')


def test_a_town_reached_mid_campaign_begins_its_quests_once(client, app):
    client.put('/api/story/scene', json={'city_id': 'the-concourse', 'place_id': 'the-plaza'})
    client.delete('/api/story')
    started = client.post('/api/story/start', json={'persona': ASH, 'stats': STATS})
    assert started.status_code == 200, started.text
    with app.state.database.connect(write=True) as connection:
        assert {quest['id'] for quest in quests.rows(connection, 'open')} >= {'the-name-off-the-roll'}
        from dungeon import story
        story.place_scene(connection, 'hollin', 'the-green', 'now')
        patch = next(quest for quest in quests.rows(connection, 'open') if quest['id'] == 'the-patch-before-the-cold')
        assert patch['title'] == 'The patch before the cold' and patch['known'] and patch['due_at']
        quests.end(connection, 'the-patch-before-the-cold', 'failed', 'Too late.')
        story.place_scene(connection, 'hollin', 'the-mill', 'now')
        assert 'the-patch-before-the-cold' not in {quest['id'] for quest in quests.rows(connection, 'open')}


def test_the_babel_and_havenbrooke_packages_carry_their_towns_adventures(tmp_path):
    for world, town in (('babel', 'hollin'), ('havenbrooke', 'haven')):
        contents = packages.read(packages.installed(tmp_path, world))
        assert ('adventures', town) in contents['engine'] and ('finds', town) in contents['engine']
