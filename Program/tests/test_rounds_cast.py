"""The other leads join as the party at Begin (adventure/rounds/cast.py): each travels with the character from the
first line and sits at the round table with the mind the cast page gave them. The leads left out stay in the bank and
live in town as background characters (adventure/rounds/bank.py)."""
import json

from conftest import Chunk

from adventure import story, story_clock, tiers
from adventure.rounds import context
from adventure.world import townsfolk


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
        'lirien-of-the-ford': {}, 'tobin-pell': {'mind': 'program', 'notes': 'Gruff, but fair.'}}}))
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
    assert tobin['role'] == 'A Timber Guild tally clerk who skims'  # the package's own concept for him
    # The play screen lists them as the party, and shows them travelling with the player.
    shown = ok(client.get('/api/story'))
    listed = {person['key']: person for person in shown['people']}
    assert listed['tobin-pell']['party'] and listed['tobin-pell']['doing'] == 'travelling with you'
    assert listed['lirien-of-the-ford']['name'] == 'Lirien of the Ford'
    labels = {item['key']: item['label'] for item in shown['scene']['present']}
    assert labels['tobin-pell'] == 'Tobin, travelling with you'


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


def test_the_cast_page_fills_the_party_up_to_the_agent_cap(client):
    kingswood(client)
    assert ok(client.get('/api/story/start'))['party_size'] == 6
    ok(client.put('/api/rounds/settings', json={'agent_cap': 2}))
    assert ok(client.get('/api/story/start'))['party_size'] == 2


def test_a_lead_left_in_the_bank_lives_in_town(client):
    kingswood(client)
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt', 'party': {'tobin-pell': {'mind': 'program'}}}))
    # Only the lead the cast page named joins; Lirien stays in the bank, seated nowhere and not in the party.
    assert {row['key'] for row in rows(client, 'SELECT key FROM round_seats')} == {'you', 'tobin-pell'}
    assert {row['key'] for row in rows(client, 'SELECT key FROM story_party')} == {'tobin-pell'}
    assert [row['key'] for row in rows(client, 'SELECT key FROM story_bank')] == ['lirien-of-the-ford']
    database = client.app.state.database
    with database.connect() as connection:
        data = story.city_data(connection, 'kingswood')
        lirien = next(item for item in data['notables'] if item['id'] == 'lirien-of-the-ford')
        # At their own home in town, a regular there, after the city's own notables.
        assert (lirien['place'], lirien['staff'], lirien['pronouns']) == ('the-ford', False, 'they/them')
        assert data['notables'][-1] is lirien
        found = [sheet for sheet in townsfolk.at_place(data, 'the-ford')
                 if sheet.get('notable') == 'lirien-of-the-ford']
        assert [sheet['full'] for sheet in found] == ['Lirien of the Ford']
        # Met in the story, what the package says they know still reaches them.
        met = found[0]
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, "
                           "meetings, notes) VALUES (?, 'kingswood', ?, '', '', '', 1, '[]')", (met['key'], met['full']))
        assert context.cast_of(connection, tiers.world_of('kingswood'), met['key']) == 'lirien-of-the-ford'
    # A new story forgets the bank, and Begin without a party banks nobody.
    ok(client.delete('/api/story'))
    assert rows(client, 'SELECT * FROM story_bank') == []
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    assert rows(client, 'SELECT * FROM story_bank') == []


def test_havenbrooke_banks_the_leads_past_the_cap_at_their_haunts(client):
    ok(client.put('/api/story/scene', json={'city_id': 'haven', 'place_id': 'commons-coffee'}))
    ok(client.delete('/api/story'))
    choices = ok(client.get('/api/story/start'))
    leads = [lead['id'] for lead in choices['premades']]
    assert len(leads) - 1 > choices['party_size']
    others = [key for key in leads if key != 'piper-marsh']
    joining = others[:choices['party_size']]
    ok(client.post('/api/story/start', json={'premade_id': 'piper-marsh', 'party': {key: {} for key in joining}}))
    assert {row['key'] for row in rows(client, 'SELECT key FROM story_party')} == set(joining)
    banked = {row['key']: json.loads(row['entry'])['place'] for row in rows(client, 'SELECT * FROM story_bank')}
    assert banked == {'paula-mercer': 'chancellor-wynne-library', 'amanda-rhodes': 'mirren-studio'}
