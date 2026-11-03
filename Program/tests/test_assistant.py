"""The Sidebar Assistant (adventure/assistant.py): it sees the story, never becomes part of it, and only proposes
changes, each checked against what it was shown; GM context and GM edits only while the GM view is on."""
import json

from conftest import ok, tell
from test_director import start
from test_pace import reply

from adventure import assistant, record


def ask(client, message='What happened?', **extra):
    return ok(client.post('/api/assistant/chat', json={'message': message, **extra}))


def answer(text='Here you go.', changes=()):
    return reply(json.dumps({'reply': text, 'changes': list(changes)}))


def every_text(app) -> str:
    with app.state.database.connect() as connection:
        tables = [row['name'] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return '\n'.join(str(value) for table in tables for row in connection.execute(f'SELECT * FROM "{table}"')
                         for value in tuple(row) if isinstance(value, str))


def test_it_sees_the_story_and_proposes_checked_changes_while_nothing_is_kept(client, connected, provider, app):
    provider.replies = [reply('Rain hammers the shutters of the inn.')]
    tell(client, 'I step inside out of the rain.', 'side-0001')
    ok(client.post('/api/story/journal', json={'subject': 'Mara', 'text': 'Mara keeps the inn.'}))
    ok(client.put('/api/authors-notes/story', json={'text': 'Keep it quiet.', 'enabled': True}))
    provider.replies = [
        # A user's line cannot be reworded: sent back once with the reason.
        answer('Done.', [{'kind': 'narration', 'ref': 'm1', 'text': 'I stride in.'}]),
        answer('A few changes for the plum-velvet mood.', [
            {'kind': 'authors_note', 'text': 'Keep it slow and wet.'},
            {'kind': 'narration', 'ref': 'm2', 'text': 'Rain drums on the inn shutters.'},
            {'kind': 'journal_add', 'subject': 'The inn', 'text': 'The inn leaks.'},
            {'kind': 'journal_fix', 'ref': 'k1', 'text': 'fact · Mara: Mara owns the inn.'},
            {'kind': 'lore_add', 'title': 'Rain', 'text': 'It always rains here.', 'keywords': ['rain']},
            {'kind': 'feelings', 'ref': 'p1', 'trust': 3},
        ])]
    found = ask(client, 'Make it gloomier.', history=[{'role': 'assistant', 'content': 'Hi.'}])
    first, again = provider.requests[-2:]
    assert 'I step inside out of the rain.' in first['system'] and 'Mara keeps the inn.' in first['system']
    assert '(on) Keep it quiet.' in first['system'] and 'Behind the story' not in first['system']
    assert [turn['role'] for turn in first['messages']] == ['user'], 'a history starting with its own words is cut'
    assert "only the narrator's passages" in again['messages'][-1]['content']
    assert found['reply'] == 'A few changes for the plum-velvet mood.' and found['gm'] is False
    kinds = [change['kind'] for change in found['changes']]
    assert kinds == ['authors_note', 'narration', 'journal_add', 'journal_fix', 'lore_add'], 'no GM edit without the GM view'
    note, narration, _added, fixed, entry = found['changes']
    assert note == {'kind': 'authors_note', 'before': 'Keep it quiet.', 'enabled': True, 'text': 'Keep it slow and wet.'}
    assert narration['before'] == 'Rain hammers the shutters of the inn.'
    assert fixed['text'] == 'Mara owns the inn.' and fixed['before'] == 'Mara keeps the inn.'
    assert entry['visibility'] == 'public' and entry['keywords'] == ['rain']
    assert 'plum-velvet' not in every_text(app) and 'Keep it slow and wet.' not in every_text(app)


def test_hidden_truth_and_gm_edits_need_the_gm_view(client, connected, provider, app):
    start(client)
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day) VALUES "
                           "('pell', 'kingswood', 'Pell', 'x', 'x', '1290-05-01')")
        record.add(connection, 'secret', 'Pell', 'Pell smuggles saffron.', 'x', truth='world')
    provider.replies = [answer(), answer()]
    ask(client)
    hidden = provider.requests[-1]['system']
    assert 'saffron' not in hidden and 'Behind the story' not in hidden and '"feelings"' not in hidden
    ok(client.put('/api/settings', json={'gm_view': True}))
    context = assistant.Context(app.state.database)
    arc = next(ref for ref, row in context.arcs.items() if row['id'] == 'the-eight-pieces')
    beat = next(iter(context.beats), None)
    changes = [{'kind': 'feelings', 'ref': 'p1', 'trust': 9, 'fear': 0},
               {'kind': 'beat_add', 'ref': arc, 'text': 'A courier  comes looking.'},
               {'kind': 'lore_add', 'text': 'The wards are failing.', 'always': True, 'secret': True}]
    if beat:
        changes.append({'kind': 'beat_cut', 'ref': beat, 'cut': not context.beats[beat]['cut']})
    provider.replies = [answer('GM edits.', changes)]
    found = ask(client)
    shown = provider.requests[-1]['system']
    assert 'saffron' in shown and 'Behind the story' in shown and '"feelings"' in shown
    feelings, added, lore = found['changes'][:3]
    assert feelings == {'kind': 'feelings', 'key': 'pell', 'name': 'Pell', 'values': {'trust': 5},
                        'before': {'trust': 0, 'affection': 0, 'respect': 0, 'fear': 0, 'desire': 0}}
    assert added == {'kind': 'beat_add', 'arc_id': 'the-eight-pieces', 'arc': 'The Eight Pieces',
                     'text': 'A courier comes looking.'}
    assert lore['visibility'] == 'gm' and lore['always'] is True
    assert len(found['changes']) == len(changes) and found['gm'] is True


def test_a_model_that_will_not_answer_in_json_still_answers(client, connected, provider):
    provider.replies = [reply('Plain words.'), reply('Still plain words.')]
    found = ask(client)
    assert found == {'reply': 'Still plain words.', 'changes': [], 'gm': False}


def test_it_needs_a_text_model(client):
    response = client.post('/api/assistant/chat', json={'message': 'Hello?'})
    assert response.status_code == 409 and 'Sidebar Assistant' in response.json()['detail']


def test_a_narration_in_new_words_is_undone_by_switch_wording(client, connected, provider):
    provider.replies = [reply('The door creaks open.')]
    tell(client, 'I open the door.', 'side-0002')
    narration = next(message for message in ok(client.get('/api/story'))['messages'] if message['role'] == 'narrator')
    path = f"/api/story/messages/{narration['id']}"
    stale = client.post(f'{path}/reword', json={'text': 'New words.', 'expected': 'Other words.'})
    assert stale.status_code == 409
    changed = ok(client.post(f'{path}/reword', json={'text': 'The door groans.', 'expected': 'The door creaks open.'}))
    line = next(message for message in changed['messages'] if message['id'] == narration['id'])
    assert line['text'] == 'The door groans.' and line['previous'] is True
    back = ok(client.post(f'{path}/switch'))
    assert next(message for message in back['messages'] if message['id'] == narration['id'])['text'] == \
        'The door creaks open.'


def test_gm_beats_are_added_and_taken_out_only_with_the_gm_view(client, app):
    start(client)
    beat = {'arc_id': 'the-eight-pieces', 'text': 'A courier comes looking.'}
    assert client.post('/api/story/gm/beats', json=beat).status_code == 409
    ok(client.put('/api/settings', json={'gm_view': True}))
    view = ok(client.post('/api/story/gm/beats', json=beat))
    plan = next(item for item in view['plans'] if item['arc_id'] == 'the-eight-pieces')
    assert plan['beats'][-1] | {'id': ''} == {'id': '', 'text': 'A courier comes looking.', 'cut': False, 'used': False,
                                             'landed': False, 'source': 'assistant'}
    assert plan['beats'][-1]['id'] == view['added']
    view = ok(client.delete(f"/api/story/gm/beats/{view['added']}"))
    plan = next(item for item in view['plans'] if item['arc_id'] == 'the-eight-pieces')
    assert all(item['text'] != 'A courier comes looking.' for item in plan['beats'])
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_arc_beats (id, arc_id, stage, text) VALUES ('w1', 'the-eight-pieces', 0, "
                           "'The world planned this.')")
    assert client.delete('/api/story/gm/beats/w1').status_code == 409


def test_lore_entries_of_the_users_own_go_in_one_book(client):
    first = ok(client.post('/api/lore/entries', json={'title': 'Rain', 'text': 'It always rains.', 'keywords': ['rain', 'rain']}))
    second = ok(client.post('/api/lore/entries', json={'text': 'The wards fail.', 'always': True, 'visibility': 'gm'}))
    books = [book for book in second['books'] if book['name'] == 'Written with the Sidebar Assistant']
    assert len(books) == 1 and [entry['id'] for entry in books[0]['entries']] == [first['added'], second['added']]
    assert books[0]['entries'][0]['keywords'] == ['rain'] and books[0]['entries'][1]['visibility'] == 'gm'
    assert client.post('/api/lore/entries', json={'text': 'No way in.'}).status_code == 422
    assert client.post('/api/lore/entries', json={'text': 'x', 'always': True, 'visibility': 'known'}).status_code == 422
    left = ok(client.delete(f"/api/lore/entries/{first['added']}"))
    book = next(book for book in left['books'] if book['name'] == 'Written with the Sidebar Assistant')
    assert [entry['id'] for entry in book['entries']] == [second['added']]
