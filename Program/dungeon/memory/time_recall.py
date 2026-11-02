"""Time-aware recall and near-duplicate spreading for the recalled section (PRD M10).

A question that names a time ("what did I tell you last weekend?", "how was the trip in March?")
adds one more ranking to the keyword and semantic fusion: the eligible items from that time. The
phrase is resolved by dungeon/memory/dates.py in the user's timezone, so no model is involved and
nothing outside the eligible pool is reached. The idea of a separate time path fused with the
others comes from Kitzkatz/memoria (MIT); no code was copied.

Spreading keeps a handful of near-identical turns from filling the whole recalled section: an item
whose words mostly repeat one already chosen waits behind the others instead of being dropped.
"""
import re
from datetime import date, datetime

from dungeon.clock import parse
from dungeon.memory import dates
from dungeon.memory.retrieval import terms

# Talk of what is coming; otherwise a bare weekday or date in a question means the latest one.
FUTURE = re.compile(r"\b(?:will|won't|gonna|going to|plan(?:s|ned|ning)?|upcoming|next)\b", re.IGNORECASE)
LIMIT = 16
SIMILAR = 0.6


def query_span(query: str, now: datetime, timezone: str) -> tuple[datetime, datetime] | None:
    """The UTC bounds of the first time phrase in the query, or None.

    A single day that contains today ("today", "tonight") is skipped: those turns are already in
    the recent conversation, and the words are said far more often than they ask about the past.
    """
    span = dates.resolve(query, now, timezone, past=not FUTURE.search(query))
    if span is None:
        return None
    today = dates.local_day(now, timezone)
    if span.start <= today < span.end and (span.end - span.start).days <= 1:
        return None
    return dates.bounds(span, timezone)


def moment(kind: str, owner: dict, timezone: str) -> tuple[datetime | None, datetime | None, datetime]:
    """(start, end, said): when the item happened, if known, and when it was said."""
    if kind in ('summary', 'storyline'):
        start = dates.instant(date.fromisoformat(owner['day']), timezone)
        return None, None, start
    if kind == 'memory':
        return parse(owner.get('applies_from')), parse(owner.get('applies_until')), parse(owner['stated_at'])
    return None, None, parse(owner['created_at'])


def within(kind: str, owner: dict, span: tuple[datetime, datetime], timezone: str) -> bool:
    lower, upper = span
    start, end, said = moment(kind, owner, timezone)
    if start is not None and start < upper and (end is None or end > lower):
        return True
    return lower <= said < upper


ORDER = {'memory': 0, 'summary': 1, 'storyline': 1, 'message': 2}


def ranking(chunks, owners, span, timezone: str) -> list[str]:
    """Chunk ids from the span: memories, then day summaries, then turns, newest first in each."""
    if span is None:
        return []
    found = [chunk for chunk in chunks if within(*owners[chunk.id], span, timezone)]
    found.sort(key=lambda chunk: (ORDER[owners[chunk.id][0]], -moment(*owners[chunk.id], timezone)[2].timestamp(),
                                  chunk.id))
    return [chunk.id for chunk in found[:LIMIT]]


def similarity(left: set, right: set) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def spread(hits, limit: int) -> list:
    """The best `limit` hits in fused order, with near-repeats of an earlier pick moved behind the rest."""
    chosen, deferred, words = [], [], []
    for hit in hits:
        current = set(terms(hit.chunk.text))
        if any(similarity(current, earlier) >= SIMILAR for earlier in words):
            deferred.append(hit)
            continue
        chosen.append(hit)
        words.append(current)
    return (chosen + deferred)[:limit]
