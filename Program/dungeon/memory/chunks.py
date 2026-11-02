"""Markdown-aware, reversible chunks. Originals and offsets are never normalized.

Adapted from prosperos-study server/memory/chunks.py at bbcbde4 (persistent cache format removed).
"""
import hashlib
import re
from dataclasses import dataclass

from dungeon.memory.cache import memoized

MAX_CHARS = 2400
HEADINGS = re.compile(r'^#{1,6}[ \t]+(.+)$', re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    id: str
    source_id: str
    title: str
    text: str
    start: int
    end: int
    digest: str
    kind: str = 'message'
    aliases: tuple[str, ...] = ()

    def evidence(self):
        return {'id': self.id, 'source_id': self.source_id, 'title': self.title,
                'text': self.text, 'start': self.start, 'end': self.end,
                'sha256': self.digest, 'kind': self.kind}


def split_end(text, start, end, limit):
    stop = min(start + limit, end)
    if stop == end:
        return stop
    # Prefer a paragraph, then a word boundary. No text is dropped between chunks.
    minimum = start + limit // 2
    paragraph = text.rfind('\n\n', minimum, stop)
    if paragraph >= minimum:
        return paragraph + 2
    space = text.rfind(' ', minimum, stop)
    return space + 1 if space >= minimum else stop


@memoized('markdown-chunks-v1', 32 * 1024 * 1024)
def compile_chunks(source_id, title, text, kind='message', aliases=()):
    """The cache key includes immutable identity AND bytes, never just a source ID."""
    headings = list(HEADINGS.finditer(text))
    sections = [(0, title), *[(match.start(), match.group(1).strip()) for match in headings]]
    chunks = []
    for index, (start, heading) in enumerate(sections):
        end = sections[index + 1][0] if index + 1 < len(sections) else len(text)
        while start < end:
            stop = split_end(text, start, end, MAX_CHARS)
            excerpt = text[start:stop]
            digest = hashlib.sha256(excerpt.encode('utf-8')).hexdigest()
            if excerpt.strip():
                chunks.append(Chunk(f'{source_id}@{start}:{stop}:{digest[:12]}', source_id,
                                    heading, excerpt, start, stop, digest, kind, tuple(aliases)))
            start = stop
    return tuple(chunks)
