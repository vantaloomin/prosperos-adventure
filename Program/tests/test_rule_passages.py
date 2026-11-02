"""Rule passages (dungeon/rules/passages.py): the few lines of rule text that fit what the turn resolved, for the
narrator to describe the result by; never a change to it."""
from itertools import cycle

from conftest import tell
from test_ironsworn import made
from test_rulesets import reply, start
from test_travel import ok

from dungeon import record
from dungeon.narration import prompt
from dungeon.rules import passages


class WeakHit:
    """The action die shows 4, the challenge dice 2 and 9: +iron 3 beats one of them."""

    def __init__(self):
        self.tens = cycle([2, 9])

    def randint(self, low, high):
        return next(self.tens) if high == 10 else max(low, min(high, 4))


def narrated(client, provider, text: str, number: int) -> str:
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('You climb.')
    tell(client, text, f'rules-{number:04d}')
    return next(request['system'] for request in reversed(provider.requests) if '## Scene' in request['system'])


def roll(skill: str, band: str = 'success', ruleset: str = 'srd52') -> dict:
    return {'ruleset': ruleset, 'skill': skill, 'band': band}


def test_an_ironsworn_weak_hit_gets_the_moves_weak_hit_text_before_the_outcomes(client, connected, provider, app):
    ok(start(client, persona={'name': 'Kara'}, ruleset='ironsworn', ironsworn=made()))
    app.state.dice = WeakHit()
    system = narrated(client, provider, 'I climb the wall.', 1)
    assert '## Rules that apply' in system and 'Face Danger: When you attempt something risky' in system
    assert 'troublesome cost' in system and 'On a strong hit' not in system and 'On a miss' not in system
    assert system.index('## Rules that apply') < system.index('## This turn (decided by the game)')


def test_the_table_turns_rule_text_off(client, connected, provider, app):
    ok(start(client, persona={'name': 'Kara'}, ruleset='ironsworn', ironsworn=made()))
    assert ok(client.get('/api/story/table'))['rule_text'] == 'on'
    ok(client.put('/api/story/table', json={'rule_text': 'off'}))
    app.state.dice = WeakHit()
    assert '## Rules that apply' not in narrated(client, provider, 'I climb the wall.', 1)


def test_a_prospero_turn_gets_no_rule_text(client, connected, provider):
    assert '## Rules that apply' not in narrated(client, provider, 'I climb the wall and look for poison.', 1)


def test_prospero_fate_and_narrative_only_have_no_passages():
    for ruleset in ('marvel', 'fate', 'narrative'):
        assert passages.text(ruleset, [roll('Face Danger +iron vs 2 and 9', ruleset=ruleset)], 'poison traps',
                             ['The bandit is grappled.']) == ''


def test_a_condition_the_fight_names_brings_its_text():
    found = passages.text('srd52', [], 'I hold on.', ['The bandit is grappled and can barely move.'])
    assert '- Grappled: While you have the Grappled condition' in found


def test_the_rolls_pick_first_and_the_line_only_when_nothing_matched():
    by_roll = passages.text('srd52', [roll('Stealth')], 'I check the door for poison.', [])
    assert '- Stealth:' in by_roll and 'Poison' not in by_roll
    assert '- Poison:' in passages.text('srd52', [roll('Dexterity save')], 'I check the door for poison.', [])
    assert '- Blast:' in passages.text('brp', [roll('Blast 2 45%, 3 power points', ruleset='brp')], '', [])


def test_the_caps_hold_and_a_compact_model_gets_one_short_passage():
    rolls = [roll('Fireball (spell)'), roll('Fire Bolt (spell)'), roll('Stealth'), roll('Athletics')]
    fight = ['The bandit is grappled, prone and frightened.']
    full = passages.text('srd52', rolls, '', fight).split('\n')[2:]
    assert len(full) == passages.MOST and sum(len(line.split()) for line in full) <= passages.MOST_WORDS + passages.MOST
    compact = passages.text('srd52', rolls, '', fight, context_tokens=8_000).split('\n')[2:]
    assert len(compact) == 1 and len(compact[0].split()) <= passages.COMPACT_WORDS + 1


def test_a_passage_is_cut_at_a_sentence():
    assert passages.cut('One two three. Four five six. Seven.', 6) == 'One two three. Four five six.'
    assert passages.cut('One two three four five six seven.', 3) == 'One two three…'


def test_with_no_rule_text_the_prompt_is_built_as_before():
    layers = {'scene': '## Scene\nA wet road.', 'memory': '## Known\nThe reeve is away.',
              'outcomes': [{'actor': 'Kara', 'action': 'climb', 'band': 'success'}]}
    assert prompt.system('Core.', 'Craft.', **layers) == prompt.system('Core.', 'Craft.', **layers, rules='')
    with_rules = prompt.system('Core.', 'Craft.', **layers, rules=f'{passages.HEAD}\n- Stealth: Escape notice.')
    assert with_rules.index('## Scene') < with_rules.index('## Rules that apply') < with_rules.index('## This turn')
