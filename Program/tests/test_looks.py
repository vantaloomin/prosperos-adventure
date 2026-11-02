"""What someone looks like: one sheet, the same every time, that keeps their pictures one person."""
import re
from collections import Counter

from dungeon.world import catalog, dating, looks, townsfolk


def test_a_roll_never_pairs_a_height_with_an_implausible_weight():
    low, high = looks.bank()['bmi_limits']
    seen = Counter()
    for n in range(1500):
        definition = {'identity': ['She is a nurse.', 'He fixes bikes.', 'A painter.'][n % 3]}
        sheet = looks.for_companion(f'companion-{n}', definition)
        bmi = sheet['weight_kg'] / (sheet['height_cm'] / 100) ** 2
        assert low - 0.5 <= bmi <= high + 0.5, sheet
        assert 135 <= sheet['height_cm'] <= 215 and sheet['age'] >= 18
        seen[sheet['face']] += 1
        if sheet['build'] == 'tall and lean':
            assert sheet['height_cm'] >= dating.HEIGHT[dating.gender(looks.stand_in(definition, f'companion-{n}'))][0] + 5
    assert len(seen) == len(looks.bank()['face'])


def test_the_same_companion_always_gets_the_same_sheet_and_what_the_user_set_wins():
    definition = {'identity': '34. A Korean-American nurse; she works nights.'}
    first = looks.for_companion('abc', definition)
    assert first == looks.for_companion('abc', definition) and first['age'] == 34
    assert looks.heritage_of(definition) == 'korea' and looks.pronouns_of(definition) == 'she/her'
    mine = looks.for_companion('abc', {**definition, 'looks': {'height_cm': 150, 'face': 'heart-shaped', 'nose': ''}})
    assert mine['height_cm'] == 150 and mine['face'] == 'heart-shaped' and mine['nose'] == first['nose']


def test_what_the_appearance_already_says_is_not_drawn_again():
    sheet = looks.automatic({'appearance': 'Long red hair, green eyes, freckles. Tall and broad-shouldered.'}, 'x')
    assert sheet['hair'] == sheet['eyes'] == sheet['eye_shape'] == sheet['feature'] == sheet['build'] == ''
    assert sheet['height_cm'] is None and sheet['skin'] and sheet['face']
    words = looks.picture(sheet, 'she')
    assert words.startswith('A woman in her ') and 'hair' not in words and 'eyes' not in words


def test_a_townsperson_keeps_their_matchlight_looks():
    data = catalog.city('baltimore')
    place = next(place for place in data['places'] if townsfolk.count(data, place))
    sheet = townsfolk.person(data, place, 0)
    found, card = looks.for_sheet(sheet, data), dating.looks(sheet, data)
    assert found['height_cm'] == card['height_cm'] and found['hair'] == card['hair'] and found['build'] == card['build']
    assert found == looks.for_sheet(sheet, data) and found['age'] == sheet['age']


def test_a_drawn_build_or_weight_follows_what_the_user_set():
    she = {'identity': 'She is a nurse.'}
    heavy = looks.for_companion('abc', {**she, 'looks': {'height_cm': 160, 'weight_kg': 110}})
    light = looks.for_companion('abc', {**she, 'looks': {'height_cm': 147, 'weight_kg': 41}})
    assert heavy['build'] == 'full-figured' and light['build'] == 'slim'
    slim = looks.for_companion('abc', {**she, 'looks': {'height_cm': 165, 'build': 'slim'}})
    assert 18 <= slim['weight_kg'] / 1.65 ** 2 <= 21
    # What the user set stays as they set it, even when it is unusual.
    mine = looks.for_companion('abc', {**she, 'looks': {'weight_kg': 120, 'build': 'slim'}})
    assert mine['weight_kg'] == 120 and mine['build'] == 'slim'


def test_someone_whose_identity_says_they_are_under_18_is_never_given_an_adult_age():
    sheet = looks.for_companion('c1', {'identity': 'June Park, 16. She works weekends at a bakery.'})
    assert sheet['age'] is None
    assert 'years old' not in looks.text(sheet) and 'twenties' not in looks.picture(sheet, 'she')
    assert looks.for_companion('c1', {'identity': 'June Park, 26. She runs a bakery.'})['age'] == 26


def test_a_height_written_in_words_counts_as_said():
    for text in ("She's five-foot-six with a runner's legs.", 'A 6 foot 2 frame.', 'A six-footer.'):
        assert 'height_cm' in looks.covered(text)


def test_old_injuries_are_pictured_as_they_look_now():
    """A picture model draws "broken" and "healed" as the injury itself, so pictures say what the camera sees."""
    assert looks.seen('a broken nose that healed a little crooked') == 'a nose that bends slightly to one side'
    assert looks.seen('her once-broken nose') == 'her nose that bends slightly to one side'
    assert looks.seen('a scar through one eyebrow') == 'a thin bare notch through one eyebrow'
    assert looks.seen('a healed scar across his cheek') == 'a faint pale mark across his cheek'
    assert looks.seen('burn scars on his forearms') == 'patches of smoother, paler skin on his forearms'
    for detail in dating.DETAILS:
        assert not re.search(r'broken|healed|scar|crooked|gap-tooth', looks.seen(detail))
    drawn = looks.picture({'nose': 'a straight nose', 'feature': 'a broken nose that healed a little crooked'}, 'he')
    assert drawn == 'A man with a nose that bends slightly to one side.'


def test_an_age_spelled_out_is_read_like_digits():
    def age(text):
        return looks.age_of({'identity': text}, 'seed')
    assert age('Jordan is fifty-nine') == 59
    assert age('Forty-two. A night nurse.') == 42
    assert age('a thirty-one-year-old baker') == 31
    assert age("She's nineteen, and loud") == 19
    # Digits still come first, decades stay as they were, and a count of things is no age.
    assert age('34, and her brother is fifty') == 34
    assert age('in her thirties') == 35
    assert age('has fifty-nine cats') == age('has cats')
