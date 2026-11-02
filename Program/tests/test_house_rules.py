"""The house rulebook (adventure/rounds/house_rules.py): defaults, the world's additions and the campaign's edits as
data, and rulings that apply from the turn they were made forward on that branch."""
from conftest import Chunk, ok, tell

from adventure.rounds import house_rules
from adventure.rounds.house_rules import Rulebook


def rules(client):
    return ok(client.get('/api/story/house-rules'))


def test_the_defaults_are_the_writing_rules_and_worldsmiths_made_up_names():
    book = Rulebook()
    assert book.punctuation == ('em dash',) and 'Elara' in book.names and 'Voss' in book.names
    assert any('reported speech' in rule for rule in book.dialogue)
    assert house_rules.layered(None, None) == book


def test_a_world_adds_to_each_list_and_an_edit_keeps_only_what_changed():
    world = {'words': ['suddenly'], 'names': ['Grimbold'], 'thoughts': 'italics'}
    edits = {'names': {'add': ['Hesk'], 'remove': ['elara']}, 'words': {'add': [], 'remove': ['Suddenly']}}
    book = house_rules.layered(world, edits)
    assert 'Grimbold' in book.names and 'Hesk' in book.names and 'Elara' not in book.names
    assert book.words == () and book.thoughts == 'italics'
    # A name the shipped list gains later still reaches the campaign: its edit was only what it changed.
    assert 'Voss' in book.names


def test_the_table_edits_the_book_and_the_format_and_scope_come_from_the_table(client, app):
    found = rules(client)
    assert (found['pov'], found['tense']) == ('second', 'present') and 'Elara' in found['names']
    names = [name for name in found['names'] if name != 'Elara'] + ['Bob Ross']
    changed = ok(client.put('/api/story/house-rules', json={'names': names, 'words': ['suddenly', 'Suddenly'],
                                                            'punctuation': ['em dash', '!'], 'thoughts': 'plain',
                                                            'pane_title': '== {title} =='}))
    assert 'Elara' not in changed['names'] and changed['names'][-1] == 'Bob Ross'
    assert changed['words'] == ['suddenly'] and changed['thoughts'] == 'plain'
    with app.state.database.connect() as connection:
        assert house_rules.stored(connection)['names'] == {'add': ['Bob Ross'], 'remove': ['Elara']}
    ok(client.put('/api/story/table', json={'pov': 'third', 'tense': 'past'}))
    assert (rules(client)['pov'], rules(client)['tense']) == ('third', 'past')
    # Setting a choice back to the world's own is no longer an edit.
    ok(client.put('/api/story/house-rules', json={'thoughts': 'quoted-italics'}))
    with app.state.database.connect() as connection:
        assert 'thoughts' not in house_rules.stored(connection)


def test_a_bad_edit_is_refused(client):
    for body in ({'thoughts': 'shouted'}, {'pane_title': 'Status'}, {'pane_row': '{label}'},
                 {'punctuation': ['em dash', 'x']}):
        assert client.put('/api/story/house-rules', json=body).status_code == 400, body


def test_a_ruling_applies_from_its_turn_forward_on_that_branch(client, connected, provider):
    provider.replies = [[Chunk(f'Reply {number}.'), Chunk('', 'stop')] for number in range(1, 6)]
    tell(client, 'I look around.', 'story-0001')
    second = tell(client, 'I walk to the bar.', 'story-0002')['message']
    made = ok(client.post('/api/story/rulings', json={'text': "  Hesk's limp   is permanent. "}))['rulings']
    assert [item['text'] for item in made] == ["Hesk's limp is permanent."]
    tell(client, 'I order a drink.', 'story-0003')
    assert len(rules(client)['rulings']) == 1
    # Going back before the line it was made after un-makes it on the new branch.
    ok(client.post('/api/story/back', json={'message_id': second['id']}))
    assert rules(client)['rulings'] == []


def test_a_withdrawal_applies_from_its_turn_forward_too(client, connected, provider):
    provider.replies = [[Chunk(f'Reply {number}.'), Chunk('', 'stop')] for number in range(1, 6)]
    tell(client, 'I look around.', 'story-0001')
    ruling = ok(client.post('/api/story/rulings', json={'text': 'No one in town knows the Tower has floors above '
                                                                'twelve.'}))['rulings'][0]
    second = tell(client, 'I walk to the bar.', 'story-0002')['message']
    assert ok(client.delete(f"/api/story/rulings/{ruling['id']}"))['rulings'] == []
    assert client.delete(f"/api/story/rulings/{ruling['id']}").status_code == 404
    tell(client, 'I order a drink.', 'story-0003')
    ok(client.post('/api/story/back', json={'message_id': second['id']}))
    assert [item['id'] for item in rules(client)['rulings']] == [ruling['id']]


def test_a_new_story_starts_from_the_worlds_book(client, app):
    ok(client.put('/api/story/house-rules', json={'words': ['suddenly']}))
    ok(client.post('/api/story/rulings', json={'text': 'Magic is rare.'}))
    ok(client.delete('/api/story'))
    found = rules(client)
    assert found['words'] == [] and found['rulings'] == []


def test_the_book_as_the_writer_reads_it():
    book = Rulebook(words=('suddenly',), punctuation=('em dash', ';'), rulings=('Magic is rare.',),
                    pane_title='== {title} ==', pane_row='{label} = {value}')
    text = house_rules.text(book)
    assert 'close third person, past tense' in text and 'em dashes' in text and '";"' in text
    assert 'suddenly' in text and 'Elara' in text and '- Magic is rare.' in text.split('## Rulings')[1]
    assert '"== Status =="' in text and 'Intensity:' in text
    assert 'Intensity:' not in house_rules.text(book, scope=False)
    assert house_rules.pane(book, 'Status', [('Health', '8 of 20')]) == '```\n== Status ==\nHealth = 8 of 20\n```'
    # A format is filled in, never evaluated.
    assert house_rules.filled('{title.__class__} {title}', title='Status') == '{title.__class__} Status'


def test_a_worlds_rules_and_the_tables_scope_reach_the_book(app):
    with app.state.database.connect() as connection:
        book = house_rules.of(connection, {'house_rules': {'phrases': ['a beat passed'], 'thoughts': 'plain'},
                                           'intensity': {'preset': 'restrained'}})
    assert book.phrases == ('a beat passed',) and book.thoughts == 'plain' and set(book.levels.values()) == {1}
