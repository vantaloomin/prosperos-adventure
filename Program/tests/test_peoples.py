"""The peoples of fantasy worlds (scripts/world/peoples.py): a kind and a naming scheme for each, and towns that mix
them with their human folk by the share of each kind (a city's `kinds` block, dungeon/world/lifespans.py)."""
import json
import runpy
from collections import Counter
from pathlib import Path

from dungeon.world import catalog, generators, lifespans, naming, townsfolk

SCRIPTS = Path(__file__).parent.parent / 'scripts' / 'world'
PEOPLES = catalog.names()['banks']['peoples']


def raw(key: str = 'baltimore', **changes) -> dict:
    data = catalog.city(key) | changes
    return {field: value for field, value in data.items()
            if field not in ('data_version', 'builtin', 'origin', 'import_notes')}


def town(kinds: dict) -> dict:
    return catalog.prepare(raw('kingswood', era='medieval', names={'bank': 'medieval'}, kinds=kinds), mend=True)


def test_the_shipped_bank_and_kinds_match_their_script():
    made = runpy.run_path(str(SCRIPTS / 'names.py'))
    written = json.loads((catalog.DATA / 'names.json').read_text(encoding='utf-8'))
    assert made['NAMES']['banks']['peoples'] == written['banks']['peoples'], 'Rerun scripts/world/names.py.'
    assert made['peoples'].lifespans() == lifespans.table(), 'Rerun scripts/world/names.py.'


def test_every_people_has_its_own_kind_and_a_hundred_given_and_family_names():
    kinds = lifespans.kinds()
    assert len(PEOPLES) >= 70
    for key in ('wolf-kin', 'fox-kin', 'cat-kin', 'naga', 'minotaur', 'rabbit-kin', 'stag-kin', 'bear-kin', 'owl-kin',
                'dragon-kin', 'high-elf', 'wood-elf', 'dark-elf', 'sea-elf', 'dwarf', 'orc', 'half-orc', 'goblin',
                'hobgoblin', 'halfling', 'gnome', 'ogre', 'troll', 'giant', 'half-giant', 'tiefling', 'succubus',
                'demon-blooded', 'merfolk', 'sea-kin', 'oni', 'tengu', 'kappa', 'mind-eater', 'centaur', 'dryad',
                'fae', 'lizardfolk', 'kobold', 'gnoll', 'clockwork-folk'):
        group = PEOPLES[key]
        given = {*group['feminine'], *group['masculine'], *group['neutral']}
        assert len(given) >= 100 and len(set(group['family'])) >= 100, key
        assert group['kind'] == key and kinds[key]['label'] and kinds[key]['folk'], key
    assert kinds['elf']['lifespan'] == 600 and kinds['fae']['lifespan'] is None and kinds['orc']['lifespan'] == 55


def test_no_peoples_name_reads_as_made_up_by_a_model():
    for key, group in PEOPLES.items():
        for field in ('feminine', 'masculine', 'neutral', 'family'):
            words = [word for name in group[field] for word in naming.WORD.findall(name)]
            assert not [word for word in words if word.casefold() in naming.invented()
                        or naming.COINED_GIVEN.search(word) or naming.COINED_FAMILY.search(word)], (key, field)


def test_own_words_name_a_people_and_no_two_kinds_share_a_word():
    words = lifespans.from_words
    assert words('A wolf-kin tracker with a torn ear.') == 'wolf-kin' and words('a drow exile') == 'dark-elf'
    assert words('She is a dark elf.') == 'dark-elf' and words('a plain elf') == 'elf'
    assert words('Half-orc, and proud of it.') == 'half-orc' and words('an orcish brute') == 'orc'
    assert words('A tiefling with ram horns.') == 'tiefling' and words('the last centaur') == 'centaur'
    # Animals and things are not peoples: keeping a cat or a clockwork toy says nothing about who you are.
    assert words('Keeps a cat and a clockwork toy; likes giant sandwiches.') == 'human'
    named = Counter(word.casefold() for kind in lifespans.kinds().values() for word in kind['words'])
    assert not [word for word, count in named.items() if count > 1]


def test_a_half_orc_is_born_of_a_human_and_an_orc():
    assert lifespans.blend('orc', 'human') == 'half-orc' and lifespans.blend('human', 'giant') == 'half-giant'


def test_a_towns_shares_bring_its_peoples_named_from_their_own_groups():
    data = town({'dwarf': {'share': 0.2}, 'wolf-kin': {'share': 0.1}})
    drawn = Counter(townsfolk.folk_of(data, f'seed-{index}') for index in range(1000))
    assert set(drawn) == {'human', 'dwarf', 'wolf-kin'} and drawn['human'] > drawn['dwarf'] > drawn['wolf-kin'] > 60
    for index in range(200):
        seed = f'seed-{index}'
        kind, person = townsfolk.folk_of(data, seed), generators.name(data, seed=seed)
        if kind == 'human':
            assert person['group'] in catalog.names()['eras']['medieval']['mix']
        else:
            assert person['group'] == kind and person['family'] in PEOPLES[kind]['family']
        assert not naming.is_invented(person['full'])
    # Wolf-kin live their kind's years.
    wolf = next(f'seed-{index}' for index in range(1000) if townsfolk.folk_of(data, f'seed-{index}') == 'wolf-kin')
    assert townsfolk.lifespan_of_seed(data)(wolf) == 70


def test_the_peoples_bank_names_a_whole_town_of_other_peoples():
    data = catalog.prepare(raw(names={'bank': 'peoples', 'mix': {'orc': 3, 'goblin': 1}}))
    assert {townsfolk.folk_of(data, f'o-{index}') for index in range(80)} == {'orc', 'goblin'}
    orc = next(generators.name(data, seed=f'o-{index}') for index in range(80)
               if townsfolk.folk_of(data, f'o-{index}') == 'orc')
    assert orc['family'] in PEOPLES['orc']['family']
