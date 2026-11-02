"""Someone with a reason may stop the character leaving, and the Table can turn it off (dungeon/leaving.py)."""
from conftest import Chunk, ok

from dungeon import combat, leaving, record

NOW = '2026-10-01T12:00:00Z'


class Dice:
    def __init__(self, natural):
        self.natural = natural

    def randint(self, low, high):
        return self.natural if (low, high) == (1, 100) else low

    def choice(self, items):
        return items[0]


def begin(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))


def person(key, full):
    return {'sheet': {'key': key, 'full': full, 'name': full.split()[0]}}


MARR, ASH = person('marr', 'Aldous Marr'), person('ash', 'Pell Ash')


def view(people, known):
    return {'people': people, 'known': known, 'local_time': '2026-10-01T12:00:00'}


def test_the_hostile_who_fear_nothing_and_the_fond_would_stop_the_character():
    assert leaving.holder(view([MARR], {'marr': {'affection': -3}}), set())['why'] == 'hostile'
    assert leaving.holder(view([MARR], {'marr': {'trust': -4}}), set())['strength'] == 4
    # Afraid of the character, they let them go; mildly cool, they don't care.
    assert leaving.holder(view([MARR], {'marr': {'affection': -5, 'fear': 3}}), set()) is None
    assert leaving.holder(view([MARR], {'marr': {'affection': -2}}), set()) is None
    assert leaving.holder(view([MARR], {'marr': {'desire': 4}}), set())['why'] == 'fond'
    assert leaving.holder(view([MARR], {'marr': {'affection': 3}}), set()) is None
    # Strangers and the character's own party never hold them; the strongest feeling does.
    assert leaving.holder(view([MARR], {}), set()) is None
    assert leaving.holder(view([MARR], {'marr': {'affection': 5}}), {'marr'}) is None
    found = leaving.holder(view([MARR, ASH], {'marr': {'affection': -3}, 'ash': {'desire': 5}}), set())
    assert (found['name'], found['why'], found['strength']) == ('Pell Ash', 'fond', 5)


def test_the_roll_fits_how_the_line_leaves():
    hostile = {'name': 'Aldous Marr', 'why': 'hostile'}
    assert leaving.approach(hostile, 'I shove past him and out.')[0] == 'Vitality'
    assert leaving.approach(hostile, 'I talk my way out of it.')[0] == 'Allure'
    assert leaving.approach(hostile, 'I leave.') == ('Resolve', 'get past Aldous, who means to stop them leaving')
    assert leaving.approach({'name': 'Pell Ash', 'why': 'fond'}, 'I leave.')[0] == 'Resolve'
    assert leaving.leaves('I storm out.') and leaving.leaves('Time to leave.') and not leaving.leaves('I sit down.')


def test_a_failed_roll_keeps_the_character_and_is_decided_once(app, client):
    begin(client)
    held = view([MARR], {'marr': {'affection': -4}})
    with app.state.database.connect(write=True) as connection:
        assert leaving.decide(connection, 'm0', held, 'I order another ale.', False, NOW, Dice(1)) is None
        kept = leaving.decide(connection, 'm1', held, 'I walk out.', False, NOW, Dice(1))
        assert kept['stopped'] and 'Aldous Marr stops them' in kept['lines'][1]
        assert kept['roll']['difficulty'] == 'hard'
        assert leaving.decide(connection, 'm1', held, 'I walk out.', False, NOW, Dice(100))['stopped']
        assert leaving.stopped(connection, 'm1')
        assert any('stopped the player' in row['text'] for row in record.entries(connection, known_only=False))
        away = leaving.decide(connection, 'm2', held, 'I walk out.', False, NOW, Dice(100))
        assert not away['stopped'] and 'gets past them' in away['lines'][1]


def test_the_table_decides_who_can_stop_the_character(app, client):
    begin(client)
    held = view([MARR], {'marr': {'affection': -4}})
    assert ok(client.get('/api/story/table'))['leaving'] == 'anyone'
    ok(client.put('/api/story/table', json={'leaving': 'fights'}))
    with app.state.database.connect(write=True) as connection:
        assert leaving.decide(connection, 'm1', held, 'I walk out.', True, NOW, Dice(1)) is None
        assert not leaving.free_from_fights(connection)
    ok(client.put('/api/story/table', json={'leaving': 'nobody'}))
    with app.state.database.connect() as connection:
        assert leaving.free_from_fights(connection)
    assert client.put('/api/story/table', json={'leaving': 'sometimes'}).status_code == 422


def test_someone_there_stops_the_menu_and_the_line_that_walks_off(client, connected, provider, monkeypatch, app):
    begin(client)
    monkeypatch.setattr(leaving, 'holder', lambda view, kept: {'name': 'Aldous Marr', 'key': 'marr', 'why': 'hostile',
                                                               'strength': 3})
    refused = client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'shrine-of-tidum'})
    assert refused.status_code == 409 and "Aldous won't let you just walk away" in refused.text
    app.state.dice = Dice(1)
    provider.replies = [[Chunk('He blocks the door.'), Chunk('', 'stop')]] * 3
    told = ok(client.post('/api/story/messages', json={'text': 'I go to the shrine.', 'client_id': 'story-0001'}))
    view_now = ok(client.get('/api/story'))
    assert view_now['scene']['place']['id'] == 'felled-oak'
    system = [request for request in provider.requests if 'Leaving (decided by the game)' in request['system']]
    assert system and 'goes nowhere this line' in system[-1]['system']
    with app.state.database.connect() as connection:
        cards = connection.execute('SELECT action FROM story_rolls WHERE message_id=?',
                                   (told['message']['id'],)).fetchall()
    assert any('get past Aldous' in row['action'] for row in cards)
    # A rule that lets fights hold the character but nobody else lets them go.
    ok(client.put('/api/story/table', json={'leaving': 'fights'}))
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'shrine-of-tidum'}))


def test_with_nobody_holding_the_character_they_walk_out_of_a_fight(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, {'round': 1, 'wants': 'kill', 'foes': [
            {'id': 'f1', 'name': 'the wolf', 'wound': 0, 'broken': False}], 'initiative': None, 'bare': 0,
            'area': None})
    assert client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'shrine-of-tidum'}).status_code \
        == 409
    ok(client.put('/api/story/table', json={'leaving': 'nobody'}))
    moved = ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'shrine-of-tidum'}))
    assert moved['scene']['place']['id'] == 'shrine-of-tidum'
    with app.state.database.connect() as connection:
        assert combat.fight(connection) is None
        assert any('Walked away from a fight with the wolf' in row['text']
                   for row in record.entries(connection, known_only=False))


def test_with_nobody_holding_the_character_a_flight_always_gets_away(app, client):
    begin(client)
    state = {'round': 1, 'wants': 'kill', 'foes': [{'id': 'f1', 'name': 'the wolf', 'wound': 0, 'broken': False}]}
    roll = {'action': 'I run for the door', 'stat': 'Vitality', 'band': 'failure'}
    with app.state.database.connect(write=True) as connection:
        assert combat.player_move(connection, state, roll, [], Dice(1), []) == (False, False)
    ok(client.put('/api/story/table', json={'leaving': 'nobody'}))
    with app.state.database.connect(write=True) as connection:
        assert combat.player_move(connection, state, roll, [], Dice(1), [])[0]
