"""Image backends and text models per world (adventure/images/world_choice.py, adventure/world_models.py): anime in
one world, photographs in another. Backends and profiles follow the user between worlds; each world keeps its own pick."""
from adventure.images import backends


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def add(client, label, address):
    return ok(client.post('/api/images/backends', json={'kind': 'comfyui', 'base_url': address, 'label': label}))


def used(app):
    with app.state.database.connect() as connection:
        return [backend['label'] for backend in backends.ordered(connection, enabled_only=True)]


def test_a_world_uses_every_backend_until_one_is_picked_for_it(client, app):
    photos = add(client, 'Photographs', 'http://127.0.0.1:8188')
    anime = add(client, 'Anime', 'http://127.0.0.1:8189')
    listing = ok(client.get('/api/images/backends'))
    assert listing['world'] == {'own': False, 'picked': [], 'falls_back': False, 'used': [photos['id'], anime['id']]}
    assert [backend['in_world'] for backend in listing['backends']] == [True, True]

    picked = ok(client.put('/api/images/world', json={'backend_ids': [anime['id']]}))
    assert picked['world']['own'] and picked['world']['used'] == [anime['id']]
    assert [backend['in_world'] for backend in picked['backends']] == [False, True]
    assert used(app) == ['Anime']
    # None picked is refused rather than leaving the world with no pictures.
    assert client.put('/api/images/world', json={'backend_ids': []}).status_code == 422
    assert ok(client.put('/api/images/world', json={'backend_ids': None}))['world']['own'] is False
    assert used(app) == ['Photographs', 'Anime']


def test_a_world_whose_picks_are_all_off_uses_the_rest_again(client, app):
    add(client, 'Photographs', 'http://127.0.0.1:8188')
    anime = add(client, 'Anime', 'http://127.0.0.1:8189')
    ok(client.put('/api/images/world', json={'backend_ids': [anime['id']]}))
    ok(client.put(f"/api/images/backends/{anime['id']}", json={'enabled': False}))
    assert ok(client.get('/api/images/backends'))['world']['falls_back']
    assert used(app) == ['Photographs']
    # A backend added here joins this world's picks; removing the last pick goes back to all of them.
    added = add(client, 'Painterly', 'http://127.0.0.1:8190')
    assert ok(client.get('/api/images/backends'))['world']['picked'] == [anime['id'], added['id']]
    ok(client.delete(f"/api/images/backends/{added['id']}"))
    world = ok(client.delete(f"/api/images/backends/{anime['id']}"))['world']
    assert world['own'] is False


def test_each_world_keeps_its_own_pick_while_backends_follow_the_user(client, app):
    photos = add(client, 'Photographs', 'http://127.0.0.1:8188')
    anime = add(client, 'Anime', 'http://127.0.0.1:8189')
    first = ok(client.get('/api/worlds'))['active_world_id']
    made = ok(client.post('/api/worlds', json={'name': 'Runeterra'}))
    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    ok(client.put('/api/images/world', json={'backend_ids': [anime['id']]}))
    assert used(app) == ['Anime']
    ok(client.post(f'/api/worlds/{first}/switch'))
    listing = ok(client.get('/api/images/backends'))
    assert [backend['id'] for backend in listing['backends']] == [photos['id'], anime['id']]
    assert listing['world']['own'] is False and used(app) == ['Photographs', 'Anime']
    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    assert used(app) == ['Anime']


def test_a_world_can_have_its_own_models_and_changes_only_its_own(client, connected):
    """Text models follow the same rule (Vanta, 2026-10-28): the usual assignments until a world has its own."""
    usual = connected['profile_id']
    other = client.post('/api/models/profiles', json={'name': 'Fantasy', 'config': {
        'provider': 'local', 'model': 'fantasy-model', 'base_url': 'http://127.0.0.1:1234/v1'}}).json()
    ok(client.put('/api/models/mix', json={'profile_ids': [usual, other['id']], 'mode': 'in_turn'}))  # The narrator's Mix.
    first = ok(client.get('/api/worlds'))['active_world_id']
    made = ok(client.post('/api/worlds', json={'name': 'Runeterra'}))
    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    assert ok(client.get('/api/models'))['world'] == {'own': False}

    own = ok(client.put('/api/models/world', json={'own': True}))
    assert own['world']['own'] and own['routes']['chat'] == usual and not own['mix']['story']['enabled']
    switched = ok(client.put('/api/models/routes', json={'job': 'chat', 'profile_id': other['id']}))
    assert switched['routes']['chat'] == other['id']

    ok(client.post(f'/api/worlds/{first}/switch'))
    back = ok(client.get('/api/models'))
    assert back['world'] == {'own': False} and back['routes']['chat'] == usual and back['mix']['story']['enabled']

    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    assert ok(client.get('/api/models'))['routes']['chat'] == other['id']
    assert ok(client.put('/api/models/world', json={'own': False}))['routes']['chat'] == usual
