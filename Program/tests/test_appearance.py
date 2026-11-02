"""How the character looks (dungeon/appearance.py): cleanliness, clothes, the state of dress and what is on show."""
from conftest import Chunk, tell

from dungeon import appearance, inventory


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def begin(client, place='the-wayhouse'):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': place}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))


def test_the_road_a_fight_and_work_dirty_the_character_and_washing_cleans(client, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        assert appearance.changed(connection, 'm1', 'I set out for Eriane.', {'travelled': True}, 'the road',
                                  '2026-10-01') == ['The character is worn (road dust) now.']
        lines = appearance.changed(connection, 'm2', 'I swing at him.', {'fought': True, 'wounded': True}, 'the road',
                                   '2026-10-01')
        assert lines == ['The character is grimy (road dust, sweat, blood) now.', 'Their clothes are torn now.']
        # Told again, the same line changes nothing more.
        assert appearance.changed(connection, 'm2', 'I swing at him.', {'fought': True, 'wounded': True}, 'x',
                                  '2026-10-01') == lines
        assert appearance.state(connection)['grime'] == 2
        appearance.changed(connection, 'm3', 'I spend the day felling trees.', {}, 'the stump fields', '2026-10-01')
        assert appearance.state(connection)['grime'] == 3 and 'sawdust' in appearance.state(connection)['marks']
        appearance.changed(connection, 'm4', 'I wash in the river.', {}, 'the ford', '2026-10-01')
        assert (appearance.state(connection)['grime'], appearance.state(connection)['marks']) == (2, [])
        # Another wound in torn clothes ruins them; new clothes bought replace ruined ones.
        appearance.changed(connection, 'm5', 'I fight on.', {'fought': True, 'wounded': True}, 'x', '2026-10-01')
        assert appearance.state(connection)['clothes'] == 'ruined'
        appearance.changed(connection, 'm6', 'I buy a cloak.', {'bought_clothes': True}, 'x', '2026-10-01')
        assert appearance.state(connection)['clothes'] == 'intact'


def test_a_paid_bath_and_mending_clear_it_all(client, app):
    begin(client)
    inn = inventory.shop_at('kingswood', 'the-wayhouse')
    with app.state.database.connect(write=True) as connection:
        appearance.save(connection, {'grime': 3, 'marks': ['blood'], 'clothes': 'torn', 'dress': dict(appearance.DRESSED)})
        inventory.set_purse(connection, 1000)
        for item_id in ('hot-bath', 'mending'):
            inventory.buy(connection, 'kingswood', inn, item_id, 1, '2026-10-01T18:00:00Z', '2026-10-01')
        appearance.changed(connection, 'm1', 'I sink into the bath.', {}, 'the Wayhouse', '2026-10-01')
        assert appearance.state(connection) | {'dress': None} == {'grime': 0, 'marks': [], 'clothes': 'intact',
                                                                  'dress': None}
        # A bath is used once: the next line's dirt stays.
        appearance.changed(connection, 'm2', 'I spend the day hauling logs.', {}, 'x', '2026-10-01')
        assert appearance.state(connection)['grime'] == 1


def test_undressing_and_dressing_by_layer(client, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        appearance.changed(connection, 'm1', 'I take off my cloak and boots.', {}, 'the Felled Oak', '2026-10-01')
        dress = appearance.state(connection)['dress']
        assert dress == {'outer': 'off (the Felled Oak)', 'under': 'worn', 'accessories': 'off (the Felled Oak)'}
        appearance.changed(connection, 'm2', 'I loosen my shirt.', {}, 'x', '2026-10-01')
        assert appearance.state(connection)['dress']['under'] == 'loosened'
        appearance.changed(connection, 'm3', 'I undress.', {}, 'the Wayhouse', '2026-10-01')
        assert set(appearance.state(connection)['dress'].values()) == {'off (the Felled Oak)', 'off (the Wayhouse)'}
        appearance.changed(connection, 'm4', 'I get dressed.', {}, 'x', '2026-10-01')
        assert appearance.state(connection)['dress'] == appearance.DRESSED
        # A world that keeps only cleanliness and condition ignores the state of dress.
        appearance.changed(connection, 'm5', 'I take off my cloak.', {}, 'x', '2026-10-01', 'basic')
        assert appearance.state(connection)['dress'] == appearance.DRESSED


def test_the_narrator_and_the_pack_are_told_how_the_character_looks(client, connected, provider):
    begin(client, 'the-green')
    provider.replies = [[Chunk('The road is long.'), Chunk('', 'stop')]] * 2
    tell(client, 'I spend the day chopping wood.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert '## How the character looks (changed this turn, by the game)\n- The character is worn (sweat, sawdust) now.' \
        in narrator
    assert 'How the character looks right now (kept by the game' in narrator and 'on show: Plain sword, Belt knife' in narrator
    looks = ok(client.get('/api/story/gear'))['looks']
    assert looks['grime'] == 'worn' and looks['on_show'] == ['Plain sword', 'Belt knife']


def test_carrying_limits_can_be_turned_off(client, app):
    begin(client)
    assert ok(client.get('/api/story/gear'))['slots']['max'] == 13
    ok(client.put('/api/story/table', json={'carry_limit': 'off'}))
    assert ok(client.get('/api/story/gear'))['slots']['max'] is None
    with app.state.database.connect() as connection:
        assert inventory.capacity(connection) == inventory.UNLIMITED
