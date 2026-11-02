"""Intensity v0 (dungeon/story.py intensity): the world's preset, or the player's, shapes the narrator's prompt."""
from conftest import Chunk, tell


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def narrator_after(client, provider, client_id):
    provider.replies = [[Chunk('Rain on the shingles.'), Chunk('', 'stop')]]
    tell(client, 'I listen.', client_id)
    return provider.requests[-1]['system']


def test_kingswood_is_grim_and_unflinching_until_the_player_turns_it_down(client, connected, provider):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    found = ok(client.get('/api/story'))['intensity']
    assert {key: found[key] for key in ('preset', 'chosen', 'world', 'drama', 'drama_chosen', 'drama_world', 'cutaways',
                                        'defeat', 'ruleset', 'levels', 'custom', 'veils', 'voice_chosen')} == \
        {'preset': 'unflinching', 'chosen': 'world', 'world': 'unflinching', 'drama': 'eventful',
         'drama_chosen': 'world', 'drama_world': 'eventful', 'cutaways': False, 'defeat': 'as_written',
         'ruleset': 'marvel', 'levels': dict.fromkeys(('violence', 'sex', 'horror', 'cruelty', 'drugs'), 3),
         'custom': False, 'veils': [], 'voice_chosen': 'world'}
    narrator = narrator_after(client, provider, 'story-0001')
    assert '- Violence: unflinching: explicit' in narrator and 'Voice: grim and earthy' in narrator

    # Mid-story, the next line follows the new preset; the world's voice stays.
    settings = ok(client.put('/api/settings', json={'intensity': 'restrained'}))
    assert settings['intensity'] == 'restrained'
    assert ok(client.get('/api/story'))['intensity']['preset'] == 'restrained'
    narrator = narrator_after(client, provider, 'story-0002')
    assert '- Sex: restrained: implied' in narrator and 'unflinching' not in narrator
    assert 'Voice: grim and earthy' in narrator
    assert client.put('/api/settings', json={'intensity': 'gory'}).status_code == 422


def test_a_world_without_its_own_preset_is_unflinching_with_no_voice(client, connected, provider):
    ok(client.put('/api/story/scene', json={'city_id': 'baltimore'}))
    narrator = narrator_after(client, provider, 'story-0001')
    assert '- Horror: unflinching' in narrator and 'Voice:' not in narrator


def test_each_category_has_its_own_level_veils_fade_to_black_and_a_preset_resets_them(client, connected, provider):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    rules = ok(client.put('/api/story/table', json={'levels': {'sex': 0, 'violence': 2}, 'veils': ['torture'],
                                                    'voice': 'wry'}))
    assert rules['levels'] == {'sex': 0, 'violence': 2} and rules['veils'] == ['torture']
    found = ok(client.get('/api/story'))['intensity']
    assert found['levels'] == {'violence': 2, 'sex': 0, 'horror': 3, 'cruelty': 3, 'drugs': 3} and found['custom']
    narrator = narrator_after(client, provider, 'story-0001')
    assert '- Sex: off the page' in narrator and '- Violence: mature' in narrator and '- Horror: unflinching' in narrator
    assert '- Veiled: torture.' in narrator and 'Voice: wry and dry' in narrator and 'grim and earthy' not in narrator
    # A preset sets every category again; the veils and the voice stay.
    ok(client.put('/api/story/table', json={'intensity': 'mature'}))
    found = ok(client.get('/api/story'))['intensity']
    assert set(found['levels'].values()) == {2} and not found['custom'] and found['veils'] == ['torture']
    assert client.put('/api/story/table', json={'levels': {'gore': 1}}).status_code == 422
    assert client.put('/api/story/table', json={'levels': {'sex': 4}}).status_code == 422


def test_low_violence_leaves_maiming_out_of_the_lasting_injuries(client, app):
    from datetime import datetime

    from dungeon import injuries, table
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    maiming = {entry['id'] for entry in injuries.table() if entry.get('intensity')}
    assert maiming == {'lost-eye', 'ruined-hand', 'lost-fingers'}
    with app.state.database.connect(write=True) as connection:
        table.change(connection, {'levels': {'violence': 1}})
        got = {injuries.roll(connection, datetime(1290, 5, 1), 'a test') for _ in range(len(injuries.table()))}
        kept = {row['injury_id'] for row in connection.execute('SELECT injury_id FROM story_injuries')}
    assert kept and not kept & maiming and None in got
