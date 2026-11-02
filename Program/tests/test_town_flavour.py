"""Townsfolk that fit their town: jobs weighted by the city's industries, titles that fit the place, legends and
rumours as hearsay, the city's own quirks and goals, casino jobs only where there is a casino, and one change of
line on a commute."""
import itertools
from collections import Counter
from datetime import date

import pytest

from dungeon.world import catalog, generators, mend, townsfolk
from dungeon.world.schema import HEARSAY_KINDS, LOCAL_COLOR_KINDS, PracticeSpot


def occupations(data: dict) -> Counter:
    return Counter(sheet['occupation'] for hood in data['neighborhoods']
                   for sheet in townsfolk.residents(data, hood['id'], named=False))


def industries(data: dict) -> set[str]:
    """Names of the careers the city itself has or its employers hire for."""
    offered = catalog.careers_for(data)
    ids = {career['id'] for career in data['careers']} | {key for item in data['employers'] for key in item['careers']}
    return {offered[key]['name'].lower() for key in ids if key in offered}


def test_most_pellmouth_residents_work_in_its_own_industries():
    data = catalog.city('pellmouth')
    counts = occupations(data)
    working = sum(count for job, count in counts.items() if job not in ('retired', ''))
    local = sum(count for job, count in counts.items() if job in industries(data))
    assert local / working > 0.7
    assert counts['quarry worker'] > counts['stockbroker'] + counts['chorus dancer']


def test_a_big_city_stays_varied():
    counts = occupations(catalog.city('baltimore'))
    working = {job: count for job, count in counts.items() if job not in ('retired', '')}
    assert len(working) >= 35 and max(working.values()) / sum(working.values()) < 0.1


def test_career_weights_favour_the_citys_own_and_bigger_employers():
    data = catalog.city('pellmouth')
    weights = generators.career_weights(data, catalog.careers_for(data))
    assert weights['quarry-worker'] > weights['fisherman'] > weights['bank-teller'] >= 1
    assert min(weights.values()) >= 1


def test_a_career_pick_is_stable_when_another_career_goes():
    data = catalog.city('baltimore')
    weights = generators.career_weights(data, catalog.careers_for(data))
    fewer = {key: value for key, value in weights.items() if key != 'software-engineer'}
    for seed in (f's{n}' for n in range(200)):
        before = generators.rank_pick(seed, 'career', weights)
        if before != 'software-engineer':
            assert generators.rank_pick(seed, 'career', fewer) == before


def test_a_companions_circle_and_new_acquaintances_work_in_the_town_too():
    data = catalog.city('pellmouth')
    people = [generators.resident(data, seed=f'p{n}', age=40) for n in range(80)]
    jobs = [person['job']['career']['name'].lower() for person in people if person['job']]
    assert sum(job in industries(data) for job in jobs) / len(jobs) > 0.6


def titles(city_id: str, place_id: str) -> list[str]:
    return [sheet['role'] for sheet in townsfolk.at_place(catalog.city(city_id), place_id) if sheet['staff']]


@pytest.mark.parametrize('city_id, place_id, title', [
    ('pellmouth', 'tarbox-drug-store', 'soda jerk'),
    ('pellmouth', 'the-college-spa', 'soda jerk'),
    ('pellmouth', 'furtados-bakery', 'baker'),
    ('pellmouth', 'gambrel-tea-room', 'waiter'),
    ('pellmouth', 'gannet-point-light', 'lighthouse keeper'),
    ('new-york-1925', 'luna-park', 'barker'),
    ('new-york-1925', 'grand-central-terminal', 'redcap'),
])
def test_period_titles_fit_the_place(city_id, place_id, title):
    assert titles(city_id, place_id)[0] == title


@pytest.mark.parametrize('place_id, title', [('larkin-pratt-dry-goods', 'floorwalker'), ('tuttles-books', 'bookseller'),
                                             ('narrows-landing-store', 'shopkeeper')])
def test_who_runs_a_shop_depends_on_the_shop(place_id, title):
    data = catalog.city('pellmouth')
    place = catalog.find(data, place_id)
    assert townsfolk.role_title(data, townsfolk.ROLES['shopping'][1], place) == title


def test_no_soda_jerks_or_floorwalkers_where_they_do_not_belong():
    data = catalog.city('pellmouth')
    place = catalog.find(data, 'furtados-bakery')
    assert townsfolk.role_title(data, townsfolk.ROLES['cafe'][0], place) != 'soda jerk'
    shop = catalog.find(data, 'tuttles-books')
    assert 'floorwalker' not in [townsfolk.role_title(data, role, shop) for role in townsfolk.ROLES['shopping']]
    roles = {townsfolk.role_title(data, role, place) for place in data['places']
             for role in townsfolk.ROLES.get(place['kind'], ())}
    assert 'gatekeeper' not in roles
    london = catalog.city('london-1895')
    assert townsfolk.role_title(london, townsfolk.ROLES['shopping'][1], catalog.find(london, 'harrods')) == 'shopwalker'
    # Modern cities keep their titles unless the place says otherwise.
    baltimore = catalog.city('baltimore')
    assert townsfolk.role_title(baltimore, townsfolk.ROLES['cafe'][0], catalog.find(baltimore, 'zekes-coffee')) == 'barista'


def test_legends_and_rumours_are_known_kinds_and_reach_prompts_as_hearsay():
    assert set(HEARSAY_KINDS) <= set(LOCAL_COLOR_KINDS)
    data = catalog.city('pellmouth')
    kinds = Counter(item['kind'] for item in data['local_color'])
    assert kinds['legend'] >= 3 and kinds['rumor'] >= 3
    told = generators.local_color(data, seed='s', kinds=['legend', 'rumor'], count=10)
    assert told and all(item['hearsay'] for item in told)
    assert not any(item['hearsay'] for item in generators.local_color(data, seed='s', kinds=['dish']))
    line = generators.color_line(next(item for item in data['local_color'] if item['kind'] == 'legend'))
    assert 'hearsay' in line and 'not confirmed' in line


def test_mending_reads_rumour_and_folklore_as_the_known_kinds():
    assert mend.COLOR_KINDS['rumour'] == 'rumor' and mend.COLOR_KINDS['folklore'] == 'legend'


def test_baker_street_alone_is_modern_london():
    assert catalog.resolve('Baker Street, London')['city'] == 'london'
    assert catalog.resolve('Victorian London')['city'] == 'london-1895'


def test_pellmouth_townsfolk_draw_the_towns_own_quirks_and_goals():
    data = catalog.city('pellmouth')
    own_quirks = {item['text'] for item in data['townsfolk']['quirks']}
    own_goals = {item['id'] for item in data['townsfolk']['goals']}
    people = [sheet for hood in data['neighborhoods'] for sheet in townsfolk.residents(data, hood['id'])]
    share = sum(sheet['quirk'] in own_quirks for sheet in people) / len(people)
    assert 0.15 < share < 0.5
    firsts = [sheet for sheet in people if sheet['goals'][0] in own_goals]
    assert firsts
    state = townsfolk.story(firsts[0], data, date(2026, 3, 2))
    assert state['goal']['text'] and state['goal']['interest'] and '{name}' not in state['goal']['progress']
    # A city without its own keeps exactly the shared banks.
    baltimore = catalog.city('baltimore')
    assert 'townsfolk' not in baltimore
    assert set(townsfolk.goal_bank(baltimore)) == {goal[0] for goal in townsfolk.GOALS}


def test_a_citys_goal_practice_spots_are_the_ones_townsfolk_go_to():
    assert set(PracticeSpot.__args__) == set(townsfolk.GOAL_KINDS)


def test_casino_dealers_only_where_there_is_a_casino():
    for city_id in ('las-vegas', 'jeju', 'new-orleans'):
        assert 'casino-dealer' in catalog.careers_for(catalog.city(city_id))
    for city_id in ('los-angeles', 'san-diego', 'haddon-harbor'):
        assert 'casino-dealer' not in catalog.careers_for(catalog.city(city_id))


def test_stockbrokers_only_where_there_is_an_exchange():
    assert 'stockbroker' in catalog.careers_for(catalog.city('new-york-1925'))
    data = catalog.city('pellmouth')
    assert 'stockbroker' not in catalog.careers_for(data)
    assert not occupations(data)['stockbroker']


def test_commutes_change_lines_once_rather_than_drive():
    data = catalog.city('london')
    hoods = [hood['id'] for hood in data['neighborhoods']]
    trips = [generators.commute(data, a, b) for a, b in itertools.combinations(hoods, 2)]
    assert not [trip for trip in trips if trip['mode'] == 'car']
    changed = [trip for trip in trips if 'change' in trip]
    assert changed
    trip = changed[0]
    start, end = catalog.neighborhood(data, trip['from']), catalog.neighborhood(data, trip['to'])
    hub = catalog.neighborhood(data, trip['change']['at'])
    lines = {line['name']: line['id'] for line in data['transit']}
    first, second = (lines[name] for name in trip['change']['lines'])
    assert first in start['transit'] and second in end['transit'] and {first, second} <= set(hub['transit'])
    assert generators.commute(data, trip['from'], trip['to']) == trip
    # A shared line still wins over a change.
    direct = next(t for t in trips if t['line'] and 'change' not in t)
    assert ', then ' not in direct['line']
