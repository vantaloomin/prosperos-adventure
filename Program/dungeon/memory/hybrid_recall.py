"""Rank fusion of independent lexical and semantic candidate lists.

Copied from prosperos-study server/memory/hybrid_recall.py at bbcbde4. Changes: takes Chunk
objects and a read limit from the caller instead of Study source rows and MAX_READS.
"""
from dungeon.memory.retrieval import Corpus, Hit

RANK_OFFSET = 60


def hybrid_hits(sources, queries, semantic, limit):
    chunks = {chunk.id: chunk for chunk in sources}
    corpus = Corpus(list(chunks.values()))
    lexical = [corpus.search(query, limit=limit) for query in queries]
    ranks = [[hit.chunk.id for hit in hits] for hits in lexical] + [
        [identity for identity in ranking if identity in chunks] for ranking in semantic['rankings']]
    totals, matched = {}, {}
    for ranking in ranks:
        for rank, identity in enumerate(ranking, 1):
            totals[identity] = totals.get(identity, 0) + 1 / (RANK_OFFSET + rank)
    for hits in lexical:
        for hit in hits:
            matched.setdefault(hit.chunk.id, set()).update(hit.matched)
    ordered = sorted(totals, key=lambda identity: (-totals[identity], identity))[:limit]
    return [Hit(chunks[identity], totals[identity], tuple(sorted(matched.get(identity, set()))),
                'Combined keyword and semantic search') for identity in ordered]
