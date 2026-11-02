import json
import runpy
from datetime import date, timedelta
from pathlib import Path

import pytest

from dungeon.world import catalog, changes, generators
from dungeon.world.schema import Place
from dungeon.world.source import KINDS, CatalogWorld

CITIES = sorted(key for key, value in catalog.cities().items() if value['origin'] == 'builtin')
LATER = date(2029, 6, 1)


def baltimore():
    return catalog.city('baltimore')


def first(found, kind):
    return next(change for change in found if change['kind'] == kind)


def test_seeded_changes_are_stable_and_once_heard_of_stay_known():
    data = baltimore()
    early, late = changes.known(data, date(2027, 3, 1)), changes.known(data, LATER)
    assert early == changes.known(data, date(2027, 3, 1))
    assert {change['id'] for change in early} <= {change['id'] for change in late}
    assert {change['kind'] for change in late} == {'opening', 'closing', 'renovation', 'roadworks'}
    assert all(change['announced'] <= change['starts'] for change in late)


@pytest.mark.parametrize('city_id', CITIES)
def test_every_city_changes_in_its_own_style_with_valid_places(city_id):
    data = catalog.city(city_id)
    found = changes.known(data, LATER)
    assert found
    for change in found:
        if change['kind'] == 'opening':
            Place.model_validate(change['opened'])
            assert change['opened']['kind'] in changes.style(data)['openings']
            assert catalog.find(data, change['place']) is None
    applied = changes.apply(data, found, LATER)
    ids = [place['id'] for place in applied['places']]
    assert len(ids) == len(set(ids))
    for hood in data['neighborhoods']:  # still somewhere to eat or drink everywhere
        assert any(place['kind'] in generators.FOOD and place['neighborhood'] == hood['id']
                   for place in applied['places']) or not any(
            place['kind'] in generators.FOOD and place['neighborhood'] == hood['id'] for place in data['places'])


@pytest.mark.parametrize('city_id', [key for key in CITIES if catalog.city(key)['setting'] == 'real'])
def test_seeds_never_close_a_real_business(city_id):
    data = catalog.city(city_id)
    shut = [change for change in changes.known(data, LATER) if change['kind'] in ('closing', 'renovation')]
    assert shut and all(change['place'].startswith('new-') for change in shut)


def test_the_world_hands_generators_the_city_as_it_stands_that_day():
    data, world = catalog.city('camelot'), CatalogWorld()
    renovation = first(changes.known(data, LATER), 'renovation')
    starts, ends = date.fromisoformat(renovation['starts']), date.fromisoformat(renovation['ends'])
    kind = renovation['place_kind']
    kinds = [name for name, matched in KINDS.items() if kind in matched]

    def ids(day):
        return {place.id for place in world.places('camelot', kinds, day=day)} if kinds else set()

    if kinds:
        assert renovation['place'] in ids(starts - timedelta(days=1))
        assert renovation['place'] not in ids(starts)
        assert renovation['place'] in ids(ends)
    assert renovation['place'] not in {place['id'] for place in world.find('camelot', starts)['places']}
    assert renovation['place'] in {place['id'] for place in world.find('camelot')['places']}
    assert catalog.find(catalog.city('camelot'), renovation['place'])  # the shipped data is untouched


def test_openings_appear_from_their_day_and_road_works_slow_trips_by_road():
    data, world = baltimore(), CatalogWorld()
    opening = first(changes.known(data, LATER), 'opening')
    day = date.fromisoformat(opening['starts'])
    assert opening['place'] not in {place['id'] for place in world.find('baltimore', day - timedelta(days=1))['places']}
    assert opening['place'] in {place['id'] for place in world.find('baltimore', day)['places']}
    works = first(changes.known(data, LATER), 'roadworks')
    during = world.find('baltimore', date.fromisoformat(works['starts']))
    other = next(hood['id'] for hood in data['neighborhoods'] if hood['id'] != works['neighborhood'])
    normal = generators.commute(data, works['neighborhood'], other, 'car')
    slowed = generators.commute(during, works['neighborhood'], other, 'car')
    assert slowed['minutes'] == normal['minutes'] + works['delay'] and slowed['works'] == [works['summary']]
    assert 'works' not in generators.commute(during, works['neighborhood'], other, 'walk')


def test_context_lines_read_like_local_news():
    data = catalog.city('whitlock')
    day = LATER
    lines = [changes.change_text(change, data, day) for change in changes.known(data, day)
             if changes.newsworthy(change, day)]
    assert lines and all(line.startswith('- ') for line in lines)


def test_users_add_changes_and_dismiss_seeded_ones(client):
    place = catalog.places(baltimore(), kind='cafe')[0]
    world = CatalogWorld(client.app.state.database)
    closed = client.post('/api/world/cities/baltimore/changes', json={
        'kind': 'closing', 'starts_on': '2026-10-10', 'place_id': place['id']})
    assert closed.status_code == 200, closed.text
    assert closed.json()['origin'] == 'user' and closed.json()['name'] == place['name']
    assert place['id'] in {item.id for item in world.places('baltimore', ['cafe'], day=date(2026, 10, 9))}
    assert place['id'] not in {item.id for item in world.places('baltimore', ['cafe'], day=date(2026, 10, 10))}
    opened = client.post('/api/world/cities/baltimore/changes', json={
        'kind': 'opening', 'starts_on': '2026-10-12', 'name': 'Moonlight Diner', 'place_kind': 'restaurant',
        'neighborhood': 'canton'}).json()
    assert opened['opened']['neighborhood'] == 'canton'
    assert 'Moonlight Diner' in {item.name for item in world.places('baltimore', ['restaurant'],
                                                                    day=date(2026, 10, 12))}
    listed = client.get('/api/world/cities/baltimore/changes', params={'day': '2026-10-12'}).json()['changes']
    assert {opened['id'], closed.json()['id']} <= {item['id'] for item in listed}
    assert client.delete(f"/api/world/cities/baltimore/changes/{opened['id']}").json() == {'deleted': opened['id']}
    seed = first(changes.known(baltimore(), LATER), 'opening')
    assert client.delete(f"/api/world/cities/baltimore/changes/{seed['id']}").json() == {'dismissed': seed['id']}
    assert seed['id'] not in {item['id'] for item in world.changes('baltimore', LATER)}
    bad = client.post('/api/world/cities/baltimore/changes', json={'kind': 'closing', 'starts_on': '2026-10-10',
                                                                   'place_id': 'nowhere'})
    assert bad.status_code == 422
    lasting = client.post('/api/world/cities/baltimore/changes', json={
        'kind': 'closing', 'starts_on': '2026-10-10', 'ends_on': '2026-10-20', 'place_id': place['id']})
    assert lasting.status_code == 422
    assert client.delete('/api/world/cities/baltimore/changes/unknown').status_code == 404


def test_shipped_wording_matches_its_script():
    script = Path(__file__).parent.parent / 'scripts' / 'world' / 'changes.py'
    written = json.loads((catalog.DATA / 'changes.json').read_text(encoding='utf-8'))
    assert runpy.run_path(str(script))['CHANGES'] == written, 'Rerun scripts/world/changes.py.'
