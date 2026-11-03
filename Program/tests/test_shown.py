"""Character sheets refreshed from the page at a chapter's close (adventure/rounds/shown.py)."""
from conftest import Chunk, tell
from test_inventory import begin
from test_travel import ok

from adventure import chapters, record, timeline
from adventure.database import encode, identifier, optional
from adventure.rounds import seats, shown


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def committed(connection, seq, number, intents, now):
    connection.execute(
        "INSERT INTO round_turns (id, branch_id, seq, number, state, mode, snapshot, draft, created_at, committed_at) "
        "VALUES (?, ?, ?, ?, 'committed', 'play', '{}', ?, ?, ?)",
        (identifier(), timeline.active(connection), seq, number,
         encode({'declarations': {key: {'seat': key, 'intent': intent} for key, intent in intents.items()}}), now, now))


def chapter_with_mara(client, app, provider):
    """A chapter at Pell's with Mara seated, a wound and two things shown about her, one hidden truth, and the same
    act declared twice; closed by the next line."""
    database = app.state.database
    begin(client)
    with database.connect(write=True) as connection:
        seats.set_seat(connection, 'mara', 'Mara Quill', database.now())
    provider.replies = [reply('Mara counts the coins.'), reply('Morning comes.')]
    tell(client, 'I pay Pell.', 'story-0001')
    with database.connect(write=True) as connection:
        line = optional(connection, "SELECT id, seq FROM story_messages WHERE role='narrator' ORDER BY seq DESC LIMIT 1")
        now = database.now()
        record.add(connection, 'wound', 'Mara', 'Mara has a cut across her palm.', now, message_id=line['id'])
        record.add(connection, 'fact', 'Mara Quill', 'Mara Quill is left-handed.', now, message_id=line['id'])
        record.add(connection, 'secret', 'Mara', 'Mara works for the co-op.', now, truth='world', message_id=line['id'])
        record.add(connection, 'fact', 'Pell', 'Pell bites every coin.', now, message_id=line['id'])
        committed(connection, line['seq'], 1, {'mara': 'Mara checks the exits.'}, now)
        committed(connection, line['seq'], 2, {'mara': 'Checks the exits again, by the back door.'}, now)
        chapters.mark(connection, 'player')
    tell(client, 'I get up.', 'story-0002')


def test_a_chapter_close_drafts_what_the_page_showed_and_the_gm_view_applies_it(client, connected, app, provider):
    chapter_with_mara(client, app, provider)
    updates = ok(client.get('/api/story/shown'))['updates']
    assert [(update['seat'], update['status']) for update in updates] == [('mara', 'drafted')]
    # Hidden truth stays off the sheet, and so does what the chapter showed of someone not seated.
    assert updates[0]['items'] == [{'kind': 'injury', 'text': 'Mara has a cut across her palm.'},
                                   {'kind': 'revealed', 'text': 'Mara Quill is left-handed.'},
                                   {'kind': 'habit', 'text': 'Often: Checks the exits again, by the back door.'}]
    with app.state.database.connect() as connection:
        assert shown.text(connection, 'mara') == ''
    path = f"/api/story/shown/{updates[0]['id']}"
    assert client.post(path, json={'apply': True}).status_code == 403
    ok(client.put('/api/story/table', json={'gm_view': True}))
    edited = updates[0]['items'][:2]
    done = ok(client.post(path, json={'apply': True, 'items': edited}))
    assert done['status'] == 'applied' and done['items'] == edited
    assert client.post(path, json={'apply': False}).status_code == 409
    with app.state.database.connect() as connection:
        assert shown.text(connection, 'mara') == ('- Hurt: Mara has a cut across her palm.\n'
                                                   '- Shown: Mara Quill is left-handed.')


def test_in_watch_an_update_applies_at_once_and_nobody_seated_drafts_nothing(app):
    database = app.state.database
    with database.connect(write=True) as connection:
        branch = timeline.active(connection)
        now = database.now()
        assert shown.close(connection, 'chapter-1', branch, 0, 10, now) == []
        seats.set_seat(connection, 'hesk', 'Hesk', now)
        seats.change(connection, {'mode': 'watch'}, False)
        committed(connection, 2, 1, {'hesk': 'I watch the road.'}, now)
        committed(connection, 4, 2, {'hesk': 'Hesk watches the road from the wall.'}, now)
        committed(connection, 12, 3, {'hesk': 'Hesk watches the road.'}, now)
        made = shown.close(connection, 'chapter-1', branch, 0, 10, now)
        # The third turn is after the chapter's end, so it does not count.
        assert [(update['status'], update['items']) for update in made] == [
            ('applied', [{'kind': 'habit', 'text': 'Often: watches the road from the wall.'}])]
        assert shown.sheet(connection, 'hesk') == [{'kind': 'habit', 'text': 'Often: watches the road from the wall.'}]
