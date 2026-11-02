"""Local politics (dungeon/world/politics.py, dungeon/politics.py): issues a town argues about, people's views and the
factions behind them, all seeded, with the world's powers (dungeon/factions.py) as the town's first factions and the
player's changes on top."""
from datetime import date, timedelta

import pytest
from conftest import tell
from test_inventory import begin
from test_travel import ok, reply

from dungeon import factions
from dungeon import politics as town_politics
from dungeon.world import catalog, politics

DAY = date(2026, 12, 10)


# --- The banks ---

def test_the_banks_hold_enough_and_every_blank_can_be_filled():
    data = politics.bank()
    assert len(data['local']) >= 100
    assert set(data['eras'].values()) == set(data['styles']) == set(data['questions']) == set(data['factions'])
    tags = {tag for group in data['factions'].values() for faction in group for tag in faction['tags']}
    for template in data['local']:
        assert len(template['sides']) == 2 and template['styles'], template['id']
        assert set(template['beats']) == {'whispers', 'open', 'heated', 'won', 'lost', 'fizzled'}, template['id']
        assert politics.needs(template) <= {'office', 'office2', 'institution', 'trade', 'place', 'hood', 'person'}
        for side in template['sides']:
            assert set(side.get('jobs', [])) <= set(data['jobs']), template['id']
            assert set(side.get('words', [])) <= set(data['words']), template['id']
            assert set(side.get('backers', [])) <= tags, template['id']
    for style, questions in data['questions'].items():
        assert questions and all(len(item['sides']) == 2 for item in questions), style
    # Every world faction reads as some side of town life.
    assert {tag for kind in data['world_kinds'].values() for tag in kind} <= tags
    assert {tag for kind in data['world_tags'].values() for tag in kind} <= tags
    for world in ('vallarith', 'havenbrooke', 'babel'):
        for power in factions.factions(world):
            assert politics.from_power(power)['tags'], (world, power['id'])


def test_a_citys_politics_block_drops_what_is_broken_and_keeps_the_rest():
    data = {'politics': {'factions': [{'id': 'reds', 'name': 'The Reds', 'pull': 9}, {'name': 'no id'}],
                         'questions': [{'id': 'q', 'title': 'Q', 'sides': [{'name': 'Yes'}]}],
                         'issues': [{'id': 'i', 'title': 'The well', 'sides': [{'name': 'Dig'}, {'name': 'Wait'}],
                                     'beats': {'whispers': 'Dry again.'}}]}}
    notes = politics.clean(data)
    assert [faction['pull'] for faction in data['politics']['factions']] == [5]
    assert data['politics']['questions'] == [] and len(data['politics']['issues']) == 1
    assert len(notes) == 2
    assert politics.clean({'politics': 'nonsense'}) and politics.clean({}) == []


# --- Factions: the world's powers first ---

def test_the_powers_holding_a_town_are_its_first_factions_and_the_era_fills_the_gaps():
    data = catalog.city('kingswood')
    held = factions.local('vallarith', 'kingswood')
    found = politics.factions(data, held)
    assert [item['id'] for item in found[:len(held)]] == [power['id'] for power in held]
    assert all(item['origin'] == 'world' for item in found[:len(held)])
    cyrel = next(item for item in found if item['id'] == 'kingdom-of-cyrel')
    assert cyrel['pull'] == 4 and 'crown' in cyrel['tags'] and 'cyrel-timber-guild' in cyrel['allies']
    # The realm is the crown, the council and the law, and the timber guild the guilds: only the town groups none
    # of the powers covers come from the era.
    era = {item['id'] for item in found if item['origin'] == 'era'}
    assert era and not era & {'the-council', 'the-watch', 'merchant-guilds'}
    assert 'the-temple' in era
    # Named allies and rivals are where two factions start.
    elves = next(item for item in found if item['id'] == 'brynwyr-high-elves')
    assert politics.base_stance(cyrel, elves) == -1
    assert politics.base_stance(cyrel, next(item for item in found if item['id'] == 'cyrel-timber-guild')) == 2


# --- Issues ---

def test_issues_are_seeded_the_same_way_every_time():
    data = catalog.city('chicago')
    first = politics.seeded_locals(data, DAY, 2, 1)
    politics._SEEDED.clear()
    assert politics.seeded_locals(data, DAY, 2, 1) == first
    assert first and all(issue['dates']['whispers'] < issue['dates']['open'] < issue['dates']['heated']
                         < issue['dates']['settled'] for issue in first)
    assert all('{' not in issue['title'] + issue['question'] for issue in first)


def test_a_new_year_does_not_change_the_issues_still_talked_about():
    data = catalog.city('chicago')
    december = {issue['id']: issue for issue in politics.seeded_locals(data, date(2026, 12, 31), 2, 1)}
    january = politics.seeded_locals(data, date(2027, 1, 1), 2, 1)
    talked = [issue for issue in january if politics.live(issue, date(2027, 1, 1))]
    assert talked and all(december.get(issue['id']) == issue for issue in talked)


def test_more_drama_and_livelier_politics_start_more_local_issues():
    data = catalog.city('london')
    later = DAY + timedelta(days=330)
    quiet = len(politics.seeded_locals(data, later, 1, 0))
    lively = len(politics.seeded_locals(data, later, 3, 3))
    assert lively > quiet * 2
    assert politics.era_issues(data, DAY, 0) == [] and len(politics.era_issues(data, DAY, 3)) == 3


def test_a_real_city_keeps_the_questions_of_its_year():
    data = catalog.city('new-york-1925')
    assert 'Prohibition' in [issue['title'] for issue in politics.era_issues(data, DAY, 2)]
    made_up = catalog.city('pellmouth')
    assert 'Prohibition' not in [question['title'] for question in politics.era_questions(made_up, DAY)]


def test_a_stage_the_player_picks_holds_and_pushes_later_stages_back():
    dates = {'whispers': '2026-10-01', 'open': '2026-10-10', 'heated': '2026-11-01', 'settled': '2026-11-20'}
    found = town_politics.staged(dates, 'heated', date(2026, 10, 12))
    assert found == {'whispers': '2026-10-01', 'open': '2026-10-10', 'heated': '2026-10-12', 'settled': '2026-11-20'}
    found = town_politics.staged(dates, 'whispers', date(2026, 10, 15))
    assert found['open'] == '2026-10-16' and found['heated'] == '2026-11-07' and found['settled'] == '2026-11-26'


# --- Views ---

def test_views_follow_work_and_character():
    issue = politics.era_issue(catalog.city('new-york-1925'), next(
        item for item in politics.bank()['questions']['jazz'] if item['id'] == 'prohibition'), DAY)

    def person(key, job):
        return {'key': key, 'jobs': politics.jobs_of(job), 'groups': set(), 'age': 40}
    police = [politics.view_of(person(f'p{n}', 'police officer'), issue, [], []) for n in range(80)]
    barkeeps = [politics.view_of(person(f'b{n}', 'bartender'), issue, [], []) for n in range(80)]
    assert sum(view < 0 for view in police) > 50  # Dry is the second side.
    assert sum(view > 0 for view in barkeeps) > 50
    assert politics.view_text(2, issue) == 'wants to see Prohibition repealed, and says so'
    assert politics.view_label(-1, issue) == 'Leans: Dry'


# --- In play ---

def test_talk_of_the_town_in_kingswood_backs_sides_with_the_worlds_powers(client):
    begin(client)
    assert ok(client.get('/api/story'))['politics'] is True
    found = ok(client.get('/api/story/politics'))
    assert found['city']['id'] == 'kingswood' and found['level'] == 2 and found['level_name'] == 'true_to_life'
    assert found['issues'] and all(sum(issue['split'].values()) > 20 for issue in found['issues'])
    powers = {item['id'] for item in found['factions'] if item['power']}
    assert powers == {power['id'] for power in factions.local('vallarith', 'kingswood')}
    assert any(issue['lines'][power] is not None for issue in found['issues'] for power in powers)
    # Nobody met yet; the odds of a settled issue stay hidden with the dice hidden.
    assert found['people'] == []
    for issue in found['issues']:
        assert not issue['settled'] or 'odds' not in issue['settled']['options'][0]
    assert ok(client.get('/api/story/politics')) == found


def test_the_player_can_change_views_issues_and_factions(client):
    begin(client)
    found = ok(client.get('/api/story/politics'))
    era = next(item['id'] for item in found['issues'] if item['kind'] == 'era')
    found = ok(client.put('/api/story/politics/views', json={'issue': era, 'person': 'town:kingswood:~x:0',
                                                             'view': -2}))
    found = ok(client.post('/api/story/politics/issues', json={'title': 'The new mill', 'sides': ['Build it', 'No mill'],
                                                               'stands': ['build the mill', '']}))
    mine = next(item for item in found['issues'] if item['title'] == 'The new mill')
    assert mine['origin'] == 'user' and mine['stage'] == 'open' and mine['sides'][1]['stand'] == 'side with No mill'
    found = ok(client.patch(f"/api/story/politics/issues/{mine['id']}", json={'stage': 'heated', 'question': 'A mill?'}))
    assert next(item for item in found['issues'] if item['id'] == mine['id'])['stage'] == 'heated'
    found = ok(client.patch(f"/api/story/politics/issues/{mine['id']}", json={'outcome': 0}))
    assert next(item for item in found['issues'] if item['id'] == mine['id'])['stage'] == 'settled'
    found = ok(client.delete(f"/api/story/politics/issues/{mine['id']}"))
    assert mine['id'] not in [item['id'] for item in found['issues']]

    assert client.patch(f'/api/story/politics/issues/{era}', json={'outcome': 0}).status_code == 422
    assert client.patch(f'/api/story/politics/issues/{era}', json={'stage': 'heated'}).status_code == 422
    found = ok(client.patch(f'/api/story/politics/issues/{era}', json={'sides': ['Yes', 'No']}))
    assert [side['name'] for side in next(item for item in found['issues'] if item['id'] == era)['sides']] == \
        ['Yes', 'No']
    found = ok(client.delete(f'/api/story/politics/issues/{era}'))
    assert era not in [item['id'] for item in found['issues']]

    found = ok(client.post('/api/story/politics/factions', json={'name': 'The Mill Wives', 'pull': 1}))
    wives = next(item for item in found['factions'] if item['name'] == 'The Mill Wives')
    found = ok(client.patch(f"/api/story/politics/factions/{wives['id']}", json={'pull': 3}))
    assert next(item for item in found['factions'] if item['id'] == wives['id'])['pull'] == 3
    found = ok(client.put('/api/story/politics/relations', json={'a': 'kingdom-of-cyrel', 'b': wives['id'],
                                                                 'stance': 2}))
    assert any({link['a'], link['b']} == {'kingdom-of-cyrel', wives['id']} and link['stance'] == 2
               and link['by'] == 'you' for link in found['relations'])
    # A world power renamed or put away here changes only in this town's talk.
    found = ok(client.patch('/api/story/politics/factions/kingdom-of-cyrel', json={'name': 'The Crown'}))
    assert 'The Crown' in [item['name'] for item in found['factions']]
    assert factions.find('vallarith', 'kingdom-of-cyrel')['name'] == 'The Kingdom of Cyrel'
    found = ok(client.delete('/api/story/politics/factions/kingdom-of-cyrel'))
    assert 'kingdom-of-cyrel' not in [item['id'] for item in found['factions']]
    assert client.patch('/api/story/politics/factions/nobody', json={'name': 'X'}).status_code == 404

    # A new story starts the town's talk afresh.
    ok(client.delete('/api/story'))
    assert 'kingdom-of-cyrel' in [item['id'] for item in ok(client.get('/api/story/politics'))['factions']]


def test_turning_local_politics_off_empties_talk_of_the_town(client):
    begin(client)
    ok(client.put('/api/story/table', json={'politics': 'off'}))
    found = ok(client.get('/api/story/politics'))
    assert found['level'] == 0 and found['issues'] == [] and found['factions'] == []
    assert ok(client.get('/api/story'))['politics'] is False


@pytest.mark.usefixtures('connected')
def test_the_narrator_hears_what_the_town_argues_about(client, provider):
    begin(client)
    issues = ok(client.get('/api/story/politics'))['issues']
    reply(provider, 'The talk in the shop is all of one thing.')
    tell(client, 'I listen to the talk.', 'politics-1')
    narrator = provider.requests[-1]['system']
    assert '## Talk of the town' in narrator and 'never decide how an open issue ends' in narrator
    assert all(issue['title'] in narrator for issue in issues)
    assert 'Backing ' in narrator


@pytest.mark.usefixtures('connected')
def test_the_narrator_hears_nothing_with_politics_off(client, provider):
    begin(client)
    ok(client.put('/api/story/table', json={'politics': 'off'}))
    reply(provider, 'Quiet today.')
    tell(client, 'I listen to the talk.', 'politics-2')
    assert '## Talk of the town' not in provider.requests[-1]['system']
