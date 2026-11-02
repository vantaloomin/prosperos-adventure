"""Townsfolk: seeded people at the city's places, run by rules, met by the companion while out."""
import copy
from collections import Counter
from datetime import date, datetime, timedelta

import pytest

from dungeon.world import catalog, generators, naming, townsfolk


def test_every_place_has_its_own_people_rebuilt_the_same_from_their_key():
    for data in catalog.cities().values():
        for place in data['places']:
            people = townsfolk.at_place(data, place['id'])
            extra = len(townsfolk.notables_at(data, place['id']))
            if townsfolk.WILD in place['tags']:
                assert len(people) == extra  # Nobody lives or works in the wild; only named people turn up.
                continue
            assert townsfolk.PEOPLE[0] <= len(people) - extra <= townsfolk.PEOPLE[1]
            assert people == townsfolk.at_place(data, place['id'])
            for sheet in people:
                assert townsfolk.find(data, sheet['key']) == sheet
                assert sheet.get('notable') or not naming.is_invented(sheet['full'])
                assert sheet['flaw'] in townsfolk.FLAWS and sheet['desire'] in townsfolk.DESIRES
            if any(role[2] for role in townsfolk.ROLES.get(place['kind'], ())):
                assert people[0]['staff'] and people[0]['shifts']['days']
    data = catalog.city('baltimore')
    assert townsfolk.find(data, 'town:baltimore:nowhere:0') is None
    assert townsfolk.find(data, 'town:camelot:national-aquarium:0') is None
    assert townsfolk.at_place(data, 'nowhere') == []


def test_period_cities_get_period_jobs():
    data = catalog.city('camelot')
    roles = {sheet['role'] for place in data['places'] for sheet in townsfolk.at_place(data, place['id'])}
    assert 'barkeep' in roles and 'bartender' not in roles and 'barista' not in roles


def test_simple_rules_decide_where_they_are():
    data = catalog.city('baltimore')
    sheet = next(sheet for place in data['places'] for sheet in townsfolk.at_place(data, place['id'])
                 if sheet['staff'] and not sheet['night_owl'])
    day = date(2026, 10, 5)
    while day.weekday() not in sheet['shifts']['days']:
        day += timedelta(days=1)
    start = sheet['shifts']['window'][0]
    on_shift = townsfolk.whereabouts(sheet, data, datetime.combine(day, datetime.min.time())
                                     + timedelta(minutes=start + 30))
    assert on_shift['at_place'] and sheet['role'] in on_shift['doing']
    night = townsfolk.whereabouts(sheet, data, datetime(day.year, day.month, day.day, 3, 0))
    assert night == {'place': None, 'at_place': False, 'neighborhood': sheet['home'], 'doing': 'asleep',
                     'mood': night['mood']}
    regular = next(sheet for place in data['places'] for sheet in townsfolk.at_place(data, place['id'])
                   if not sheet['staff'] and sheet['visits']['part'] == 'afternoon')
    day = date(2026, 10, 5)
    while day.weekday() not in regular['visits']['days']:
        day += timedelta(days=1)
    visit = townsfolk.whereabouts(regular, data, datetime(day.year, day.month, day.day, 14, 0))
    assert visit['place']['id'] == regular['place']['id'] and 'usual spot' in visit['doing']


def test_goals_move_week_by_week_and_lead_to_the_next_one():
    data = catalog.city('baltimore')
    sheet = townsfolk.at_place(data, data['places'][0]['id'])[0]
    states = [townsfolk.story(sheet, data, townsfolk.EPOCH + timedelta(weeks=week)) for week in range(120)]
    assert states == [townsfolk.story(sheet, data, townsfolk.EPOCH + timedelta(weeks=week)) for week in range(120)]
    beats = {state['beat'] for state in states}
    assert {'progress', 'stall'} <= beats and 'achieved' in beats
    done = next(index for index, state in enumerate(states) if state['beat'] == 'achieved')
    assert states[done]['line'] and states[done]['reached'] and states[done]['goal'] != states[done - 1]['goal']
    assert townsfolk.story(sheet, data, date(2020, 1, 1))['beat'] == 'stall'


def test_every_neighborhood_has_residents_with_their_own_days():
    data = catalog.city('baltimore')
    total = 0
    for hood in data['neighborhoods']:
        people = townsfolk.residents(data, hood['id'])
        total += len(people)
        assert townsfolk.RESIDENTS[0] <= len(people) <= townsfolk.RESIDENTS[1]
        for sheet in people[:5]:
            assert townsfolk.find(data, sheet['key']) == sheet and sheet['kind'] == 'resident'
            assert sheet['home'] == hood['id'] and sheet['full'] and not naming.is_invented(sheet['full'])
            assert sheet['place']['id'] in sheet['reach'] and f"~{hood['id']}" in sheet['reach']
    assert total >= 1000
    commuter = next(sheet for hood in data['neighborhoods'] for sheet in townsfolk.residents(data, hood['id'])
                    if sheet.get('commute') and sheet['commute']['stop'] and sheet['commute']['leave'] < 9 * 60
                    and not sheet['night_owl'])
    monday = date(2026, 10, 5)
    leave = datetime.combine(monday, datetime.min.time()) + timedelta(minutes=commuter['commute']['leave'] - 10)
    waiting = townsfolk.whereabouts(commuter, data, leave)
    assert waiting['place']['id'] == f"~{commuter['home']}" and waiting['doing'].startswith('waiting for the ')
    assert townsfolk.whereabouts(commuter, data, leave + timedelta(hours=3))['doing'].startswith('at work')
    assert townsfolk.whereabouts(commuter, data, datetime(2026, 10, 5, 3, 0))['doing'] == 'asleep'
    assert commuter in [sheet for sheet in townsfolk.residents(data, commuter['home'])]
    assert commuter['key'] in {sheet['key'] for sheet in townsfolk.reaching(data, f"~{commuter['home']}")}
    regulars = townsfolk.reaching(data, commuter['place']['id'])
    assert commuter['key'] in {sheet['key'] for sheet in regulars}
    assert all(commuter['place']['id'] in sheet['reach'] for sheet in regulars)
    assert townsfolk.find(data, 'town:baltimore:~nowhere:0') is None


def everyone(data):
    return [*(sheet for place in data['places'] for sheet in townsfolk.at_place(data, place['id'])),
            *(sheet for hood in data['neighborhoods'] for sheet in townsfolk.residents(data, hood['id']))]


def test_the_city_view_lists_a_neighborhoods_residents(client):
    hood = catalog.city('baltimore')['neighborhoods'][0]['id']
    response = client.get(f'/api/world/cities/baltimore/neighborhoods/{hood}/people', params={'at': '08:00'})
    assert response.status_code == 200, response.text
    assert len(response.json()) >= townsfolk.RESIDENTS[0] and all(person['now']['doing'] for person in response.json())
    assert client.get('/api/world/cities/baltimore/neighborhoods/nowhere/people').status_code == 404


def test_the_city_view_lists_everyone_at_a_place(client):
    response = client.get('/api/world/cities/baltimore/places/national-aquarium/people', params={'at': '10:00'})
    assert response.status_code == 200, response.text
    people = response.json()
    assert people and all(person['story']['goal']['text'] and person['routine'] for person in people)
    assert client.get('/api/world/cities/baltimore/places/nowhere/people').status_code == 404


def test_no_baltimore_resident_teaches_surfing():
    data = catalog.city('baltimore')
    jobs = {townsfolk._occupation(data, f'resident-{n}', 30) for n in range(2000)}
    assert 'surf instructor' not in jobs and len(jobs) > 20


OLD_WORK = ('london-1895', 'camelot', 'calderwick', 'whitlock', 'ellerbruck')


def test_the_old_eras_keep_work_by_gender_and_fantasy_and_today_leave_it_open():
    assert all(generators.by_gender(catalog.city(city)) for city in OLD_WORK)
    # Ellerbruck's fairy-tale customs turn it on; Grandport's republic and Oz leave it open, like today.
    for city in ('grandport', 'emerald-city', 'new-york-1925', 'baltimore', 'london'):
        assert not generators.by_gender(catalog.city(city)), city
    assert not generators.by_gender(catalog.city('london-1895') | {'work_by_gender': False})


@pytest.mark.parametrize('city_id', OLD_WORK)
def test_in_an_older_era_nobody_works_the_other_sides_job(city_id):
    data = catalog.city(city_id)
    careers = catalog.careers_for(data)
    by_name = {career['name'].lower(): career for career in careers.values()}
    seen = Counter()
    for n in range(300):
        person = generators.resident(data, seed=f'era-{n}', role='friend', age=40)
        side = generators.SIDES.get(person['name']['pronouns'].split('/')[0])
        if person['job'] and side:
            worked_by = careers[person['job']['career']['id']].get('worked_by')
            assert worked_by in (None, side), (person['name']['full'], person['job']['career']['name'])
            seen[side, worked_by] += 1
        # The town's own people at home and on its streets, named or not yet, the same.
        resident = townsfolk.resident(data, data['neighborhoods'][n % len(data['neighborhoods'])]['id'], n)
        found, job = generators.SIDES.get(resident['pronouns'].split('/')[0]), by_name.get(resident['occupation'])
        if found and job:
            assert job.get('worked_by') in (None, found), (resident['full'], resident['occupation'])
        unnamed = townsfolk.resident(data, data['neighborhoods'][n % len(data['neighborhoods'])]['id'], n, named=False)
        assert unnamed['occupation'] == resident['occupation']
    # Both sides still have work of their own and work anyone does.
    assert seen['men', 'men'] and seen['women', 'women'] and seen['men', None] and seen['women', None], seen


def test_a_job_kept_to_an_age_goes_to_someone_that_age():
    """A squire is young and a student 18 to 22 (Career.ages): never a 55-year-old squire."""
    data = copy.deepcopy(catalog.city('kingswood'))
    smith = next(career for career in data['careers'] if career['id'] == 'smith')
    data['careers'].append(smith | {'id': 'squire', 'name': 'Squire', 'ages': [18, 24]})
    assert list(catalog.careers_for(data)['squire']['ages']) == [18, 24]
    assert list(catalog.careers()['undergraduate']['ages']) == [18, 22]
    for n in range(300):
        older = generators.resident(data, seed=f'age-{n}', role='friend', age=55, pronouns='he/him')
        assert not older['job'] or older['job']['career']['id'] != 'squire'
        assert townsfolk._occupation(data, f'old-{n}', 55, 'he/him') != 'squire'
    young = {generators.town_career(data, f'y-{n}', pronouns='he/him', age=20)['id'] for n in range(400)}
    assert 'squire' in young
    assert generators.fits_age({'ages': (18, 24)}, 24) and not generators.fits_age({'ages': (18, 24)}, 25)
    assert generators.fits_age({'name': 'Baker'}, 64) and generators.fits_age(None, 30)


def test_a_they_them_resident_and_a_city_of_today_pick_from_every_job():
    data = catalog.city('london-1895')
    assert generators.fits_side(data, 'they/them') is None and generators.fits_side(catalog.city('london'), 'she') is None
    women = {generators.town_career(data, f'w-{n}', pronouns='she/her')['id'] for n in range(400)}
    assert 'cabman' not in women and 'docker' not in women and {'governess', 'typist'} & women
    men = {generators.town_career(data, f'm-{n}', pronouns='he')['id'] for n in range(400)}
    assert 'governess' not in men and 'typist' not in men and 'cabman' in men


def with_notables(city_id: str = 'baltimore') -> dict:
    """A built-in city with two named people added, the way a pack lists its characters."""
    raw = copy.deepcopy(catalog.city(city_id))
    for key in ('data_version', 'builtin', 'origin', 'pack_file'):
        raw.pop(key, None)
    place = next(item for item in raw['places'] if item['kind'] == 'bar')
    source = next(iter(raw['sources']))
    raw['notables'] = [
        {'id': 'tess', 'name': 'Tess Harrow', 'pronouns': 'she/her', 'age': 41, 'place': place['id'],
         'role': 'owner', 'staff': True, 'about': 'Runs the bar her mother opened.', 'temperament': 'gruff',
         'source': source},
        {'id': 'old-ned', 'name': 'Edward "Ned" Pike', 'given': 'Ned', 'pronouns': 'he/him', 'age': 77,
         'place': place['id'], 'role': 'retired harbor pilot', 'about': 'Knows every ship that ever docked here.',
         'source': source}]
    return catalog.prepare(raw, mend=True)


def test_a_citys_notables_join_the_townsfolk_at_their_place():
    data = with_notables()
    place_id = data['notables'][0]['place']
    people = townsfolk.at_place(data, place_id)
    seeded = townsfolk.count(data, catalog.find(data, place_id))
    named = people[seeded:]
    assert [sheet['full'] for sheet in named] == ['Tess Harrow', 'Edward "Ned" Pike']
    tess, ned = named
    assert (tess['name'], tess['age'], tess['role'], tess['temperament'], tess['staff']) == \
        ('Tess', 41, 'owner', 'gruff', True)
    assert tess['shifts']['days'] and 'visits' not in tess
    assert ned['name'] == 'Ned' and not ned['staff'] and ned['visits']['days']
    assert ned['about'] == 'Knows every ship that ever docked here.' and ned['notable'] == 'old-ned'
    for sheet in named:
        assert townsfolk.find(data, sheet['key']) == sheet
        assert townsfolk.whereabouts(sheet, data, datetime(2026, 3, 4, 20, 0))
    assert tess['flaw'] != ned['flaw'] or tess['quirk'] != ned['quirk']
