"""The reference library: long texts split into passages, the few that fit the story given to the narrator
(dungeon/library.py, dungeon/library_readers.py). Ported from Prospero's Companion 1.0."""
import base64
import html
import io
import json
import zipfile

import pytest
from conftest import Chunk

from dungeon import library
from dungeon.errors import DomainError
from dungeon.library_readers import read, wikitext

NOVEL = ('The Lighthouse Keeper\n\n'
         'Chapter 1\n\nThe lighthouse at Gull Point had been dark since the storm of 1998. Nobody in the village '
         'would say who had put the lamp out.\n\n'
         'Chapter 2\n\nMarguerite Fenwick kept bees on the cliff above the harbour, and every spring she sold '
         'heather honey at the market in Saltcombe.\n')


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def add(client, filename, data: bytes, status=200):
    response = client.post('/api/library/books', json={'filename': filename, 'data': encoded(data)})
    assert response.status_code == status, response.text
    return response.json()


def connect(client):
    response = client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'})
    assert response.status_code == 200, response.text


def say(client, provider, text, client_id) -> str:
    """One turn; the narrator's system prompt for it."""
    provider.replies = [[Chunk('The tide turns.'), Chunk('', 'stop')]]
    response = client.post('/api/story/messages', json={'text': text, 'client_id': client_id})
    assert response.status_code == 200, response.text
    return provider.requests[-1]['system']


def tiddlywiki(tiddlers, title='Harbor Wiki') -> bytes:
    store = json.dumps([{'title': '$:/SiteTitle', 'text': title}, *tiddlers]).replace('<', '\\u003C')
    return ('<!doctype html><html><head><meta name="application-name" content="TiddlyWiki" /></head><body>'
            f'<script class="tiddlywiki-tiddler-store" type="application/json">{store}</script></body></html>').encode()


WIKI = tiddlywiki([
    {'title': 'Edgar', 'text': "!! Edgar Grandeholm\n''Merchant lord'' of [[Grandport|Grandport]]. "
                               '<<tag Merchants>> He built the <span style="color:red">tall tower</span>.'},
    {'title': '$:/state/sidebar', 'text': 'open'},
    {'title': 'Draft of Edgar', 'text': 'unfinished', 'draft.of': 'Edgar'},
    {'title': 'Edgar.mp4', 'text': '<video src="edgar.mp4"></video>'},
    {'title': 'Banner.png', 'type': 'image/png', 'text': 'iVBORw0KGgo='},
    {'title': 'Leylines', 'text': 'The leylines carry mana under the sea. {{Leylines/Footer}}'},
])


# Reading files ------------------------------------------------------------------------------------------

def test_a_novel_splits_at_its_chapters():
    found = read('keeper.txt', NOVEL.encode())
    assert found['format'] == 'Plain text' and found['name'] == 'keeper'
    assert [title for title, _text in found['sections']] == ['keeper', 'Chapter 1', 'Chapter 2']


def test_markdown_and_web_pages_keep_their_headings():
    found = read('notes.md', b'Intro words.\n\n# The Docks\n\nShips come in at dawn.\n\n## Fish market\n\nCod.')
    assert [title for title, _text in found['sections']] == ['notes', 'The Docks', 'Fish market']
    page = read('page.html', b'<html><head><title>Harbor guide</title><style>p{color:red}</style></head><body>'
                             b'<h1>The Docks</h1><p>Ships &amp; boats.</p><script>alert(1)</script><h2>Market</h2>'
                             b'<p>Cod.</p></body></html>')
    assert page['name'] == 'Harbor guide' and page['format'] == 'Web page'
    assert [(title, ' '.join(text.split())) for title, text in page['sections']] == [('The Docks', 'Ships & boats.'),
                                                                                    ('Market', 'Cod.')]


def test_an_epub_is_read_in_spine_order():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('mimetype', 'application/epub+zip')
        archive.writestr('META-INF/container.xml', '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:'
                         'opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles>'
                         '</container>')
        archive.writestr('OEBPS/book.opf', '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
                         'xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata><dc:title>Saltcombe Tales</dc:title>'
                         '</metadata><manifest><item id="b" href="two.xhtml"/><item id="a" href="one.xhtml"/>'
                         '</manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
        archive.writestr('OEBPS/one.xhtml', '<html><body><h1>One</h1><p>Bees on the cliff.</p></body></html>')
        archive.writestr('OEBPS/two.xhtml', '<html><body><h1>Two</h1><p>Honey at market.</p></body></html>')
    found = read('tales.epub', buffer.getvalue())
    assert found['name'] == 'Saltcombe Tales' and [title for title, _ in found['sections']] == ['One', 'Two']


def test_a_tiddlywiki_gives_one_section_per_tiddler_with_its_title():
    found = read('wiki.html', WIKI)
    assert found['format'] == 'TiddlyWiki' and found['name'] == 'Harbor Wiki'
    sections = dict(found['sections'])
    assert list(sections) == ['Edgar', 'Leylines']
    assert ' '.join(sections['Edgar'].split()) == 'Edgar Grandeholm Merchant lord of Grandport. He built the tall tower .'


def test_an_older_tiddlywiki_store_is_read_too():
    body = html.escape("Ships ''dock'' at [[the pier]].")
    page = ('<html><head><meta name="generator" content="TiddlyWiki" /></head><body><div id="storeArea">'
            f'<div title="Pier" modifier="Oak"><pre>{body}</pre></div>'
            '<div title="$:/core"><pre>x</pre></div></div></body></html>')
    assert read('old.html', page.encode())['sections'] == [('Pier', 'Ships dock at the pier.')]


def test_wikitext_keeps_urls_and_tables_readable():
    assert wikitext('See https://example.org //now//.') == 'See https://example.org now.'
    assert wikitext('|!Name|!Age|\n|Edgar|60|') == 'Name; Age\nEdgar; 60'


def test_other_files_are_turned_down():
    with pytest.raises(DomainError, match='.txt, .md'):
        read('cover.png', b'\x89PNG\r\n')


def test_passages_are_short_and_keep_every_word():
    text = ' '.join(f'Sentence number {index} is about the harbour.' for index in range(200))
    found = library.passages([('Book', text)])
    assert all(len(piece) <= library.PASSAGE_CHARS + library.SCRAP_CHARS for _title, piece in found)
    assert ' '.join(piece for _title, piece in found).split() == text.split()


def test_a_scrap_at_the_end_of_a_section_joins_the_passage_before_it():
    chapter = ' '.join(f'Sentence number {index} is about the harbour.' for index in range(11))
    found = library.passages([('Chapter I', f'{chapter}\n\nContinue to Chapter II'), ('Chapter II', 'Short.')])
    assert [title for title, _piece in found] == ['Chapter I', 'Chapter II']
    assert found[0][1].endswith('harbour.\n\nContinue to Chapter II')


def test_everyday_words_pick_out_no_passage_and_names_are_what_was_capitalized():
    assert library.particular("How was your day? I'm tired, work was long.") == ''
    assert library.particular('Have you ever been to the Admiralty?') == 'admiralty'
    assert library.names('Is Old Marigold still by the window? Did Lady Corrow collect it?') == [
        'Old Marigold', 'Lady Corrow']


# The library in the app ----------------------------------------------------------------------------------

def test_books_are_added_listed_browsed_switched_off_and_removed(client):
    made = add(client, 'keeper.txt', NOVEL.encode())
    assert made['added']['passages'] == 3
    add(client, 'wiki.html', WIKI)
    books = client.get('/api/library').json()['books']
    assert [(book['name'], book['passages']) for book in books] == [('keeper', 3), ('Harbor Wiki', 2)]
    book = books[0]
    listed = client.get(f"/api/library/books/{book['id']}/passages").json()
    assert listed['total'] == 3 and listed['passages'][0]['title'] == 'keeper'
    found = client.get(f"/api/library/books/{book['id']}/passages", params={'q': 'honey'}).json()
    assert [item['title'] for item in found['passages']] == ['Chapter 2']
    assert client.put(f"/api/library/books/{book['id']}", json={'enabled': False}).json()['books'][0]['enabled'] is False
    assert [item['name'] for item in client.delete(f"/api/library/books/{book['id']}").json()['books']] == ['Harbor Wiki']


def test_an_empty_or_broken_file_says_so(client):
    assert 'no words' in add(client, 'empty.txt', b'   \n', status=422)['detail']
    response = client.post('/api/library/books', json={'filename': 'a.txt', 'data': 'not base64!'})
    assert response.status_code == 422 and 'did not arrive whole' in response.json()['detail']


# For the narrator ---------------------------------------------------------------------------------------

def test_matching_passages_join_the_narrators_prompt_and_wait_before_coming_again(client, provider):
    connect(client)
    add(client, 'keeper.txt', NOVEL.encode())
    assert library.HEADING not in say(client, provider, 'I look around the room.', 'library-0001')
    system = say(client, provider, 'I ask whether Marguerite Fenwick sold her honey this spring.', 'library-0002')
    assert library.HEADING in system and '- Chapter 2: Marguerite Fenwick kept bees' in system
    assert 'Gull Point' not in system
    # Just given: the next turn leaves it out rather than repeat it.
    system = say(client, provider, 'I ask more about Marguerite Fenwick and her honey.', 'library-0003')
    assert 'Marguerite Fenwick kept bees' not in system


def test_a_switched_off_book_stays_out(client, provider):
    connect(client)
    book = add(client, 'keeper.txt', NOVEL.encode())['added']
    client.put(f"/api/library/books/{book['id']}", json={'enabled': False})
    assert library.HEADING not in say(client, provider, 'Who put out the lighthouse at Gull Point?', 'library-0001')


def test_a_turn_gets_at_most_three_passages(client, provider):
    connect(client)
    lens = 'The lighthouse keeper polished lamp lens number {index} at dusk, humming as the gulls circled.'
    bees = 'Marguerite kept her bees in hive number {index} on the cliff and sold the honey in town.'
    text = '\n\n'.join(f'Chapter {index}\n\n' + (lens if index % 2 else bees).format(index=index) for index in range(16))
    add(client, 'lamps.txt', text.encode())
    system = say(client, provider, 'I ask about the lighthouse keeper and the lamp lens.', 'library-0001')
    notes = system.split(library.HEADING)[1]
    lines = [line for line in notes.splitlines() if line.startswith('- Chapter')]
    assert len(lines) == library.MOST_PASSAGES and sum(len(line) for line in lines) <= library.MOST_CHARS + 60


def test_a_one_word_match_on_a_name_needs_the_whole_name(client, provider):
    connect(client)
    text = ('Chapter 1\n\nThe Academic Quarter climbs toward the citadel, where scholars argue all night.\n\n'
            'Chapter 2\n\nHelp came from an unlikely quarter: a fisherman who knew the tides.\n\n'
            'Chapter 3\n\nIn the Old Quarter the lanterns burn green and the tanners work by the river.\n\n'
            + ''.join(f'Chapter {index}\n\nThe ferry crossed the estuary for the {index}th time that week.\n\n'
                      for index in range(4, 12)))
    add(client, 'city.txt', text.encode())
    system = say(client, provider, 'I head for the Old Quarter.', 'library-0001')
    notes = system.split(library.HEADING)[1]
    assert 'lanterns burn green' in notes
    assert 'unlikely quarter' not in notes and 'Academic Quarter' not in notes
