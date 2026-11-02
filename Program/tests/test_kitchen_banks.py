"""The dish banks behind Kitchen and food (dungeon/world/data/kitchen/*.json)."""
import json
import re
from pathlib import Path

import pytest

BANKS = Path(__file__).resolve().parents[1] / 'dungeon' / 'world' / 'data' / 'kitchen'
IDS = ('modern-us', 'modern-uk', 'modern-japan', 'modern-korea', 'modern-world', 'jazz-age-us', 'victorian-uk',
       'medieval', 'old-world', 'frontier-us')
PROTEINS = {'vegan', 'veg', 'fish', 'shellfish', 'meat', 'pork'}
ALLERGENS = {'dairy', 'egg', 'gluten', 'nuts'}
OTHER = {'big', 'quick', 'bake', 'treat', 'cold', 'warm', 'breakfast'}
TAGS = PROTEINS | ALLERGENS | OTHER
# Brand and business names never belong in a bank; neither do vague dishes.
VAGUE = re.compile(r'^(?:food|dinner|a meal|something|stuff|leftovers|soup|pasta|salad|sandwich|stew|curry|rice)$')


def load(bank_id: str) -> dict:
    return json.loads((BANKS / f'{bank_id}.json').read_text(encoding='utf-8'))


def tags_of(text: str) -> set[str]:
    return set(text.split())


@pytest.mark.parametrize('bank_id', IDS)
def test_bank_shape_and_size(bank_id):
    bank = load(bank_id)
    assert bank['id'] == bank_id and bank['label']
    dishes, takeout, staples = bank['dishes'], bank['takeout'], bank['staples']
    assert len(dishes) >= 110, f'{bank_id}: {len(dishes)} dishes'
    names = [dish[0] for dish in dishes]
    assert len(set(map(str.casefold, names))) == len(names), 'duplicate dishes'
    for name, skill, tags in dishes:
        found = tags_of(tags)
        assert found <= TAGS, (name, found - TAGS)
        assert len(found & PROTEINS) == 1, (name, 'exactly one of vegan veg fish shellfish meat pork')
        assert skill in (1, 2, 3), name
        assert name == name.strip(), name
        assert not name.casefold().startswith(('a ', 'an ', 'the ', 'some ')), (name, 'no leading article')
        assert not VAGUE.match(name.casefold()), (name, 'too vague')
        assert 3 <= len(name) <= 60, name
        if 'vegan' in found:
            assert not found & {'dairy', 'egg'}, (name, 'vegan with dairy or egg')
    skills = [dish[1] for dish in dishes]
    assert skills.count(1) >= 25 and skills.count(2) >= 45 and skills.count(3) >= 15, (bank_id, skills.count(1),
                                                                                        skills.count(2), skills.count(3))
    every = [tags_of(dish[2]) for dish in dishes]
    meatless = sum(bool(tags & {'vegan', 'veg'}) for tags in every)
    assert meatless >= 30, (bank_id, 'vegetarian dishes', meatless)
    assert sum('vegan' in tags for tags in every) >= 12, (bank_id, 'vegan dishes')
    assert sum('vegan' in tags and 'gluten' not in tags and 'nuts' not in tags for tags in every) >= 6
    assert sum('bake' in tags for tags in every) >= 12, (bank_id, 'baking')
    assert sum('big' in tags for tags in every) >= 20, (bank_id, 'batch dishes that leave leftovers')
    assert sum('treat' in tags for tags in every) >= 15, (bank_id, 'dishes for having someone over')
    assert sum('quick' in tags for tags in every) >= 20, (bank_id, 'quick dishes')
    assert sum(dish[1] == 1 and bool(tags_of(dish[2]) & {'vegan', 'veg'}) for dish in dishes) >= 8

    assert len(takeout) >= 25, f'{bank_id}: {len(takeout)} takeout'
    for dish, cuisine, source, tags in takeout:
        found = tags_of(tags)
        assert found <= TAGS and len(found & PROTEINS) == 1, (dish, found)
        assert cuisine == cuisine.casefold() and re.fullmatch(r'[a-z][a-z-]*', cuisine), (dish, cuisine)
        assert source.startswith(('the ', 'a ', 'an ')), (dish, source)
        assert not dish.casefold().startswith(('a ', 'an ', 'the ')), dish
    assert sum(bool(tags_of(item[3]) & {'vegan', 'veg'}) for item in takeout) >= 6, (bank_id, 'meatless takeout')

    assert 3 <= len(staples) <= 5
    for staple in staples:
        assert set(staple) <= {'name', 'tags', 'swap', 'days'} and staple['name']
        assert set(staple.get('tags', '').split()) <= ALLERGENS | {'vegan'}
        assert 3 <= staple.get('days', 7) <= 30
