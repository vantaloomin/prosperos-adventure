"""Fixes from the shops-and-services playtest (2026-10-23): rooms by tier, selling what isn't carried, shut shops,
Mother Mag's hours, shoplifting, dressing again, attacks that always roll, no phantom bodies, waiting until evening."""
from datetime import datetime

from conftest import Chunk, tell
from test_inventory import begin, begin_when

from dungeon import appearance, finds, inventory, referee, story_clock

NOW = '2026-10-01T12:00:00Z'


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def test_a_room_named_by_its_comfort_is_bought():
    stock = [{'item_id': 'private-room', 'name': 'Private room, a night at the Wayhouse'}]
    assert inventory.wanted('I take a private room for the night.', stock) == [('private-room', 1)]


def test_selling_what_the_character_lacks_is_no_sale(client, app):
    begin(client)
    pell = inventory.shop_at('kingswood', 'pell-provisions')
    with app.state.database.connect(write=True) as connection:
        purse = inventory.purse(connection)
        lines = inventory.sell_in_story(connection, 'kingswood', pell, 'I sell my lute.', '2026-10-01', NOW,
                                        {'symbol': 'cr.'})
        assert lines[0].startswith("No sale: the player's character carries no such thing")
        assert inventory.purse(connection) == purse


def test_a_shut_shop_tells_the_narrator_nobody_is_behind_the_counter(client, clock, connected, provider):
    begin_when(client, clock, open_now=False)
    provider.replies = [reply('The door is barred.')]
    tell(client, 'I buy two loaves of bread.', 'story-0001')
    assert 'The shop is shut: nobody is behind the counter' in provider.requests[-1]['system']


def test_shoplifting_takes_from_the_stock_or_gets_caught(client, app):
    begin(client)
    pell = inventory.shop_at('kingswood', 'pell-provisions')
    with app.state.database.connect(write=True) as connection:
        stock = inventory.window(connection, 'kingswood', pell, True, '', '2026-10-01')['stock']
        candles = next(row['qty'] for row in stock if row['item_id'] == 'candles')
        caught = [{'action': 'pocket the candles', 'stat': 'Allure', 'band': 'failure'}]
        lines = inventory.lift(connection, 'kingswood', pell, 'I pocket a candle.', caught, stock)
        assert 'caught in the act' in lines[0]
        clean = [{'action': 'pocket the candles', 'stat': 'Allure', 'band': 'success'}]
        lines = inventory.lift(connection, 'kingswood', pell, 'I pocket a candle.', clean, stock)
        assert 'pockets' in lines[0] and 'stolen' in lines[0]
        after = inventory.stock(connection, 'kingswood', pell, '2026-10-01')['candles']
        assert after == candles - 1
        assert any(row['item_id'] == 'candles' and row['stolen'] for row in inventory.carried(connection, 'kingswood'))
        # No roll, no theft.
        assert inventory.lift(connection, 'kingswood', pell, 'I pocket a candle.', [], stock) == []


def test_putting_named_clothes_back_on_dresses_only_them():
    look = {'grime': 0, 'marks': [], 'clothes': 'intact',
            'dress': {'outer': 'off (the river)', 'under': 'off (the river)', 'accessories': 'off (the river)'}}
    dressed = appearance.dressing(look, 'I put my shirt and coat back on.', 'the river')['dress']
    assert dressed == {'outer': 'worn', 'under': 'worn', 'accessories': 'off (the river)'}
    assert appearance.dressing(look, 'I put the kettle on.', 'here')['dress'] == look['dress']


def test_an_attack_always_rolls_whatever_the_referee_says():
    added = referee.armed('I draw my sword and cut down the foreman.', [])
    assert added[0]['stat'] == 'Vitality' and added[0]['roll']
    assert referee.armed('I cut the bread for him.', []) == []
    kept = [{'action': 'swing', 'roll': True, 'stat': 'Vitality', 'difficulty': 'normal'}]
    assert referee.armed('I stab him.', kept) == kept


def test_no_body_where_nobody_fell(client, app):
    begin(client)
    city, place = {'id': 'kingswood', 'currency': {}}, {'id': 'the-sawpit', 'name': 'the Sawpit', 'kind': 'workshop'}
    with app.state.database.connect(write=True) as connection:
        lines = finds.look(connection, city, place, 'I search the body.', [], None, NOW)
        assert lines == ['There is no body at the Sawpit: nobody has fallen here. Describe no corpse.']


def test_waiting_until_a_time_of_day_waits_that_long():
    at = datetime(2026, 10, 5, 16, 30)
    assert story_clock.minutes_for('I wait outside until she opens for the evening.', False, at) == 30
    assert story_clock.minutes_for('I wait till dawn.', False, datetime(2026, 10, 5, 22, 0)) == 8 * 60
    assert story_clock.minutes_for('I wait for him.', False, at) == story_clock.TALK_MINUTES


def test_an_empty_tavern_gets_no_invented_patrons():
    from dungeon import story
    view = {'data': {'name': 'Kingswood', 'summary': 'A logging town.', 'era': 'Post-Reform'},
            'place': {'id': 'sawpit', 'name': 'the Sawpit', 'kind': 'tavern', 'neighborhood': 'the yards',
                      'summary': 'A tavern.'},
            'local_time': '2026-10-01T16:11:00', 'weather': '', 'people': [], 'known': {}}
    assert story.EMPTY_ROOM in story.scene_text(view)
    assert 'only passers-by' in story.scene_text(view | {'place': view['place'] | {'kind': 'square'}})


def test_a_blow_the_referee_called_luck_or_skipped_still_rolls_vitality():
    assert referee.armed("I pick out the loudest logger in the place, call him a coward, and cut at him with my "
                         'sword.', [])[0]['stat'] == 'Vitality'
    luck = [{'action': 'I creep up behind the loudest drunk and hit him over the head with my sword hilt', 'roll': True,
             'stat': 'Luck', 'difficulty': 'normal'}]
    assert referee.armed(luck[0]['action'], luck) == [luck[0] | {'stat': 'Vitality'}]


def test_giving_in_to_foes_rolls_nothing():
    handing = [{'action': 'I hand over my purse', 'roll': True, 'stat': 'Vitality', 'difficulty': 'normal'}]
    assert referee.armed('I hand over my purse.', handing, 'the bandit (unhurt)') == []
    assert referee.armed('I hand over my purse.', handing) == handing


def test_selling_everything_i_can_spare():
    pack = [{'item_id': 'knife', 'name': 'Belt knife', 'category': 'weapon', 'qty': 2, 'stolen': 0},
            {'item_id': 'candle', 'name': 'Tallow candles', 'category': 'gear', 'qty': 1, 'stolen': 1},
            {'item_id': 'bread', 'name': 'Bread', 'category': 'food', 'qty': 3, 'stolen': 0},
            {'item_id': 'cloak', 'name': 'Wool cloak', 'category': 'clothing', 'qty': 1, 'stolen': 0}]
    spare = inventory.offered('I sell Mother Mag everything I can spare.', pack)
    assert [(row['item_id'], qty) for row, qty in spare] == [('candle', 1), ('knife', 1)]
    everything = inventory.offered('I sell her everything.', pack)
    assert [(row['item_id'], qty) for row, qty in everything] == [('candle', 1), ('knife', 2), ('bread', 3)]
    assert [(row['item_id'], qty) for row, qty in inventory.offered('I sell the knife.', pack)] == [('knife', 1)]


class Keeper:
    """The keeper's d100 shows `natural`; every other die rolls lowest."""

    def __init__(self, natural):
        self.natural = natural

    def randint(self, low, high):
        return self.natural if (low, high) == (1, 100) else low


def test_a_haggle_is_allure_against_the_keepers_resolve():
    shop = {'place': 'pells', 'resolve': 10}
    # A keeper who does better than the character costs them a step.
    assert inventory.opposed(shop, 'success', Keeper(99)) == ('success_cost', 'critical_success')
    # One who does worse leaves the character's result as it was.
    assert inventory.opposed(shop, 'success', Keeper(2)) == ('success', 'critical_failure')
    assert inventory.opposed(shop, 'critical_failure', Keeper(99))[0] == 'critical_failure'
