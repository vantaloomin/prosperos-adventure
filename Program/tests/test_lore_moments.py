"""Lore in the story: always-on, named lately, or fitting the moment (dungeon/lore.py, dungeon/lore_moments.py)."""
import base64
import json
from datetime import datetime

from conftest import Chunk

from dungeon import lore_moments as moments
from dungeon import story


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def lorebook(entries) -> dict:
    data = base64.b64encode(json.dumps({'name': 'Harbour lore', 'entries': entries}).encode()).decode('ascii')
    return {'filename': 'harbour.json', 'data': data}


def test_a_when_needs_one_condition_of_each_kind_it_names():
    keys = {'weather:rain', 'time:night', 'day:weekday', 'place:docks'}
    assert moments.matches(['weather:rain', 'time:night'], keys)
    assert moments.matches(['time:evening', 'time:night'], keys)
    assert not moments.matches(['weather:rain', 'time:morning'], keys)
    assert not moments.matches([], keys)
    assert moments.matches(['place:Docks'], keys)


def test_a_when_is_read_from_keywords_that_are_a_moment():
    assert moments.guessed(['Winter', 'rain', 'snow'], []) == ['season:winter']
    assert moments.guessed(['fall', 'harbour'], []) == []
    assert moments.guessed(['Lantern Night'], ['Lantern Night']) == ['holiday:Lantern Night']
    assert moments.tidy(['place:docks', 'weather:rain', 'mood:sad', 'weather:rain', 'time: ']) == \
        ['weather:rain', 'place:docks']


def test_the_weather_counts_as_rain_snow_fog_or_heat():
    assert moments.weather_keys({'rain': True, 'low_f': 50, 'high_f': 60, 'note': ''}) == {'weather:rain'}
    assert moments.weather_keys({'rain': True, 'low_f': 25, 'high_f': 33, 'note': ''}) == {'weather:snow'}
    assert moments.weather_keys({'rain': False, 'low_f': 50, 'high_f': 60, 'note': 'Morning fog'}) == {'weather:fog'}
    assert moments.weather_keys({'rain': False, 'low_f': 70, 'high_f': 95, 'note': ''}) == {'weather:heat'}
    assert moments.weather_keys(None) == set()


def test_the_scene_gives_the_time_the_day_the_season_and_the_place(client):
    with client.app.state.database.connect() as connection:
        data = story.city_data(connection, 'baltimore')
    place = data['places'][0]
    keys = moments.now_keys(data, place['id'], datetime(2026, 1, 10, 22, 30))
    assert {'time:night', 'day:weekend', 'season:winter', f"place:{place['id']}",
            f"place:{place['neighborhood']}"} <= keys
    assert not any(key.startswith('place:') for key in moments.now_keys(data, '~somewhere', datetime(2026, 1, 12, 9)))


def test_the_narrator_reads_lore_that_is_always_on_named_lately_or_fits_the_moment(client, provider):
    ok(client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'}))
    ok(client.post('/api/import/lorebook', json=lorebook([
        {'keys': ['x'], 'content': 'The harbour bell rings for the drowned.', 'constant': True},
        {'keys': ['Pellam'], 'content': 'Pellam owes money to the tide-wardens.'},
        {'keys': ['morning', 'afternoon', 'evening', 'night'], 'content': 'Gulls cry over the slate roofs.'},
        {'keys': ['lanterns'], 'content': 'On wet days the lamplighters work double shifts.'},
    ])))
    listed = ok(client.get('/api/lore'))
    entries = listed['books'][0]['entries']
    assert entries[2]['when_guessed'] and [item['key'] for item in entries[2]['when']] == \
        ['time:morning', 'time:afternoon', 'time:evening', 'time:night']
    assert entries[2]['fits_now'] and not entries[1]['when'] and not entries[0]['when']
    assert {'weather', 'season', 'time', 'day', 'holiday', 'place'} <= set(listed['choices'])

    # The lamplighters' entry is given its own "when": never true, so it stays out until it is named.
    rain_at_noon = ['weather:rain', 'weather:snow', 'time:afternoon', 'place:nowhere-at-all']
    after = ok(client.put(f"/api/lore/entries/{entries[3]['id']}/when", json={'when': rain_at_noon}))
    assert not after['books'][0]['entries'][3]['when_guessed']

    provider.replies = [[Chunk('The bell tolls.'), Chunk('', 'stop')]]
    ok(client.post('/api/story/messages', json={'text': 'I ask after Pellam.', 'client_id': 'lore-0001'}))
    system = provider.requests[-1]['system']
    assert '## Lore' in system and 'The harbour bell rings for the drowned.' in system
    assert 'Pellam owes money to the tide-wardens.' in system and 'Gulls cry over the slate roofs.' in system
    assert 'lamplighters' not in system

    # Cleared, the entry comes by its keywords only.
    ok(client.put(f"/api/lore/entries/{entries[2]['id']}/when", json={'when': []}))
    provider.replies = [[Chunk('Quiet.'), Chunk('', 'stop')]]
    ok(client.post('/api/story/messages', json={'text': 'I wait for the lanterns.', 'client_id': 'lore-0002'}))
    system = provider.requests[-1]['system']
    assert 'Gulls cry' not in system and 'lamplighters work double shifts' in system


def test_an_always_on_entry_has_no_when(client):
    ok(client.post('/api/import/lorebook', json=lorebook([{'keys': ['x'], 'content': 'Always.', 'constant': True}])))
    entry = ok(client.get('/api/lore'))['books'][0]['entries'][0]
    refused = client.put(f"/api/lore/entries/{entry['id']}/when", json={'when': ['time:night']})
    assert refused.status_code == 422
