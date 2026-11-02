"""Spots inside places and homes, used as detail (dungeon/world/inside.py, Hit List #46)."""
from dungeon.world import catalog, inside
from dungeon.world.schema import Place


def test_every_place_kind_gets_a_few_named_spots_that_stay_the_same():
    data = catalog.city('baltimore')
    for place in data['places']:
        spots = inside.for_place(place)
        assert 2 <= len(spots) <= 4, place['kind']
        assert spots == inside.for_place(place)
        assert all(not name.startswith(('at ', 'in ', 'on ', 'out ')) for name in inside.names(spots))
    cafes = [inside.names(inside.for_place(place)) for place in catalog.places(data, kind='cafe')]
    assert len({tuple(spots) for spots in cafes}) > 1


def test_a_pack_can_name_its_own_spots():
    place = {'id': 'tower', 'kind': 'shopping', 'spots': ['the café on L5', 'out on the roof terrace', ' ']}
    assert inside.for_place(place) == ['at the café on L5', 'out on the roof terrace']
    assert inside.names(inside.for_place(place)) == ['the café on L5', 'the roof terrace']
    assert 'spots' in Place.model_fields


def test_a_home_has_rooms_from_its_size_and_features():
    flat = inside.for_home({'bedrooms': 'one_bedroom', 'features': ['a tiny balcony', 'a galley kitchen']})
    assert flat == ['in the living room', 'in the bedroom', 'out on the balcony', 'in the galley kitchen']
    assert inside.for_home({'bedrooms': 'studio', 'features': []}) == ['in the kitchen corner', 'by the window']
    assert 'by the hearth' in inside.for_home({'features': ['a smoky hearth', 'low beams']})
    assert inside.for_home(None) == []


def test_an_entry_sometimes_says_where_inside_it_happened():
    place = {'id': 'blue-moon', 'name': 'Blue Moon Cafe', 'kind': 'cafe'}
    entries = [inside.touch({'summary': 'Got coffee at Blue Moon Cafe.', 'activity': 'coffee', 'place': place}, f'seed-{n}')
               for n in range(200)]
    told = [entry for entry in entries if entry.get('inside')]
    assert 20 < len(told) < 100
    assert all(entry['summary'].startswith('Got coffee at Blue Moon Cafe. ') for entry in told)
    assert {entry['inside'] for entry in told} & {line.format(where=spot) for line in inside.SENTENCES
                                                  for spot in inside.for_place(place)}
    again = inside.touch({'summary': 'Got coffee.', 'activity': 'coffee', 'place': place}, 'seed-1')
    assert again == inside.touch({'summary': 'Got coffee.', 'activity': 'coffee', 'place': place}, 'seed-1')


def test_home_activities_use_a_room_the_home_has_and_details_never_pile_up():
    home = {'bedrooms': 'one_bedroom', 'features': ['a galley kitchen']}
    cooked = [inside.touch({'summary': 'Made soup.', 'activity': 'home-cooking'}, f's{n}', home) for n in range(60)]
    assert {entry.get('inside') for entry in cooked} - {None} <= {
        line.format(where='in the galley kitchen') for line in inside.HOME_SENTENCES}
    assert any(entry.get('inside') for entry in cooked)
    woven = {'summary': 'Read. Fed the cat.', 'activity': 'reading', 'home': {'items': []}}
    assert all(inside.touch(woven, f's{n}', home) is woven for n in range(30))
    shift = {'summary': 'Worked.', 'activity': 'steady-shift', 'place': {'id': 'x', 'kind': 'cafe'}}
    assert all(inside.touch(shift, f's{n}') is shift for n in range(30))


def test_a_period_or_fantasy_place_never_gets_a_modern_spot():
    for city_id in ('grandport', 'pellmouth', 'new-york-1925'):
        data = catalog.city(city_id)
        for place in data['places']:
            spots = inside.for_place(place, data.get('era'))
            assert spots and not set(spots) & inside.MODERN_SPOTS, (city_id, place['id'], spots)
    shop = {'id': 'mall', 'kind': 'shopping'}
    assert set(inside.for_place(shop, 'modern')) <= set(inside.BY_KIND['shopping'])


def test_a_1925_soda_fountain_has_stools_not_a_back_patio():
    data = catalog.city('pellmouth')
    for place in catalog.places(data, kind='cafe') + catalog.places(data, kind='restaurant'):
        spots = inside.for_place(place, data['era'])
        assert not [spot for spot in spots if 'patio' in spot or 'shared table' in spot], place['id']
    fountain = catalog.find(data, 'tarbox-drug-store')
    assert 'on a stool at the counter' in inside.for_place(fountain, data['era'])
