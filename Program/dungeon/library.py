"""A reference library (ported from Prospero's Companion 1.0, companion/library.py): long texts the player adds to
the world, such as a world bible, a novel, a script, transcripts or a wiki export (dungeon/library_readers.py).

A book is split into short passages, kept whole, and indexed for keyword recall (dungeon/memory/retrieval.py). Each
turn the narrator gets at most MOST_PASSAGES passages that match the last few messages (`prompt_text`), skipping
what the last few turns were given (`library_given`). No model picks them and nothing is sent anywhere. Companion's
embedding match and its downloadable Neokosmos wiki are left out: Dungeon's story recall is keyword-only for now.
"""
import re

from dungeon.database import identifier, many, one
from dungeon.errors import require
from dungeon.library_readers import read
from dungeon.memory.chunks import Chunk
from dungeon.memory.retrieval import STOP, Corpus, terms

# A passage is a few sentences: cut at a paragraph, else a sentence, else a word, near this many characters.
PASSAGE_CHARS = 480
# A piece shorter than this at the end of a section joins the passage before it.
SCRAP_CHARS = 120
MOST_BOOK_PASSAGES = 30_000
# Per turn: at most this many passages, this many characters in all.
MOST_PASSAGES = 3
MOST_CHARS = 1200
# The messages matched, counting the one being answered.
SCAN_MESSAGES = 4
# A passage given in one of the last few turns (a turn is the player's line and the narration) waits before it
# comes again.
RECENT_TURNS = 4
# How well a passage must match to be used: keyword score (0 to 1).
KEYWORD_FLOOR = 0.1
CANDIDATES = 12
RANK_OFFSET = 60
SHOWN_PASSAGES = 20
HEADING = ("## From the library (passages from the world's reference books; true in this world. Use what bears on "
           'the scene as your own knowledge, in your own words: never quote them or say where they come from)')
# A run of capitalized words: a name, a place, a title.
NAME = re.compile(r"(?<![\w'’-])[A-Z][\w'’-]*(?: [A-Z][\w'’-]*)*")
SENTENCE = re.compile(r'[.!?…]["\')\]’”]*\s')
# Everyday chat words, which would match any long text: a passage has to match something more particular, like a
# name, a place or a subject. A word also counts in these forms: -s, -es, -ed, -d, -ing, -ly, -er.
CHAT_WORDS = frozenset("""
able about actually after afternoon again ago agree ah all almost alone along already alright also always am amazing
any anything anyway anywhere around ask away awesome back bad bed being best better big bit bored both bring busy buy
call came can can't cant care cause chat check come cool could couldn't cute dad day days dear did didn't dinner do
does doesn't doing don't done down dream drink each early easy eat else end enough even evening ever every everyone
everything exactly fair far feel fine first food for forget found free friend fun funny get give glad go god going
gone gonna good got great guess guy had happen happy hard has hate have haven't he'd hear heard heart hello help hey hi
hmm home hope hour house how huh i'd i'll i'm i've idea just keep kind kinda know last late later laugh least leave
less let let's life like little live lol long look lot love lunch made make many maybe mean meet might mind miss mom
moment money more morning most move much must need never new next nice night nope nothing now ok okay old once one only
other out over own people pretty probably put quite rather read ready real really remember right said same saw say
see seem seen send should show since sleep small so some someone something sometimes soon sorry sound start stay still
stop story stuff such sure take talk tell than thank thanks that's thing things think though thought through time
tired today together told tomorrow tonight too took true try trying turn um understand until up very wait walk want
was watch way week weekend weird well went what's whatever while who's why wish without won't wonder work world worry
would wow write wrong yeah year yes yesterday yet you're you've yours""".split())



# Adding a book ------------------------------------------------------------------------------------------

def tidy(text: str) -> str:
    text = re.sub(r'[ \t ]+', ' ', text.replace('\r\n', '\n').replace('\r', '\n'))
    return re.sub(r'\n[ \n]*\n', '\n\n', re.sub(r' *\n *', '\n', text)).strip()


def cut(text: str, start: int, limit: int) -> int:
    """Where a passage starting at `start` ends: a paragraph, else a sentence, else a word, in its second half."""
    stop = min(start + limit, len(text))
    if stop == len(text):
        return stop
    least = start + limit // 2
    paragraph = text.rfind('\n\n', least, stop)
    if paragraph >= least:
        return paragraph + 2
    sentences = [match.end() for match in SENTENCE.finditer(text, least, stop)]
    if sentences:
        return sentences[-1]
    space = text.rfind(' ', least, stop)
    return space + 1 if space >= least else stop


def passages(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """(title, text) passages of a book's sections, in order; every word kept once."""
    found = []
    for title, body in sections:
        text, start, first = tidy(body), 0, len(found)
        while start < len(text):
            stop = cut(text, start, PASSAGE_CHARS)
            if (piece := text[start:stop].strip()) and len(piece) < SCRAP_CHARS and len(found) > first:
                # A scrap, such as a wiki's "Continue to Chapter II" link, goes with the passage before it, so it
                # never takes one of a reply's few places by itself.
                found[-1] = (found[-1][0], f'{found[-1][1]}\n\n{piece}')
            elif piece:
                found.append((title[:200], piece))
            start = stop
    require(found, 'There are no words to read in this file.', 422)
    require(len(found) <= MOST_BOOK_PASSAGES, 'This text is longer than the library takes (about 14 MB of words). '
            'Split it into parts and add each one.', 422)
    return found


def add(database, filename: str, source: bytes) -> dict:
    """A file as a new book of the world's library."""
    found = read(filename, source)
    pieces = passages(found['sections'])
    timestamp = database.now()
    with database.connect(write=True) as connection:
        book_id = identifier()
        connection.execute('INSERT INTO library_books (id, name, source_format, source_file, created_at, updated_at) '
                           'VALUES (?, ?, ?, ?, ?, ?)',
                           (book_id, found['name'][:200], found['format'], filename[:260], timestamp, timestamp))
        connection.executemany('INSERT INTO library_passages (id, book_id, position, title, text) VALUES (?, ?, ?, ?, ?)',
                               [(identifier(), book_id, index, title, text) for index, (title, text) in enumerate(pieces)])
    return {**listing(database), 'added': {'id': book_id, 'name': found['name'][:200], 'passages': len(pieces)}}


# The books on the page ----------------------------------------------------------------------------------

def book_view(book: dict, count: int) -> dict:
    return {'id': book['id'], 'name': book['name'], 'source_format': book['source_format'],
            'source_file': book['source_file'], 'enabled': bool(book['enabled']), 'passages': count,
            'created_at': book['created_at'], 'updated_at': book['updated_at']}


def listing(database) -> dict:
    """The world's books, with how many passages each has."""
    with database.connect() as connection:
        counts = dict(connection.execute('SELECT book_id, COUNT(*) FROM library_passages GROUP BY book_id').fetchall())
        books = many(connection, 'SELECT * FROM library_books ORDER BY created_at')
        return {'books': [book_view(book, counts.get(book['id'], 0)) for book in books]}


def set_book(database, book_id: str, enabled: bool) -> dict:
    with database.connect(write=True) as connection:
        one(connection, 'SELECT id FROM library_books WHERE id=?', (book_id,))
        connection.execute('UPDATE library_books SET enabled=? WHERE id=?', (int(enabled), book_id))
    return listing(database)


def remove_book(database, book_id: str) -> dict:
    with database.connect(write=True) as connection:
        one(connection, 'SELECT id FROM library_books WHERE id=?', (book_id,))
        connection.execute('DELETE FROM library_books WHERE id=?', (book_id,))
    return listing(database)


def browse(database, book_id: str, query: str = '') -> dict:
    """A book's passages, so the player can see what it draws from: the first few, or the best matches for `query`."""
    with database.connect() as connection:
        one(connection, 'SELECT id FROM library_books WHERE id=?', (book_id,))
        rows = many(connection, 'SELECT id, title, text FROM library_passages WHERE book_id=? ORDER BY position',
                    (book_id,))
    if query.strip():
        found = corpus_of(rows).search(query, limit=SHOWN_PASSAGES)
        shown = [{'id': hit.chunk.id, 'title': hit.chunk.title, 'text': hit.chunk.text} for hit in found]
    else:
        shown = rows[:SHOWN_PASSAGES]
    return {'total': len(rows), 'passages': shown}


# For the narrator ---------------------------------------------------------------------------------------

CORPORA: dict[tuple, Corpus] = {}


def corpus_of(rows: list[dict], key: tuple | None = None) -> Corpus:
    """Keyword statistics over passages; kept for the same books at the same revision (`key`)."""
    if key is not None and key in CORPORA:
        return CORPORA[key]
    corpus = Corpus([Chunk(row['id'], row.get('book_id', ''), row['title'], row['text'], 0, len(row['text']), '',
                           'passage') for row in rows])
    if key is not None:
        if len(CORPORA) >= 4:
            CORPORA.pop(next(iter(CORPORA)))
        CORPORA[key] = corpus
    return corpus


def passage_text(row: dict) -> str:
    return f"{row['title']}: {row['text']}" if row['title'] else row['text']


def everyday(word: str) -> bool:
    return word in CHAT_WORDS or word.isdigit() or any(
        word.endswith(ending) and word[:-len(ending)] in CHAT_WORDS for ending in ('s', 'es', 'ed', 'd', 'ing', 'ly', 'er'))


def particular(text: str, known=None) -> str:
    """The words of `text` that could pick out a passage: not stopwords, not everyday chat, and (with `known`, the
    words of the books) in the books at all, so a word they never use doesn't water down the ones they do."""
    return ' '.join(word for word in terms(text) if not everyday(word) and (known is None or word in known))


def plain(word: str) -> bool:
    return word.casefold() in STOP or everyday(word.casefold())


def names(text: str) -> list[str]:
    """What the text calls by name, as the user capitalized it: "Old Quarter", "Lady Corrow", "Picts". A capital at
    the start of a sentence counts only when the word is not an everyday one ("Is", "Tell")."""
    found = []
    for match in NAME.finditer(text):
        words = match.group().split()
        if plain(words[0]) and (match.start() == 0 or re.search(r'[.!?…]\s*$', text[:match.start()])):
            words = words[1:]
        if len(words) > 1 or (words and not plain(words[0])):
            found.append(' '.join(words))
    return found


def named(called: list[str], passage: str) -> bool:
    """Whether the passage has one of these names whole, in any letter case."""
    return any(re.search(r'(?<!\w)' + r'\s+'.join(map(re.escape, name.split())) + r'(?!\w)', passage, re.I)
               for name in called)


def fits(hit, called: list[str], words: str, texts: dict[str, str]) -> bool:
    """Whether a keyword match is close enough: it has two of the words, or one when that is all there was; and when
    the message names something (`called`), a passage matched on one word must name it whole, so "the Old Quarter"
    never brings back "an unlikely quarter"."""
    if len(set(hit.matched)) >= 2:
        return True
    return named(called, texts[hit.chunk.id]) if called else len(set(words.split())) == 1


def ranked(corpus: Corpus, queries: list[str], meaning: list[str], texts: dict[str, str]) -> list[str]:
    """Passage ids that match the conversation by keywords or by meaning, fused by rank, best first. `texts` (each
    passage with its title) holds keyword matches to `fits`."""
    rankings = [meaning]
    for query in queries:
        if words := particular(query, corpus.df):
            called = names(query)
            rankings.append([hit.chunk.id for hit in corpus.search(words, limit=CANDIDATES, threshold=KEYWORD_FLOOR)
                             if fits(hit, called, words, texts)])
    totals = {}
    for ranking in rankings:
        for rank, identity in enumerate(ranking, 1):
            totals[identity] = totals.get(identity, 0) + 1 / (RANK_OFFSET + rank)
    return sorted(totals, key=lambda identity: (-totals[identity], identity))


def recently_given(connection, seq: int) -> set[str]:
    # Bounded above too: a new story or a branch taken back numbers its messages again.
    rows = connection.execute('SELECT passage_id FROM library_given WHERE seq BETWEEN ? AND ?',
                              (seq - 2 * RECENT_TURNS, seq - 1))
    return {row[0] for row in rows.fetchall()}


def prompt_text(connection, recent: list[str], seq: int) -> tuple[str, list[str]]:
    """(the library block for this turn, the passage ids in it): up to MOST_PASSAGES passages that fit the last few
    messages, the newest (the player's line) first. ('', []) with no switched-on book or nothing that fits."""
    books = many(connection, 'SELECT id, updated_at FROM library_books WHERE enabled=1 ORDER BY id')
    if not books:
        return '', []
    marks = ','.join('?' * len(books))
    rows = many(connection, f'SELECT id, book_id, title, text FROM library_passages WHERE book_id IN ({marks}) '
                'ORDER BY book_id, position', tuple(book['id'] for book in books))
    corpus = corpus_of(rows, tuple((book['id'], book['updated_at']) for book in books))
    texts = {row['id']: row for row in rows}
    skip = recently_given(connection, seq)
    latest = recent[-1] if recent else ''
    found = ranked(corpus, [latest, '\n'.join(recent[-SCAN_MESSAGES:])], [],
                   {row['id']: passage_text(row) for row in rows})
    lines, given, used = [], [], 0
    for identity in found:
        row = texts[identity]
        if identity in skip or used + len(row['text']) > MOST_CHARS:
            continue
        lines.append(f'- {passage_text(row)}')
        given.append(identity)
        used += len(row['text'])
        if len(given) >= MOST_PASSAGES:
            break
    return (f'{HEADING}\n' + '\n'.join(lines), given) if lines else ('', [])


def mark_given(connection, passage_ids: list[str], seq: int) -> None:
    """The passages a turn was given, so the next few leave them out rather than repeat them."""
    connection.executemany('INSERT OR REPLACE INTO library_given (passage_id, seq) VALUES (?, ?)',
                           [(identity, seq) for identity in passage_ids])
