"""Foes fight for what they want (dungeon/combat.py terms, the robbers' demand, captors who take the character whole)."""
from conftest import Chunk, tell

from dungeon import combat, inventory

NOW = '2026-10-01T12:00:00Z'


class Dice:
    """Every d100 shows `natural`; every other die rolls lowest."""

    def __init__(self, natural):
        self.natural = natural

    def randint(self, low, high):
        return self.natural if (low, high) == (1, 100) else low

    def choice(self, items):
        return items[0]


def foe(**values):
    return {'id': 'f', 'name': 'the bandit', 'vitality': 10, 'resolve': 30, 'weapon': 0, 'wound': 0,
            'zone': 'engaged', 'broken': False} | values


def begin(client):
    client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'})
    client.delete('/api/story')
    client.post('/api/story/start', json={'premade_id': 'agna-holt'})


def test_a_line_that_gives_in_is_met_by_what_the_foes_want(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        assert inventory.purse(connection) > 0
        robbers = {'round': 1, 'wants': 'rob', 'foes': [foe()]}
        assert combat.terms(connection, robbers, 'I swing at him again.', NOW) == ([], False)
        lines, over = combat.terms(connection, robbers, 'I hand over my purse.', NOW)
        assert over and 'hands over their purse' in lines[0] and inventory.purse(connection) == 0

        captors = {'round': 1, 'wants': 'capture', 'foes': [foe(name='the warden')]}
        lines, over = combat.terms(connection, captors, 'I drop my sword and surrender.', NOW)
        assert over and 'takes them prisoner' in lines[0]
        assert connection.execute('SELECT captors FROM story_wounds').fetchone()[0] == 'the warden'

        brawl = {'round': 1, 'wants': 'drive_off', 'foes': [foe(name='the logger')]}
        assert combat.terms(connection, brawl, 'I back off, hands up.', NOW)[1]
        killers = {'round': 1, 'wants': 'kill', 'foes': [foe(name='the gnoll')]}
        lines, over = combat.terms(connection, killers, 'I beg for mercy.', NOW)
        assert not over and lines == ["The player's character tries to give in; the gnoll gives no quarter."]


def test_robbers_demand_the_purse_and_captors_take_the_character_whole(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        robbers = {'round': 1, 'wants': 'rob', 'foes': [foe(weapon=1)]}
        _, lines, ending = combat.play_round(connection, robbers, [], [], Dice(80))
        assert ending == '' and lines[-1] == ("The bandit demands the character's purse: hand it over and the robbers "
                                              'go.')
        # Only once: the next blow is just a blow.
        _, lines, _ = combat.play_round(connection, robbers, [], [], Dice(80))
        assert 'demands' not in ' '.join(lines)

        combat.set_condition(connection, 3)
        captors = {'round': 1, 'wants': 'capture', 'foes': [foe(name='the warden', weapon=1)]}
        _, lines, ending = combat.play_round(connection, captors, [], [], Dice(99))
        assert combat.condition(connection)['level'] == combat.DOWN and ending == 'dying'
        lines = []
        combat.fall(connection, captors, Dice(1), NOW, lines, [])
        assert lines[-1].startswith("The player's character is beaten down.")


def test_paying_robbers_off_in_the_story_ends_the_fight(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, {'round': 1, 'wants': 'rob', 'foes': [foe()]})
    provider.replies = [[Chunk('He weighs the purse.'), Chunk('', 'stop')]]
    tell(client, 'I toss him my purse and back away.', 'story-0001')
    assert 'hands over their purse' in provider.requests[-1]['system']
    with app.state.database.connect() as connection:
        assert combat.fight(connection) is None and inventory.purse(connection) == 0
