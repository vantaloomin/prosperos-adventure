"""The record and the story so far (dungeon/record.py)."""
from conftest import Chunk, tell

from dungeon import record
from dungeon.errors import DomainError


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def route_continuity(client):
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': 'continuity', 'profile_id': profiles[0]['id']}))


def test_facts_the_narrator_brings_in_are_kept_unless_they_contradict_the_record(client, connected, app, provider):
    # Without a Continuity model nothing is asked after the turn.
    provider.replies = [reply('The barman nods.')]
    tell(client, 'I order a drink.', 'story-0001')
    assert len(provider.requests) == 1 and ok(client.get('/api/story/journal'))['entries'] == []

    route_continuity(client)
    with app.state.database.connect(write=True) as connection:
        record.add(connection, 'death', 'Old Tom', 'Old Tom drowned off the pier.', app.state.database.now())
    # The narration names the dead, so the contradiction check runs and its rewrite is used.
    provider.replies = [
        reply('Old Tom waves from the door. The bouncer swings and breaks your nose.'),
        reply("Old Tom's stool by the door sits empty. The bouncer swings and breaks your nose."),
        reply('{"facts": [{"kind": "wound", "subject": "you", "text": "Your nose is broken.", "truth": "both"},'
              ' {"kind": "fact", "subject": "Old Tom", "text": "Old Tom is at the bar.", "truth": "both"},'
              ' {"kind": "secret", "subject": "the bouncer", "text": "The bouncer works for the co-op.",'
              ' "truth": "world"}, {"kind": "mood", "subject": "you", "text": "You feel sad."}]}')]
    tell(client, 'I shove past the bouncer.', 'story-0002')
    assert 'The record says these people are dead: old tom.' in provider.requests[-2]['system']
    assert provider.requests[-1]['system'].startswith(record.EXTRACT)
    assert "The narrator: Old Tom's stool" in provider.requests[-1]['messages'][0]['content']
    known = ok(client.get('/api/story/journal'))['entries']
    # The dead stay dead, hidden truth stays out of the journal, and a made-up kind is dropped.
    assert [(entry['kind'], entry['subject']) for entry in known] == [('wound', 'you'), ('death', 'Old Tom')]

    # The narrator is given the record, hidden truth marked as hidden.
    provider.replies = [reply('You wipe the blood away.'), reply('{"facts": []}')]
    tell(client, 'I wipe my nose.', 'story-0003')
    narrator = provider.requests[-2]['system']
    assert '## The record (kept by the game; never contradict it)' in narrator
    assert '- death, Old Tom: Old Tom drowned off the pier.' in narrator.split('\n')[narrator.split('\n').index(
        '## The record (kept by the game; never contradict it)') + 1]
    assert "- secret, the bouncer: The bouncer works for the co-op. (hidden: the player's character does not know)" \
        in narrator

    # Telling it again takes the old reply's facts with it.
    provider.replies = [reply('You dab at your nose.'), reply('{"facts": []}')]
    ok(client.post('/api/story/retry'))
    assert len(ok(client.get('/api/story/journal'))['entries']) == 2


def test_the_player_corrects_their_journal_and_it_is_logged(client, app):
    added = ok(client.post('/api/story/journal', json={'subject': 'Nell', 'text': 'Nell owes the co-op money.'}))
    [entry] = added['entries']
    assert entry['source'] == 'player'
    changed = ok(client.patch(f"/api/story/journal/{entry['id']}", json={'text': 'Nell owes Gus money.'}))
    assert changed['entries'][0]['text'] == 'Nell owes Gus money.'
    assert ok(client.delete(f"/api/story/journal/{entry['id']}"))['entries'] == []
    assert client.delete(f"/api/story/journal/{entry['id']}").status_code == 404
    with app.state.database.connect() as connection:
        log = [(row['before'], row['after']) for row in connection.execute(
            'SELECT before, after FROM record_corrections ORDER BY created_at, rowid')]
        hidden = record.add(connection, 'secret', 'Gus', 'Gus is a fence.', app.state.database.now(),
                               truth='world')
    assert log == [('Nell owes the co-op money.', 'Nell owes Gus money.'), ('Nell owes Gus money.', None)]
    assert client.delete(f"/api/story/journal/{hidden['id']}").status_code == 404


def test_older_turns_fold_into_the_story_so_far(client, connected, app, provider, monkeypatch):
    monkeypatch.setattr(record, 'RECENT', 4)
    monkeypatch.setattr(record, 'FOLD', 2)
    provider.replies = [reply(f'Narration {number}.') for number in range(1, 4)]
    provider.replies.append(reply('You arrived and asked about Turn 1.'))
    for number in range(1, 4):
        tell(client, f'Turn {number}.', f'story-000{number}')
    # Six messages: four recent plus two to fold, so the third reply folds the first two.
    assert provider.requests[-1]['system'].startswith(record.SUMMARIZE)
    assert 'The player: Turn 1.\n\nThe narrator: Narration 1.' in provider.requests[-1]['messages'][0]['content']
    assert 'Turn 2.' not in provider.requests[-1]['messages'][0]['content']

    provider.replies = [reply('Narration 4.'), reply('You arrived, asked about Turns 1 and 2.')]
    tell(client, 'Turn 4.', 'story-0004')
    # The next two waiting messages fold in after this turn, on top of the summary so far.
    assert 'The summary so far:\nYou arrived and asked about Turn 1.' in provider.requests[-1]['messages'][0]['content']
    narrator = provider.requests[-2]
    assert '## The story so far (older turns, summarized)\nYou arrived and asked about Turn 1.' in narrator['system']
    assert 'Turn 1.' not in str(narrator['messages']) and 'Turn 2.' in str(narrator['messages'])


def test_an_older_workspace_keeps_its_facts_under_the_new_name(tmp_path):
    """The ledger was renamed the record (2026-10-22): the tables carry their rows over, and saves made before the
    rename still put their facts back."""
    import json
    import sqlite3

    from dungeon import timeline
    from dungeon.database import rename_tables
    connection = sqlite3.connect(tmp_path / 'old.sqlite3')
    connection.execute('CREATE TABLE ledger_entries (id TEXT PRIMARY KEY, subject TEXT)')
    connection.execute("INSERT INTO ledger_entries VALUES ('a', 'Old Tom')")
    connection.execute('CREATE TABLE ledger_corrections (id TEXT PRIMARY KEY)')
    rename_tables(connection)
    rename_tables(connection)
    assert connection.execute('SELECT subject FROM record_entries').fetchall() == [('Old Tom',)]
    assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'ledger%'").fetchall()
    connection.execute('DELETE FROM record_entries')
    timeline.restore(connection, json.dumps({'ledger_entries': [{'id': 'b', 'subject': 'Gus'}]}), ('record_entries',))
    assert connection.execute('SELECT subject FROM record_entries').fetchall() == [('Gus',)]


def test_extraction_is_schema_first_and_says_what_each_system_asks(client, connected, app, provider):
    route_continuity(client)
    provider.replies = [reply('Pell hands you the key.'),
                        reply('{"facts": [{"kind": "item", "subject": "the key", "text": "Pell gave you a key.", '
                              '"truth": "both"}], "oaths": [], "dark": []}')]
    tell(client, 'I take the key.', 'story-0001')
    shape = provider.requests[-1]['config']['json_schema']
    assert shape['required'][:1] == ['facts'] and {'oaths', 'dark'} <= set(shape['properties'])
    assert shape['properties']['facts']['items'] == record.FACT and shape['additionalProperties'] is False
    assert 'json_schema' not in provider.requests[-2]['config']
    assert [entry['text'] for entry in ok(client.get('/api/story/journal'))['entries']] == ['Pell gave you a key.']


def test_a_backend_that_refuses_the_schema_is_asked_without_it_and_a_weak_model_field_by_field(client, connected,
                                                                                                app, provider):
    route_continuity(client)

    def respond(system, messages):
        if system.startswith(record.EXTRACT) and provider.requests[-1]['config'].get('json_schema'):
            raise DomainError('This model does not take response_format.', 400, 'provider')
        if system.startswith(record.EXTRACT):
            return reply('{"facts": [{"kind": "promise", "subject": "Pell", "text": "You owe Pell.", '
                         '"truth": "both"}]}')
        return reply('Pell lends you a coin.')
    provider.respond = respond
    tell(client, 'I borrow a coin.', 'story-0001')
    provider.respond = None
    # Sent again without the schema after the refusal.
    assert 'json_schema' in provider.requests[-2]['config'] and 'json_schema' not in provider.requests[-1]['config']
    assert ok(client.get('/api/story/journal'))['entries'][0]['text'] == 'You owe Pell.'

    # A weak model answers prose: then the facts as lines, and each field for all of them.
    provider.replies = [reply('Pell bleeds from the lip. A stranger watches.'),
                        reply('I think the lip bled, honestly.'), reply('I think the lip bled, honestly.'),
                        reply('1. Pell has a split lip.\n2. A stranger in grey watches the shop.'),
                        reply('1. wound\n2. fact'), reply('1. Pell\n2. the stranger in grey'), reply('1. both\n2. world')]
    tell(client, 'I punch Pell.', 'story-0002')
    assert provider.requests[-4]['system'] == record.LINES
    assert '1. Pell has a split lip.' in provider.requests[-1]['messages'][0]['content']
    with app.state.database.connect() as connection:
        pulled = [(row['kind'], row['subject'], row['truth']) for row in record.entries(connection, known_only=False)
                  if row['source'] == 'narrator']
    assert pulled[:2] == [('fact', 'the stranger in grey', 'world'), ('wound', 'Pell', 'both')]


def test_the_gm_view_shows_everything_and_asks_again_for_or_clears_one_fact(client, connected, app, provider):
    route_continuity(client)
    provider.replies = [reply('The bouncer is on the co-op payroll.'),
                        reply('{"facts": [{"kind": "secret", "subject": "the bouncer", "text": "He works for the '
                              'co-op.", "truth": "world"}]}')]
    tell(client, 'I watch the bouncer.', 'story-0001')
    assert ok(client.get('/api/story/journal')) | {'quests': [], 'institutions': [], 'threads': []} == {
        'entries': [], 'gm': False, 'quests': [], 'institutions': [], 'threads': [], 'summary': ''}
    with app.state.database.connect() as connection:
        [hidden] = record.entries(connection, known_only=False)
    assert client.post(f"/api/story/journal/{hidden['id']}/regenerate").status_code == 409

    ok(client.put('/api/settings', json={'gm_view': True}))
    view = ok(client.get('/api/story/journal'))
    assert view['gm'] is True and view['entries'][0]['truth'] == 'world' and view['entries'][0]['pulled'] is True
    provider.replies = [reply('{"kind": "secret", "subject": "the bouncer", "text": "He takes the co-op\'s pay.", '
                              '"truth": "world"}')]
    view = ok(client.post(f"/api/story/journal/{hidden['id']}/regenerate"))
    assert view['entries'][0]['text'] == "He takes the co-op's pay."
    assert provider.requests[-1]['system'] == record.REGENERATE
    assert provider.requests[-1]['config']['json_schema'] == record.FACT
    assert 'The fact as it was pulled: secret, the bouncer: He works for the co-op.' in \
        provider.requests[-1]['messages'][0]['content']
    assert ok(client.delete(f"/api/story/journal/{hidden['id']}"))['entries'] == []
    with app.state.database.connect() as connection:
        log = [row['after'] for row in connection.execute('SELECT after FROM record_corrections ORDER BY rowid')]
    assert log == ["He takes the co-op's pay.", None]


def test_repeats_and_items_the_pack_never_got_are_not_recorded(client, connected, app, provider):
    route_continuity(client)
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    with app.state.database.connect(write=True) as connection:
        record.add(connection, 'fact', 'the crew boss', 'The crew boss runs the felling gang.', 'x')
    provider.replies = [reply('You take everything you find.'),
                        reply('{"facts": [{"kind": "item", "subject": "you", "text": "You took a sack of teeth.", '
                              '"truth": "both"}, {"kind": "fact", "subject": "The crew boss", "text": "The crew boss '
                              'runs the felling gang here.", "truth": "both"}, {"kind": "item", "subject": "Pell", '
                              '"text": "Pell keeps a brass bell.", "truth": "both"}]}')]
    tell(client, 'I take everything I found.', 'story-0001')
    assert 'Already in the record:\n- fact, the crew boss: The crew boss runs the felling gang.' in \
        provider.requests[-1]['messages'][0]['content']
    assert 'A demand, threat or ultimatum someone else made of the character is not their oath.' in \
        provider.requests[-1]['system']
    texts = {entry['text'] for entry in ok(client.get('/api/story/journal'))['entries']}
    assert texts == {'Pell keeps a brass bell.', 'The crew boss runs the felling gang.'}
