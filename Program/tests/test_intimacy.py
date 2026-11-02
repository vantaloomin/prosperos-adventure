"""The adult side of life (dungeon/world/intimacy.py): adults only, off by default, in their own prompt only."""
import json
import re
from collections import Counter

from dungeon.world import catalog, dating, intimacy, townsfolk

# Themes the bank must never touch: anyone under 18, anything without consent, family, animals, real people,
# and anything illegal or done to someone who can't say yes.
BANNED = re.compile(r'\b(minor|child|kid|teen|young|underage|school|student|age ?play|daddy|little|incest|step|'
                    r'sister|brother|mother|father|family|cousin|animal|beast|pet|non-?con|rape|forc|force|coerc|'
                    r'blackmail|drunk|asleep|sleeping|unconscious|drug|hidden|secretly|spy|public|stranger|'
                    r'celebrity|real person|blood|knife|choke|chok)', re.IGNORECASE)


def preview(client):
    return client.get('/api/context/preview').json()['prompt']


def revise(client, **changes):
    current = client.get('/api/companion').json()['companion']
    response = client.post('/api/companion/versions', json={'definition': {**current['version']['definition'], **changes},
                                                             'expected_version_id': current['active_version_id']})
    assert response.status_code == 200, response.text


def test_the_bank_only_holds_things_between_consenting_adults():
    data = json.loads((catalog.DATA / 'intimacy.json').read_text(encoding='utf-8'))
    for entry in data['interests'] + data['levels'] + data['drives']:
        words = f"{entry['id']} {entry['label']} {entry['text']}"
        assert not BANNED.search(words), words
    assert {entry['tier'] for entry in data['interests']} == {1, 2, 3}
    assert len({entry['id'] for entry in data['interests']}) == len(data['interests'])
    groups = {group['id'] for group in data['groups']}
    assert all(entry['group'] in groups for entry in data['interests'])
    assert {entry['group'] for entry in data['interests']} == groups


def test_every_townsperson_is_an_adult_and_rolls_the_same_every_time():
    data = catalog.city('baltimore')
    sheets = [townsfolk.person(data, place, index) for place in data['places'][:40] for index in range(3)]
    sheets += townsfolk.residents(data, data['neighborhoods'][0]['id'])
    assert sheets and all(sheet['age'] >= 18 for sheet in sheets)
    for sheet in sheets:
        found = intimacy.for_sheet(sheet)
        assert found == intimacy.for_sheet(sheet)
        # The same orientation their partner details have.
        assert found['orientation'] == dating.details(sheet, data)['orientation']


def test_most_people_are_in_the_middle_and_the_level_caps_what_they_are_into():
    tiers = {entry['id']: entry['tier'] for entry in intimacy.bank()['interests']}
    rolls = [intimacy.roll(f'seed-{n}', 35, 'man') for n in range(3000)]
    levels = Counter(found['level'] for found in rolls)
    assert set(levels) == set(intimacy.DRAWS)
    assert levels['curious'] > levels['adventurous'] > levels['wild']
    assert levels['conventional'] > levels['reserved']
    qualities = {entry['id'] for entry in intimacy.bank()['interests'] if entry['group'] == intimacy.QUALITIES}
    for found in rolls:
        count, boldest = intimacy.DRAWS[found['level']]
        doing = [entry for entry in found['interests'] if entry not in qualities]
        assert len(doing) <= count and all(tiers[entry] <= boldest for entry in doing)
        # At most one thing that draws them in ("a sharp mind"), whatever the level.
        assert len(found['interests']) - len(doing) <= 1
    assert all(not set(found['interests']) - qualities for found in rolls if found['level'] == 'reserved')
    drawn = sum(bool(set(found['interests']) & qualities) for found in rolls) / len(rolls)
    assert 0.3 < drawn < 0.5


def test_adding_what_draws_them_in_left_everyone_s_earlier_picks_alone():
    qualities = {entry['id'] for entry in intimacy.bank()['interests'] if entry['group'] == intimacy.QUALITIES}
    assert {'sharp-mind', 'quick-wit', 'kindness'} <= qualities
    # The draw before the qualities were added, pinned for a few seeds.
    assert {seed: sorted(set(intimacy.roll(seed, 35, 'woman')['interests']) - qualities) for seed in ('a', 'b', 'c')} \
        == {'a': ['deep-voice', 'strong-arms'], 'b': ['hair-stroking', 'quickies'], 'c': ['deep-voice', 'paddle', 'sex-dice']}


def test_an_age_is_read_however_it_is_written():
    for text in ('Madison is 17 and posts videos.', "I'm 16, bored at home.", "She's seventeen."):
        assert intimacy.reads_as_minor({'identity': text}), text
        assert intimacy.own_age({'identity': text}) < 18
    for text in ('Ashley is 20 and runs a page.', 'Her shift is 9-5.', "She's 5'4\" with dark hair."):
        assert not intimacy.reads_as_minor({'identity': text}), text
    assert intimacy.own_age({'identity': 'Dana is 41 and raising a 15-year-old.'}) == 41


def test_a_few_more_sheet_wordings_read_the_same_way():
    for text in ('An elf, 150, who looks about twelve.', 'A dwarf, 90, a youngling by the reckoning of her kin.',
                 'An elf of 150 years, still a child among her people.', 'An elf, 120, not yet of age.'):
        assert intimacy.reads_as_minor({'identity': text}), text
    for text in ('Aerin is an elf, 312. Looks about 48.', 'She has an elf child of her own, 312.',
                 'A 40-year-old who looks 5 years younger.', 'Mira, 29. Looks after a child among the refugees.'):
        assert not intimacy.reads_as_minor({'identity': text}), text


def test_nobody_under_18_gets_one():
    assert intimacy.roll('someone', 17, 'woman') is None
    assert intimacy.roll('someone', None, 'woman') is None
    assert intimacy.roll('someone', True, 'woman') is None
    assert intimacy.roll('someone', 18, 'woman') is not None
    for text in ('A 17-year-old barista.', 'Aged 16, loves skating.', 'A high school student.', 'Age: 15.',
                 'Still a teenager.', 'An underage runaway.'):
        assert intimacy.reads_as_minor({'identity': text}), text
    assert not intimacy.reads_as_minor({'identity': '34, a nurse. Moved here at 12.', 'background': 'As a teen she ran.'})


def test_the_ways_people_write_a_young_age_all_read_as_under_18():
    for text in ('June Park, 16. She works weekends at a bakery.', '16. Works as a barista.', 'Mia Lane, 16.',
                 'Sixteen years old and restless.', 'A 16 y.o. skater.', 'A junior at Poly High.', 'Freshman, 17',
                 'She is in eleventh grade.', 'An 11th grader who skates.'):
        assert intimacy.reads_as_minor({'identity': text}), text
    for text in ('Mira Okafor, 29. Works as a nurse.', '28. Works as a barista.', 'She teaches tenth grade at Poly.',
                 'A senior at a high-rise firm.', 'Born 1990, she works at the docks.'):
        assert not intimacy.reads_as_minor({'identity': text}), text
    assert intimacy.stated_ages({'identity': 'Mira Okafor, 29. Works as a nurse.'}) == [29]
