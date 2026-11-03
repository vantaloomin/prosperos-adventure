"""The other leads join as the party at Begin (adventure/rounds/cast.py): each travels with the character from the
first line and sits at the round table with the mind the cast page gave them."""
import json

from conftest import Chunk

from adventure import story, story_clock


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def rows(client, sql):
    with client.app.state.database.connect() as connection:
        return [dict(row) for row in connection.execute(sql).fetchall()]


def kingswood(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'the-wayhouse'}))
    ok(client.delete('/api/story'))


def test_begin_without_a_party_seats_nobody(client):
    kingswood(client)
    choices = ok(client.get('/api/story/start'))['premades']
    # Each lead says how they play if they join: Kingswood's leads are playable personas, so they think.
    assert {lead['id']: lead['default_mind'] for lead in choices} == {
        'agna-holt': 'agent', 'lirien-of-the-ford': 'agent', 'tobin-pell': 'agent'}
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    assert rows(client, 'SELECT * FROM round_seats') == []
    assert rows(client, 'SELECT * FROM story_party') == []


def test_the_other_leads_join_as_the_party_with_their_minds(client):
    kingswood(client)
    refused = client.post('/api/story/start', json={'premade_id': 'agna-holt', 'party': {'agna-holt': {}}})
    assert refused.status_code == 422  # The player's own character cannot also join.
    assert client.post('/api/story/start', json={'premade_id': 'agna-holt', 'party': {'nobody': {}}}).status_code == 422
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt', 'party': {
        'tobin-pell': {'mind': 'program', 'notes': 'Gruff, but fair.'}}}))
    seated = {row['key']: (row['name'], row['mind'], row['notes']) for row in rows(client, 'SELECT * FROM round_seats')}
    assert seated == {'you': ('Agna Holt', 'human', ''), 'lirien-of-the-ford': ('Lirien of the Ford', 'agent', ''),
                      'tobin-pell': ('Tobin Pell', 'program', 'Gruff, but fair.')}
    # They travel with the character, are met, and are in the scene wherever it is.
    assert {row['key'] for row in rows(client, 'SELECT key FROM story_party')} == {'lirien-of-the-ford', 'tobin-pell'}
    assert {row['key'] for row in rows(client, 'SELECT key FROM story_people')} >= {'lirien-of-the-ford', 'tobin-pell'}
    with client.app.state.database.connect() as connection:
        view = story.scene(connection, story_clock.now(connection, client.app.state.database.clock))
    here = {person['sheet']['key']: person['sheet'] for person in view['people']}
    assert {'lirien-of-the-ford', 'tobin-pell'} <= set(here)
    tobin = here['tobin-pell']
    assert (tobin['full'], tobin['pronouns'], tobin['cast']) == ('Tobin Pell', 'he/him', 'tobin-pell')


def test_a_party_lead_is_present_and_decides_in_the_first_turn(client, provider):
    kingswood(client)
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt', 'party': {
        'lirien-of-the-ford': {'mind': 'agent'}, 'tobin-pell': {'mind': 'program'}}}))
    ok(client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'}))
    provider.replies = [[Chunk('The fire cracks.'), Chunk('', 'stop')]] * 8
    response = client.post('/api/story/messages', json={'text': 'I sit by the fire.', 'client_id': 'cast-0001'})
    assert response.status_code == 200, response.text
    played = rows(client, 'SELECT state, snapshot FROM round_turns ORDER BY created_at DESC LIMIT 1')
    assert played[0]['state'] in ('committed', 'awaiting_user')
    snapshot = json.loads(played[0]['snapshot'])
    assert {'you', 'lirien-of-the-ford', 'tobin-pell'} <= set(snapshot['present'])
    assert {seat['key'] for seat in snapshot['seats']} == {'you', 'lirien-of-the-ford', 'tobin-pell'}
