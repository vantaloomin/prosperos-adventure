"""The story as a book, the campaign file and legacy (dungeon/book.py, dungeon/legacy.py)."""
import io
import zipfile

from conftest import Chunk, tell
from test_inventory import begin
from test_travel import ok

from dungeon import book, chapters, record
from dungeon.images import storage


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def played(client, provider, lines=('I pay Pell.', 'I ask about the road.')):
    begin(client)
    narrations = iter(['Pell takes the *coin* and grunts.\n\nThe lamp gutters (as lamps do).', 'He points west.'] * 3)
    provider.respond = lambda system, messages: (reply('{"facts": []}') if system.startswith(record.EXTRACT)
                                                 else reply(next(narrations)))
    for number, line in enumerate(lines, 1):
        tell(client, line, f'story-{number:04d}')


def download(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert 'attachment; filename=' in response.headers['content-disposition']
    return response


def test_the_story_exports_as_a_book_in_markdown_epub_and_pdf(client, connected, provider):
    played(client, provider)
    text = download(client, '/api/story/export/book?format=md').text
    assert text.startswith('# The story of Agna Holt') and '## Chapter 1' in text
    assert '> I pay Pell.' in text and 'Pell takes the *coin* and grunts.\n\nThe lamp gutters' in text
    # Nothing hidden goes in.
    assert "game master's note" not in text.lower() and '## The record' not in text

    epub = zipfile.ZipFile(io.BytesIO(download(client, '/api/story/export/book?format=epub').content))
    assert epub.namelist()[0] == 'mimetype' and epub.getinfo('mimetype').compress_type == zipfile.ZIP_STORED
    assert epub.read('mimetype') == b'application/epub+zip'
    chapter = epub.read('OEBPS/chapter-1.xhtml').decode()
    assert '<p class="player">I pay Pell.</p>' in chapter and '<em>coin</em>' in chapter
    assert 'properties="nav"' in epub.read('OEBPS/content.opf').decode()

    pdf = download(client, '/api/story/export/book?format=pdf').content
    assert pdf.startswith(b'%PDF-1.4') and pdf.rstrip().endswith(b'%%EOF') and b'/Type /Page ' in pdf
    assert client.get('/api/story/export/book?format=doc').status_code == 422


def test_an_empty_story_has_no_book(client):
    assert client.get('/api/story/export/book').status_code == 409


def test_the_pdf_wraps_long_paragraphs_and_breaks_pages():
    words = ' '.join(['lantern'] * 3000)
    pages = book.laid_out({'title': 'A story', 'chapters': [{'title': 'Chapter 1', 'number': 1,
                                                              'paragraphs': [('narrator', words), ('user', 'I wait (long).')]}]})
    assert len(pages) > 3
    for runs in pages:
        for font, size, x, y, line in runs:
            assert book.measure(line, size, font == 'heading') <= book.WIDTH - 2 * book.MARGIN
            assert book.MARGIN <= y <= book.HEIGHT
    assert book.escaped('I wait (long).') == 'I wait \\(long\\).'


def test_a_campaign_file_comes_back_as_a_new_world(client, connected, provider):
    played(client, provider)
    archive = download(client, '/api/story/export/campaign').content
    response = client.post('/api/worlds/import', content=archive, headers={'Content-Type': 'application/zip'})
    assert response.status_code == 200, response.text
    worlds = [world for persona in response.json()['personas'] for world in persona['worlds']]
    imported = next(world for world in worlds if world['name'].endswith('(imported)'))
    assert not imported['active']
    ok(client.post(f"/api/worlds/{imported['id']}/switch"))
    assert [line['text'] for line in ok(client.get('/api/story'))['messages'] if line['role'] == 'user'] == [
        'I pay Pell.', 'I ask about the road.']
    bad = client.post('/api/worlds/import', content=b'not a zip', headers={'Content-Type': 'application/zip'})
    assert bad.status_code == 422


def legacy_world(client, provider):
    """A story in the first world, then a new world to start in; the first world's id."""
    played(client, provider)
    first = next(world['id'] for persona in ok(client.get('/api/worlds'))['personas'] for world in persona['worlds']
                 if world['active'])
    made = ok(client.post('/api/worlds', json={'name': 'A later age'}))
    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    return first


def test_an_earlier_character_can_come_back_as_a_legend_a_villain_or_a_corpse(client, connected, provider, app):
    first = legacy_world(client, provider)
    offered = ok(client.get('/api/story/start'))['legacy']
    assert [(item['world_id'], item['name'], item['dead']) for item in offered] == [(first, 'Agna Holt', False)]
    for role in ('legend', 'villain', 'corpse'):
        ok(client.delete('/api/story'))
        ok(client.post('/api/story/start', json={'premade_id': 'tobin-pell', 'legacy': {'world_id': first, 'role': role}}))
        with app.state.database.connect() as connection:
            facts = connection.execute("SELECT kind, truth, weight, text FROM record_entries WHERE subject='Agna Holt' "
                                       "AND source='code'").fetchall()
            nemeses = connection.execute("SELECT name FROM story_nemeses WHERE name='Agna Holt'").fetchall()
            dead = record.dead(connection)
        kinds = {(row['kind'], row['truth']) for row in facts}
        assert facts and all(row['weight'] == 3 for row in facts)
        if role == 'legend':
            assert kinds == {('fact', 'both')} and 'legend' in facts[0]['text'] and not nemeses
        elif role == 'villain':
            assert ('secret', 'world') in kinds and len(nemeses) == 1
        else:
            assert ('death', 'both') in kinds and 'agna holt' in dead
    bad = client.post('/api/story/start', json={'premade_id': 'tobin-pell', 'legacy': {'world_id': first, 'role': 'ghost'}})
    assert bad.status_code == 422



def test_the_epub_carries_each_chapters_pictures_after_their_passages(client, connected, provider, app):
    played(client, provider)
    database = app.state.database
    stored = storage.store(database, 'art-1', b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + (64).to_bytes(4, 'big') * 2 + b'\x08\x02\x00\x00\x00')
    with database.connect(write=True) as connection:
        chapter = chapters.listing(connection)[0]['id']
        first = connection.execute("SELECT id FROM story_messages WHERE role='narrator' ORDER BY seq LIMIT 1").fetchone()['id']
        connection.execute("INSERT INTO story_art (id, kind, subject, chapter_id, prompt, state, status, file, created_at) "
                           "VALUES ('art-1', 'passage', ?, ?, 'p', 's', 'done', ?, 'x')", (first, chapter, stored['file']))
    epub = zipfile.ZipFile(io.BytesIO(download(client, '/api/story/export/book?format=epub').content))
    assert 'OEBPS/images/art-1.png' in epub.namelist()
    page = epub.read('OEBPS/chapter-1.xhtml').decode()
    # After the passage it shows (its two paragraphs), before the player's next line.
    assert page.index('The lamp gutters') < page.index('<figure><img src="images/art-1.png"') < page.index('I ask about the road.')
    assert 'media-type="image/png"' in epub.read('OEBPS/content.opf').decode()
