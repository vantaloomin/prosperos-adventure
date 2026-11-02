"""Chapters, the branch tree, bookmarks, Ironman and the notebook (dungeon/chapters.py)."""
import json

from conftest import Chunk, narrator, tell
from test_inventory import begin
from test_travel import ok

from dungeon import chapters, combat, record


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def summary(title, text, hook='The bill.'):
    return reply(json.dumps({'title': title, 'summary': text, 'hook': hook}))


def route_continuity(client):
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': 'continuity', 'profile_id': profiles[0]['id']}))


def campaign(client):
    return ok(client.get('/api/story'))['campaign']


def test_a_scene_break_opens_the_next_chapter_and_the_one_that_ended_is_summarized(client, connected, provider,
                                                                                   monkeypatch):
    begin(client)
    route_continuity(client)
    narrations = iter(['Pell weighs the coin.', 'You sleep badly.', 'Grey.', 'Morning comes grey.',
                       'The street is wet.'])
    summaries = iter([summary("A night at Pell's", 'You paid Pell and slept in the back room.'),
                      summary('Something else', 'You got up.')])

    def respond(system, messages):
        if system == chapters.SUMMARIZE:
            return next(summaries)
        return reply('{"facts": []}') if system.startswith(record.EXTRACT) else reply(next(narrations))
    provider.respond = respond
    tell(client, 'I pay Pell.', 'story-0001')
    assert [(chapter['number'], chapter['open']) for chapter in campaign(client)['chapters']] == [(1, True)]
    # A rest is time passing: the chapter is summarized as the break is made, and the next line opens chapter 2.
    tell(client, 'I go to bed and sleep.', 'story-0002')
    assert campaign(client)['pending'] == {'reason': 'time', 'title': ''}
    asked = next(request for request in reversed(provider.requests) if request['system'] == chapters.SUMMARIZE)
    assert 'The player: I pay Pell.' in asked['messages'][0]['content']
    tell(client, 'I get up.', 'story-0003')
    # Two lines are too few for a "previously": the player has just read them.
    assert chapters.PREVIOUSLY not in narrator(provider)['system']
    # With enough lines it opens with one, from the chapter that ended and the hook it left (told again here).
    monkeypatch.setattr(chapters, 'RECAP_TURNS', 2)
    ok(client.post('/api/story/retry'))
    opened = narrator(provider)['system']
    assert chapters.PREVIOUSLY in opened and 'You paid Pell and slept in the back room.' in opened
    assert 'Still open: The bill.' in opened
    first, second = campaign(client)['chapters']
    assert (first['title'], first['summary'], first['ended_by'], first['turns'], first['hook']) == (
        "A night at Pell's", 'You paid Pell and slept in the back room.', 'time', 2, 'The bill.')
    assert (second['title'], second['open'], second['turns']) == ('Chapter 2', True, 1)
    # The player closes one with a name; the model's title never replaces it.
    ok(client.post('/api/story/chapters/close', json={'title': 'The grey morning'}))
    tell(client, 'I step outside.', 'story-0004')
    assert campaign(client)['chapters'][1]['title'] == 'The grey morning'
    lines = ok(client.get(f"/api/story/chapters/{second['id']}"))['lines']
    assert [line['text'] for line in lines] == ['I get up.', 'Morning comes grey.']


def test_a_previously_waits_for_enough_lines_since_the_last():
    def chapter(turns, ended_by='time'):
        return {'turns': turns, 'ended_by': ended_by}
    assert not chapters.recap_due([chapter(2)])
    assert chapters.recap_due([chapter(2), chapter(3), chapter(1)])
    # After one, the count starts again.
    assert not chapters.recap_due([chapter(6), chapter(2)])
    assert chapters.recap_due([chapter(6), chapter(1, 'player')])


def test_chapters_follow_the_branches_and_the_tree_marks_how_each_ended(client, connected, provider, app):
    begin(client)
    provider.replies = [reply('One.'), reply('Two.'), reply('Three.')]
    tell(client, 'I look around.', 'story-0001')
    ok(client.post('/api/story/chapters/close', json={'title': ''}))
    second = tell(client, 'I walk on.', 'story-0002')['message']
    tell(client, 'I keep walking.', 'story-0003')
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 5, dead=True)
    # Back to before chapter 2's first line: the new branch shares chapter 1, but not where it ended there.
    went = ok(client.post('/api/story/back', json={'message_id': second['id']}))
    assert [(chapter['title'], chapter['open']) for chapter in went['campaign']['chapters']] == [('Chapter 1', True)]
    tree = {branch['id']: branch for branch in went['campaign']['tree']}
    old = next(branch for branch in tree.values() if not branch['playing'])
    assert old['ending'] == 'death' and [chapter['number'] for chapter in old['chapters']] == [1, 2]
    playing = next(branch for branch in tree.values() if branch['playing'])
    assert playing['parent_id'] == old['id'] and playing['chapters'] == []
    # Playing on from chapter 2 in the tree goes back to its first line in the old branch.
    back = ok(client.post(f"/api/story/chapters/{old['chapters'][1]['id']}/back"))
    assert back['draft'] == 'I walk on.'


def test_ironman_turns_off_going_back_and_death_is_final(client, connected, provider, app):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt', 'ironman': True}))
    provider.replies = [reply('One.')]
    line = tell(client, 'I look around.', 'story-0001')['message']
    assert campaign(client)['ironman'] is True
    response = client.post('/api/story/back', json={'message_id': line['id']})
    assert response.status_code == 409 and 'Ironman' in response.json()['detail']
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 5, dead=True)
    response = client.post('/api/story/messages', json={'text': 'I get up.', 'client_id': 'story-0002'})
    assert response.status_code == 409 and 'In Ironman, that is final' in response.json()['detail']
    # A new story is not Ironman unless chosen again.
    ok(client.delete('/api/story'))
    assert campaign(client)['ironman'] is False


def test_bookmarks_find_a_moment_and_the_notebook_is_never_read_by_a_model(client, connected, provider):
    begin(client)
    provider.replies = [reply('One.'), reply('Two.'), reply('Three.')]
    first = tell(client, 'I look around.', 'story-0001')['message']
    tell(client, 'I walk on.', 'story-0002')
    marked = ok(client.post('/api/story/bookmarks', json={'message_id': first['id'], 'name': 'Arrival'}))
    [mark] = marked['campaign']['bookmarks']
    assert (mark['name'], mark['text']) == ('Arrival', 'I look around.')
    went = ok(client.post(f"/api/story/bookmarks/{mark['id']}/go"))
    assert went['message_id'] == first['id']
    assert ok(client.delete(f"/api/story/bookmarks/{mark['id']}"))['campaign']['bookmarks'] == []

    notes = ok(client.post('/api/story/notebook', json={'text': 'Pell is lying about the key.'}))['notes']
    ok(client.patch(f"/api/story/notebook/{notes[0]['id']}", json={'text': 'Pell is hiding the key.'}))
    tell(client, 'I watch Pell.', 'story-0003')
    assert 'Pell is hiding the key' not in str(provider.requests)
    assert [note['text'] for note in ok(client.get('/api/story/notebook'))['notes']] == ['Pell is hiding the key.']
    assert ok(client.delete(f"/api/story/notebook/{notes[0]['id']}"))['notes'] == []


def test_going_somewhere_opens_the_next_chapter(client, connected, provider):
    # Playtest M3, finding 2: "Go somewhere else" on the screen ends the chapter too.
    begin(client)
    provider.replies = [reply('One.')]
    tell(client, 'I look around.', 'story-0001')
    places = ok(client.get('/api/story'))['scene']['places']
    here = ok(client.get('/api/story'))['scene']['place']['id']
    ok(client.put('/api/story/scene', json={'city_id': ok(client.get('/api/story'))['scene']['city']['id'],
                                            'place_id': next(place['id'] for place in places if place['id'] != here)}))
    assert campaign(client)['pending']['reason'] == 'place'
