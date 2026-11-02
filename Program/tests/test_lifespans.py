"""Lifespans for elves and other long-lived people (dungeon/world/lifespans.py): a life age beside the real one."""
import copy

from dungeon.world import catalog, couples, dating, lifespans, looks, townsfolk, turnover

ELF = {'name': 'Aerin Leafmantle', 'identity': 'Aerin is an elf, 90. A quiet bookbinder. They/them.',
       'personality': 'Patient and dry.', 'timezone': 'UTC', 'home_city': 'baltimore'}


def connect(client, write=True):
    return client.app.state.database.connect(write=write)


def make(client, **changes) -> dict:
    response = client.post('/api/companion', json={**ELF, **changes})
    assert response.status_code == 200, response.text
    return client.get('/api/companion').json()['companion']


def test_life_age_is_the_real_age_for_a_human_and_stretched_after_childhood_for_others():
    assert [lifespans.life_age(age, 80) for age in (0, 9, 18, 34, 80, 101)] == [0, 9, 18, 34, 80, 101]
    assert [lifespans.life_age(age, 600) for age in (5, 17, 18, 100, 300, 550)] == [5, 17, 18, 27, 48, 75]
    assert lifespans.life_age(40, 55) == 55  # An orc is older at 40.
    assert lifespans.life_age(312, None) == 312 and lifespans.life_age(None, 600) is None
    for span in (55, 110, 180, 600, 1000):
        assert all(abs(lifespans.life_age(lifespans.real_age(life, span), span) - life) <= 1 for life in range(18, 90))
    assert lifespans.real_age(48, 600) == 300 and lifespans.real_age(12, 600) == 12


def test_kinds_come_from_their_own_words_never_from_a_word_inside_another_or_said_with_not():
    words = lifespans.from_words
    assert words('A half-elf ranger with a scar.') == 'half-elf' and words('Her elven ears twitch.') == 'elf'
    assert words('Stout, bearded, a dwarf of the iron hills.') == 'dwarf'
    assert words('She is not an elf, whatever her ears say.') == 'human'
    assert words('Keeps herself to a shelf of books.') == 'human' and words('') == 'human'
    assert lifespans.sheet_kind({'identity': 'An accountant.', 'kind': 'orc'}) == 'orc'
    assert lifespans.sheet_kind({'identity': 'An elf.', 'kind': 'nonsense'}) == 'elf'
    assert lifespans.sheet_lifespan({'identity': 'An elf.', 'lifespan': 1000}) == 1000
    assert lifespans.ageless({'identity': 'An immortal scholar.'}) and not lifespans.ageless(ELF)


def test_a_child_of_two_kinds_takes_a_listed_blend_else_the_longer_lived_parent():
    assert lifespans.blend('elf', 'human') == 'half-elf' and lifespans.blend('human', 'elf') == 'half-elf'
    assert lifespans.blend('dwarf', 'dwarf') == 'dwarf' and lifespans.blend('dwarf', 'halfling') == 'dwarf'
    assert lifespans.blend('orc', None) == 'half-orc' and lifespans.blend('orc', 'goblin') == 'orc' and lifespans.blend('ageless', 'elf') == 'ageless'


def test_grandport_elves_are_often_centuries_old_and_the_same_seed_gives_the_same_person():
    data = catalog.city('grandport')
    assert data['names']['groups']['elven']['kind'] == 'elf' and not data.get('import_notes')
    elves = [seed for seed in (f'town:grandport:test:{n}' for n in range(4000)) if townsfolk.folk_of(data, seed) == 'elf']
    assert elves and all(townsfolk.folk_of(data, seed) == 'human' for seed in ('a', 'b') if seed not in elves)
    real = [townsfolk.seeded_real_age(data, seed, True) for seed in elves]
    assert max(real) > 100 and real == [townsfolk.seeded_real_age(data, seed, True) for seed in elves]
    # Their job and retiring follow their age in human terms: nobody's turned away for being 300.
    assert all(lifespans.life_age(age, 600) <= 84 for age in real)
    # A city with no long-lived people never pays for working out kinds in turnover.
    assert townsfolk.lifespan_of_seed(catalog.city('baltimore')) is None
    assert townsfolk.lifespan_of_seed(data)(elves[0]) == 600


def test_a_long_lived_townsperson_seldom_retires_or_passes_away():
    old_human = turnover.chances('staff', 70, 2, 3)
    elf_of_400 = turnover.chances('staff', lifespans.life_age(400, 600), 2, 3)
    assert elf_of_400['passed'] < old_human['passed'] / 2 and elf_of_400['retired'] == 0.0
    levels = ((), 2, 3, 2)
    left = [turnover.tenure(f's{n}', 'staff', 70, turnover.START_WEEK, levels) for n in range(300)]
    stayed = [turnover.tenure(f's{n}', 'staff', 400, turnover.START_WEEK, levels, 'modern', 600) for n in range(300)]
    passed = sum(1 for item in left if item and item[1] in ('passed', 'retired'))
    assert sum(1 for item in stayed if item and item[1] in ('passed', 'retired')) < passed / 3


def test_partner_details_and_town_couples_go_by_age_in_human_terms():
    data = catalog.city('grandport')
    sheet = {**townsfolk.resident(data, 'gran-porte', 3), 'age': 300, 'folk': 'elf'}
    found = dating.details(sheet, data)
    assert found['life'] == 48 and found['age_range'][1] <= 60
    partner = couples.partner(sheet, data, 0, found)
    assert 38 <= lifespans.life_age(partner['age'], lifespans.lifespan_of(partner.get('folk'), data)) <= 58


def test_a_city_file_can_change_a_lifespan_and_add_a_kind_and_a_bad_entry_is_dropped():
    raw = copy.deepcopy(catalog.city('grandport'))
    for key in ('data_version', 'import_notes'):
        raw.pop(key, None)
    raw['kinds'] = {'elf': {'lifespan': 750}, 'cyclops': {'label': 'Cyclops', 'lifespan': 110, 'words': ['cyclops']},
                    'colossus': {'label': 'Colossus', 'lifespan': 9000, 'words': ['colossus']},
                    'sprite': {'lifespan': 30}, 'nameless': {'lifespan': 200}}
    raw['names']['groups']['pictish']['kind'] = 'cyclops'
    raw['names']['groups']['far-voyagers']['kind'] = 'ghoul'
    data = catalog.prepare(raw, mend=True)
    assert data['kinds'] == {'elf': {'lifespan': 750},
                             'cyclops': {'label': 'Cyclops', 'lifespan': 110, 'words': ['cyclops']}}
    notes = ' '.join(data['import_notes'])
    assert all(word in notes for word in ('colossus', 'sprite', 'nameless', 'ghoul'))
    assert 'kind' not in data['names']['groups']['far-voyagers']
    assert lifespans.lifespan_of('elf', data) == 750 and lifespans.lifespan_of('elf') == 600
    assert lifespans.from_words('A cyclops bard.', data) == 'cyclops' and lifespans.from_words('A cyclops.') == 'human'
    assert lifespans.of_group(data, 'pictish') == 'cyclops'
    # The user's own pick wins over the city's.
    assert lifespans.lifespan_of('elf', data, 300) == 300


def test_milestone_birthdays_are_round_hundreds_and_fifties_for_a_long_lived_kind():
    assert [age for age in range(18, 120) if lifespans.milestone(age)] == [30, 40, 50, 60, 70, 80, 90, 100, 110]
    assert [age for age in range(18, 420) if lifespans.milestone(age, 600)] == [100, 150, 200, 250, 300, 350, 400]
    assert lifespans.milestone(40, 110) and not lifespans.milestone(40, 180) and lifespans.milestone(150, None)


def test_a_three_digit_age_is_read_only_for_a_long_lived_kind_and_drawn_the_age_they_look():
    assert looks.age_of({'identity': 'Aerin is an elf, 312. A bookbinder.'}, 's') == 312
    assert looks.age_of({'identity': 'A 450-year-old dwarf smith.'}, 's') == 450
    assert looks.age_of({'identity': 'She is 312 days sober, a 34-year-old nurse.'}, 's') == 34
    elf = looks.picture({'age': 312, 'looks_age': 48, 'pronouns': 'they/them'}, 'Aerin')
    assert 'forties' in elf and 'three hundred' not in elf


def test_a_city_file_whose_kinds_block_is_the_wrong_shape_still_loads():
    for block in ({'elf': 750}, [{'elf': {'lifespan': 750}}], 'elves'):
        raw = copy.deepcopy(catalog.city('grandport'))
        for key in ('data_version', 'import_notes', 'builtin', 'origin'):
            raw.pop(key, None)
        raw['kinds'] = block
        data = catalog.prepare(raw, mend=True)
        assert 'kinds' not in data and any('kind' in note for note in data['import_notes'])
        assert lifespans.lifespan_of('elf', data) == 600


def test_a_city_file_cannot_change_how_long_humans_live_or_make_doesnt_age_age():
    raw = copy.deepcopy(catalog.city('grandport'))
    for key in ('data_version', 'import_notes', 'builtin', 'origin'):
        raw.pop(key, None)
    raw['kinds'] = {'human': {'lifespan': 120}, 'ageless': {'lifespan': 500}, 'elf': {'lifespan': 750}}
    data = catalog.prepare(raw, mend=True)
    assert data['kinds'] == {'elf': {'lifespan': 750}}
    notes = ' '.join(data['import_notes'])
    assert '"human"' in notes and '"ageless"' in notes
    assert lifespans.lifespan_of('human', data) == 80 and lifespans.lifespan_of('ageless', data) is None
    assert lifespans.sheet_lifespan({'identity': 'A baker.'}, data) == 80


def test_a_new_persona_can_be_made_an_elf(client):
    made = client.post('/api/worlds/personas', json={'name': 'Lorien', 'age': 250, 'kind': 'elf'})
    assert made.status_code == 200, made.text
    assert made.json()['kind'] == 'elf' and made.json()['age'] == 250
    assert client.post('/api/worlds/personas', json={'name': 'Tom', 'age': 250}).status_code == 422


def test_a_typed_persona_age_stays_adult_and_whole(client):
    for age in (17, 0, -3, 30.5, 5001):
        assert client.post('/api/worlds/personas', json={'name': 'Tom', 'age': age}).status_code == 422, age
    assert client.post('/api/worlds/personas', json={'name': 'Tom', 'age': 18}).status_code == 200


def test_an_elfs_partner_details_give_their_age_in_human_terms():
    data = catalog.city('grandport')
    elf = {**townsfolk.resident(data, 'gran-porte', 3), 'age': 225, 'folk': 'elf'}
    assert dating.details(elf, data)['life'] == dating.life_of(elf, data) == 40
    human = {**townsfolk.resident(data, 'gran-porte', 3), 'age': 34, 'folk': 'human'}
    assert dating.details(human, data)['life'] == 34


