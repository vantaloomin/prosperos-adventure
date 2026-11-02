"""Narrative Only (dungeon/rules/narrative.py, dungeon/judge.py): no stats and no dice; a judge's verdict per action."""
import json

from conftest import Chunk, tell
from test_rulesets import start
from test_travel import ok

from dungeon import judge, story, story_clock, turn
from dungeon.rules import narrative
from dungeon.world import intimacy


def judging(provider, verdicts):
    """The judge answers with `verdicts`; everyone else gets a line of story."""
    def respond(system, messages):
        text = json.dumps({'verdicts': verdicts}) if system == judge.SYSTEM else 'The bar goes quiet.'
        return [Chunk(text), Chunk('', 'stop')]
    provider.respond = respond


def player(client, **extra):
    persona = {'name': 'Dale', 'about': 'Thirty-four, overweight, has not left his room in a year.'}
    ok(start(client, persona=persona, ruleset='narrative',
             narrative={'good_at': ['old games'], 'bad_at': ['talking to women']}, **extra))


def test_the_judge_decides_each_action_from_who_the_character_is(client, connected, provider, app):
    player(client)
    view = ok(client.get('/api/story/sheet'))
    assert (view['ruleset'], view['ruleset_name'], view['good_at'], view['bad_at']) == \
        ('narrative', 'Narrative', ['old games'], ['talking to women'])
    judging(provider, [{'verdict': 'no_but', 'reason': 'he opens with her looks; she does laugh at the joke'}])
    tell(client, 'I try to seduce the shopkeeper with my best line.', 'story-0001')
    asked = next(request for request in provider.requests if request['system'] == judge.SYSTEM)
    told = asked['messages'][-1]['content']
    assert 'overweight' in told and 'bad at talking to women' in told and 'seduce the shopkeeper' in told
    assert '## Scene' in told
    with app.state.database.connect() as connection:
        row = connection.execute('SELECT band, die, natural, ruleset, skill FROM story_rolls').fetchone()
    assert tuple(row) == ('failure_upside', 0, 0, 'narrative',
                          'No, but: he opens with her looks; she does laugh at the joke')
    narrator = [request for request in provider.requests if request['system'] != judge.SYSTEM][-1]['system']
    assert 'fails, but something useful comes out of the attempt. Why: he opens with her looks' in narrator


def test_no_roll_card_is_ever_shown_but_the_gm_view_sees_the_verdicts(client, connected, provider):
    player(client, table={'show_odds': True})
    judging(provider, [{'verdict': 'yes', 'reason': 'an easy ask'}])
    tell(client, 'I try to convince the shopkeeper to let me sleep in the back room.', 'story-0001')
    lines = [row for row in ok(client.get('/api/story'))['messages'] if row['role'] == 'user']
    assert 'rolls' not in lines[0] and not ok(client.get('/api/story'))['dice_shown']
    ok(client.put('/api/story/table', json={'gm_view': True}))
    lines = [row for row in ok(client.get('/api/story'))['messages'] if row['role'] == 'user']
    assert lines[0]['rolls'] and lines[0]['rolls'][0]['skill'].startswith('Yes')


def test_with_no_readable_verdict_the_difficulty_decides_without_dice():
    assert narrative.result(None, '', 'hard')['band'] == 'failure_upside'
    assert narrative.result('maybe', '', 'easy')['band'] == 'success'
    assert narrative.result('no', 'locked tight', 'easy')['skill'] == 'No: locked tight'
    assert judge.verdicts('{"verdicts": [{"verdict": "yes", "reason": "fine"}]}', 2) is None
    assert judge.verdicts('{"verdicts": [{"verdict": "sure"}]}', 1) == [{'verdict': None, 'reason': ''}]
    assert turn.judged_why({'ruleset': 'narrative', 'skill': 'Yes, but: costs him'}) == 'costs him'
    assert turn.judged_why({'ruleset': 'marvel', 'skill': 'x: y'}) == ''


def test_with_the_adult_side_on_the_judge_knows_who_the_people_here_are_drawn_to(client, connected, provider, app):
    player(client)
    judging(provider, [{'verdict': 'no', 'reason': 'not her type'}])
    tell(client, 'I try to seduce the shopkeeper with my best line.', 'story-0001')
    told = [request for request in provider.requests if request['system'] == judge.SYSTEM][-1]['messages'][-1]['content']
    assert 'drawn to' not in told
    ok(client.put('/api/settings', json={'adult_side': True}))
    tell(client, 'I try to seduce the shopkeeper again, with a joke this time.', 'story-0002')
    told = [request for request in provider.requests if request['system'] == judge.SYSTEM][-1]['messages'][-1]['content']
    with app.state.database.connect() as connection:
        people = story.scene(connection, story_clock.now(connection, app.state.database.clock))['people']
        expected = judge.attractions(connection, people)
    adults = [person for person in people if intimacy.for_sheet(person['sheet'])]
    assert bool(expected) == bool(adults)
    if adults:
        assert expected in told and adults[0]['sheet']['full'] in expected
    # Shown to nobody: not on the screen, and not in the narrator's prompt.
    narrator = [request for request in provider.requests if request['system'] != judge.SYSTEM][-1]['system']
    assert 'are drawn to' not in narrator


def test_who_someone_is_drawn_to_reads_in_a_line():
    found = {'orientation': 'bisexual', 'level': 'curious', 'drive': 'high',
             'interests': ['sharp-mind', 'deep-voice'], 'note': ''}
    said = intimacy.attraction_text(found)
    assert said.startswith('bisexual, drawn in by a sharp mind') and 'into ' in said and said.endswith('high drive')
    assert intimacy.attraction_text(None) == ''
