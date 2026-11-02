"""Gear and the shop (dungeon/inventory.py): the purse, the pack, carry slots and Pell's Provisions."""
from datetime import timedelta

from conftest import Chunk, tell

from dungeon import inventory
from dungeon.world import catalog


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def begin(client, premade='agna-holt', place='pell-provisions'):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': place}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': premade}))


def begin_when(client, clock, open_now=True, premade='agna-holt'):
    """Start the story at Pell's at an hour when the shop is open (or shut), moving the app clock an hour at a time."""
    for _ in range(24 * 7):
        begin(client, premade)
        if ok(client.get('/api/story/gear'))['shop']['open'] == open_now:
            return
        clock.instant = clock.now() + timedelta(hours=1)
    raise AssertionError("Pell's never opens or never shuts.")


def test_every_item_file_prices_from_its_catalog_and_kits_fit():
    for path in inventory.ITEMS.glob('*.json'):
        data = inventory.catalog(path.stem)
        ids = {entry['id'] for entry in data['items']}
        city = catalog.city(path.stem)
        places = {place['id'] for place in city['places']}
        for shop in data['shops']:
            assert shop['place'] in places and set(shop['stock']) <= ids and 0 < shop['sell_rate'] < 1
        for kit in data['kits'].values():
            assert set(kit['items']) <= ids and kit['coins'] >= 0
        # Ordinary things stay within ordinary means: no shop item costs more than a month of a logger's wage.
        wage = next(price['high'] for price in city['prices'] if price['id'] == 'day-wage')
        for shop in data['shops']:
            for item_id in shop['stock']:
                assert inventory.item(path.stem, item_id)['price'] <= wage * 30, item_id


def test_a_premade_starts_with_their_kit_and_the_narrator_knows_it(client, connected, provider):
    begin(client)
    gear = ok(client.get('/api/story/gear'))
    assert gear['coins'] == 340 and gear['currency']['symbol'] == 'cr.'
    assert {item['item_id'] for item in gear['items']} == {'sword', 'knife', 'blanket', 'boots', 'whetstone'}
    assert gear['slots']['max'] == 5 + 16 / 2 and gear['slots']['used'] == 1 + 0.25 + 1 + 1 + 0.1
    provider.replies = [[Chunk('The bell over the door rings.'), Chunk('', 'stop')]]
    tell(client, 'I look at the shelves.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert 'Carrying (kept by the game' in narrator and 'Plain sword' in narrator and 'Purse: 3.40 cr.' in narrator
    assert '## The shop here' in narrator
    # The symbol is how the game writes money; the narrator is told what it is called ("crowns", not "credits").
    assert 'Money here is silver crowns (cr. is only how the game writes it)' in narrator


def test_buying_and_selling_at_the_counter(client, connected, clock, app):
    begin_when(client, clock)
    shop = ok(client.get('/api/story/gear'))['shop']
    assert shop['open'] and shop['keeper'].startswith('the ')
    rope = next(row for row in shop['stock'] if row['item_id'] == 'rope')
    assert (rope['price'], rope['qty']) == (75, 5)

    bought = ok(client.post('/api/story/shop/buy', json={'item_id': 'rope', 'qty': 2}))
    assert bought['coins'] == 340 - 150
    assert next(row for row in bought['shop']['stock'] if row['item_id'] == 'rope')['qty'] == 3
    assert ok(client.get('/api/story'))['messages'][-1]['text'] == 'You buy 2 × Rope, fifty feet for 1.50 cr.'

    # Too dear, too heavy, or not stocked: refused, and nothing changes.
    assert client.post('/api/story/shop/buy', json={'item_id': 'lantern', 'qty': 2}).status_code == 409
    assert client.post('/api/story/shop/buy', json={'item_id': 'felling-axe'}).status_code == 404
    assert client.post('/api/story/shop/buy', json={'item_id': 'rope', 'qty': 4}).status_code == 409

    # Pell's buys what it deals in at half price; it doesn't buy swords.
    gear = ok(client.get('/api/story/gear'))
    boots = next(row for row in gear['items'] if row['item_id'] == 'boots')
    sword = next(row for row in gear['items'] if row['item_id'] == 'sword')
    assert gear['shop']['offers'][boots['id']] == 200 and sword['id'] not in gear['shop']['offers']
    sold = ok(client.post('/api/story/shop/sell', json={'inventory_id': boots['id']}))
    assert sold['coins'] == 190 + 200 and 'boots' not in {row['item_id'] for row in sold['items']}
    assert next(row for row in sold['shop']['stock'] if row['item_id'] == 'boots')['qty'] == 3
    assert client.post('/api/story/shop/sell', json={'inventory_id': sword['id']}).status_code == 409
    with app.state.database.connect() as connection:
        assert [row['kind'] for row in connection.execute('SELECT kind FROM story_trades ORDER BY rowid')] == \
            ['buy', 'sell']


def test_a_full_pack_refuses_more(client, connected, clock, app):
    begin_when(client, clock, premade='tobin-pell')
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE character_stats SET value=2 WHERE stat='Vitality'")
        inventory.set_purse(connection, 10000)
    assert ok(client.get('/api/story/gear'))['slots']['max'] == 6
    response = client.post('/api/story/shop/buy', json={'item_id': 'blanket', 'qty': 3})
    assert response.status_code == 200
    response = client.post('/api/story/shop/buy', json={'item_id': 'cloak', 'qty': 2})
    assert response.status_code == 409 and 'carry' in response.json()['detail']


def test_a_closed_shop_sells_nothing_and_elsewhere_there_is_no_shop(client, connected, clock):
    begin_when(client, clock, open_now=False)
    assert not ok(client.get('/api/story/gear'))['shop']['open']
    assert client.post('/api/story/shop/buy', json={'item_id': 'rope'}).status_code == 409
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'the-green'}))
    assert ok(client.get('/api/story/gear'))['shop'] is None
    assert client.post('/api/story/shop/buy', json={'item_id': 'rope'}).status_code == 404


def test_going_back_puts_the_purse_back(client, connected, clock, provider):
    begin_when(client, clock)
    provider.replies = [[Chunk('Fine.'), Chunk('', 'stop')]] * 2
    first = tell(client, 'I nod to the storekeeper.', 'story-0001')
    ok(client.post('/api/story/shop/buy', json={'item_id': 'bread'}))
    tell(client, 'I eat the bread.', 'story-0002')
    assert ok(client.get('/api/story/gear'))['coins'] == 330
    ok(client.post('/api/story/back', json={'message_id': first['message']['id']}))
    assert ok(client.get('/api/story/gear'))['coins'] == 340


def test_a_made_character_gets_the_default_kit(client, connected):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood'}))
    ok(client.delete('/api/story'))
    stats = {'Mind': 10, 'Allure': 10, 'Resolve': 10, 'Vitality': 10, 'Essence': 10, 'Luck': 10}
    ok(client.post('/api/story/start', json={'persona': {'name': 'Wat Fenn'}, 'stats': stats}))
    gear = ok(client.get('/api/story/gear'))
    assert gear['coins'] == 500 and {item['item_id'] for item in gear['items']} == {'knife', 'bread', 'waterskin', 'cloak'}


def test_a_line_names_what_it_buys():
    rows = [inventory.item('kingswood', item_id) | {'item_id': item_id} for item_id in ('bread', 'rope', 'candles', 'knife')]
    assert inventory.wanted('I buy two loaves of bread and a rope.', rows) == [('bread', 2), ('rope', 1)]
    assert inventory.wanted("I'll take 3 tallow candles.", rows) == [('candles', 3)]
    # Talking about an item isn't buying it.
    assert inventory.wanted('How much is the rope?', rows) == []


class Charming:
    """Dice that land a plain success on every roll: a d100 of 80, every other die its lowest."""

    def randint(self, low, high):
        return 80 if high == 100 else low

    def choice(self, items):
        return items[0]


def test_haggling_and_buying_in_the_story(client, connected, clock, provider, app):
    begin_when(client, clock)
    app.state.dice = Charming()
    provider.replies = [[Chunk('Pell sighs and names a better figure.'), Chunk('', 'stop')]] * 3
    tell(client, 'I haggle with the storekeeper over the price of rope.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert "## At the counter (decided by the game)\n- The haggle settles today's prices: 15% off today." in narrator
    assert "Today's prices after haggling: 15% off today." in narrator
    shop = ok(client.get('/api/story/gear'))['shop']
    assert shop['haggled'] == -15 and next(row for row in shop['stock'] if row['item_id'] == 'rope')['price'] == 64

    # Telling it again keeps the haggle, and a second haggle the same day gets nowhere.
    ok(client.post('/api/story/retry'))
    assert provider.requests[-1]['system'].count('## At the counter') == 1
    tell(client, 'I buy two ropes, and I haggle for a better price again.', 'story-0002')
    narrator = provider.requests[-1]['system']
    assert 'will not move on price again' in narrator
    assert "buys 2 × Rope, fifty feet for 1.28 cr.; it is in their pack" in narrator
    gear = ok(client.get('/api/story/gear'))
    assert gear['coins'] == 340 - 128 and any(row['item_id'] == 'rope' and row['qty'] == 2 for row in gear['items'])
    assert ok(client.post('/api/story/shop/buy', json={'item_id': 'bread'}))['coins'] == 340 - 128 - 9


def test_buying_more_than_the_purse_holds_in_the_story_is_refused(client, connected, clock, provider):
    begin_when(client, clock)
    provider.replies = [[Chunk('Pell shakes his head.'), Chunk('', 'stop')]]
    tell(client, 'I buy two hooded lanterns.', 'story-0001')
    assert "No sale of Hooded lantern: You can't afford that." in provider.requests[-1]['system']
    assert ok(client.get('/api/story/gear'))['coins'] == 340


def test_selling_in_the_story(client, connected, clock, provider):
    begin_when(client, clock)
    provider.replies = [[Chunk('Pell weighs the blanket.'), Chunk('', 'stop')]]
    tell(client, 'I sell my blanket and my sword to the storekeeper.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert "The player's character sells Wool blanket for" in narrator
    assert "No sale of Plain sword: This shop doesn't buy that." in narrator
    gear = ok(client.get('/api/story/gear'))
    assert not any(row['item_id'] == 'blanket' for row in gear['items'])
    assert any(row['item_id'] == 'sword' for row in gear['items']) and gear['coins'] > 340


def test_a_line_names_what_it_sells():
    pack = [{'id': 'a', 'item_id': 'knife', 'name': 'Belt knife', 'qty': 3, 'stolen': 0},
            {'id': 'b', 'item_id': 'knife', 'name': 'Belt knife', 'qty': 1, 'stolen': 1},
            {'id': 'c', 'item_id': 'rope', 'name': 'Rope, fifty feet', 'qty': 2, 'stolen': 0}]
    assert [(row['id'], qty) for row, qty in inventory.offered('I sell all my rope and the knife', pack)] == \
        [('b', 1), ('c', 2)]
    assert inventory.offered('I look at the rope', pack) and not inventory.SELL.search('I look at the rope')


def test_shops_restock_and_their_cash_runs_out(client, app):
    begin(client)
    shop = inventory.shop_at('kingswood', 'pell-provisions')
    with app.state.database.connect(write=True) as connection:
        assert inventory.stock(connection, 'kingswood', shop, '2026-10-01')['rope'] == 5
        assert inventory.cash(connection, 'kingswood', shop) == inventory.start_cash('kingswood', shop) == 2928
        connection.execute("UPDATE story_stock SET qty=0 WHERE item_id='rope'")
        inventory.pay(connection, 'kingswood', shop, -2900)
        # Six days on nothing has come in; on the seventh, the rope is back and the till topped up.
        assert inventory.stock(connection, 'kingswood', shop, '2026-10-07')['rope'] == 0
        assert inventory.stock(connection, 'kingswood', shop, '2026-10-08')['rope'] == 5
        assert inventory.cash(connection, 'kingswood', shop) == 2928
        # A shop without the money can't buy; with unlimited cash at the Table it can.
        inventory.pay(connection, 'kingswood', shop, -2928)
        knife = next(row for row in inventory.carried(connection, 'kingswood') if row['item_id'] == 'blanket')
        try:
            inventory.sell(connection, 'kingswood', shop, knife['id'], 1, '2026-10-08T12:00:00Z', '2026-10-08')
            raise AssertionError('sold to an empty till')
        except inventory.DomainError as refused:
            assert refused.message == "The keeper hasn't the money for that."
        connection.execute("UPDATE story_campaign SET shop_cash='unlimited' WHERE id=1")
        assert inventory.sell(connection, 'kingswood', shop, knife['id'], 1, '2026-10-08T12:00:00Z',
                              '2026-10-08')['amount'] > 0


def test_stolen_goods_go_only_to_a_fence(client, app):
    begin(client)
    pell, mag = (inventory.shop_at('kingswood', place) for place in ('pell-provisions', 'mother-mags'))
    with app.state.database.connect(write=True) as connection:
        inventory.add_item(connection, 'kingswood', 'candles', 2, stolen=True)
        rows = [row for row in inventory.carried(connection, 'kingswood') if row['item_id'] == 'candles']
        assert len(rows) == 1 and rows[0]['stolen'] == 1
        assert '(stolen)' in inventory.prompt_text(connection, 'kingswood', {'symbol': 'cr.'})
        stolen = rows[0]
        try:
            inventory.sell(connection, 'kingswood', pell, stolen['id'], 1, '2026-10-01T12:00:00Z', '2026-10-01')
            raise AssertionError('an honest shop bought stolen goods')
        except inventory.DomainError as refused:
            assert refused.message == "The keeper won't touch stolen goods."
        honest = inventory.offer(pell, stolen | {'stolen': 0})
        fenced = inventory.sell(connection, 'kingswood', mag, stolen['id'], 1, '2026-10-01T12:00:00Z', '2026-10-01')
        assert 0 < fenced['amount'] < honest


def test_life_cards_move_markets(client, app):
    begin(client)
    shop = inventory.shop_at('kingswood', 'pell-provisions')
    bread = inventory.item('kingswood', 'bread')
    with app.state.database.connect(write=True) as connection:
        inventory.move_market(connection, 'kingswood', 'food', 60, '2026-10-10')
        inventory.move_market(connection, 'kingswood', 'arms', -30, '2026-10-10')
        assert inventory.market(connection, 'kingswood', bread, '2026-10-10') == 60
        assert inventory.market(connection, 'kingswood', bread, '2026-10-11') == 0
        view = inventory.window(connection, 'kingswood', shop, True, 'the storekeeper', '2026-10-05')
        assert next(row for row in view['stock'] if row['item_id'] == 'bread')['price'] == 16
        assert view['market'] == 'Prices moved by what is going on: arms -30%, food +60%.' or \
            view['market'] == 'Prices moved by what is going on: food +60%, arms -30%.'


def test_a_market_card_moves_the_towns_prices(client, app):
    from dungeon import happenings
    begin(client)
    with app.state.database.connect(write=True) as connection:
        lines = happenings.marketed(connection, {'kind': 'market', 'goods': 'medicine', 'shift': 80, 'days': 21},
                                    {'city': 'kingswood', 'day': '2026-10-01'})
        assert lines == ['Prices of medicine here are 80% up for 21 days.']
        poultice = inventory.item('kingswood', 'poultice')
        assert inventory.market(connection, 'kingswood', poultice, '2026-10-21') == 80
        assert inventory.market(connection, 'kingswood', poultice, '2026-10-22') == 0


def test_services_are_paid_for_not_carried(client, app):
    begin(client)
    inn = inventory.shop_at('kingswood', 'the-wayhouse')
    with app.state.database.connect(write=True) as connection:
        before = inventory.used(inventory.carried(connection, 'kingswood'))
        done = inventory.buy(connection, 'kingswood', inn, 'private-room', 1, '2026-10-01T18:00:00Z', '2026-10-01')
        assert done['amount'] == 150 and inventory.used(inventory.carried(connection, 'kingswood')) == before
        assert inventory.bed(connection, 'kingswood', 'the-wayhouse', '2026-10-01')['tier'] == 'private'
        assert inventory.bed(connection, 'kingswood', 'the-wayhouse', '2026-10-02') is None
        assert 'Paid for today (kept by the game): Private room, a night at the Wayhouse.' in inventory.prompt_text(
            connection, 'kingswood', {'symbol': 'cr.'}, '2026-10-01')
        # Rooms are finite each night, and come back the next day.
        inventory.set_purse(connection, 1000)
        inventory.buy(connection, 'kingswood', inn, 'private-room', 2, '2026-10-01T18:00:00Z', '2026-10-01')
        assert inventory.stock(connection, 'kingswood', inn, '2026-10-01')['private-room'] == 0
        assert inventory.stock(connection, 'kingswood', inn, '2026-10-02')['private-room'] == 3


def test_lodging_and_meals_stay_within_ordinary_means():
    # A common-room night and a meal cost no more than an unskilled day's wage; a private room no more than a good one.
    for city_id in ('kingswood', 'the-concourse', 'the-gilded-bazaar'):
        city = catalog.city(city_id)
        low, high = next((price['low'], price['high']) for price in city['prices'] if price['id'] == 'day-wage')
        services = [entry for entry in inventory.catalog(city_id)['items'] if entry['category'] == 'service']
        common = [entry['price'] for entry in services if entry.get('tier') == 'common']
        meals = [entry['price'] for entry in services if entry['service'] == 'meal']
        if common and meals:
            assert min(common) + min(meals) <= low, city_id
        for entry in services:
            assert entry['slots'] == 0 and entry['service'] in ('lodging', 'meal', 'drink', 'bath', 'stabling', 'guide',
                                                                'laundry', 'mending', 'repair')
            if entry.get('tier') == 'private':
                assert entry['price'] <= high * 2, (city_id, entry['id'])
