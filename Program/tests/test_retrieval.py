import sys

from dungeon.memory.cache import retained_bytes
from dungeon.memory.chunks import compile_chunks
from dungeon.memory.hybrid_recall import hybrid_hits
from dungeon.memory.retrieval import STOP, Corpus, term_counts


def chunks(*texts):
    return [chunk for index, text in enumerate(texts) for chunk in compile_chunks(f's{index}', 'note', text)]


def test_conversation_words_are_searchable():
    assert 'story' not in STOP and 'continue' not in STOP
    hits = Corpus(chunks('Tell me a story about the lighthouse', 'Groceries: milk and eggs')).search('story')
    assert [hit.chunk.source_id for hit in hits] == ['s0']


def test_hybrid_fusion_accepts_caller_rankings():
    sources = chunks('Genmaicha is my favourite tea', 'The interview is on Thursday')
    semantic = {'rankings': [[sources[1].id, 'unknown-id']]}
    hits = hybrid_hits(sources, ['tea'], semantic, limit=5)
    assert {hit.chunk.id for hit in hits} == {sources[0].id, sources[1].id}


def test_term_counts_keep_a_ten_thousand_message_history():
    """Recall scans the whole history on every reply; an LRU smaller than that misses on every
    message, which made assembling a reply take about a second at 10,000 messages."""
    texts = [f'Message {index}: honestly it was a long day and then the bus was late twice. What about the '
             f'garden and that book and the rain? Then {index * 7} more words about the weekend plans.'
             for index in range(10_000)]
    term_counts.cache_clear()
    for text in texts:
        term_counts(text)
    for text in texts:
        term_counts(text)
    info = term_counts.cache_info()
    assert info['misses'] == len(texts) and info['hits'] == len(texts)


def test_cache_sizes_shared_leaves_once():
    word = 'lighthouse'
    pair = (word, word)
    assert retained_bytes(pair) == sys.getsizeof(pair) + sys.getsizeof(word)
