"""Interiors (requirements "### Interiors"): the format, the shipped ones, and finding them."""
import json

import pytest
from pydantic import ValidationError

from dungeon import interiors, packages
from dungeon.world.schema import Interior

SHIPPED = sorted((packages.DATA / 'interiors').glob('*.json'))


def keep() -> dict:
    return json.loads((packages.DATA / 'interiors' / 'abandoned-keep.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('path', SHIPPED, ids=lambda path: path.stem)
def test_every_shipped_interior_validates_and_its_way_in_exists(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    interior = Interior.model_validate(data)
    assert interior.id == path.stem
    assert interior.world in packages.builtin_ids()
    if interior.at.node:
        nodes = {node['id'] for node in packages.engine_for(interior.world)[('travel', interior.world)]['nodes']}
        assert interior.at.node in nodes
    if interior.at.place:
        city = json.loads((packages.DATA / 'cities' / f'{interior.at.city}.json').read_text(encoding='utf-8'))
        assert interior.at.place in {place['id'] for place in city['places']}


def test_a_world_package_carries_its_interiors():
    assert ('interiors', 'abandoned-keep') in packages.engine_for('vallarith')
    assert ('interiors', 'abandoned-keep') not in packages.engine_for('havenbrooke')
    assert 'interiors' in packages.ENGINE_KINDS


def test_interiors_are_found_by_their_way_in():
    assert interiors.entered_from(node='abandoned-keep')['id'] == 'abandoned-keep'
    assert interiors.entered_from(city='vallarith-road', place='abandoned-keep')['id'] == 'abandoned-keep'
    assert interiors.entered_from(world='havenbrooke', node='abandoned-keep') is None
    assert interiors.entered_from(node='kingswood') is None
    assert [item['id'] for item in interiors.for_world('vallarith')] == ['abandoned-keep']


def test_hidden_and_one_way_passages_show_only_when_they_should():
    interior = interiors.get('abandoned-keep')
    assert {way['to'] for way in interiors.ways_out(interior, 'cellars')} == {'cold-hall'}
    assert {way['to'] for way in interiors.ways_out(interior, 'cellars', frozenset({'ley-vault'}))} == {'cold-hall', 'ley-vault'}
    one_way = interiors.validated(keep() | {'passages': keep()['passages'] + [
        {'between': ['commanders-room', 'ward-court'], 'kind': 'shaft', 'one_way': True}]})
    assert 'ward-court' in {way['to'] for way in interiors.ways_out(one_way, 'commanders-room')}
    assert 'commanders-room' not in {way['to'] for way in interiors.ways_out(one_way, 'ward-court')}


@pytest.mark.parametrize('change, problem', [
    ({'entrance': 'nowhere'}, 'entrance'),
    ({'passages': [{'between': ['broken-gate', 'the-moon']}]}, 'unknown rooms'),
    ({'passages': []}, 'No passage reaches'),
    ({'rooms': keep()['rooms'] + [keep()['rooms'][0]]}, 'used twice'),
    ({'at': {'place': 'abandoned-keep'}}, 'with its city'),
    ({'wanders': [{'weight': 1, 'action': 'run'}]}, 'a text, or an action'),
])
def test_an_interior_that_does_not_hang_together_is_refused(change, problem):
    with pytest.raises(ValidationError, match=problem):
        Interior.model_validate(keep() | change)
