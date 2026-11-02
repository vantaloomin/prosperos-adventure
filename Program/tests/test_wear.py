"""Gear wears and the fallen carry things (dungeon/inventory.py wear and repair, dungeon/combat.py, dungeon/finds.py
spoils)."""
from conftest import Chunk, tell

from dungeon import combat, finds, inventory

NOW, DAY = '2026-10-01T12:00:00Z', '2026-10-01'


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


class Dice:
    """A d100 that shows `natural`; every other die and every table roll comes up highest."""

    def __init__(self, natural=50):
        self.natural = natural

    def randint(self, low, high):
        return self.natural if (low, high) == (1, 100) else high

    def choice(self, items):
        return items[0]


def begin(client, place='felled-oak'):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': place}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))


def sword(connection):
    return next(row for row in inventory.carried(connection, 'kingswood') if row['item_id'] == 'sword')


def test_wear_splits_one_off_its_stack_and_a_smith_mends_it(client, app):
    begin(client)
    smithy = inventory.shop_at('kingswood', 'blackwood-smithy')
    with app.state.database.connect(write=True) as connection:
        inventory.add_item(connection, 'kingswood', 'knife', 2)
        knives = next(row for row in inventory.carried(connection, 'kingswood') if row['item_id'] == 'knife')
        assert inventory.wear(connection, knives['id']) == 'damaged'
        rows = {row['condition']: row['qty'] for row in inventory.carried(connection, 'kingswood')
                if row['item_id'] == 'knife'}
        assert rows == {'sound': 2, 'damaged': 1}
        assert 'Belt knife (damaged)' in inventory.prompt_text(connection, 'kingswood', {'symbol': 'cr.'})
        # Worn goods sell for less.
        damaged = next(row for row in inventory.carried(connection, 'kingswood') if row['condition'] == 'damaged')
        assert inventory.offer(smithy, damaged) == inventory.offer(smithy, damaged | {'condition': 'sound'}) // 2
        assert inventory.wear(connection, damaged['id']) == 'broken'
        broken = next(row for row in inventory.carried(connection, 'kingswood') if row['condition'] == 'broken')
        assert inventory.wear(connection, broken['id']) is None
        # The smith mends the worst thing carried one step a repair.
        done = inventory.buy(connection, 'kingswood', smithy, 'repair', 1, NOW, DAY)
        assert done['mended'] == ['Belt knife (damaged now)']
        inventory.buy(connection, 'kingswood', smithy, 'repair', 1, NOW, DAY)
        assert all(row['condition'] == 'sound' for row in inventory.carried(connection, 'kingswood'))
        try:
            inventory.buy(connection, 'kingswood', smithy, 'repair', 1, NOW, DAY)
            raise AssertionError('paid to repair nothing')
        except inventory.DomainError as refused:
            assert refused.message == 'Nothing you carry needs repair.'


def test_a_repair_asked_for_in_the_story_buys_no_sword():
    stock = [{'item_id': 'sword', 'name': 'Plain sword'}, {'item_id': 'repair', 'name': inventory.item(
        'kingswood', 'repair')['name']}]
    assert inventory.wanted('I have the smith mend my sword.', stock) == [('repair', 1)]
    assert inventory.wanted('I buy the sword.', stock) == [('sword', 1)]


def test_a_worn_weapon_hits_softer_and_a_botched_blow_wears_it(app, client):
    begin(client)
    assert combat.weapon_bonus([{'item_id': 'sword', 'condition': 'damaged'}]) == 0
    assert combat.weapon_bonus([{'item_id': 'sword', 'condition': 'broken'}]) == combat.BARE_HANDS
    assert combat.weapon_bonus([{'item_id': 'sword', 'condition': 'damaged'}, {'item_id': 'knife'}]) == 0
    with app.state.database.connect(write=True) as connection:
        items = inventory.carried(connection, 'kingswood')
        botched = [{'action': 'I swing at the bandit', 'band': 'critical_failure', 'stat': 'Vitality'}]
        assert combat.worn(connection, botched, {'bare': True}, items) == []
        assert combat.worn(connection, [botched[0] | {'band': 'failure'}], {}, items) == []
        assert combat.worn(connection, botched, {}, items) == [
            "The player's character's plain sword is damaged by the botched blow."]
        assert sword(connection)['condition'] == 'damaged'


def test_the_fallen_carry_what_they_had_and_a_beast_nothing(client, app):
    begin(client, 'the-green')
    city, place = {'id': 'kingswood'}, {'id': 'the-green', 'name': 'the Green', 'kind': 'square'}
    with app.state.database.connect(write=True) as connection:
        bandit = combat.foes_from({'name': 'bandit', 'weapon': 1})[0]
        wolf = combat.foes_from({'name': 'starving wolf', 'beast': True})[0]
        lines = finds.spoils(connection, city, place, [bandit, wolf], 'rob', Dice(), NOW)
        assert lines and 'bandit' in lines[0]
        body = finds.stored(connection, 'kingswood:the-green:body')
        assert body['seen'] == 0 and body['contents'] == [{'coins': 300}, {'item_id': 'sword', 'qty': 1}]
        assert finds.spoils(connection, city, place, [], 'rob', Dice(), NOW) == []
    # A town with no finds table still knows a body.
    assert finds.container('the-concourse', 'I search the body.') == ('body', 'body')


def test_a_fight_won_leaves_a_body_to_search_and_rob(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, {'round': 1, 'wants': 'rob', 'foes': combat.foes_from(
            {'name': 'bandit', 'vitality': 10, 'resolve': 10, 'weapon': 0}, 'engaged')})
        purse = inventory.purse(connection)
    app.state.dice = Dice(95)
    provider.replies = [reply('He drops.'), reply('You kneel.'), reply('Coins.')]
    tell(client, 'I run the bandit through with my sword.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert 'the fight is won' in narrator and 'The fallen lie where they fell (bandit)' in narrator
    tell(client, 'I search the body.', 'story-0002')
    assert 'Inside the body at the Felled Oak: 3.00 cr.; Belt knife.' in provider.requests[-1]['system']
    tell(client, 'I take the coins and the knife.', 'story-0003')
    items = [row for row in ok(client.get('/api/story/gear'))['items'] if row['item_id'] == 'knife']
    # What a body gives is not stolen.
    assert ok(client.get('/api/story/gear'))['coins'] == purse + 300 and not any(row['stolen'] for row in items)
