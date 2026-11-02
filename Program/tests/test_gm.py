"""The GM view (dungeon/gm.py): everything behind the story, secrets included, and set by hand."""
from test_director import start
from test_travel import ok

from dungeon import record


def test_the_gm_view_shows_what_is_behind_the_story_and_sets_feelings_and_standing(client, app):
    start(client)
    assert client.get('/api/story/gm').status_code == 409
    ok(client.put('/api/settings', json={'gm_view': True}))
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day) VALUES "
                           "('pell', 'kingswood', 'Pell', 'x', 'x', '1290-05-01')")
        entry = record.add(connection, 'fact', 'Pell', 'Pell sells rope.', 'x', 'player')
        record.correct(connection, entry['id'], 'y', 'Pell sells good rope.')
    view = ok(client.get('/api/story/gm'))
    heartwood = next(quest for quest in view['quests'] if quest['id'] == 'the-heartwood-contract')
    assert heartwood['truth'] and {arc['id'] for arc in view['arcs']} >= {'the-eight-pieces'}
    assert next(arc for arc in view['arcs'] if arc['id'] == 'the-eight-pieces')['title'] == 'The Eight Pieces'
    assert view['corrections'][0] | {'created_at': ''} == {'before': 'Pell sells rope.', 'after': 'Pell sells good rope.',
                                                          'subject': 'Pell', 'created_at': ''}
    view = ok(client.patch('/api/story/gm/people/pell', json={'trust': 4, 'fear': 2}))
    assert view['people'][0]['feelings'] | {} == {'trust': 4, 'affection': 0, 'respect': 0, 'fear': 2, 'desire': 0}
    assert client.patch('/api/story/gm/people/nobody', json={'trust': 1}).status_code == 404
    view = ok(client.put('/api/story/gm/factions/the-guild', json={'value': -3}))
    assert {'faction_id': 'the-guild', 'value': -3} in view['factions']
