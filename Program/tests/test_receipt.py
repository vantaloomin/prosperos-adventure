"""The turn receipt (dungeon/receipt.py): what each turn changed, read from the saves the timeline keeps."""
from conftest import tell

from dungeon import combat, inventory


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def receipt_of(client, message_id):
    line = next(message for message in ok(client.get('/api/story'))['messages'] if message['id'] == message_id)
    return [chip['text'] for chip in line.get('receipt', [])]


def test_a_turn_shows_what_it_changed_and_the_next_turn_closes_it(client, connected, app):
    first = tell(client, 'I look around the room.', 'receipt-0001')['message']
    # What the turn did, as the game's systems would: coins spent, bread bought, a wound, a quest heard of, and a fact.
    with app.state.database.connect(write=True) as connection:
        inventory.set_purse(connection, inventory.purse(connection) + 250)
        inventory.add_item(connection, 'kingswood', 'bread', 2)
        combat.set_condition(connection, 1)
        connection.execute("INSERT INTO story_quests (id, city_id, status, known) VALUES "
                           "('the-heartwood-contract', 'kingswood', 'open', 1)")
        connection.execute("INSERT INTO record_entries (id, kind, subject, text, truth, source, created_at) VALUES "
                           "('fact-1', 'fact', 'Gannet & Pryce', 'They buy heartwood.', 'both', 'narrator', 'now'), "
                           "('fact-2', 'secret', 'Gannet & Pryce', 'A Mammon front.', 'world', 'code', 'now'), "
                           "('fact-3', 'fact', 'the player''s character', 'Bought bread.', 'both', 'code', 'now')")
    chips = receipt_of(client, first['id'])
    assert chips == ['Hurt: grazed', '+2.50 $', 'Gained Loaf of black bread ×2', 'New quest: The Heartwood contract',
                     'Learned about Gannet & Pryce']
    # The hidden truth and the character's own lines are not news under the line.
    assert not any('Mammon' in chip or 'character' in chip for chip in chips)

    second = tell(client, 'I eat some bread.', 'receipt-0002')['message']
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE story_inventory SET qty=1 WHERE item_id='bread'")
    # The first turn's receipt is closed by the second line; the second shows only its own.
    assert 'Gained Loaf of black bread ×2' in receipt_of(client, first['id'])
    assert receipt_of(client, second['id']) == ['Lost Loaf of black bread']


def test_a_turn_that_changed_nothing_has_no_receipt(client, connected):
    line = tell(client, 'I wait.', 'receipt-0003')['message']
    assert receipt_of(client, line['id']) == []
