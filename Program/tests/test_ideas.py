"""Ideas (dungeon/ideas.py): two or three things the character could do now, used once and never kept, from what the
character knows only."""
import json

from conftest import tell
from test_pace import ok, reply

from dungeon import ideas, record

PICKS = ['I ask the cellarman about the zebra-striped barge.', 'I climb onto the quince-stacked roof.',
         'I wait by the marmalade door and watch.']


def ask(client):
    return ok(client.post('/api/story/ideas'))


def every_text(app) -> str:
    """Every text value in every table, for checking what was kept."""
    with app.state.database.connect() as connection:
        tables = [row['name'] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return '\n'.join(str(value) for table in tables for row in connection.execute(f'SELECT * FROM "{table}"')
                         for value in tuple(row) if isinstance(value, str))


def test_ideas_come_from_the_model_as_actions_and_nothing_is_kept(client, connected, provider, app):
    tell(client, 'I step inside out of the rain.', 'ideas-0001')
    provider.replies = [reply(json.dumps(PICKS))]
    found = ask(client)
    assert found['ideas'] == PICKS and found['turn'] == 2
    asked = provider.requests[-1]
    assert asked['system'] == ideas.SYSTEM and len(asked['messages']) == 1
    assert 'I step inside out of the rain.' in asked['messages'][0]['content']
    assert not any(pick in every_text(app) for pick in PICKS)


def test_unsent_ideas_never_reach_another_prompt_or_the_next_ideas(client, connected, provider, app):
    tell(client, 'I step inside out of the rain.', 'ideas-0001')
    provider.replies = [reply(json.dumps(PICKS))]
    ask(client)
    since = len(provider.requests)
    provider.replies = [reply('The cellarman shrugs.')]
    tell(client, 'I order a drink.', 'ideas-0002')
    provider.replies = [reply(json.dumps(['I pay and leave.', 'I ask for a room.']))]
    ask(client)
    later = json.dumps([{'system': request['system'], 'messages': request['messages']}
                        for request in provider.requests[since:]])
    assert not any(word in later for word in ('zebra-striped', 'quince-stacked', 'marmalade'))
    assert not any(word in every_text(app) for word in ('zebra-striped', 'quince-stacked', 'marmalade'))


def test_a_picked_idea_that_is_sent_is_the_players_own_line(client, connected, provider):
    provider.replies = [reply(json.dumps(PICKS))]
    pick = ask(client)['ideas'][0]
    tell(client, pick, 'ideas-0001')
    assert ok(client.get('/api/story'))['messages'][0]['text'] == pick


def test_hidden_truth_stays_out_of_the_ideas_prompt(client, connected, provider, app):
    with app.state.database.connect(write=True) as connection:
        record.add(connection, 'secret', 'The cellarman', 'The cellarman poisoned the mayor with foxglove.',
                   app.state.database.now(), truth='world')
        record.add(connection, 'fact', 'The cellarman', 'The cellarman owes the character a favour.',
                   app.state.database.now(), truth='both')
    provider.replies = [reply(json.dumps(PICKS))]
    ask(client)
    told = provider.requests[-1]['messages'][0]['content']
    assert 'foxglove' not in told and 'owes the character a favour' in told


def test_with_no_model_the_scene_gives_ideas(client):
    found = ask(client)
    assert 2 <= len(found['ideas']) <= ideas.MOST and 'I take a careful look around.' in found['ideas']


def test_a_bad_answer_falls_back_to_the_scene(client, connected, provider):
    provider.replies = [reply('Sure! Here are some ideas.')]
    assert 'I take a careful look around.' in ask(client)['ideas']


def test_parse_keeps_actions_and_drops_results_rolls_and_long_ones():
    long = 'I ' + 'walk ' * 25
    answer = json.dumps(['I ask Hollis about the cart.', 'I roll to sneak past.', 'I succeed in picking the lock.',
                         long, 'I ask Hollis about the cart.', 'I wait.', 'I leave.'])
    assert ideas.parse(f'Here: {answer}') == ['I ask Hollis about the cart.', 'I wait.', 'I leave.']
    assert ideas.parse('not json') == [] and ideas.parse('[1, 2]') == []
