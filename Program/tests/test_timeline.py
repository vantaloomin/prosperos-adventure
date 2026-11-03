"""Every turn is a save point (adventure/timeline.py): going back starts a branch with the state as it was, and new
dice; the branch left behind is kept and can be played on."""
import random

from conftest import Chunk


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def say(client, text, client_id):
    return ok(client.post('/api/story/messages', json={'text': text, 'client_id': client_id}))


def texts(story):
    return [message['text'] for message in story['messages'] if message['role'] == 'user']


def test_going_back_brings_new_dice_and_keeps_the_old_branch(client, app, provider):
    ok(client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'}))
    ok(client.put('/api/settings', json={'show_odds': True}))
    app.state.dice = random.Random(3)
    provider.replies = [[Chunk(f'Reply {number}.'), Chunk('', 'stop')] for number in range(1, 6)]
    first = say(client, 'I look around.', 'story-0001')['message']
    second = say(client, 'I punch the bouncer.', 'story-0002')['message']
    ok(client.put('/api/story/sheet', json={'stats': {'Vitality': 20}}))
    say(client, 'I run for the door.', 'story-0003')
    before = ok(client.get('/api/story'))
    old_roll = next(m for m in before['messages'] if m['id'] == second['id'])['rolls'][0]

    went = ok(client.post('/api/story/back', json={'message_id': second['id']}))
    assert went['draft'] == 'I punch the bouncer.'
    assert texts(went) == ['I look around.'] and went['messages'][-1]['text'] == 'Reply 1.'
    # The sheet is as it was when that line was sent.
    assert ok(client.get('/api/story/sheet'))['stats']['Vitality'] == 10
    assert [branch['playing'] for branch in went['branches']] == [True, False]
    assert went['branches'][1]['turns'] == 3 and went['branches'][1]['last_line'] == 'I run for the door.'
    # Retelling is for lines of this branch; the shared one keeps its reply.
    assert client.post('/api/story/retry').status_code == 409

    again = say(client, 'I punch the bouncer.', 'story-0004')['message']
    replayed = ok(client.get('/api/story'))
    assert texts(replayed) == ['I look around.', 'I punch the bouncer.']
    new_roll = next(m for m in replayed['messages'] if m['id'] == again['id'])['rolls'][0]
    assert new_roll['natural'] != old_roll['natural']
    # The narrator only sees this branch.
    assert 'I run for the door' not in str(provider.requests[-1]['messages'])

    # Back to the first branch, where it was left: three turns, Vitality 20.
    old = next(branch for branch in replayed['branches'] if not branch['playing'])
    switched = ok(client.post(f"/api/story/branches/{old['id']}/switch"))
    assert texts(switched) == ['I look around.', 'I punch the bouncer.', 'I run for the door.']
    assert ok(client.get('/api/story/sheet'))['stats']['Vitality'] == 20
    assert client.post('/api/story/branches/nowhere/switch').status_code == 404
    assert texts(ok(client.post(f"/api/story/branches/{old['id']}/switch"))) == texts(switched)  # Already there.
    # And the newer branch is still there to go back to.
    newer = next(branch for branch in switched['branches'] if not branch['playing'])
    assert newer['last_line'] == 'I punch the bouncer.' and newer['turns'] == 2

    # Going back from inside a branch to a line before its fork.
    went = ok(client.post('/api/story/back', json={'message_id': first['id']}))
    assert texts(went) == [] and len(went['branches']) == 3
    assert client.post('/api/story/back', json={'message_id': second['id']}).status_code == 404

    cleared = ok(client.delete('/api/story'))
    assert cleared['messages'] == [] and [branch['playing'] for branch in cleared['branches']] == [True]


def test_an_older_workspace_gains_the_branch_column(tmp_path):
    import sqlite3

    from adventure.database import add_columns
    path = tmp_path / 'old.sqlite3'
    connection = sqlite3.connect(path)
    connection.execute('CREATE TABLE story_messages (id TEXT PRIMARY KEY, seq INTEGER)')
    connection.execute("INSERT INTO story_messages VALUES ('a', 1)")
    connection.execute('CREATE TABLE story_rolls (id TEXT PRIMARY KEY)')
    add_columns(connection)
    add_columns(connection)
    assert connection.execute('SELECT branch_id FROM story_messages').fetchall() == [('first',)]
    assert 'threat' in {row[1] for row in connection.execute('PRAGMA table_info(story_rolls)')}


def test_branches_are_named_renamed_and_deleted_with_undo(client, provider):
    """From Prospero's Companion #496: a new branch is named after the line it went back from, any other branch can
    be renamed, and Delete takes it out of the list (and the chapter tree) without erasing it."""
    ok(client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'}))
    provider.replies = [[Chunk(f'Reply {number}.'), Chunk('', 'stop')] for number in range(1, 6)]
    say(client, 'I look around.', 'story-0101')
    second = say(client, 'I walk up to the long table where the merchants sit and ask for work.', 'story-0102')['message']
    went = ok(client.post('/api/story/back', json={'message_id': second['id']}))
    playing, old = went['branches']
    assert playing['playing'] and playing['label'] == 'Instead of “I walk up to the long table where…”'
    assert old['label'] == ''

    renamed = ok(client.patch(f"/api/story/branches/{old['id']}", json={'label': '  The   merchants  '}))
    assert next(b for b in renamed['branches'] if b['id'] == old['id'])['label'] == 'The merchants'
    assert client.patch(f"/api/story/branches/{old['id']}", json={'label': '  '}).status_code == 422
    # The branch being played stays: there must always be one to play.
    assert client.patch(f"/api/story/branches/{playing['id']}", json={'label': 'Here'}).status_code == 409
    assert client.delete(f"/api/story/branches/{playing['id']}").status_code == 409

    gone = ok(client.delete(f"/api/story/branches/{old['id']}"))
    assert [b['id'] for b in gone['branches']] == [playing['id']]
    assert old['id'] not in [b['id'] for b in gone['campaign']['tree']]
    assert client.post(f"/api/story/branches/{old['id']}/switch").status_code == 404
    assert client.delete(f"/api/story/branches/{old['id']}").status_code == 404

    back = ok(client.post(f"/api/story/branches/{old['id']}/restore"))
    restored = next(b for b in back['branches'] if b['id'] == old['id'])
    assert restored['label'] == 'The merchants' and restored['turns'] == 2
    assert texts(ok(client.post(f"/api/story/branches/{old['id']}/switch")))[-1].startswith('I walk up')
