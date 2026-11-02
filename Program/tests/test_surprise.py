"""Surprise and ambushes (dungeon/combat.py surprise): stealth against awareness as a fight begins."""
from conftest import Chunk, tell

from dungeon import combat


class Dice:
    """d100s in the order given, then 50s; every other die rolls lowest."""

    def __init__(self, *naturals):
        self.naturals = list(naturals)

    def randint(self, low, high):
        return (self.naturals.pop(0) if self.naturals else 50) if (low, high) == (1, 100) else low

    def choice(self, items):
        return items[0]


def foe(**values):
    return {'id': 'f', 'name': 'the bandit', 'vitality': 10, 'resolve': 10, 'weapon': 0, 'wound': 0,
            'zone': 'engaged', 'broken': False} | values


def roll(action, band, stat='Vitality'):
    return {'action': action, 'band': band, 'stat': stat}


def test_a_stealthy_attack_takes_the_foe_unawares(app, client):
    client.delete('/api/story')
    spec = {'name': 'the bandit', 'vitality': 10, 'resolve': 10}
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'rob', 'foes': [foe()], 'initiative': 'player'}
        # Not by stealth: nothing is rolled.
        assert combat.surprise(connection, dict(state), spec, [roll('I stab the bandit', 'success')], False,
                               Dice()) == state
        sneaking = [roll('I creep up behind the bandit and stab him', 'success')]
        caught = combat.surprise(connection, dict(state), spec, sneaking, False, Dice(99, 10))
        assert caught['surprised'] == 'foes' and caught['cards'][0]['action'] == 'Sneak up unseen'
        heard = combat.surprise(connection, dict(state), spec, sneaking, False, Dice(10, 99))
        assert heard['surprised'] is None and len(heard['cards']) == 1


def test_a_danger_can_ambush_the_character(app, client):
    client.delete('/api/story')
    spec = {'name': 'the bandit', 'vitality': 10, 'resolve': 10}
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'rob', 'foes': [foe(zone='near')], 'initiative': 'foe'}
        caught = combat.surprise(connection, dict(state), spec, [], True, Dice(10, 99))
        assert caught['surprised'] == 'player' and caught['foes'][0]['zone'] == 'engaged'
        assert caught['cards'][0]['action'] == 'Spot the ambush'
        spotted = combat.surprise(connection, {**state, 'foes': [foe(zone='near')]}, spec, [], True, Dice(99, 10))
        assert spotted['surprised'] is None and spotted['foes'][0]['zone'] == 'near'


def test_the_side_taken_unawares_loses_the_first_round(app, client):
    client.delete('/api/story')
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'rob', 'foes': [foe(vitality=20)], 'surprised': 'foes'}
        state, lines, ending = combat.play_round(connection, state, [roll('I stab the bandit', 'success')],
                                                 [{'item_id': 'knife'}], Dice(90))
        assert state['foes'][0]['wound'] == 2 and lines[-1] == 'Taken unawares, the foes do nothing this round.'
        assert combat.condition(connection)['level'] == 0 and ending == ''
        # The second round is an ordinary one.
        _, lines, _ = combat.play_round(connection, state, [], [], Dice(10))
        assert 'unawares' not in ' '.join(lines)

        ambushed = {'round': 0, 'wants': 'rob', 'foes': [foe()], 'surprised': 'player'}
        ambushed, lines, _ = combat.play_round(connection, ambushed, [roll('I stab the bandit', 'success')],
                                               [{'item_id': 'knife'}], Dice(90))
        assert ambushed['foes'][0]['wound'] == 0 and lines[0].startswith('Taken unawares, the player')


def test_a_fight_on_a_plan_plays_on_to_a_turning_point(client, connected, provider, app):
    client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'})
    client.delete('/api/story')
    client.post('/api/story/start', json={'premade_id': 'agna-holt'})
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, {'round': 1, 'wants': 'rob', 'foes': combat.foes_from(
            {'name': 'bandit', 'vitality': 1, 'resolve': 30, 'weapon': 0}, 'engaged')})
    app.state.dice = Dice(*[60] * 40)
    provider.replies = [[Chunk('Steel on steel.'), Chunk('', 'stop')]]
    tell(client, 'I cut at the bandit with my sword and fight on until he is down.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert "- Round 3, fighting on the player's plan:\n- The player's character hits bandit: now down." in narrator
    assert "The fight on the player's plan stops here: the fight is over." in narrator
    with app.state.database.connect() as connection:
        actions = [row['action'] for row in connection.execute('SELECT action FROM story_rolls ORDER BY position')]
    assert actions[-1] == 'I cut at the bandit with my sword and fight on until he is down.' and len(actions) == 2


def test_a_plan_stops_at_once_when_it_makes_no_sense(app, client):
    client.delete('/api/story')
    with app.state.database.connect(write=True) as connection:
        state = {'round': 1, 'wants': 'rob', 'foes': [foe()]}
        lines = []
        after, ending = combat.fight_on(connection, 'm', state, 'I sing to them until they give up', [],
                                        Dice(), '', (combat.mark(connection, state), ''), lines)
        assert after['round'] == 1 and ending == '' and 'the plan no longer makes sense' in lines[-1]
        assert combat.fight_on(connection, 'm', state, '', [], Dice(), '', ((0, 0, 0), ''), lines) == (state, '')
