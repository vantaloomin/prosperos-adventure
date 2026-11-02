"""Allies fight beside the character on their own, and foes split their blows (dungeon/allies.py)."""
from test_bonds import met
from test_combat import foe, roll
from test_lies import begin

from dungeon import allies, bonds, combat, party, record

NOW = '2026-10-01T12:00:00Z'
HESK = {'sheet': {'key': 'hesk', 'full': 'Hesk Aldane', 'name': 'Hesk', 'role': 'woodcutter', 'occupation': 'woodcutter'}}


class Dice:
    """d100 shows `natural`; `chance` is every random() (under 0.5: a foe turns on an ally and hits)."""

    def __init__(self, natural, chance):
        self.natural, self.chance = natural, chance

    def randint(self, low, high):
        return self.natural if high == 100 else high

    def random(self):
        return self.chance

    def randrange(self, count):
        return 0

    def choice(self, items):
        return items[0]


def companion(connection):
    met(connection)
    bonds.forge(connection, 'hesk', 'Hesk Aldane', 'sworn', NOW)
    party.turn(connection, 'join', {'people': [HESK], 'known': party.story_people.known(connection),
                                    'city': {'id': 'kingswood'}, 'local_time': '2026-10-01T12:00'},
               'Come with me.', '2026-10-01', NOW)


def test_skill_follows_their_work():
    assert allies.skill({'occupation': 'woodcutter'}) == allies.FIGHTER
    assert allies.skill({'occupation': 'baker', 'role': 'baker'}) == allies.COMMONER


def test_a_companion_fights_beside_the_character_and_draws_blows(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        companion(connection)
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(weapon=1), foe(id='g', name='the lookout')]}
        # The character misses; Hesk lands a hit (Prospero rolls high); both foes turn on Hesk and hit.
        state, lines, ending = combat.play_round(connection, state, [roll('I swing at the bandit', 'failure')], [],
                                                 Dice(95, 0.1))
        assert any(line.startswith('Hesk Aldane, fighting beside the character, hits the bandit') for line in lines)
        assert state['foes'][0]['wound'] >= 2
        assert 'The lookout turns on Hesk Aldane and hits them: they go down, out of the fight.' in lines
        # Nobody was free to hit the character.
        assert combat.condition(connection)['level'] == 0 and ending == ''
        assert allies.view(state) == [{'name': 'Hesk Aldane', 'state': 'down'}]
        # Down, they no longer fight; the foes come for the character again.
        state, lines, _ = combat.play_round(connection, state, [], [], Dice(95, 0.1))
        assert not any('Hesk' in line for line in lines) and combat.condition(connection)['level'] > 0
        allies.aftermath(connection, state, NOW)
        assert any('badly hurt fighting beside' in row['text'] for row in record.entries(connection))


def test_without_a_party_nothing_changes(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'kill', 'foes': [foe()]}
        state, lines, _ = combat.play_round(connection, state, [], [], Dice(95, 0.1))
        assert state['allies'] == [] and lines == ["The bandit hits the player's character: now hurt."]
