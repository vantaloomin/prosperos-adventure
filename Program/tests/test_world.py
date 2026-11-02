import copy
import json
import re
import runpy
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeon.errors import DomainError
from dungeon.world import catalog, custom, generators
from dungeon.world.check import FOOD
from dungeon.world.schema import City, Featured

CITIES = sorted(key for key, value in catalog.cities().items() if value['origin'] == 'builtin')
DERIVED = ('data_version', 'builtin', 'origin', 'pack_file')
SEEDS = [f'seed-{index}' for index in range(60)]


def baltimore():
    return catalog.city('baltimore')


def plain(data):
    """A city as written, without the fields the loader adds."""
    return {key: value for key, value in copy.deepcopy(data).items() if key not in DERIVED}


@pytest.mark.parametrize('city_id', CITIES)
def test_every_shipped_city_validates_and_cites_its_sources(city_id):
    data = catalog.city(city_id)
    assert data['country'] and data['data_version']
    for source in catalog.sources(data):
        assert source['license'] and source['retrieved']
    for career in catalog.careers_for(data):
        result = generators.job(data, career, seed=career)
        assert result['employer']['name'] and result['refs'] and result['sources']


SCRIPTS = Path(__file__).parent.parent / 'scripts' / 'world'


@pytest.mark.parametrize('city_id', [city for city in CITIES if (SCRIPTS / f'{city.replace("-", "_")}.py').exists()])
def test_shipped_json_matches_its_source_script(city_id):
    script = SCRIPTS / f'{city_id.replace("-", "_")}.py'
    written = json.loads((catalog.BUILTIN_CITIES / f'{city_id}.json').read_text(encoding='utf-8'))
    assert runpy.run_path(str(script))['CITY'] == json.loads(json.dumps(written)), 'Rerun the script.'


# The Road and BABEL's floors (dungeon/travel.py) are the ways between towns, not towns: their wild regions have
# nowhere to eat.
@pytest.mark.parametrize('city_id', [city for city in CITIES if city not in ('vallarith-road', 'babel-floors')])
def test_every_neighborhood_has_somewhere_to_eat_or_drink(city_id):
    data = catalog.city(city_id)
    kinds = {hood['id']: set() for hood in data['neighborhoods']}
    for place in data['places']:
        kinds[place['neighborhood']].add(place['kind'])
    assert not sorted(hood for hood, found in kinds.items() if not FOOD & found)

def test_validation_rejects_broken_references():
    raw = plain(baltimore())
    City.model_validate(raw)
    raw['places'][0] = raw['places'][0] | {'neighborhood': 'atlantis'}
    with pytest.raises(ValidationError, match='atlantis|neighborhoods'):
        City.model_validate(raw)
    raw = plain(baltimore())
    raw['colleges'][0] = raw['colleges'][0] | {'source': 'made-up'}
    with pytest.raises(ValidationError, match='sources'):
        City.model_validate(raw)


def test_choices_are_stable_across_runs_and_python_versions():
    assert generators.unit('slot', 'outing') == generators.unit('slot', 'outing')
    assert round(generators.unit('stable', 'check'), 12) == 0.380102014478
    first = generators.outing(baltimore(), seed='evening@2026-10-04', day=date(2026, 10, 4), neighborhood='canton')
    again = generators.outing(baltimore(), seed='evening@2026-10-04', day=date(2026, 10, 4), neighborhood='canton')
    assert first == again


def test_outings_follow_constraints_and_prefer_the_neighborhood():
    data = baltimore()
    nearby = 0
    for seed in SEEDS:
        result = generators.outing(data, seed=seed, day_part='evening', company='date', neighborhood='fells-point',
                                   budget='$$', exclude=['berthas'])
        place = result['place']
        assert 'evening' in place['day_parts'] and 'date' in place['good_for']
        assert generators.COSTS.index(place['cost']) <= 2 and place['id'] != 'berthas'
        assert result['travel']['from'] == 'fells-point'
        nearby += result['travel']['distance_km'] <= 3
    assert nearby > len(SEEDS) / 2


def test_bad_weather_favours_indoor_places_and_seasons_are_respected():
    data = baltimore()
    winter = [generators.outing(data, seed=seed, day=date(2026, 1, 20)) for seed in SEEDS]
    assert all('winter' in r['place']['seasons'] or not r['place']['seasons'] for r in winter)
    july = [generators.outing(data, seed=seed, day=date(2026, 7, 15)) for seed in SEEDS]
    wet = [r for r in july if r['weather']['rain']]
    if wet:
        assert sum(r['place']['setting'] == 'outdoor' for r in wet) < len(wet) / 2


def test_meals_pick_food_places_for_the_time_of_day():
    for seed in SEEDS[:20]:
        result = generators.meal(baltimore(), seed=seed, meal='breakfast')
        assert result['place']['kind'] in generators.FOOD and result['meal'] == 'breakfast'


def test_commutes_choose_a_sensible_mode():
    data = baltimore()
    assert generators.commute(data, 'harbor-east', 'little-italy')['mode'] == 'walk'
    rail = generators.commute(data, 'mount-vernon', 'station-north')
    assert rail['mode'] == 'light-rail' and rail['line'] == 'Light RailLink'
    far = generators.commute(data, 'towson', 'inner-harbor')
    assert far['mode'] == 'car' and 20 <= far['minutes'] <= 90


def test_jobs_use_real_employers_and_fall_back_without_inventing_names():
    data = baltimore()
    nurse = generators.job(data, 'registered-nurse', seed='a', home='canton')
    assert nurse['employer']['named'] and nurse['employer']['fit'] == 'employer'
    assert nurse['commute']['from'] == 'canton'
    student = generators.job(data, 'undergraduate', seed='a')
    assert student['employer']['fit'] == 'college' and student['schedule'][0]['kind'] == 'study'
    barista = generators.job(data, 'barista', seed='a')
    assert barista['employer']['fit'] == 'workplace'
    assert catalog.find(data, barista['employer']['id'])['kind'] in {'cafe', 'market'}


def test_homes_stay_within_budget_and_typical_ranges():
    data = baltimore()
    for seed in SEEDS:
        result = generators.home(data, seed=seed, bedrooms='one_bedroom', budget=1400)
        low, high = result['neighborhood']['rent']['one_bedroom']
        assert low <= result['rent'] <= min(high, 1400) and result['rent'] % 25 == 0


def test_free_text_locations_resolve_to_cities_and_neighborhoods():
    assert catalog.resolve('Fells Point, Baltimore') == {'city': 'baltimore', 'neighborhood': 'fells-point'}
    assert catalog.resolve('Charm City') == {'city': 'baltimore', 'neighborhood': None}
    assert catalog.resolve('Lisbon') is None
    assert catalog.resolve('') is None


def test_world_api(client):
    cities = client.get('/api/world/cities').json()
    shelves = {city['id']: city['category'] for city in cities}
    assert shelves['baltimore'] == 'real' and shelves['london-1895'] == shelves['whitlock'] == 'other-eras'
    assert shelves['camelot'] == shelves['calderwick'] == shelves['emerald-city'] == 'fictional'
    assert 'baltimore' in {city['id'] for city in cities}
    # Each city names the world package whose travel map it is on, so the Worlds page shows only the open world's.
    worlds = {city['id']: (city['world'], city['world_name']) for city in cities}
    assert worlds['kingswood'] == ('vallarith', 'Vallarith') and worlds['haven'][0] == 'havenbrooke'
    assert worlds['the-concourse'][0] == worlds['hollin'][0] == 'babel'
    assert worlds['haddon-harbor'] == worlds['baltimore'] == (None, None)
    assert client.get('/api/world/cities/atlantis').status_code == 404
    places = client.get('/api/world/cities/baltimore/places', params={'kind': 'museum'}).json()
    assert places and all(place['kind'] == 'museum' for place in places)
    outing = client.get('/api/world/cities/baltimore/generate/outing',
                        params={'seed': 's', 'day': '2026-10-04', 'neighborhood': 'hampden', 'company': 'friends'})
    assert outing.status_code == 200 and outing.json()['outing']['company'] == 'friends'
    job = client.get('/api/world/cities/baltimore/generate/job', params={'career': 'teacher', 'seed': 's'}).json()
    assert job['schedule'][0]['key'] == 'work'
    commute = client.get('/api/world/cities/baltimore/commute', params={'from': 'canton', 'to': 'towson'})
    assert commute.status_code == 200 and commute.json()['mode']
    assert client.get('/api/world/resolve', params={'text': 'Hampden, Baltimore'}).json()['match'] == {
        'city': 'baltimore', 'neighborhood': 'hampden'}


def test_users_build_their_own_cities(client):
    template = client.get('/api/world/template').json()
    assert client.post('/api/world/validate', json=template).json()['valid']
    response = client.post('/api/world/validate', json=template | {'places': []})
    assert response.status_code == 422 and 'places' in response.json()['detail']
    city = template | {'id': 'port-calloway', 'name': 'Port Calloway', 'aliases': ['Calloway']}
    created = client.post('/api/world/cities', json=city)
    assert created.status_code == 200, created.text
    assert created.json()['revision'] == 1 and not created.json()['builtin']
    assert client.post('/api/world/cities', json=city).status_code == 409
    assert client.post('/api/world/cities', json=template | {'id': 'baltimore'}).status_code == 409
    listed = {item['id']: item for item in client.get('/api/world/cities').json()}
    assert listed['port-calloway']['builtin'] is False and listed['baltimore']['builtin'] is True
    assert listed['port-calloway']['category'] == 'custom'

    job = client.get('/api/world/cities/port-calloway/generate/job', params={'career': 'barista', 'seed': 's'})
    assert job.status_code == 200 and job.json()['neighborhood']['id'] == 'old-town'
    outing = client.get('/api/world/cities/port-calloway/generate/outing', params={'seed': 's', 'day': '2026-10-04'})
    assert outing.json()['outing']['place']['id'] == 'corner-cafe' and outing.json()['outing']['weather'] is None
    home = client.get('/api/world/cities/port-calloway/generate/home', params={'seed': 's'}).json()
    assert home['neighborhood']['id'] == 'old-town' and home['rent'] is None
    assert client.get('/api/world/resolve', params={'text': 'Calloway'}).json()['match']['city'] == 'port-calloway'

    edited = city | {'summary': 'A foggy harbour town.'}
    stale = client.put('/api/world/cities/port-calloway', json={'definition': edited, 'expected_revision': 2})
    assert stale.status_code == 409
    updated = client.put('/api/world/cities/port-calloway', json={'definition': edited, 'expected_revision': 1})
    assert updated.json()['summary'] == 'A foggy harbour town.' and updated.json()['revision'] == 2
    assert client.put('/api/world/cities/baltimore', json={'definition': edited, 'expected_revision': 1}
                      ).status_code == 409


def test_a_saved_city_that_no_longer_validates_leaves_the_others_listed(app, client):
    """A city saved under an older app's rules, or edited by hand, once made every city list fail, so the
    home city pickers offered only "None"."""
    template = client.get('/api/world/template').json()
    assert client.post('/api/world/cities', json=template | {'id': 'stale-town', 'name': 'Stale Town'}).status_code == 200
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE world_cities SET definition=? WHERE id='stale-town'",
                           (json.dumps(template | {'id': 'stale-town', 'name': 'Stale Town', 'neighborhoods': []}),))
    listed = client.get('/api/world/cities')
    assert listed.status_code == 200
    assert 'baltimore' in {city['id'] for city in listed.json()} and 'stale-town' not in {city['id'] for city in listed.json()}
    broken = client.get('/api/world/broken-cities').json()
    assert [(item['id'], item['name']) for item in broken] == [('stale-town', 'Stale Town')]
    assert 'neighborhoods' in broken[0]['error'] and broken[0]['definition']['neighborhoods'] == []
    assert client.delete('/api/world/cities/stale-town').status_code == 200
    assert client.get('/api/world/broken-cities').json() == []


def test_a_saved_city_that_crashes_while_loading_leaves_the_others_listed(app, client, monkeypatch):
    """A tester's Settings > Life & cities said "Something went wrong": any error loading one saved city, not
    only a validation error, failed the city list."""
    template = client.get('/api/world/template').json()
    assert client.post('/api/world/cities', json=template | {'id': 'odd-town', 'name': 'Odd Town'}).status_code == 200
    real = catalog.mending.mend

    def mend(definition):
        if definition.get('id') == 'odd-town':
            raise AttributeError("'NoneType' object has no attribute 'get'")
        return real(definition)
    monkeypatch.setattr(catalog.mending, 'mend', mend)
    listed = client.get('/api/world/cities')
    assert listed.status_code == 200 and 'odd-town' not in {city['id'] for city in listed.json()}
    assert [item['id'] for item in client.get('/api/world/broken-cities').json()] == ['odd-town']


def test_a_city_dropped_among_the_built_in_ones_loads_like_a_pack(client, tmp_path, monkeypatch):
    """A Mac tester put a Los Angeles file among the built-in cities. Loaded strictly, its one job the app lacked
    failed every city list, so Life & cities showed errors.
    Such a file now loads like a pack, mended, and one that still cannot load is left out and named."""
    folder = tmp_path / 'cities'
    folder.mkdir()
    for path in catalog.city_files(catalog.BUILTIN_CITIES):
        (folder / path.name).write_bytes(path.read_bytes())
    stray = plain(baltimore()) | {'id': 'harbor-town', 'name': 'Harbor Town', 'aliases': [], 'setting': 'fictional'}
    stray['employers'][0]['careers'].append('aerospace-engineer')
    (folder / 'Harbor Town.json').write_text(json.dumps(stray), encoding='utf-8')
    (folder / 'notes.json').write_text('[1, 2]', encoding='utf-8')
    monkeypatch.setattr(catalog, 'BUILTIN_CITIES', folder)
    monkeypatch.setenv(catalog.PACKS_ENV, str(tmp_path / 'no-packs'))
    try:
        report = catalog.reload()
        assert [Path(item['file']).name for item in report['errors']] == ['notes.json']
        assert [item['id'] for item in report['loaded']] == ['harbor-town']
        listed = client.get('/api/world/cities')
        assert listed.status_code == 200 and {'baltimore', 'harbor-town'} <= {city['id'] for city in listed.json()}
    finally:
        monkeypatch.undo()
        catalog.reload()


def test_a_saved_copy_of_a_city_that_is_now_built_in_is_not_listed_twice(app, client):
    """Los Angeles became a built-in city after testers had imported their own copy of it."""
    with app.state.database.connect(write=True) as connection:
        connection.execute('INSERT INTO world_cities (id, definition, created_at, updated_at) VALUES (?, ?, ?, ?)',
                           ('los-angeles', json.dumps(plain(catalog.city('los-angeles'))), '2026-10-01', '2026-10-01'))
    listed = [city for city in client.get('/api/world/cities').json() if city['id'] == 'los-angeles']
    assert [city['origin'] for city in listed] == ['builtin']
    assert client.get('/api/world/broken-cities').json() == []
    assert client.delete('/api/world/cities/los-angeles').status_code == 200
    assert 'los-angeles' in catalog.cities()
    assert client.delete('/api/world/cities/los-angeles').status_code == 409


def test_the_app_falls_back_to_the_city_it_ships():
    from conftest import SHIPPED_CITIES, SHIPPED_DEFAULT_CITY
    assert (SHIPPED_CITIES / f'{SHIPPED_DEFAULT_CITY}.json').exists()


def test_every_shipped_city_loads_strictly():
    from conftest import SHIPPED_CITIES
    shipped = catalog.city_files(SHIPPED_CITIES)
    assert shipped and all(catalog.prepare(path.read_bytes())['id'] == path.stem for path in shipped)
    assert catalog.reload()['errors'] == []
    assert all(data['origin'] == 'builtin' for data in catalog.cities().values() if not data.get('pack_file'))
    assert {path.stem for path in catalog.city_files(catalog.BUILTIN_CITIES)} == \
        {key for key, data in catalog.cities().items() if data['origin'] == 'builtin'}


def test_settings_without_money_or_climate_still_generate():
    raw = plain(baltimore())
    raw |= {'id': 'storybook', 'setting': 'original', 'era': 'fantasy', 'climate': None, 'employers': [],
            'career_hubs': [], 'speeds': {'walk': 4.5, 'horse': 12},
            'careers': [{'id': 'baker-fantasy', 'name': 'Baker', 'sector': 'food', 'schedule': 'early', 'pay': '$',
                         'summary': 'Bakes bread before dawn.', 'themes': ['bread'], 'eras': ['fantasy']}],
            'neighborhoods': [hood | {'rent': None} for hood in raw['neighborhoods']]}
    data = catalog.prepare(raw)
    assert set(catalog.careers_for(data)) == {'baker-fantasy'}
    assert generators.job(data, 'baker-fantasy', seed='x')['employer']['fit'] == 'workplace'
    assert generators.home(data, seed='x', budget=10)['rent'] is None
    assert generators.commute(data, 'towson', 'inner-harbor')['mode'] == 'horse'
    assert generators.conditions(data, date(2026, 1, 1)) is None
    with pytest.raises(DomainError):
        generators.job(data, 'software-engineer', seed='x')


def test_private_city_packs_load_from_a_local_folder(client, tmp_path, monkeypatch):
    pack = plain(baltimore()) | {'id': 'harbor-town', 'name': 'Harbor Town', 'aliases': [],
                                  'setting': 'fictional', 'distribution': 'private'}
    (tmp_path / 'harbor-town.json').write_text(json.dumps(pack), encoding='utf-8')
    (tmp_path / 'broken.json').write_text('{"id": "broken"}', encoding='utf-8')
    monkeypatch.setenv(catalog.PACKS_ENV, str(tmp_path))
    try:
        report = client.post('/api/world/packs/reload').json()
        assert [item['id'] for item in report['loaded']] == ['harbor-town']
        assert report['loaded'][0]['distribution'] == 'private' and report['loaded'][0]['origin'] == 'pack'
        assert report['errors'][0]['file'].endswith('broken.json')
        assert client.get('/api/world/cities/harbor-town/generate/job',
                          params={'career': 'teacher', 'seed': 's'}).status_code == 200
        assert client.delete('/api/world/cities/harbor-town').status_code == 409
        assert client.post('/api/world/cities', json=pack).status_code == 409
        copied = client.post('/api/world/cities/harbor-town/copy', json={'id': 'my-harbor', 'name': 'Mine'})
        assert copied.status_code == 200 and copied.json()['origin'] == 'user'
    finally:
        monkeypatch.delenv(catalog.PACKS_ENV)
        catalog.reload()
    assert 'harbor-town' not in catalog.cities()


# The start of the Finder data macOS writes as `._<name>` beside each file copied to an exFAT or FAT32 drive.
APPLE_DOUBLE = b'\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        '


def test_macos_finder_files_beside_the_cities_are_skipped(client, tmp_path, monkeypatch):
    """A Mac tester running the app from an external drive had a `._` file beside every built-in city; reading
    one as a city broke the city list, and with it Today's context and the city pickers."""
    (tmp_path / 'baltimore.json').write_text('{}', encoding='utf-8')
    (tmp_path / '._baltimore.json').write_bytes(APPLE_DOUBLE)
    assert catalog.city_files(tmp_path) == [tmp_path / 'baltimore.json']
    assert catalog.city_files(tmp_path / 'missing') == []
    packs = tmp_path / 'packs'
    packs.mkdir()
    (packs / '._harbor-town.json').write_bytes(APPLE_DOUBLE)
    monkeypatch.setenv(catalog.PACKS_ENV, str(packs))
    try:
        report = client.post('/api/world/packs/reload').json()
        assert report['loaded'] == [] and report['errors'] == []
        assert client.get('/api/world/cities').status_code == 200
    finally:
        monkeypatch.delenv(catalog.PACKS_ENV)
        catalog.reload()


def test_packs_are_not_committed():
    ignored = (Path(__file__).parent.parent / '.gitignore').read_text(encoding='utf-8')
    assert '/private-cities/' in ignored and catalog.CHECKOUT_PACKS.name == 'private-cities'


def test_small_currency_rents_use_the_whole_range():
    rents = {generators.home(catalog.city('camelot'), seed=seed)['rent'] for seed in SEEDS}
    assert len(rents) > 3


def test_the_world_source_filters_by_time_of_day_and_season():
    from dungeon.world.source import CatalogWorld
    world = CatalogWorld()
    evening = world.places('baltimore', ['museum', 'attraction'], day_part='evening')
    assert evening and 'National Aquarium' not in {place.name for place in evening}
    winter = world.places('baltimore', ['attraction'], day=date(2026, 1, 15))
    assert 'The Maryland Zoo' not in {place.name for place in winter}
    assert 'The Maryland Zoo' in {place.name for place in world.places('baltimore', ['attraction'],
                                                                        day=date(2026, 6, 15))}


def test_shipped_names_match_their_script_and_every_era_has_a_bank():
    script = Path(__file__).parent.parent / 'scripts' / 'world' / 'names.py'
    written = json.loads((catalog.DATA / 'names.json').read_text(encoding='utf-8'))
    assert runpy.run_path(str(script))['NAMES'] == written, 'Rerun the script.'
    for city_id in CITIES:
        groups, mix = catalog.name_groups(catalog.city(city_id))
        assert mix and set(mix) <= set(groups)


def test_residents_follow_their_arguments():
    data = baltimore()
    nurse = generators.resident(data, seed='n', career='registered-nurse', age=41, near='canton')
    assert nurse['job']['career']['id'] == 'registered-nurse' and nurse['age'] == 41
    assert nurse['job']['commute']['from'] == nurse['home']['neighborhood']['id']
    retired = generators.resident(data, seed='r', age=72)
    assert retired['job'] is None and retired['schedule'] == generators.RETIRED_SCHEDULE
    away = generators.resident(data, seed='a', role='parent', local=False, family='Okafor')
    assert away['home'] is None and away['name']['family'] == 'Okafor'
    student = generators.resident(data, seed='s', career='undergraduate')
    assert 18 <= student['age'] <= 22 and student['job']['employer']['fit'] == 'college'
    with pytest.raises(DomainError):
        generators.resident(data, seed='x', role='rival')
    with pytest.raises(DomainError):
        generators.resident(data, seed='x', employer='atlantis')


def test_names_follow_the_city_bank_and_its_own_groups():
    miami = catalog.city('miami')
    groups = [generators.name(miami, seed=seed)['group'] for seed in SEEDS]
    assert groups.count('hispanic') > len(SEEDS) / 3
    whitlock = catalog.city('whitlock')
    assert all(generators.name(whitlock, seed=seed)['group'] in catalog.names()['banks']['frontier'] for seed in SEEDS)
    raw = plain(baltimore()) | {'names': {'groups': {'harbor': {'feminine': ['Wren'], 'family': ['Tidewell']}}}}
    custom = catalog.prepare(raw)
    assert {generators.name(custom, seed=seed)['full'] for seed in SEEDS[:5]} == {'Wren Tidewell'}
    with pytest.raises(ValueError):
        catalog.prepare(plain(baltimore()) | {'names': {'bank': 'atlantis'}})


def test_people_api(client):
    circle = client.get('/api/world/cities/baltimore/generate/circle',
                        params={'seed': 's', 'size': 4, 'home': 'canton', 'age': 31, 'career': 'teacher'}).json()
    assert [person['role'] for person in circle['people']] == ['close-friend', 'coworker', 'sibling', 'friend']
    assert circle['people'][1]['job']['career']['id'] == 'teacher'
    person = client.get('/api/world/cities/whitlock/generate/resident', params={'seed': 's', 'role': 'mentor'})
    assert person.status_code == 200 and person.json()['role'] == 'mentor'
    assert client.get('/api/world/cities/baltimore/generate/circle', params={'seed': 's', 'size': 40}).status_code == 422
    assert 'modern' in client.get('/api/world/names').json()['banks']


def test_a_circle_spreads_across_workplaces():
    data = baltimore()
    for seed in SEEDS[:30]:
        people = generators.circle(data, seed=seed, size=6, home='fells-point')['people']
        employers = [person['job']['employer']['id'] for person in people
                     if person['job'] and person['job']['employer']['id']]
        assert all(employers.count(item) <= 2 for item in employers)


def test_shipped_holidays_match_their_script():
    script = Path(__file__).parent.parent / 'scripts' / 'world' / 'holidays.py'
    written = json.loads((catalog.DATA / 'holidays.json').read_text(encoding='utf-8'))
    assert runpy.run_path(str(script))['HOLIDAYS'] == written, 'Rerun the script.'


def test_holiday_dates():
    assert [generators.easter(year) for year in (1895, 2000, 2024, 2026, 2038)] == [
        date(1895, 4, 14), date(2000, 4, 23), date(2024, 3, 31), date(2026, 4, 5), date(2038, 4, 25)]
    year = {item['id']: item['date'] for item in generators.holidays(baltimore(), date(2026, 1, 1), date(2026, 12, 31))}
    assert year['thanksgiving'] == '2026-11-26' and year['memorial-day'] == '2026-05-25'
    assert year['labor-day'] == '2026-09-07' and year['mlk-day'] == '2026-01-19'
    london = generators.holidays(catalog.city('london-1895'), date(1895, 4, 12), date(1895, 4, 15))
    assert [item['id'] for item in london] == ['good-friday', 'easter', 'easter-monday']
    assert [item['id'] for item in generators.holidays(baltimore(), date(2026, 7, 4))] == ['independence-day']
    assert generators.holidays(catalog.city('emerald-city'), date(2026, 12, 25)) == []
    span = generators.holidays(baltimore(), date(2026, 12, 20), date(2027, 1, 2))
    assert [item['id'] for item in span] == ['christmas-eve', 'christmas', 'new-years-eve', 'new-years-day']
    with pytest.raises(DomainError):
        generators.holidays(baltimore(), date(2026, 1, 1), date(2028, 1, 1))


def test_cities_choose_and_add_holidays():
    assert {city: catalog.calendar_id(catalog.city(city)) for city in ('whitlock', 'calderwick', 'camelot')} == {
        'whitlock': 'us-1880s', 'calderwick': 'uk-victorian', 'camelot': 'medieval-england'}
    own = {'id': 'harbor-day', 'name': 'Harbor Day', 'kind': 'observance', 'month': 6, 'weekday': 5, 'nth': 1,
           'summary': 'Boats parade.'}
    custom = catalog.prepare(plain(baltimore()) | {'calendar': 'none', 'holidays': [own]})
    assert [item['date'] for item in generators.holidays(custom, date(2026, 1, 1), date(2026, 12, 31))] == ['2026-06-06']
    with pytest.raises(ValueError):
        catalog.prepare(plain(baltimore()) | {'calendar': 'atlantis'})
    with pytest.raises(ValidationError):
        catalog.prepare(plain(baltimore()) | {'holidays': [own | {'day': 3}]})


def test_holiday_api(client):
    result = client.get('/api/world/cities/baltimore/holidays', params={'start': '2026-11-01', 'end': '2026-11-30'})
    assert result.json()['calendar'] == 'us'
    assert [item['id'] for item in result.json()['holidays']] == ['veterans-day', 'thanksgiving']
    day = client.get('/api/world/cities/baltimore/conditions', params={'day': '2026-11-26'}).json()
    assert day['holidays'][0]['id'] == 'thanksgiving'


def test_local_color_is_seeded_and_seasonal():
    item = {'id': 'soft-shells', 'name': 'Soft-shell crabs', 'kind': 'dish', 'summary': 'Fried whole.',
            'places': ['fells-point'], 'seasons': ['summer'], 'source': plain(baltimore())['places'][0]['source']}
    other = item | {'id': 'hon', 'name': 'Hon', 'kind': 'saying', 'summary': 'Dear.', 'places': [], 'seasons': []}
    data = catalog.prepare(plain(baltimore()) | {'local_color': [item, other]})
    winter = generators.local_color(data, seed='s', day=date(2026, 1, 10), count=5)
    assert [entry['id'] for entry in winter] == ['hon']
    summer = generators.local_color(data, seed='s', day=date(2026, 7, 10), count=5)
    assert {entry['id'] for entry in summer} == {'hon', 'soft-shells'}
    assert generators.local_color(data, seed='s', kinds=['dish']) == [item | {'hearsay': False}]
    assert any(line.startswith('Local saying: Hon') for line in generators.facts(data))
    with pytest.raises(ValidationError, match='unknown places'):
        catalog.prepare(plain(baltimore()) | {'local_color': [item | {'places': ['atlantis']}]})


def test_generator_results_do_not_share_cached_data():
    data = baltimore()
    outing = generators.outing(data, seed='s')
    outing['place']['name'] = 'Changed'
    job = generators.job(data, 'teacher', seed='s')
    job['career']['name'] = 'Changed'
    assert all(place['name'] != 'Changed' for place in catalog.city('baltimore')['places'])
    assert catalog.careers_for(catalog.city('baltimore'))['teacher']['name'] != 'Changed'


def test_city_checker(tmp_path, capsys, monkeypatch):
    from dungeon.world import check

    good = tmp_path / 'good.json'
    good.write_text(json.dumps(plain(baltimore()) | {'id': 'good-city'}), encoding='utf-8')
    thin = plain(baltimore()) | {'id': 'thin-city', 'employers': [], 'career_hubs': [], 'climate': None, 'local_color': []}
    thin['places'] = [place for place in thin['places'] if place['neighborhood'] == 'canton']
    (tmp_path / 'thin.json').write_text(json.dumps(thin), encoding='utf-8')
    assert check.main([str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert 'OK' in output and 'fewer than two places' in output and 'No climate' in output
    (tmp_path / 'broken.json').write_text('{"id": "x"}', encoding='utf-8')
    assert check.main([str(tmp_path), '--json']) == 1
    results = {Path(item['file']).name: item for item in json.loads(capsys.readouterr().out)}
    assert results['broken.json']['errors'] and results['good.json']['warnings'] == []
    monkeypatch.setenv(catalog.PACKS_ENV, str(tmp_path / 'no-packs'))
    assert check.main([]) == 0


def test_prices_are_seeded_within_range_and_ground_facts():
    data = baltimore()
    assert data['prices'] and all(item['low'] <= item['high'] for item in data['prices'])
    item = data['prices'][0]
    first = generators.price(data, item['id'], seed='s')
    assert first == generators.price(data, item['id'], seed='s')
    assert item['low'] <= first['amount'] <= item['high'] and first['estimate']
    assert any(line.startswith('Typical prices:') for line in generators.facts(data))
    assert catalog.city('emerald-city')['prices'] == []
    with pytest.raises(DomainError):
        generators.price(data, 'unicorn-rides', seed='s')
    bad = plain(data) | {'prices': [item | {'low': 5, 'high': 1}]}
    with pytest.raises(ValidationError):
        catalog.prepare(bad)


def test_prices_api(client):
    listing = client.get('/api/world/cities/london-1895/prices').json()
    assert listing['prices'] and listing['currency']['code']
    item = listing['prices'][0]['id']
    picked = client.get('/api/world/cities/london-1895/prices', params={'item': item, 'seed': 's'}).json()
    assert picked['price']['id'] == item


def test_everyday_places_keep_near_home():
    from dungeon.world.source import NEAR_KM, CatalogWorld, nearby
    world = CatalogWorld()
    data = world.find('baltimore')
    close = nearby(data, 'Fells Point, Baltimore')
    assert close == nearby(data, 'fells-point') and close['fells-point'] == 0
    cafes = world.places('baltimore', ['cafe'], day_part='morning', near='fells-point')
    hoods = {hood['name']: hood['id'] for hood in data['neighborhoods']}
    assert len(cafes) >= 2 and all(close[hoods[place.neighborhood]] <= NEAR_KM for place in cafes)
    assert len(cafes) < len(world.places('baltimore', ['cafe'], day_part='morning'))
    # Too few within reach: the nearest few instead, closest first.
    gyms = world.places('baltimore', ['gym'], near='towson')
    assert len(gyms) == 3 and gyms[0].neighborhood == 'Towson'
    # Museums and the like stay city-wide, and an unknown place changes nothing.
    assert world.places('baltimore', ['museum'], near='fells-point') == world.places('baltimore', ['museum'])
    assert world.places('baltimore', ['cafe'], near='Atlantis') == world.places('baltimore', ['cafe'])


def test_surf_instructors_work_only_where_there_is_surf():
    assert 'surf-instructor' not in catalog.careers_for(catalog.city('baltimore'))
    assert 'surf-instructor' in catalog.careers_for(catalog.city('baltimore'), needs_met=False)
    assert 'surf-instructor' in catalog.careers_for(catalog.city('san-diego'))
    # Lifeguards also work at pools, so every city keeps them.
    assert 'lifeguard' in catalog.careers_for(catalog.city('baltimore'))


def test_featured_cities_list_only_cities_that_load_and_are_new_on_their_release(client, monkeypatch):
    from conftest import SHIPPED_CITIES, SHIPPED_FEATURED
    released = Featured.model_validate_json(SHIPPED_FEATURED.read_text(encoding='utf-8'))
    assert set(released.new_cities) <= set(released.cities) <= {path.stem for path in catalog.city_files(SHIPPED_CITIES)}
    shipped = catalog._featured()
    assert len(shipped['cities']) <= 4
    assert set(shipped['new_cities']) <= set(shipped['cities']) <= set(catalog.cities())
    monkeypatch.setattr(catalog, '_featured', lambda: shipped | {
        'release': '0.99', 'cities': ['miami', 'atlantis', 'baltimore'], 'new_cities': ['miami']})
    featured = client.get('/api/world/featured').json()
    assert [city['id'] for city in featured['cities']] == ['miami', 'baltimore'] and featured['new'] is False
    assert not any(city['new'] for city in featured['cities'])
    monkeypatch.setattr(catalog, 'VERSION', '0.99.4')
    featured = client.get('/api/world/featured').json()
    assert featured['new'] is True and [city['new'] for city in featured['cities']] == [True, False]


def test_adult_work_is_never_rolled_for_townsfolk_or_job_changes():
    adult = {key for key, career in catalog.careers().items() if career['adult']}
    assert {'subscription-creator', 'cam-model', 'exotic-dancer', 'burlesque-dancer'} <= adult
    for city_id in ('los-angeles', 'las-vegas', 'new-york-1925'):
        data = catalog.city(city_id)
        # Still found by id, for a companion whose work it is.
        assert adult & set(catalog.careers_for(data))
        assert not adult & set(catalog.everyday(catalog.careers_for(data)))
        rolled = {generators.town_career(data, f'seed-{index}')['id'] for index in range(400)}
        assert not adult & rolled


US_CITIES = [key for key in CITIES if catalog.city(key).get('country') in ('US', 'United States')]
BRITISH = re.compile(r'harbour|neighbour|honour|centre|licence|flavour|colour|favourit|labour|travell|jewellery|'
                     r'amphitheatre|\bcosy\b|\bgrey\b|modelled|storey|\btheatre\b', re.IGNORECASE)
# Real names keep their own spelling: a "... Theatre", Centre Street in Manhattan, Bal Harbour in Florida.
PROPER = re.compile(r'[A-Z][\w.\'&-]*(?: [A-Z][\w.\'&-]*)* Theatre\b|\bCentre Street\b|\bBal Harbour\b')


def shown_text(value):
    """Every string a city shows: not ids or tags, nor slugs such as vibe words, which the app matches on."""
    if isinstance(value, dict):
        return [line for name, item in value.items() if name not in ('id', 'tags') for line in shown_text(item)]
    if isinstance(value, list):
        return [line for item in value for line in shown_text(item)]
    return [value] if isinstance(value, str) and not re.fullmatch(r'[a-z0-9-]+', value) else []


@pytest.mark.parametrize('city_id', US_CITIES)
def test_us_cities_read_in_american_spelling(city_id):
    lines = [PROPER.sub('', line) for line in shown_text(catalog.city(city_id))]
    assert [line for line in lines if BRITISH.search(line)] == []


def test_every_shipped_us_city_is_checked_for_spelling():
    assert {'baltimore', 'haddon-harbor', 'new-orleans', 'new-york-1925', 'pellmouth', 'whitlock'} <= set(US_CITIES)


def test_a_city_without_work_rules_keeps_its_data_and_one_with_them_reads_them():
    open_city = catalog.city('grandport')
    assert 'work_by_gender' not in open_city and not any('worked_by' in career for career in open_city['careers'])
    old = catalog.city('london-1895')
    assert old.get('work_by_gender') is None and catalog.city('ellerbruck')['work_by_gender'] is True
    assert {career['id']: career.get('worked_by') for career in old['careers']}['cabman'] == 'men'
    raw = plain(baltimore())
    raw['careers'] = [{'id': 'lamplighter', 'name': 'Lamplighter', 'sector': 'transport', 'schedule': 'evening',
                       'pay': '$', 'summary': 'Lighting the gas lamps.', 'themes': ['dusk'], 'worked_by': 'boys'}]
    with pytest.raises(ValidationError, match='worked_by'):
        City.model_validate(raw)


def test_a_world_set_in_a_retired_city_keeps_it_as_its_own(app, client, monkeypatch):
    from dungeon.world import retired
    database = app.state.database
    with database.connect(write=True) as connection:
        retired.keep(connection, database.now())  # Nothing here names Haddon Harbor yet.
        assert not connection.execute('SELECT 1 FROM world_cities').fetchone()
    assert client.put('/api/story/scene', json={'city_id': 'haddon-harbor'}).status_code == 200
    # The tests ship Haddon Harbor as a built-in city; the app retired it (dungeon/world/data/retired).
    shipped = catalog.cities()
    monkeypatch.setattr(catalog, 'cities', lambda: {key: city for key, city in shipped.items() if key != 'haddon-harbor'})
    with database.connect(write=True) as connection:
        retired.keep(connection, database.now())
        retired.keep(connection, database.now())
        mine = custom.all_cities(connection)
    assert list(mine) == ['haddon-harbor'] and mine['haddon-harbor']['origin'] == 'user'
    story = client.get('/api/story')
    assert story.status_code == 200 and 'Haddon Harbor' in story.text
