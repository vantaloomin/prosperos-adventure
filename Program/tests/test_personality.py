"""Personality sliders (dungeon/world/personality.py): rolled for everyone, the user's words and changes win."""
import json
import re
from collections import Counter

from test_perception import GENDERED

from dungeon.world import catalog, perception, personality, townsfolk

TRAIT_NAMES = re.compile(r'\b(openness|conscientious\w*|extravers\w*|extrovers\w*|agreeabl\w*|neurotic\w*)\b', re.I)


def test_the_words_are_plain_and_every_bank_id_they_name_exists():
    bank = personality.bank()
    assert [trait['key'] for trait in bank['traits']] == ['social', 'warmth', 'order', 'curiosity', 'stress']
    for trait in bank['traits']:
        assert len(trait['shows']) == len(trait['model']) == 3 and trait['model'][1] == ''
        for text in [trait['name'], trait['low'], trait['high'], *trait['shows'], *trait['model']]:
            assert not TRAIT_NAMES.search(text) and not GENDERED.search(text), text
        assert 'anxious' not in json.dumps(trait['shows']) and 'neurotic' not in json.dumps(trait['shows'])
    ids = perception.ids()
    for facet, table in bank['implies'].items():
        assert set(table) <= set(ids[facet]), facet
        for poles in table.values():
            assert set(poles) <= set(personality.keys()) and set(poles.values()) <= {'low', 'high'}


def test_everyone_is_rolled_with_at_least_two_traits_away_from_the_middle():
    rolled = [personality.levels_of(personality.settle({}, f'seed-{n}')) for n in range(3000)]
    assert all(sum(level != 1 for level in levels.values()) >= 2 for levels in rolled)
    # Each stop turns up for every trait, so people around town differ.
    for key in personality.keys():
        counts = Counter(levels[key] for levels in rolled)
        assert all(counts[level] > 500 for level in (0, 1, 2)), (key, counts)
    assert personality.settle({}, 'same') == personality.settle({}, 'same')


def test_the_characters_own_words_settle_a_slider_and_the_roll_fills_the_rest():
    found = personality.from_words('A kind kindergarten teacher, kind of shy, never late, not lazy at all.')
    assert found == {'warmth': 2, 'social': 0}
    assert personality.from_words('Outgoing at work, but a quiet homebody at weekends.') == {'social': 1}
    sliders = personality.settle({'personality': 'Calm, and always late.'}, 'seed')
    assert sliders['stress'] == {'level': 0, 'source': 'idea'} and sliders['order'] == {'level': 0, 'source': 'idea'}
    assert {value['source'] for key, value in sliders.items() if key not in ('stress', 'order')} == {'rolled'}


def test_roll_again_and_a_type_only_change_what_the_user_and_their_idea_left_open():
    start = personality.settle({'personality': 'Shy.'}, 'seed')
    start['stress'] = {'level': 2, 'source': 'you'}
    for attempt in range(20):
        again = personality.reroll(start, f'seed:{attempt}')
        assert again['social'] == start['social'] and again['stress'] == start['stress']
        assert sum(value['level'] != 1 for value in again.values()) >= 2
    assert len({json.dumps(personality.reroll(start, f'seed:{n}')) for n in range(20)}) > 5
    typed = personality.from_type('enfj', start)
    assert typed['social'] == {'level': 0, 'source': 'idea'}  # Their idea says shy; the type leaves it.
    assert typed['curiosity'] == typed['warmth'] == typed['order'] == {'level': 2, 'source': 'you'}
    assert typed['stress'] == start['stress']
    assert personality.type_of(personality.levels_of(typed)) == 'INFJ'
    assert personality.type_of({'social': 1, 'curiosity': 2, 'warmth': 2, 'order': 2}) is None


def test_words_that_agree_with_a_roll_leave_it_rolled_and_words_that_differ_win():
    saved = {key: {'level': 2, 'source': 'rolled'} for key in personality.keys()}
    same = personality.settle({'personality': 'Outgoing.', 'personality_sliders': saved}, 'seed')
    assert same['social'] == {'level': 2, 'source': 'rolled'}
    other = personality.settle({'personality': 'Shy.', 'personality_sliders': saved}, 'seed')
    assert other['social'] == {'level': 0, 'source': 'idea'}
    mine = {**saved, 'social': {'level': 2, 'source': 'you'}}
    assert personality.settle({'personality': 'Shy.', 'personality_sliders': mine}, 'seed')['social']['source'] == 'you'


def test_the_model_reads_behaviour_only_and_nothing_for_the_middle():
    levels = {'social': 2, 'warmth': 1, 'order': 0, 'curiosity': 1, 'stress': 1}
    lines = personality.behaviour(levels)
    assert len(lines) == 2 and lines[0].startswith('Starts conversations') and lines[1].startswith('Runs late')
    assert personality.chips(levels) == ['Outgoing', 'Goes with the flow']
    assert personality.behaviour(dict.fromkeys(personality.keys(), 1)) == []


def test_perception_picks_suit_the_sliders():
    organized = {'order': 2}
    assert not personality.fits('tell', 'always-late', organized) and personality.fits('tell', 'always-early', organized)
    assert personality.fits('tell', 'always-late', {'order': 1})
    menu = perception.menu(organized)
    assert 'always-early' in menu and 'always-late' not in menu and 'always-late' in perception.menu()
    for n in range(200):
        definition = {'name': 'Bo', 'personality_sliders': {'order': {'level': 2, 'source': 'you'}}}
        picks = perception.automatic(definition, f'seed-{n}')['picks']
        assert all(personality.fits(facet, picks[facet], organized) for facet in ('tell', 'flaw', 'self_story'))


def test_townsfolk_sliders_follow_their_sheet_and_their_habits_fit():
    data = catalog.city('baltimore')
    checked = 0
    for place in data['places'][:60]:
        for sheet in townsfolk.at_place(data, place['id']):
            sliders = personality.for_sheet(townsfolk.drawn(sheet), sheet)
            levels = personality.levels_of(sliders)
            for key, pole in personality.sheet_words(sheet).items():
                assert levels[key] == pole
            picks = perception.for_sheet(data, sheet)['picks']
            checked += personality.fits('tell', picks['tell'], levels)
    assert checked > 100
    shy = {'temperament': 'shy', 'flaw': 'messy', 'key': 'k'}
    assert personality.sheet_words(shy) == {'social': 0, 'order': 0}
    assert personality.sheet_words({'temperament': 'cheerful', 'flaw': 'worrier'}) == {'stress': 1}
