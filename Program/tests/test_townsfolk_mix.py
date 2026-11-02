"""Worlds > Townsfolk mix (dungeon/world/mix.py, dungeon/townsfolk_mix.py): the shares the townsfolk
rolls use, shown, and a new world made with changed ones."""
from statistics import mean

import pytest

from dungeon.world import catalog, dating, generators, intimacy, mix, townsfolk


@pytest.fixture(autouse=True)
def built_in_mix():
    yield
    mix._active = dict(mix.DEFAULTS)


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def residents(count=600):
    data = catalog.city('baltimore')
    hood = data['neighborhoods'][0]['id']
    total = townsfolk.resident_count(data, hood)
    sheets = [townsfolk.resident(data, hood, index) for index in range(total)]
    more = [townsfolk.resident(data, other['id'], index) for other in data['neighborhoods'][1:]
            for index in range(townsfolk.resident_count(data, other['id']))]
    return data, (sheets + more)[:count]


def test_the_built_in_mix_is_what_the_rolls_always_used():
    assert mix.current() == mix.DEFAULTS and mix.fingerprint() == ''
    assert mix.pronoun_weights(True) == [47, 47, 6] and mix.pronoun_weights(False) == [47, 47, 2]
    assert all(dating.rates(band[0]) == band for band in dating.ORIENTATION_RATES)
    assert mix.height_mean('woman', 162) == 162 and mix.beard_share() == 0.35
    # The slider values match the built-in rates across the town's ages.
    assert round(mix.built_in_share('gay'), 1) == mix.DEFAULTS['gay']
    assert round(mix.built_in_share('bisexual'), 1) == mix.DEFAULTS['bisexual']


def test_a_changed_mix_changes_who_the_town_is():
    data, people = residents()
    before = [dating.details(sheet, data) for sheet in people]
    with mix.using({'gay': 30, 'bisexual': 30, 'height_man': 190, 'beard': 100, 'slender': 0, 'middle': 0,
                    'heavier': 100}):
        after = [dating.details(sheet, data) for sheet in people]
    queer = {'gay', 'lesbian', 'bisexual'}
    assert sum(item['orientation'] in queer for item in after) > 4 * sum(item['orientation'] in queer for item in before)
    men = [item['looks'] for item in after if item['gender'] == 'man']
    assert mean(looks['height_cm'] for looks in men) > 185 and all(looks.get('beard') for looks in men)
    heavier = set(dating.BUILD_GROUPS['heavier']) | {'athletic'}  # Sporty people stay athletic.
    assert all(item['looks']['build'] in heavier for item in after)


def test_the_gender_mix_goes_through_every_name_drawn():
    data = catalog.city('baltimore')
    with mix.using({'nonbinary': 0, 'women': 100}):
        drawn = {generators.name(data, seed=f'mix-{n}')['pronouns'] for n in range(200)}
    assert drawn == {'she/her'}


def test_ages_and_the_adult_check_never_follow_the_mix():
    data, people = residents(100)
    with mix.using({'bolder': 2, 'drive': 2, 'gay': 40, 'nonbinary': 40}):
        assert [sheet['age'] for sheet in residents(100)[1]] == [sheet['age'] for sheet in people]
        assert intimacy.roll('someone', 17, 'woman') is None
        bold = [intimacy.roll(f'p{n}', 30, 'woman')['level'] for n in range(300)]
    plain = [intimacy.roll(f'p{n}', 30, 'woman')['level'] for n in range(300)]
    assert bold.count('wild') > plain.count('wild')
