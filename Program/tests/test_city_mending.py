"""Forgiving city loading (dungeon/world/mend.py): user cities and packs load despite small mistakes, new kinds of
places, schools and jobs are kept, and every change is described. Built-in cities stay exact."""
import copy
import json

import pytest

from dungeon.world import catalog, generators, mend
from dungeon.world.custom import template
from dungeon.world.schema import COLLEGE_TYPES, LOCAL_COLOR_KINDS, PLACE_KINDS, SOURCE_KINDS, TRANSIT_KINDS

BUILTINS = sorted(key for key, value in catalog.cities().items() if value['origin'] == 'builtin')
DERIVED = ('data_version', 'builtin', 'origin', 'pack_file')


def messy() -> dict:
    """A city with the slips people make writing one by hand or with a chatbot."""
    city = copy.deepcopy(template('2026-10-08'))
    city |= {'era': 'Contemporary', 'website': 'https://example.com', 'speeds': {'Walking': 5, 'Metro': 30},
             'calendar': 'mars'}
    city['transit'] = [{'id': 'red', 'name': 'Red Line', 'kind': 'Metro', 'summary': 'Subway.', 'source': 'user'}]
    city['neighborhoods'][0] |= {'transit': ['red', 'blue'], 'vibe': 'Historic, Artsy'}
    city['neighborhoods'].append({'id': 'Echo Park', 'name': 'Echo Park', 'lat': '34.07', 'lon': -118.26})
    city['places'] += [
        {'id': 'brite', 'name': 'Brite Spot', 'kind': 'Diner', 'neighborhood': 'echo park', 'cost': 'cheap',
         'setting': 'inside', 'good_for': ['Couples', 'kids', 'aliens'], 'day_parts': ['all'],
         'seasons': ['Autumn'], 'source': 'made-up', 'tags': ['Late Night', 'Pie!']},
        {'id': 'lanes', 'name': 'Shatto 39 Lanes', 'kind': 'bowling alley', 'neighborhood': 'old-town',
         'summary': 'Bowling.', 'cost': '$$', 'setting': 'indoor', 'good_for': ['friends'], 'day_parts': ['evening']},
        {'id': 'ghost', 'name': 'Ghost Bar', 'kind': 'bar', 'neighborhood': 'Arts District', 'cost': '$'},
        {'name': 'No Id Cafe', 'kind': 'cafe', 'neighborhood': 'old-twon'},
    ]
    city['colleges'] = [{'id': 'afi', 'name': 'AFI Conservatory', 'type': 'Film School', 'neighborhood': 'old-town',
                         'size': 'tiny', 'known_for': ['Film']}]
    city['employers'] = [{'id': 'jpl', 'name': 'JPL', 'sector': 'aerospace', 'neighborhood': 'Echo Park',
                          'size': 'large', 'summary': 'Space lab.', 'careers': ['aerospace-engineer', 'barista']}]
    city['careers'] = [{'id': 'stunt-double', 'name': 'Stunt double', 'sector': 'media', 'schedule': '9-to-5',
                        'pay': 'expensive', 'summary': 'Falls for a living.', 'themes': ['falls']}]
    city['local_color'] = [{'id': 'tacos', 'name': 'Tacos', 'kind': 'Street Food', 'summary': 'Tacos.',
                            'places': ['brite', 'nope']}]
    city['prices'] = [{'id': 'coffee', 'item': 'A coffee', 'low': 7, 'high': 4}]
    return city


def test_a_messy_city_loads_keeping_new_kinds_and_saying_what_changed():
    data = catalog.prepare(messy(), mend=True)
    places = {place['id']: place for place in data['places']}
    assert places['brite']['kind'] == 'restaurant'
    assert (places['brite']['cost'], places['brite']['setting'], places['brite']['seasons']) == ('$', 'indoor', ['fall'])
    assert places['brite']['good_for'] == ['date', 'family'] and len(places['brite']['day_parts']) == 4
    assert places['brite']['neighborhood'] == 'echo-park' and places['brite']['tags'] == ['late-night', 'pie']
    assert places['brite']['source'] == 'user'
    # New kinds are kept; a misspelt neighbourhood is matched; a new one is added.
    assert places['lanes']['kind'] == 'bowling-alley' and places['no-id-cafe']['neighborhood'] == 'old-town'
    assert places['ghost']['neighborhood'] == 'arts-district'
    assert {hood['id'] for hood in data['neighborhoods']} == {'old-town', 'echo-park', 'arts-district'}
    assert data['colleges'][0]['type'] == 'film-school' and data['colleges'][0]['size'] == 'small'
    assert data['transit'][0]['kind'] == 'subway' and data['speeds'] == {'walk': 5, 'subway': 30}
    assert data['neighborhoods'][0]['transit'] == ['red'] and data['local_color'][0]['places'] == ['brite']
    assert data['local_color'][0]['kind'] == 'street-food' and (data['prices'][0]['low'], data['prices'][0]['high']) == (4, 7)
    assert data['era'] == 'modern' and data['calendar'] is None and 'website' not in data
    careers = {career['id']: career for career in data['careers']}
    assert careers['stunt-double']['schedule'] == 'office' and careers['stunt-double']['pay'] == '$$$'
    assert careers['aerospace-engineer']['name'] == 'Aerospace engineer'

    notes = ' '.join(data['import_notes'])
    for expected in ('"Diner" as "restaurant"', 'Added the neighborhood "Arts District"', 'Added the job "Aerospace '
                     'engineer", which JPL hires for', '"aliens"', 'ignored the field "website"', '"mars"'):
        assert expected in notes, notes
    assert 'bowling' not in notes and 'Film School' not in notes

    # Every generator works on the result, new kinds and jobs included.
    assert generators.job(data, 'aerospace-engineer', seed='s')['employer']['id'] == 'jpl'
    assert 'brite' in {generators.meal(data, seed=f's{n}', meal='late', company='date')['place']['id'] for n in range(40)}
    kinds = {generators.outing(data, seed=f's{n}', day_part='evening', company='friends')['place']['kind']
             for n in range(40)}
    assert 'bowling-alley' in kinds


def test_mending_is_stable_and_a_mended_city_needs_no_more():
    once, notes = mend.mend(messy())
    assert notes and mend.mend(messy()) == (once, notes)
    assert not catalog.prepare(catalog.prepare(messy(), mend=True), mend=True).get('import_notes')


@pytest.mark.parametrize('city_id', BUILTINS)
def test_built_in_cities_need_no_mending_and_use_the_known_kinds(city_id):
    data = catalog.city(city_id)
    raw = {key: value for key, value in copy.deepcopy(data).items() if key not in DERIVED}
    assert mend.mend(raw)[1] == []
    assert {place['kind'] for place in data['places']} <= set(PLACE_KINDS)
    assert {college['type'] for college in data['colleges']} <= set(COLLEGE_TYPES)
    assert {line['kind'] for line in data['transit']} | set(data['speeds']) <= set(TRANSIT_KINDS)
    assert {item['kind'] for item in data['local_color']} <= set(LOCAL_COLOR_KINDS)
    assert {source['kind'] for source in data['sources'].values()} <= set(SOURCE_KINDS)


def test_what_cannot_be_mended_still_fails_with_the_reason():
    city = template('2026-10-08')
    for broken, word in ((city | {'neighborhoods': []}, 'neighborhoods'), (city | {'places': []}, 'places'),
                         ({'name': 'Nowhere'}, 'neighborhoods')):
        with pytest.raises(ValueError, match=word):
            catalog.prepare(broken, mend=True)
    with pytest.raises(ValueError):
        catalog.prepare(b'{not json', mend=True)


def test_saving_a_messy_city_keeps_the_mended_version_and_reports_the_changes(client):
    saved = client.post('/api/world/cities', json=messy() | {'id': 'messy-town', 'name': 'Messy Town'})
    assert saved.status_code == 200, saved.text
    assert any('Aerospace engineer' in note for note in saved.json()['import_notes'])
    shown = client.get('/api/world/cities/messy-town').json()
    assert not shown.get('import_notes') and shown['colleges'][0]['type'] == 'film-school'
    checked = client.post('/api/world/validate', json=messy()).json()
    assert checked['valid'] and checked['summary']['import_notes']
    failed = client.post('/api/world/validate', json=messy() | {'places': []})
    assert failed.status_code == 422 and 'Mended on the way' in failed.json()['detail']


def test_a_messy_pack_loads_with_notes(client, tmp_path, monkeypatch):
    (tmp_path / 'messy.json').write_text(json.dumps(messy() | {'id': 'messy-pack', 'name': 'Messy Pack'}),
                                         encoding='utf-8')
    monkeypatch.setenv(catalog.PACKS_ENV, str(tmp_path))
    try:
        report = client.post('/api/world/packs/reload').json()
        assert [item['id'] for item in report['loaded']] == ['messy-pack'] and not report['errors']
        assert report['loaded'][0]['import_notes']
        assert client.get('/api/world/cities/messy-pack/generate/job',
                          params={'career': 'aerospace-engineer', 'seed': 's'}).status_code == 200
    finally:
        monkeypatch.delenv(catalog.PACKS_ENV)
        catalog.reload()


@pytest.mark.parametrize('sources', ['curated', 5, True, [1], []])
def test_sources_that_are_not_a_table_never_crash_the_city_list(sources):
    """A saved city whose `sources` was not a table crashed mending, and with it every city list and Settings >
    Real-world lookups. It now cites a source written by the user instead."""
    data = catalog.prepare(template('2026-10-08') | {'sources': sources}, mend=True)
    assert list(data['sources']) == ['user']


def test_sources_written_as_a_list_keep_their_ids():
    city = template('2026-10-08')
    city['sources'] = [{'id': key, **value} for key, value in city['sources'].items()]
    data = catalog.prepare(city, mend=True)
    assert list(data['sources']) == list(template('2026-10-08')['sources'])
    assert any('sources list' in note for note in data['import_notes'])


def test_notables_at_places_the_city_lacks_are_left_out_with_a_note():
    city = copy.deepcopy(template('2026-10-08'))
    place = city['places'][0]['id']
    person = {'name': 'Mara Quill', 'pronouns': 'she/her', 'age': 30, 'role': 'regular', 'about': 'A poet.'}
    city['notables'] = [person | {'id': 'mara', 'place': place}, person | {'id': 'ghost', 'place': 'nowhere'}]
    data = catalog.prepare(city, mend=True)
    assert [item['id'] for item in data['notables']] == ['mara']
    assert data['notables'][0]['source'] in data['sources']
    assert any('Mara Quill' in note and 'nowhere' in note for note in data['import_notes'])
    exact = city | {'notables': [item | {'source': 'user'} for item in city['notables']]}
    with pytest.raises(ValueError, match='unknown places'):
        catalog.prepare(exact)
