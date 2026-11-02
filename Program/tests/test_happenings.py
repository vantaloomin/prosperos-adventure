"""Life Cards in play (dungeon/happenings.py): a day in town, a journey and a rest draw from the world's deck."""
import re
from datetime import date

import pytest
from conftest import tell
from test_inventory import begin
from test_rest import out_in_the_badlands
from test_travel import Road, ok, reply

from dungeon import happenings, inventory
from dungeon.life import cards


@pytest.fixture
def dealt(monkeypatch):
    """Life Cards on, with every draw the card named in `dealt.next` (None for nothing), and each call kept."""
    monkeypatch.setattr(happenings, 'ACTIVE', True)

    class Dealer:
        next, calls = None, []

        def draw(self, world, scene, seed, level, intensity, has, recent, region=None, veils=frozenset(), forced=False):
            self.calls.append({'scene': scene, 'level': level, 'region': region, 'recent': recent,
                               'intensity': intensity})
            found = cards.card(world, self.next)
            return {'card': found, 'odds': 0.5, 'veiled': False}

    dealer = Dealer()
    dealer.calls = []
    monkeypatch.setattr(cards, 'draw', dealer.draw)
    return dealer


def test_a_day_in_town_draws_once_and_plays_the_card(client, connected, provider, app, dealt):
    begin(client)
    dealt.next = 'early-tithe'
    with app.state.database.connect() as connection:
        before = inventory.purse(connection)
    reply(provider, 'Soldiers at the doors.')
    tell(client, 'I look out of the window.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert '## What the world brings' in narrator and 'war tithe, a month early' in narrator
    assert 'It puts a choice to the player: A widow on your street' in narrator
    # Two of a logger's day wages (1.50 cr. each).
    assert 'It costs the character 3.00 cr.' in narrator
    with app.state.database.connect() as connection:
        assert inventory.purse(connection) == max(0, before - 300)
        facts = {row['truth']: row['text'] for row in connection.execute(
            "SELECT truth, text FROM record_entries WHERE subject='The tithe comes early'").fetchall()}
    assert 'lost at cards' in facts['world'] and 'door to door' in facts['belief']
    assert dealt.calls[0]['scene'] == 'town' and dealt.calls[0]['region'] == 'cyrel'
    assert dealt.calls[0]['level'] == cards.DRAMA.index('eventful')
    # The same day draws no more.
    reply(provider, 'Still raining.')
    tell(client, 'I sit down again.', 'story-0002')
    assert len(dealt.calls) == 1 and '## What the world brings' not in provider.requests[-1]['system']


def test_the_drama_setting_and_intensity_decide_what_can_turn_up(client, connected, provider, dealt):
    begin(client)
    ok(client.put('/api/settings', json={'drama': 'quiet', 'intensity': 'restrained'}))
    assert ok(client.get('/api/story'))['intensity']['drama'] == 'quiet'
    reply(provider, 'Quiet.')
    tell(client, 'I wait.', 'story-0001')
    call = dealt.calls[0]
    assert call['level'] == 0 and call['intensity'] == cards.PRESETS['restrained']
    # Cards that need someone the game cannot name yet never come up.
    assert happenings.unnamed('vallarith', faction=True) <= call['recent']


def test_a_road_card_can_bring_a_fight(client, connected, provider, app, dealt):
    begin(client)
    dealt.next = 'hungry-deserters'
    app.state.dice = Road(99)
    reply(provider, 'The road goes on.')
    tell(client, 'I set out for Eriane.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert story['scene']['place']['id'] == 'eriane' and story['fight']['fight']['foes'][0]['name'] == 'deserter 1'
    assert dealt.calls[-1]['scene'] == 'road' and 'It comes to a fight: deserters close in.' in \
        provider.requests[-1]['system']


def test_a_rest_card_with_foes_ends_the_rest(client, connected, provider, app, dealt):
    out_in_the_badlands(client)
    dealt.next = 'wolves'
    app.state.dice = Road(99)
    reply(provider, 'Eyes in the dark.')
    tell(client, 'I make camp and keep watch.', 'story-0001')
    narrator = provider.requests[-1]['system'].split('## The rest')[1]
    assert 'starving wolves close in' in narrator and 'The rest ends here' in narrator
    assert [call['scene'] for call in dealt.calls] == ['rest']


def test_every_card_the_game_can_draw_has_every_name_filled(app):
    """Real draws: whatever turns up in town, on the road or at rest, the text leaves no placeholder behind."""
    names = {'pc': 'Agna', 'npc': 'Corin Ashby', 'town': 'Kingswood'}
    with app.state.database.connect() as connection:
        for n in range(150):
            for scene, place in (('town', ('kingswood', 'felled-oak')), ('road', ('vallarith-road', 'eriane')),
                                 ('rest', ('vallarith-road', 'adlmyr'))):
                drawn = happenings.draw(connection, scene, f'seed-{n}', *place, {'intensity': {'drama': 'merciless'}},
                                        {'levels': cards.PRESETS['unflinching'], 'veils': []}, date(1290, 5, 1))
                if drawn:
                    for field in ('title', 'truth', 'seen', 'pressure'):
                        assert not re.search(r'\{\w+\}', happenings.fill(drawn['card'][field] or '', names))


def test_fate_rumor_quest_and_pursuer_effects_are_applied(client, app):
    from datetime import datetime

    from dungeon import director, record
    begin(client)
    now = datetime(2026, 10, 1, 12)
    context = {'npc': {'key': 'pell', 'full': 'Pell Ash'}, 'title': 'a knife in the dark', 'truth': 'Pell was knifed.',
               'seen': 'They say Pell was knifed.', 'pressure': '', 'logged': '2026-10-01T12:00:00Z', 'now': now,
               'city': 'kingswood', 'faction': None}
    with app.state.database.connect(write=True) as connection:
        assert happenings.fated(connection, {'who': 'npc', 'state': 'dead'}, context) == [
            'From now on Pell Ash is dead: play them so.']
        assert 'pell ash' in record.dead(connection)
        assert happenings.fated(connection, {'who': 'them', 'state': 'dead'}, context) == []

        assert 'treat them by it' in happenings.rumored(connection, {'about': 'pc', 'true': False}, context)[0]
        happenings.rumored(connection, {'about': 'npc', 'true': False}, context)
        lies = [row['text'] for row in record.entries(connection, known_only=False) if row['truth'] == 'world']
        assert 'Word going round town: They say Pell was knifed.' in lies and \
            'A false rumor: They say Pell was knifed.' in lies

        lines = happenings.quested(connection, {'from': 'npc', 'days': 10}, context)
        assert lines[0].startswith('Pell Ash wants something of the character, within 10 days')
        quest = connection.execute("SELECT * FROM story_quests WHERE kind='job'").fetchone()
        assert quest['giver'] == 'Pell Ash' and quest['due_at'].startswith('2026-10-11') and \
            quest['truth'] == 'Pell was knifed.'

        assert 'about 1 day behind' in happenings.pursued(connection, {'days': 1}, context)[0]
        assert director.due_nemesis(connection, now) is None
        due = director.due_nemesis(connection, datetime(2026, 10, 2, 12))
        assert due['name'] == "whoever is on the character's trail" and due['grudge'] == 'Pell was knifed.'


def test_a_drawn_card_shows_under_the_line_with_its_picture_and_a_veiled_one_shows_its_back(
        client, connected, provider, app, dealt, monkeypatch):
    from dungeon import world_data
    real = world_data.asset
    monkeypatch.setattr(world_data, 'asset', lambda world, name: b'RIFF0000WEBP' if name.startswith('cards/')
                        else real(world, name))
    begin(client)
    dealt.next = 'hanging-day'
    reply(provider, 'Three men in the square.')
    tell(client, 'I walk to the market.', 'story-0001')
    line = next(message for message in ok(client.get('/api/story'))['messages'] if message['role'] == 'user')
    assert line['cards'] == [{'title': 'Hanging day', 'tone': 'bad', 'veiled': False,
                              'art': '/api/story/art/card/vallarith/hanging-day.webp'}]
    served = client.get(line['cards'][0]['art'])
    assert served.status_code == 200 and served.content == b'RIFF0000WEBP'
    assert client.get('/api/story/art/card/vallarith/..%2Fmaps%2Fvallarith.jpg').status_code == 404
    with app.state.database.connect() as connection:
        rows = [{'id': line['id'], 'role': 'user', 'city_id': line['city_id']}]
        veiled = happenings.with_cards(connection, rows, {'execution'})[0]['cards'][0]
    assert veiled == {'title': 'Veiled', 'tone': 'grey', 'veiled': True, 'art': '/api/story/art/card/vallarith/back.webp'}


def test_every_life_card_has_its_picture_and_every_world_its_card_back():
    from dungeon import world_data
    for world in cards.worlds():
        assert world_data.asset(world, 'cards/back.webp'), world
        missing = [item['id'] for item in cards.cards(world) if not world_data.asset(world, f"cards/{item['id']}.webp")]
        # A card the image model refuses to draw gets its own scene in scripts/art/cards.py SCENES.
        assert not missing, (world, missing)
