"""Fixes from the party-and-rechecks playtest: falling back always rolls mid-fight, and one round of blows from
bare hands or a poor weapon no longer takes a character on their feet to Dying."""
from test_combat import foe
from test_lies import begin

from dungeon import combat, referee


class High:
    """Every d100 lands a critical hit for the foe."""

    def randint(self, low, high):
        return 100 if high == 100 else high

    def random(self):
        return 0.99

    def choice(self, items):
        return items[0]


def test_falling_back_mid_fight_always_rolls():
    text = 'Two drunks come at me with knives. I fall back to the stairs.'
    rolled = referee.armed(text, [], 'the drunks')
    assert rolled == [{'action': 'I fall back to the stairs', 'roll': True, 'stat': 'Vitality',
                       'difficulty': 'normal', 'said': True}]
    # Outside a fight, or when the Referee already rolled it, nothing is added.
    assert referee.armed(text, [], None) == []
    kept = [{'action': 'I fall back to the stairs', 'roll': True, 'stat': 'Luck', 'difficulty': 'normal'}]
    assert referee.armed(text, kept, 'the drunks') == kept


def test_bare_hands_hit_at_most_two_levels():
    assert combat.blow('critical_success', 0) == 2 and combat.blow('success_cost', 0) == 1
    assert combat.blow('critical_success', 1) == 4


def test_one_round_takes_a_standing_character_down_not_dying(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 2)
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(weapon=1, resolve=99), foe(id='g', name='the archer',
                                                                                     weapon=1, resolve=99)]}
        state, lines, ending = combat.play_round(connection, state, [], [], High())
        assert combat.condition(connection)['level'] == combat.DOWN and ending == ''
        # Already down, the next blow can kill.
        state, lines, ending = combat.play_round(connection, state, [], [], High())
        assert ending == 'dying'
