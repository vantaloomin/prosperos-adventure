"""World Life Cards (dungeon/life/cards.py): every shipped deck checks clean, and the filters do what the
requirements ask of them ("Intensity and tone", "Off-page beats")."""
import copy

import pytest

from dungeon.life import cards
from dungeon.narration import prose

OFF = dict.fromkeys(cards.CATEGORIES, 0)
TOP = cards.PRESETS['unflinching']


@pytest.mark.parametrize('world', cards.worlds())
def test_every_shipped_deck_checks_clean(world):
    assert cards.problems(cards.deck(world)) == []


@pytest.mark.parametrize('world', cards.worlds())
def test_card_text_passes_the_narrator_prose_checks(world):
    for item in cards.cards(world):
        for key in cards.TEXT:
            if item.get(key):
                found = [finding.text for finding in prose.check(item[key]) if finding.severity != prose.WATCH]
                assert found == [], (item['id'], key, found)


@pytest.mark.parametrize('world', cards.worlds())
@pytest.mark.parametrize('scene', cards.SCENES)
def test_the_lowest_settings_keep_every_scene_drawable_and_never_only_kind(world, scene):
    pool = cards.eligible(world, scene, 0, OFF, set(), set())
    assert {'good', 'bad'} <= {item['tone'] for item in pool}


@pytest.mark.parametrize('world', cards.worlds())
def test_raising_drama_or_intensity_only_adds_cards(world):
    for scene in cards.SCENES:
        sizes = [len(cards.eligible(world, scene, level, TOP, set(cards.NEEDS), set())) for level in range(4)]
        assert sizes == sorted(sizes)
        assert cards.deck(world)['chance'][scene] == sorted(cards.deck(world)['chance'][scene])
        quiet = cards.eligible(world, scene, 3, OFF, set(), set())
        assert len(quiet) < len(cards.eligible(world, scene, 3, TOP, set(), set()))


def test_intensity_filters_a_card_out_below_its_level_and_a_missing_category_counts_as_top():
    item = {'intensity': {'violence': 2}}
    assert not cards.allowed(item, {'violence': 1})
    assert cards.allowed(item, {'violence': 2})
    assert cards.allowed(item, {})


def test_needs_and_regions_gate_cards():
    has_bond = {item['id'] for item in cards.eligible('vallarith', 'town', 3, TOP, {'bond'}, set())}
    without = {item['id'] for item in cards.eligible('vallarith', 'town', 3, TOP, set(), set())}
    assert 'bond-confession' in has_bond - without
    assert 'harvest-fair' in {item['id'] for item in cards.eligible('vallarith', 'town', 3, TOP, set(), set(), 'cyrel')}
    assert 'harvest-fair' not in without


def test_a_draw_is_seeded_skips_recent_cards_and_flags_veiled_topics():
    first = cards.draw('vallarith', 'beat', 'day-9', 3, TOP, set(), set(), forced=True)
    assert first == cards.draw('vallarith', 'beat', 'day-9', 3, TOP, set(), set(), forced=True)
    assert first['card'] and 0 < first['odds'] <= 1
    again = cards.draw('vallarith', 'beat', 'day-9', 3, TOP, set(), {first['card']['id']}, forced=True)
    assert again['card']['id'] != first['card']['id']
    slavery = cards.card('vallarith', 'beat-taken')
    assert cards.veiled(slavery, {'slavery'}) and not cards.veiled(slavery, {'torture'})


def test_quiet_days_draw_less_often_than_merciless_ones():
    def hits(level):
        return sum(cards.draw('vallarith', 'town', f'day-{day}', level, TOP, set(), set())['card'] is not None
                   for day in range(200))
    assert hits(0) < hits(3)


def test_table_rows_join_their_scene_with_the_tables_weight():
    deck = cards.deck('vallarith')
    road = [item for item in cards.cards('vallarith') if item['source'] != 'deck' and 'road' in item['scenes']]
    assert abs(sum(item['weight'] for item in road) - deck['tables_weight']) <= len(road)
    assert {item['source'] for item in road} == {'Travellers', 'Hazards', 'Signs', 'Threats', 'Finds'}


def test_the_checker_catches_broken_cards_and_tables():
    deck = copy.deepcopy(cards.deck('vallarith'))
    deck['cards'][0]['truth'] += ' {stranger}'
    deck['cards'][1]['effects'].append({'kind': 'market', 'goods': 'gold', 'shift': 5, 'days': 1})
    deck['tables']['hazards']['rows'][1]['low'] = 3
    deck['cards'].append(copy.deepcopy(deck['cards'][2]))
    found = '\n'.join(cards.problems(deck))
    for expected in ('unknown placeholder {stranger}', "bad goods: 'gold'", 'gap or overlap', 'used twice'):
        assert expected in found
