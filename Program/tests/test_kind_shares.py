"""People of other kinds in town (dungeon/world/lifespans.py `shares`): a city's `kinds` block says what share of
its seeded townsfolk and residents are of each kind, and their names, ages and lines follow."""
import copy
from collections import Counter

from dungeon import story
from dungeon.world import catalog, generators, lifespans, townsfolk

VULCAN = {'label': 'Vulcan', 'lifespan': 220, 'words': ['vulcan']}


def city(base: str, kinds: dict, groups: dict | None = None) -> dict:
    raw = copy.deepcopy(catalog.city(base))
    for key in ('data_version', 'import_notes', 'builtin', 'origin'):
        raw.pop(key, None)
    raw['kinds'] = kinds
    if groups:
        raw['names'] = {**(raw.get('names') or {}), 'groups': {**(raw.get('names') or {}).get('groups', {}), **groups}}
    return catalog.prepare(raw, mend=True)


def counted(data: dict, n: int = 3000) -> Counter:
    return Counter(townsfolk.folk_of(data, f"town:{data['id']}:test:{index}") for index in range(n))


def test_a_kinds_share_is_how_many_people_in_town_are_of_that_kind():
    data = city('hollin', {'vulcan': VULCAN | {'share': 0.2}})
    found = counted(data)
    assert 0.17 < found['vulcan'] / 3000 < 0.23 and set(found) == {'human', 'vulcan'}
    # Their real age follows their kind's lifespan, and the same seed always gives the same person.
    vulcans = [f'town:hollin:test:{index}' for index in range(3000)
               if townsfolk.folk_of(data, f'town:hollin:test:{index}') == 'vulcan']
    ages = [townsfolk.seeded_real_age(data, seed, True) for seed in vulcans]
    assert max(ages) > 120 and ages == [townsfolk.seeded_real_age(data, seed, True) for seed in vulcans]
    assert townsfolk.lifespan_of_seed(data)(vulcans[0]) == 220
    # A resident's sheet carries the kind, so their life age, dating and lines read it.
    sheet = townsfolk.resident(data, data['neighborhoods'][0]['id'], 0)
    assert sheet.get('folk', 'human') == townsfolk.folk_of(data, sheet['seed'])


def test_a_kind_with_no_share_gets_a_default_unless_another_kind_has_one():
    alone = city('hollin', {'vulcan': VULCAN})
    assert lifespans.shares(alone) == {'vulcan': lifespans.DEFAULT_SHARE}
    assert 0.07 < counted(alone)['vulcan'] / 3000 < 0.13
    # Many kinds listed without shares still leave most people human.
    many = city('hollin', {f'kind-{n}': VULCAN | {'label': f'Kind {n}'} for n in range(6)})
    assert abs(sum(lifespans.shares(many).values()) - lifespans.DEFAULT_TOTAL) < 1e-9
    # Once one kind has a share, the others listed without one (or with 0) have none here.
    given = city('hollin', {'vulcan': VULCAN | {'share': 0.1}, 'andorian': VULCAN | {'label': 'Andorian'},
                               'tellarite': VULCAN | {'label': 'Tellarite', 'share': 0}})
    assert lifespans.shares(given) == {'vulcan': 0.1}
    assert set(counted(given)) == {'human', 'vulcan'}


def test_shares_past_one_leave_nobody_human_and_a_bad_share_is_dropped():
    data = city('hollin', {'yordle': VULCAN | {'label': 'Yordle', 'share': 0.9},
                              'vastaya': VULCAN | {'label': 'Vastaya', 'share': 0.6},
                              'troll': VULCAN | {'label': 'Troll', 'share': 3}})
    assert set(lifespans.shares(data)) == {'yordle', 'vastaya'} and abs(sum(lifespans.shares(data).values()) - 1) < 1e-9
    assert 'human' not in counted(data, 500)
    assert 'troll' not in data['kinds'] and any('troll' in note for note in data['import_notes'])


def test_a_kind_is_named_from_its_own_groups_else_like_everyone_else():
    vulcan_names = {'feminine': ["T'Pring", "T'Lar"], 'masculine': ['Sorel', 'Stonn'], 'neutral': [],
                    'family': ['of Shikahr'], 'own_family': True, 'kind': 'vulcan'}
    data = city('hollin', {'vulcan': VULCAN | {'share': 0.3}}, {'vulcan-names': vulcan_names})
    for index in range(300):
        seed = f'town:hollin:names:{index}'
        name = generators.name(data, seed=seed, age=40)
        assert (name['group'] == 'vulcan-names') == (townsfolk.folk_of(data, seed) == 'vulcan'), seed
    # A built-in kind with only a share keeps its own lifespan and takes its names from the peoples bank's group for
    # it; a kind of the city's own with no names of its own is named like humans.
    plain = city('hollin', {'dwarf': {'share': 0.3}})
    assert plain['kinds'] == {'dwarf': {'share': 0.3}} and lifespans.lifespan_of('dwarf', plain) == 300
    groups = {generators.group_of(plain, f'n{index}') for index in range(300)}
    assert groups <= {*catalog.name_groups(plain)[1], 'dwarf'} and 'dwarf' in groups
    alone = city('hollin', {'vulcan': VULCAN | {'share': 0.3}})
    assert {generators.group_of(alone, f'n{index}') for index in range(300)} <= set(catalog.name_groups(alone)[1])
    # A kind's `groups` names where its names come from; groups the city lacks are dropped with a note.
    listed = city('hollin', {'vulcan': VULCAN | {'share': 0.5, 'groups': ['varrow', 'nowhere']}})
    assert listed['kinds']['vulcan']['groups'] == ['varrow'] and any('nowhere' in note for note in listed['import_notes'])
    assert lifespans.groups_for(listed, 'vulcan') == {'varrow': catalog.name_groups(listed)[1]['varrow']}


def test_dungeons_own_towns_draw_as_before():
    # Kingswood's halflings and half-elves still come from its name groups; Haven's fae are on its cast only.
    kingswood, haven = catalog.city('kingswood'), catalog.city('haven')
    assert lifespans.shares(kingswood) == {} and {'halfling', 'half-elf'} <= set(counted(kingswood, 600))
    assert lifespans.shares(haven) == {} and set(counted(haven, 600)) == {'human'}
    assert not haven.get('import_notes')


def test_the_narrator_is_told_when_someone_is_not_human():
    data = catalog.city('kingswood')
    place = next(place for place in data['places'] if townsfolk.everyone(data, place) > 3)
    elf = next(sheet for place in data['places'] for index in range(townsfolk.count(data, place))
               if (sheet := townsfolk.person(data, place, index)).get('folk') == 'half-elf')
    assert townsfolk.folk_label(data, elf) == 'Half-elf' and townsfolk.folk_words(data, elf) == ', a Half-elf'
    person = {'sheet': elf, 'doing': 'drinking', 'mood': 'calm'}
    assert f"{elf['full']}, {elf['pronouns']}, {elf['age']}, Half-elf, drinking" in story.person_line(person, place, data)
    human = next(sheet for index in range(40) if not (sheet := townsfolk.person(data, place, index)).get('folk'))
    assert townsfolk.folk_label(data, human) is None and townsfolk.folk_words(data, human) == ''
