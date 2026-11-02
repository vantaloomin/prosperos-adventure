"""American wording for the shared banks in American settings (dungeon/world/wording.py)."""

from dungeon.world import catalog, life_details, perception, townsfolk, wording

BRITISH = ('neighbour', 'favourite', 'colour', 'realis', 'prize marrow', 'parish vestry', 'parish rolls', 'queue')


def test_american_cities_get_american_wording_and_british_ones_keep_theirs():
    maine, london = catalog.city('haddon-harbor'), catalog.city('london')
    assert wording.regional(maine, 'Running for the neighbourhood council.') == 'Running for the neighborhood council.'
    assert wording.regional(london, 'Running for the neighbourhood council.') == 'Running for the neighbourhood council.'
    assert wording.americanize('Nobody realises; I am realistic about the museum, Mum.') == \
        'Nobody realizes; I am realistic about the museum, Mom.'
    assert wording.regional(catalog.city('pellmouth'), 'grow the prize marrow at the harvest fair') == \
        'grow the prize pumpkin at the harvest fair'


def test_townsfolk_in_american_towns_read_american():
    for city_id in ('haddon-harbor', 'pellmouth'):
        data = catalog.city(city_id)
        for place in data['places'][:30]:
            for sheet in townsfolk.at_place(data, place['id']):
                goals = [townsfolk.goal(sheet, data, number) for number in range(len(sheet['goals']))]
                text = ' '.join([sheet['quirk'], townsfolk.quirk_bio(data, sheet['quirk']),
                                 str(perception.for_sheet(data, sheet)),
                                 str(life_details.for_sheet(data, sheet)),
                                 *(goal[field] for goal in goals for field in ('text', 'bio', 'progress', 'done'))])
                text = text.lower().replace(place['name'].lower(), '')  # A real First Parish Vestry stays.
                assert not [word for word in BRITISH if word in text], (city_id, sheet['key'])


def test_a_companions_own_lines_read_american_in_an_american_home_city():
    maine, london = catalog.city('haddon-harbor'), catalog.city('london')
    picks = {'temperament': 'nosy', 'tell': 'knows-everyones-business', 'self_story': 'good-neighbour',
             'flaw': 'favorites', 'desire': 'neighborhood'}
    american, british = [], []
    for seed in range(20):
        american.append(str(perception.compose({'name': 'Rae'}, f'rae:{seed}', picks, None, maine)))
        british.append(str(perception.compose({'name': 'Rae'}, f'rae:{seed}', picks, None, london)))
        # Without city data passed, the built-in home city the sheet names decides.
        american.append(str(perception.automatic({'name': 'Rae', 'home_city': 'haddon-harbor'}, f'rae:{seed}',
                                                 picks)))
    assert 'neighbour' in ' '.join(british).lower()
    assert not [word for word in BRITISH if word in ' '.join(american).lower()]
