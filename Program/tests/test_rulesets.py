"""Rulesets (dungeon/sheet.py, dungeon/rules/srd52.py): chosen at campaign start and locked; 5E's sheet and checks."""
import random

import pytest
from conftest import Chunk, tell
from test_travel import ok

from dungeon import record, sheet, turn
from dungeon.rules import srd52


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def start(client, **body):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.delete('/api/story'))
    return client.post('/api/story/start', json=body)


def made(scores=None, skills=('perception', 'survival')):
    return {'class_id': 'fighter', 'species_id': 'dwarf', 'background_id': 'soldier',
            'scores': scores or {'str': 15, 'con': 14, 'dex': 13, 'wis': 12, 'int': 10, 'cha': 8},
            'skills': list(skills)}


def test_a_new_campaign_offers_the_rulesets_and_marvel_stays_the_default(client):
    choices = ok(client.get('/api/story/start'))
    assert [item['id'] for item in choices['rulesets']] == ['marvel', 'srd52', 'ironsworn', 'brp', 'narrative', 'fate'] and choices['ruleset'] == 'marvel'
    assert {'fighter', 'wizard'} <= {item['id'] for item in choices['srd52']['classes']}
    assert choices['srd52']['array'] == [15, 14, 13, 12, 10, 8] and 'SRD 5.2.1' in choices['srd52']['attribution']
    ok(start(client, premade_id='agna-holt'))
    assert ok(client.get('/api/story/sheet'))['ruleset'] == 'marvel'


def test_a_made_5e_character_takes_the_array_the_background_and_the_class(client):
    ok(start(client, persona={'name': 'Brann'}, ruleset='srd52', build=made()))
    view = ok(client.get('/api/story/sheet'))
    assert view['ruleset'] == 'srd52' and view['names'] == {'class': 'Fighter', 'species': 'Dwarf',
                                                           'background': 'Soldier', 'subclass': None}
    # Soldier raises the best of Str, Dex and Con by 2 and the next by 1.
    assert view['abilities'] == {'str': 17, 'con': 15, 'dex': 13, 'wis': 12, 'int': 10, 'cha': 8}
    assert (view['level'], view['proficiency'], view['max_hp'], view['ac']) == (1, 2, 12, 16)  # Chain Mail
    assert set(view['skills']) == {'athletics', 'intimidation', 'perception', 'survival'}
    assert view['skill_bonuses']['athletics']['bonus'] == 5 and view['skill_bonuses']['stealth']['bonus'] == 1
    assert 'SRD 5.2.1' in view['attribution']
    # The sheet is set when the character is made; Prospero's stepper does not change it.
    assert client.put('/api/story/sheet', json={'stats': {'Mind': 12}}).status_code == 409


@pytest.mark.parametrize(('build', 'detail'), [
    (made(scores={'str': 15, 'con': 15, 'dex': 13, 'wis': 12, 'int': 10, 'cha': 8}), 'standard array'),
    (made(skills=('athletics', 'survival')), 'Pick 2'),
    (made() | {'class_id': 'artificer'}, 'class'),
])
def test_a_5e_build_must_be_one_the_rules_allow(client, build, detail):
    response = start(client, persona={'name': 'Brann'}, ruleset='srd52', build=build)
    assert response.status_code == 422 and detail in response.json()['detail']


def test_a_premade_plays_under_5e_with_its_own_build(client):
    ok(start(client, premade_id='lirien-of-the-ford', ruleset='srd52'))
    view = ok(client.get('/api/story/sheet'))
    assert view['names'] == {'class': 'Rogue', 'species': 'Elf', 'background': 'Criminal', 'subclass': None}
    assert view['abilities']['dex'] == 17 and 'stealth' in view['skills']


def test_a_5e_check_rolls_a_d20_with_the_skill_against_the_dc():
    built = srd52.build('rogue', 'human', 'criminal', {'dex': 15, 'int': 14, 'con': 13, 'wis': 12, 'cha': 10,
                                                        'str': 8}, ['perception', 'investigation', 'deception', 'insight'])
    rng = random.Random(4)
    result = srd52.check(built, 'Luck', 'hard', 'I sneak past the guard', rng)
    # Stealth is Dex (17 after Criminal's +2): +3, and proficient: +2.
    assert (result['skill'], result['bonus'], result['target'], result['die']) == ('Stealth', 5, 15, 20)
    assert result['band'] == ('success' if result['total'] >= 15 else 'failure')
    # No skill in the words: the approach's ability. A save adds proficiency only in the class's saves.
    assert srd52.check(built, 'Allure', 'normal', 'I stand tall', rng)['skill'] == 'Charisma'
    assert srd52.check(built, 'Vitality', 'normal', rng=rng, save=True)['skill'] == 'Constitution save'
    assert srd52.check(built, 'Luck', 'normal', rng=rng, save=True)['bonus'] == 3 + 2
    bands = {srd52.check(built, 'Mind', 'normal', 'I search the desk', random.Random(seed))['band'] for seed in range(40)}
    assert bands == {'success', 'failure'}


def test_a_turn_under_5e_rolls_the_persona_on_their_5e_sheet(client, connected, provider, app):
    ok(start(client, persona={'name': 'Brann'}, ruleset='srd52', build=made()))
    ok(client.put('/api/settings', json={'show_odds': True}))
    provider.respond = lambda system, messages: reply('{"facts": []}') if system.startswith(record.EXTRACT) \
        else reply('You climb.')
    tell(client, 'I climb the wall.', 'story-0001')
    story = ok(client.get('/api/story'))
    rolled = next(message for message in story['messages'] if message['role'] == 'user')['rolls'][0]
    assert (rolled['ruleset'], rolled['skill'], rolled['die'], rolled['target']) == ('srd52', 'Athletics', 20, 12)
    assert rolled['bonus'] == 5 and rolled['band'] in ('success', 'failure')
    assert story['bands'] is None
    with app.state.database.connect() as connection:
        assert sheet.ruleset(connection) == 'srd52' and turn.bands('srd52') is None
