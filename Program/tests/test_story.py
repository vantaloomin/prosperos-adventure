"""The story: a narrator for the user's own story around the cities (dungeon/story.py)."""
from datetime import timedelta

from conftest import Chunk

from dungeon import story
from dungeon.narration import prose


def connect(client):
    response = client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'})
    assert response.status_code == 200, response.text


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def say(client, text, client_id):
    return ok(client.post('/api/story/messages', json={'text': text, 'client_id': client_id}))


def busy_place(client, clock):
    """A Baltimore place with someone there now, moving the clock on by hours until there is one."""
    for _hour in range(48):
        with client.app.state.database.connect() as connection:
            data = story.city_data(connection, 'baltimore')
            moment = story.local_moment(data, clock.now())
            for place in data['places']:
                if people := story.present(connection, data, place['id'], moment):
                    return place, people
        clock.instant = clock.now() + timedelta(hours=1)
    raise AssertionError('Nobody is anywhere in Baltimore for two days.')


def test_the_story_starts_in_the_worlds_city_and_needs_a_model(client, clock):
    opened = ok(client.get('/api/story'))
    assert opened['ready'] is False and opened['messages'] == []
    scene = opened['scene']
    assert scene['city']['name'] == 'Baltimore' and scene['place']['kind'] == 'cafe'
    assert scene['local_time'] and any(place['id'] == scene['place']['id'] for place in scene['places'])

    refused = client.post('/api/story/messages', json={'text': 'I look around.', 'client_id': 'story-0001'})
    assert refused.status_code == 409 and refused.json()['code'] == 'no_connection'
    # The message is kept, and is answered when it is sent again with a model connected.
    connect(client)
    sent = say(client, 'I look around.', 'story-0001')
    assert sent['reply']['role'] == 'narrator' and sent['reply']['status'] == 'complete'
    assert [message['role'] for message in ok(client.get('/api/story'))['messages']] == ['user', 'narrator']
    assert ok(client.get('/api/story'))['ready'] is True


def test_the_narrator_is_given_the_scene(client, clock, provider):
    connect(client)
    place, people = busy_place(client, clock)
    moved = ok(client.put('/api/story/scene', json={'city_id': 'baltimore', 'place_id': place['id']}))
    assert moved['scene']['place']['id'] == place['id'] and moved['messages'][-1]['role'] == 'scene'
    # The screen says who is around without names the user has not been given.
    around = moved['scene']['around']
    assert len(around) == len(people) and all(person['sheet']['full'] not in ' '.join(around) for person in people)

    provider.replies = [[Chunk('The door chimes behind you.'), Chunk('', 'stop')]]
    say(client, 'I order a coffee and the secret password is plum.', 'story-0001')
    request = provider.requests[-1]
    assert 'You are the narrator of a tabletop roleplaying game for adults' in request['system']
    assert 'Never write:' in request['system'] and 'second person' in request['system']
    assert f"Place: {place['name']}" in request['system'] and 'Weather:' in request['system']
    # Named spots inside the place are detail for the narrator and the screen (dungeon/world/inside.py).
    spots = moved['scene']['place']['spots']
    assert spots and f"Spots here, for detail only (nobody moves between them): {', '.join(spots)}." in request['system']
    assert all(person['sheet']['full'] in request['system'] for person in people)
    assert request['messages'][0]['content'].startswith('[You arrive at')
    assert 'secret password is plum' in request['messages'][-1]['content']


def test_moving_to_another_city_and_unknown_places(client, clock):
    moved = ok(client.put('/api/story/scene', json={'city_id': 'new-york'}))
    assert moved['scene']['city']['name'] == 'New York' and moved['messages'][-1]['text'].endswith('New York.')
    # Choosing where the story already is adds nothing.
    again = ok(client.put('/api/story/scene', json={'city_id': 'new-york', 'place_id': moved['scene']['place']['id']}))
    assert len(again['messages']) == 1
    assert client.put('/api/story/scene', json={'city_id': 'new-york', 'place_id': 'nowhere'}).status_code == 404
    assert client.put('/api/story/scene', json={'city_id': 'atlantis'}).status_code == 404


def test_the_narrator_stays_in_the_story_unless_the_user_steps_out(client, clock, provider):
    connect(client)
    provider.replies = [[Chunk('As an AI language model, I cannot taste coffee. '), Chunk('The coffee is bitter.'),
                         Chunk('', 'stop')]]
    first = say(client, 'I taste the coffee.', 'story-0001')
    assert first['reply']['text'] == 'The coffee is bitter.'
    # Sending the same message again returns the same reply, without asking the model twice.
    count = len(provider.requests)
    assert say(client, 'I taste the coffee.', 'story-0001')['reply']['id'] == first['reply']['id']
    assert len(provider.requests) == count

    provider.replies = [[Chunk("I'm an AI language model writing the narrator."), Chunk('', 'stop')]]
    honest = say(client, 'OOC: what are you?', 'story-0002')
    assert 'AI language model' in honest['reply']['text']
    system = provider.requests[-1]['system']
    assert 'out of character' in system and 'question for the game master' in system
    # It answers as the game master and names the model only if asked.
    assert 'Only if they ask what you are' in system


def test_a_failed_reply_can_be_told_again_and_a_new_story_started(client, clock, provider):
    connect(client)
    provider.replies = [[Chunk('', 'stop')]]
    failed = say(client, 'I wave at the barista.', 'story-0001')
    assert failed['reply']['status'] == 'failed' and failed['reply']['error']
    provider.replies = [[Chunk('The barista waves back.'), Chunk('', 'stop')]]
    retold = ok(client.post('/api/story/retry'))
    assert retold['reply']['text'] == 'The barista waves back.'
    roles = [(message['role'], message['status']) for message in ok(client.get('/api/story'))['messages']]
    assert roles == [('user', 'complete'), ('narrator', 'complete')]

    cleared = ok(client.delete('/api/story'))
    assert cleared['messages'] == [] and cleared['scene']['place']
    assert client.post('/api/story/retry').status_code == 409


def test_people_named_in_the_story_are_met_and_remembered(client, clock, provider):
    connect(client)
    place, people = busy_place(client, clock)
    ok(client.put('/api/story/scene', json={'city_id': 'baltimore', 'place_id': place['id']}))
    them = people[0]['sheet']
    provider.replies = [[Chunk('Nobody looks up.'), Chunk('', 'stop')],
                        [Chunk(f'"I\'m {them["name"]}," they say, wiping the counter. "New here?"'), Chunk('', 'stop')]]
    say(client, 'I sit down.', 'story-0001')
    assert ok(client.get('/api/story'))['people'] == []
    say(client, 'I say hello and give my name.', 'story-0002')
    story_now = ok(client.get('/api/story'))
    [met] = story_now['people']
    assert met['key'] == them['key'] and met['name'] == them['full'] and met['meetings'] == 1
    assert met['notes'] == [f'"I\'m {them["name"]}," they say, wiping the counter.'] and met['doing']
    assert any(item.startswith(f"{them['name']}, ") for item in story_now['scene']['around'])

    # Next time they are in the scene, the narrator remembers; another mention the same day is not another meeting.
    provider.replies = [[Chunk(f'{them["name"]} nods.'), Chunk('', 'stop')]]
    say(client, f'I wave at {them["name"]}.', 'story-0003')
    assert 'The user has met them once and knows their name' in provider.requests[-1]['system']
    assert 'From before: "I\'m' in provider.requests[-1]['system']
    assert ok(client.get('/api/story'))['people'][0]['meetings'] == 1

    cleared = ok(client.delete('/api/story'))
    assert cleared['people'] == []


def test_finding_someone_goes_to_where_they_are(client, clock, provider):
    connect(client)
    place, people = busy_place(client, clock)
    ok(client.put('/api/story/scene', json={'city_id': 'baltimore', 'place_id': place['id']}))
    them = people[0]['sheet']
    provider.replies = [[Chunk(f'{them["name"]} smiles.'), Chunk('', 'stop')]]
    say(client, 'Hi!', 'story-0001')
    ok(client.put('/api/story/scene', json={'city_id': 'new-york'}))
    found = ok(client.post('/api/story/find', json={'key': them['key']}))
    assert found['scene']['place']['id'] == place['id'] and found['scene']['city']['id'] == 'baltimore'
    assert client.post('/api/story/find', json={'key': 'town:baltimore:nowhere:0'}).status_code == 404
    # Once they have gone home, there is nowhere to go.
    for _hour in range(24):
        clock.instant = clock.now() + timedelta(hours=1)
        person = ok(client.get('/api/story'))['people'][0]
        if person['place'] is None:
            refused = client.post('/api/story/find', json={'key': them['key']})
            assert refused.status_code == 409 and person['doing'] in refused.json()['detail']
            break
    else:
        raise AssertionError('They never went home.')


def test_a_person_line_does_not_say_their_job_twice():
    from dungeon.world import catalog, townsfolk
    data = catalog.city('baltimore')
    place = next(item for item in data['places'] if item['kind'] == 'restaurant')
    sheet = next(item for item in townsfolk.at_place(data, place['id']) if item['staff'])
    line = story.person_line({'sheet': sheet, 'doing': f"working as the {sheet['role']}", 'mood': 'fine'},
                             {'id': place['id']}, data)
    assert f"working as the {sheet['role']}. " in line and f", {sheet['role']}." not in line


def test_the_narration_is_checked_and_rewritten_before_it_is_saved(client, clock, provider):
    connect(client)
    provider.replies = [[Chunk('The door chimes—softly. A shiver ran down your spine as the room turned to look.'),
                         Chunk('', 'stop')],
                        [Chunk('The door chimes softly. Two dockhands at the bar turn to look, then go back to their '
                               'dice.'), Chunk('', 'stop')]]
    reply = say(client, 'I walk in.', 'story-0001')['reply']
    assert reply['status'] == 'complete' and reply['text'].startswith('The door chimes softly. Two dockhands')
    assert provider.requests[-1]['system'] == prose.REWRITE
    assert 'shiver' in provider.requests[-1]['messages'][0]['content']


def test_a_line_that_goes_somewhere_in_town_moves_the_story_there(client, clock, provider):
    connect(client)
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    provider.replies = [[Chunk('Candles.'), Chunk('', 'stop')]] * 4
    say(client, 'I go to the shrine and ask Mother Rook what lies under the Heartwood.', 'story-0001')
    view = ok(client.get('/api/story'))
    assert view['scene']['place']['id'] == 'shrine-of-tidum'
    assert any(row['text'].startswith('You arrive at the Shrine of Tidum') for row in view['messages'])
    # Words that fit two places equally, or none, move nobody.
    say(client, 'I walk over to the bar.', 'story-0002')
    say(client, 'I go for the door.', 'story-0003')
    assert ok(client.get('/api/story'))['scene']['place']['id'] == 'shrine-of-tidum'
    # A rest taken somewhere by name is taken there.
    say(client, 'I spend the night at the bunkhouses.', 'story-0004')
    assert ok(client.get('/api/story'))['scene']['place']['id'] == 'bunkhouses'


def test_an_ooc_question_gets_the_map_as_the_character_knows_it(client, clock, provider):
    connect(client)
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    provider.replies = [[Chunk('Convila, Eriane or the keep.'), Chunk('', 'stop')]]
    say(client, 'OOC: where can I travel from here?', 'story-0001')
    system = provider.requests[-1]['system']
    assert 'Places in Kingswood, reached by going there: the Green, the Felled Oak' in system
    assert '- Kingswood to Convila: 8 hours by the forest road, low danger' in system


def test_a_notable_who_runs_the_place_is_named_while_away():
    # Playtest M3, finding 6: with Corin Ashby away the narrator made up another keeper of the Felled Oak.
    corin = {'id': 'corin-ashby', 'name': 'Corin Ashby', 'pronouns': 'he/him', 'place': 'felled-oak',
             'role': 'tavern keeper', 'staff': True}
    view = {'data': {'notables': [corin]}, 'place': {'id': 'felled-oak'}, 'people': [], 'dead': set()}
    assert story.away_lines(view) == ['- Not here now: Corin Ashby (he/him), the tavern keeper here. Whoever minds the '
                                      'place stands in; Corin Ashby is still the tavern keeper, so invent no other.']
    assert story.away_lines(view | {'people': [{'sheet': {'full': 'Corin Ashby'}}]}) == []
    assert story.away_lines(view | {'dead': {'corin ashby'}}) == []


def test_a_line_that_goes_out_through_a_place_moves_there(client, clock, provider):
    connect(client)
    ok(client.put('/api/story/scene', json={'city_id': 'the-concourse', 'place_id': 'the-plaza'}))
    ok(client.delete('/api/story'))
    premade = ok(client.get('/api/story/start'))['premades'][0]['id']
    ok(client.post('/api/story/start', json={'premade_id': premade}))
    provider.replies = [[Chunk('Up and up.'), Chunk('', 'stop')]]
    say(client, 'I go out through the gate arch onto the Stair and look up.', 'story-0001')
    assert ok(client.get('/api/story'))['scene']['place']['id'] == 'the-gate-arch'
