"""Decide before describing (dungeon/finds.py): what is inside things is rolled once, stored, then described."""
from conftest import Chunk, tell

from dungeon import finds


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


class Low(Dice):
    """Every table roll comes up lowest."""

    def randint(self, low, high):
        return self.natural if (low, high) == (1, 100) else low


def begin(client, app, natural=50):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    app.state.dice = Dice(natural)


def test_a_line_names_what_it_looks_into():
    assert finds.container('kingswood', 'I search the chest by the hearth.') == ('chest', 'chest')
    assert finds.container('kingswood', "I pick his pockets while he's drunk.") == ('purse', 'pockets')
    assert finds.container('kingswood', 'I open the door.') is None
    assert finds.container('kingswood', 'What a chest on that man.') is None


def test_every_find_table_names_real_items():
    for path in finds.FINDS.glob('*.json'):
        for kind, spec in finds.tables(path.stem).items():
            assert spec['draws'] >= 1 and spec['words'], kind
            for entry in spec['table']:
                assert entry['weight'] > 0 and ('item' not in entry or finds.inventory.item(path.stem, entry['item']))


def test_what_is_inside_is_rolled_once_described_and_can_be_taken(client, connected, provider, app):
    begin(client, app)
    provider.replies = [reply('The lid creaks.'), reply('Still there.'), reply('Clink.'), reply('Empty now.')]
    tell(client, 'I open the chest under the stairs.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert '## What is there (decided by the game; describe only this)' in narrator
    assert '- Inside the chest at the Felled Oak: 2 × Bottle of plum spirit. Describe only this' in narrator
    journal = ok(client.get('/api/story/journal'))['entries']
    assert journal[0]['subject'] == 'the chest at the Felled Oak' and 'plum spirit' in journal[0]['text']

    # Other dice don't change what was already there.
    app.state.dice = Low()
    tell(client, 'I look inside the chest again.', 'story-0002')
    assert '2 × Bottle of plum spirit' in provider.requests[-1]['system']

    tell(client, 'I take the plum spirit.', 'story-0003')
    assert "takes 2 × Bottle of plum spirit from the chest" in provider.requests[-1]['system']
    items = {row['item_id']: row for row in ok(client.get('/api/story/gear'))['items']}
    # Taken from a chest at the tavern, someone else's: stolen, so only a fence will buy it.
    assert items['plum-spirit']['qty'] == 2 and items['plum-spirit']['stolen']
    tell(client, 'I open the chest.', 'story-0004')
    assert 'Inside the chest at the Felled Oak: nothing of use.' in provider.requests[-1]['system']


def test_a_failed_search_misses_what_is_there_until_a_better_look(client, connected, provider, app):
    begin(client, app, natural=1)
    provider.replies = [reply('Nothing.'), reply('Wait, there.')]
    tell(client, 'I search the chest.', 'story-0001')
    assert 'misses it this time: they find nothing' in provider.requests[-1]['system']
    assert ok(client.get('/api/story/journal'))['entries'] == []
    app.state.dice = Dice(95)
    tell(client, 'I search the chest more carefully.', 'story-0002')
    assert '- Inside the chest at the Felled Oak: 2 × Bottle of plum spirit.' in provider.requests[-1]['system']


def test_taking_a_seat_takes_nothing_and_going_back_puts_it_back(client, connected, provider, app):
    begin(client, app)
    provider.replies = [reply('Creak.'), reply('You sit.'), reply('Clink.')]
    first = tell(client, 'I open the chest.', 'story-0001')
    tell(client, 'I take a seat by the fire.', 'story-0002')
    assert '## What is there' not in provider.requests[-1]['system']
    tell(client, 'I take everything in the chest.', 'story-0003')
    assert any(row['item_id'] == 'plum-spirit' for row in ok(client.get('/api/story/gear'))['items'])
    ok(client.post('/api/story/back', json={'message_id': first['message']['id']}))
    assert not any(row['item_id'] == 'plum-spirit' for row in ok(client.get('/api/story/gear'))['items'])


def test_what_is_stolen_depends_on_whose_it_was():
    tavern, wilds = {'kind': 'tavern'}, {'kind': 'trail'}
    assert finds.stolen_from('kingswood', tavern, 'chest') and finds.stolen_from('kingswood', wilds, 'purse')
    assert not finds.stolen_from('kingswood', wilds, 'chest') and not finds.stolen_from('kingswood', tavern, 'body')
