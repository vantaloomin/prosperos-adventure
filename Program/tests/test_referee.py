"""The Referee (dungeon/referee.py): actions, stats and difficulty for each turn."""
from dungeon import referee


def test_keyword_rules_find_the_uncertain_actions():
    actions = referee.by_keywords('I order a coffee. Then I try to persuade the guard to let me in, and I sneak past.')
    assert [(action['stat'], action['said']) for action in actions] == [('Allure', True)]
    two = referee.by_keywords('I draw my knife and attack him. I run for the door.')
    assert [action['stat'] for action in two] == ['Vitality', 'Vitality']
    assert referee.by_keywords('I look around and sit down.') == []
    assert referee.by_keywords('I cast a ward over the doorway.')[0]['stat'] == 'Essence'
    talked = referee.by_keywords('I try to talk the guard into letting me through. Then I shove past him.')
    assert [(action['action'], action['stat']) for action in talked] == [
        ('I try to talk the guard into letting me through', 'Allure'), ('I shove past him', 'Vitality')]


def test_a_models_answer_keeps_only_what_is_well_formed():
    answer = ('Sure: {"actions": [{"action": "taunt the demon", "roll": true, "stat": "Allure", "difficulty": "hard"},'
              ' {"action": "wave", "roll": false}, {"action": "jump", "roll": true, "stat": "Agility"},'
              ' {"action": "attack", "roll": true, "stat": "Vitality", "difficulty": "impossible"}]}')
    assert referee.checked(answer) == [
        {'action': 'taunt the demon', 'roll': True, 'stat': 'Allure', 'difficulty': 'hard'},
        {'action': 'attack', 'roll': True, 'stat': 'Vitality', 'difficulty': 'normal'}]
    assert referee.checked('I cannot help with that.') is None
    assert referee.checked('{"actions": "none"}') is None


def test_mid_fight_a_line_that_keeps_at_the_foe_is_an_attack():
    # Playtest M4, finding 5: "I keep at him" is no Face Danger about pressing for an answer.
    assert referee.by_keywords('I keep at him.') == []
    assert referee.by_keywords('I keep at him.', 'the thug (hurt)')[0]['stat'] == 'Vitality'
    assert 'fighting the thug (hurt)' in referee.fight_note('the thug (hurt)')
