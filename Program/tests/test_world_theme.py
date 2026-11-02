"""A world's own colors (dungeon/world_theme.py): read from its package's world.json, whole or not at all."""
from test_travel import ok

from dungeon import world_theme


def test_a_theme_is_whole_or_none():
    palette = {'accent': '#C4623F', 'background': '#15110e', 'surface': '#1d1814', 'text': '#e8ddcb'}
    assert world_theme.cleaned({'name': ' Ember ', 'palette': palette}) == {
        'name': 'Ember', 'palette': palette | {'accent': '#c4623f'}}
    assert world_theme.cleaned({'palette': palette})['name'] == "The world's colors"
    assert world_theme.cleaned({'palette': palette | {'text': 'beige'}}) is None
    assert world_theme.cleaned({'palette': {'accent': '#c4623f'}}) is None
    assert world_theme.cleaned('dark') is None and world_theme.cleaned(None) is None


def test_the_story_wears_its_worlds_colors(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    found = ok(client.get('/api/story/theme'))
    assert found['world'] == 'vallarith'
    assert found['theme']['name'] == 'Ember and soot' and found['theme']['palette']['background'] == '#15110e'


def test_every_built_in_world_ships_a_whole_theme(tmp_path):
    for world in ('vallarith', 'havenbrooke', 'babel'):
        assert world_theme.of_world(tmp_path, world) is not None, world
    assert world_theme.of_world(tmp_path, None) is None
