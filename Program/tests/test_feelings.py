"""What the people met feel about the player's character (dungeon/feelings.py)."""
from datetime import timedelta

from conftest import Chunk

from dungeon import feelings, story


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def say(client, text, client_id):
    return ok(client.post('/api/story/messages', json={'text': text, 'client_id': client_id}))


def someone(connection, key='k1', name='Dana Kim', **values):
    connection.execute('INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day) '
                       "VALUES (?, 'baltimore', ?, '', '', '2026-10-01')", (key, name))
    if values:
        feelings.change(connection, key, values)


def test_feelings_move_within_their_ranges_and_read_as_words(app):
    with app.state.database.connect(write=True) as connection:
        someone(connection)
        feelings.change(connection, 'k1', {'trust': -9, 'fear': 2, 'desire': -3, 'mood': 4}, 'Stiffed me on the bill.')
        feelings.change(connection, 'k1', {'trust': -2, 'fear': 1}, 'Stiffed me on the bill.')
        row = dict(connection.execute("SELECT * FROM story_people WHERE key='k1'").fetchone())
    # At most two a turn, never past the ends, and an impression is kept once.
    assert feelings.of(row) == {'trust': -4, 'affection': 0, 'respect': 0, 'fear': 3, 'desire': 0}
    assert row['impressions'] == '["Stiffed me on the bill."]'
    assert feelings.text(row) == "Toward the player's character: deeply distrusts them, is afraid of them."
    assert feelings.shown(row) == 'Deeply distrusts you, is afraid of you'
    assert feelings.text(None) == '' and feelings.shown(None) == ''


def test_warm_people_are_easier_to_persuade_and_cold_ones_harder(app):
    with app.state.database.connect(write=True) as connection:
        someone(connection, 'warm', 'Dana Kim', trust=2, affection=2)
        feelings.change(connection, 'warm', {'trust': 1})
        someone(connection, 'cold', 'Rook Hale', trust=-2, affection=-2)
        actions = [{'action': 'I talk Dana into lending me her cart.', 'stat': 'Allure', 'difficulty': 'normal'},
                   {'action': 'I sweet-talk Rook.', 'stat': 'Allure', 'difficulty': 'hard'},
                   {'action': 'I punch Rook.', 'stat': 'Vitality', 'difficulty': 'normal'},
                   {'action': 'I charm the stranger.', 'stat': 'Allure', 'difficulty': 'normal'}]
        assert [action['difficulty'] for action in feelings.adjust(connection, actions)] == \
            ['easy', 'very_hard', 'normal', 'normal']


def test_a_roll_aimed_at_someone_moves_their_feelings(app):
    with app.state.database.connect(write=True) as connection:
        someone(connection)
        feelings.from_rolls(connection, [
            {'action': 'I charm Dana.', 'stat': 'Allure', 'band': 'success'},
            {'action': 'I glare at Dana until she backs off.', 'stat': 'Resolve', 'band': 'critical_success'},
            {'action': 'I punch the bouncer.', 'stat': 'Vitality', 'band': 'success'}])
        row = dict(connection.execute("SELECT * FROM story_people WHERE key='k1'").fetchone())
    assert feelings.of(row) == {'trust': 1, 'affection': 1, 'respect': 2, 'fear': 2, 'desire': 0}


class Lucky:
    """Dice that always roll high."""

    def randint(self, low, high):
        return 95 if high == 100 else high

    def choice(self, items):
        return items[0]


def met_someone(client, clock, provider):
    from test_story import busy_place, connect
    connect(client)
    place, people = busy_place(client, clock)
    ok(client.put('/api/story/scene', json={'city_id': 'baltimore', 'place_id': place['id']}))
    them = people[0]['sheet']
    provider.replies = [reply(f'"I\'m {them["name"]}," they say.')]
    say(client, 'I say hello.', 'story-0001')
    return them


def test_charming_someone_warms_them_and_the_narrator_and_player_hear_of_it(client, clock, provider, app):
    them = met_someone(client, clock, provider)
    app.state.dice = Lucky()
    provider.replies = [reply(f'{them["name"]} laughs.'), reply(f'{them["name"]} pours another.')]
    say(client, f'I charm {them["name"]} with a story about the harbour.', 'story-0002')
    say(client, f'I ask {them["name"]} about the town.', 'story-0003')
    assert "Toward the player's character: trusts them a little, likes them." in provider.requests[-1]['system']
    # The player sees it only with the dice shown.
    assert ok(client.get('/api/story'))['people'][0]['feelings'] == ''
    ok(client.put('/api/settings', json={'show_odds': True}))
    assert ok(client.get('/api/story'))['people'][0]['feelings'] == 'Trusts you a little, likes you'

    # Telling it again moves them once, not twice.
    provider.replies = [reply(f'{them["name"]} shrugs.')]
    ok(client.post('/api/story/retry'))
    assert ok(client.get('/api/story'))['people'][0]['feelings'] == 'Trusts you a little, likes you'


def test_the_continuity_model_says_how_a_turn_left_someone_feeling(client, clock, provider, app):
    them = met_someone(client, clock, provider)
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': 'continuity', 'profile_id': profiles[0]['id']}))
    provider.replies = [reply(f'{them["name"]} flinches when you slam the table.'),
                        reply('{"facts": [], "feelings": [{"key": "%s", "changes": {"fear": 2, "trust": -1}, '
                              '"why": "Slammed the table at me."}, {"key": "stranger", "changes": {"fear": 2}}]}'
                              % them['key'])]
    say(client, f'I tell {them["name"]} to talk.', 'story-0002')
    assert f"- {them['key']}: {them['full']}" in provider.requests[-1]['system']
    provider.replies = [reply('Silence.'), reply('{"facts": []}')]
    say(client, f'I wait for {them["name"]}.', 'story-0003')
    narrator = provider.requests[-2]['system']
    assert 'is wary of them, is uneasy around them' in narrator
    assert 'Their impressions of the character: Slammed the table at me.' in narrator


def test_a_named_person_pursues_their_own_ends(client, connected, app):
    with app.state.database.connect() as connection:
        data = story.city_data(connection, 'kingswood')
    corin = next(sheet for sheet in story.townsfolk.at_place(data, 'felled-oak') if sheet.get('notable'))
    line = story.initiative(corin, data, story.datetime(2026, 10, 21, 20, 0))
    assert 'Right now they are after this: to sell what he hears this week to the highest bidder.' in line
    assert 'without waiting to be asked' in line
    resident = story.townsfolk.at_place(data, 'felled-oak')[0]
    assert story.initiative(resident, data, story.datetime(2026, 10, 21) + timedelta(hours=1)) == ''
