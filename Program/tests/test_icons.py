"""Faction emblems and item icons (dungeon/icons.py): every faction and item of the built-in worlds has its picture,
and the pack, the counter and the powers carry them."""
import json

from dungeon import icons, inventory, packages, tiers, world_data

WORLDS = ('vallarith', 'havenbrooke', 'babel')


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def art(world: str) -> dict:
    return json.loads((packages.BUILTIN / world / 'engine' / 'art' / f'{world}.json').read_text(encoding='utf-8'))


def test_every_faction_has_an_emblem_and_every_item_an_icon_made(client):
    for world in WORLDS:
        data, assets = art(world), packages.BUILTIN / world / 'assets'
        factions = json.loads((packages.BUILTIN / world / 'factions.json').read_text(encoding='utf-8'))['factions']
        assert [entry['id'] for entry in data['emblems']] == [faction['id'] for faction in factions]
        ids = [entry['id'] for entry in data['icons']]
        assert len(ids) == len(set(ids)) and all(entry['prompt'] for entry in data['emblems'] + data['icons'])
        for entry in data['emblems']:
            assert (assets / 'emblems' / f"{entry['id']}.webp").is_file(), entry['id']
        for entry in data['icons']:
            assert (assets / 'icons' / f"{entry['id']}.webp").is_file(), entry['id']
        towns = [path.stem for path in inventory.ITEMS.glob('*.json') if tiers.world_of(path.stem) == world]
        assert towns
        for town in towns:
            for item in inventory.catalog(town)['items']:
                assert icons.icon(town, item['id'], item['category']) == icons.url(
                    'icon', world, next(entry['id'] for entry in data['icons']
                                        if item['id'] in (entry['id'], *entry.get('items', [])))), item['id']
                # Every kind of item has a picture too, for one an edited world adds.
                assert icons.icon(town, 'something-new', item['category'])


def test_an_item_with_no_icon_of_its_own_shows_its_kind_and_a_town_off_the_map_none(client):
    assert icons.icon('kingswood', 'bread', 'food') == '/api/story/art/icon/vallarith/bread.webp'
    assert icons.icon('kingswood', 'smoked-eel', 'food') == '/api/story/art/icon/vallarith/kind-food.webp'
    # A night's lodging of any comfort has the one bed.
    assert icons.icon('kingswood', 'private-room', 'service') == '/api/story/art/icon/vallarith/lodging.webp'
    assert icons.icon('nowhere', 'bread', 'food') is None
    assert icons.emblem('vallarith', 'kingdom-of-cyrel') == '/api/story/art/emblem/vallarith/kingdom-of-cyrel.webp'
    assert icons.emblem('vallarith', 'no-such-power') is None and icons.emblem(None, 'kingdom-of-cyrel') is None


def test_the_pack_the_counter_and_the_powers_carry_their_pictures(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    gear = ok(client.get('/api/story/gear'))
    pack = {item['item_id']: item['icon'] for item in gear['items']}
    assert pack['sword'] == '/api/story/art/icon/vallarith/sword.webp'
    assert all(row['icon'] for row in gear['shop']['stock'])
    served = client.get(pack['sword'])
    assert served.status_code == 200 and served.headers['content-type'] == 'image/webp'
    assert served.content == world_data.asset('vallarith', 'icons/sword.webp')
    powers = {faction['id']: faction['emblem'] for faction in ok(client.get('/api/story'))['factions']}
    assert powers['kingdom-of-cyrel'] == '/api/story/art/emblem/vallarith/kingdom-of-cyrel.webp'
    assert client.get(powers['kingdom-of-cyrel']).status_code == 200
    assert client.get('/api/story/art/icon/vallarith/..%2Fmaps%2Fvallarith.jpg').status_code == 404
    assert client.get('/api/story/art/icon/vallarith/no-such-thing.webp').status_code == 404
    assert client.get('/api/story/art/poster/vallarith/sword.webp').status_code == 422
