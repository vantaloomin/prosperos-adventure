"""The 5E battle map (dungeon/battlemap.py): the range bands drawn on five-foot squares."""
from test_combat import ok
from test_combat5e import fighter
from test_rulesets import start
from test_table import ASH, STATS

from dungeon import battlemap, combat


def foe(name, zone, **more):
    return {'id': name, 'name': name, 'vitality': 10, 'resolve': 100, 'weapon': 0, 'wound': 0, 'zone': zone,
            'broken': False} | more


def test_each_foe_stands_in_its_own_direction_at_its_bands_distance():
    assert [battlemap.square(index, zone) for index, zone in enumerate(('engaged', 'near', 'far'))] == \
        [(0, -1), (4, -4), (-9, -9)]
    assert battlemap.feet(4, -4) == 20 and battlemap.feet(-9, -9) == 45
    # A ninth foe stands a square further out than the first.
    assert battlemap.square(8, 'engaged') == (0, -2)
    state = {'foes': [foe('a', 'engaged'), foe('b', 'near'), foe('c', 'engaged', wound=5)], 'area': 'the stairs'}
    drawn = battlemap.drawn(state, state['foes'][:2], [{'name': 'Corin', 'state': 'hurt'}])
    assert drawn['area'] == 'the stairs' and drawn['square_feet'] == 5
    assert [(item['name'], item['feet'], item['down']) for item in drawn['foes']] == \
        [('a', 5, False), ('b', 20, False), ('c', 5, True)]
    assert drawn['allies'] == [{'name': 'Corin', 'x': 0, 'y': 1, 'down': False}]


def test_a_5e_fight_shows_its_map_and_the_narrator_hears_the_feet(client, app):
    fighter(client)
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, {'round': 1, 'wants': 'kill', 'foes': [
            foe('the bandit', 'engaged', hp=11, max_hp=11), foe('the archer', 'far', hp=11, max_hp=11)]})
        assert combat.prompt_text(['A round.'], connection).endswith(
            'On the grid: the bandit 5 ft; the archer 45 ft.')
    grid = ok(client.get('/api/story'))['fight']['fight']['grid']
    assert [(item['name'], item['x'], item['y']) for item in grid['foes']] == \
        [('the bandit', 0, -1), ('the archer', 9, -9)]


def test_other_rulesets_have_no_map(client, app):
    ok(start(client, persona=ASH, stats=STATS))
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, {'round': 1, 'wants': 'kill', 'foes': [foe('the bandit', 'engaged')]})
        assert 'On the grid' not in combat.prompt_text(['A round.'], connection)
    assert ok(client.get('/api/story'))['fight']['fight']['grid'] is None
