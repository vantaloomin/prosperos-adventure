"""Wording the companion keeps repeating across their own recent replies (PRD M10).

Copied from prosperos-study server/phrases/detection.py at bbcbde4. Changes: findings carry the
phrase and counts only (no evidence quotes or ids), and `filler` and `repeats_line` were added for
the chat context, since the Study's phrases are three words or more and a filler word like
"honestly" is one. Deterministic; nothing here calls a model.
"""
import re
import unicodedata
from bisect import bisect_right
from collections import Counter, defaultdict

from dungeon.memory.cache import memoized
from dungeon.memory.retrieval import STOP

MIN_WORDS = 3
MAX_WORDS = 8
MAX_FINDINGS = 30
WORDS = re.compile(r"[^\W_]+(?:[̀-ͯ]+[^\W_]*)*(?:['’\-][^\W_]+(?:[̀-ͯ]+[^\W_]*)*)*", re.UNICODE)
BOUNDARY = re.compile(r'[.!?;:\n\r]')
# Keep these words in matches; only suppress phrases made entirely of common words.
COMMON = frozenset('a an and are as at be been being but by did do does for from had has '
                   'have he her hers him his i if in into is it its me my of on or our she '
                   'so that the their them then there these they this those to too us was '
                   'we were what when where which who will with would you your said says'.split())


@memoized('phrase-tokens-v1', 16 * 1024 * 1024)
def tokens(node_id, text):
    """Normalize each token, retaining code-point offsets and sentence boundaries."""
    result, segment, previous = [], 0, 0
    for match in WORDS.finditer(text):
        if BOUNDARY.search(text[previous:match.start()]):
            segment += 1
        word = unicodedata.normalize('NFKC', match.group()).casefold().replace('’', "'")
        result.append((word, match.start(), match.end(), segment))
        previous = match.end()
    return tuple(result)


def windows(words):
    for start in range(len(words)):
        for size in range(MIN_WORDS, min(MAX_WORDS, len(words) - start) + 1):
            end = start + size - 1
            if words[start][3] != words[end][3]:
                break
            phrase = tuple(word[0] for word in words[start:end + 1])
            if not all(word in COMMON for word in phrase):
                yield phrase, words[start][1], words[end][2]


def occurrences(passages, minimum):
    counts = Counter(phrase for node in passages for phrase, _, _ in windows(tokens(node['id'], node['text'])))
    repeated = {phrase for phrase, count in counts.items() if count >= minimum}
    matches = defaultdict(list)
    for index, node in enumerate(passages):
        ends = {}
        for phrase, start, end in windows(tokens(node['id'], node['text'])):
            if phrase in repeated and start >= ends.get(phrase, 0):
                matches[phrase].append((index, start, end))
                ends[phrase] = end
    return {phrase: spans for phrase, spans in matches.items() if len(spans) >= minimum}


def overlaps(span, covered):
    index, start, end = span
    ranges = covered[index]
    position = max(0, bisect_right(ranges, (start, end)) - 1)
    while position < len(ranges) and ranges[position][0] < end:
        left, right = ranges[position]
        if min(end, right) - max(start, left) > (end - start) / 2:
            return True
        position += 1
    return False


def cover(spans, covered):
    additions = defaultdict(list)
    for index, start, end in spans:
        additions[index].append((start, end))
    for index, ranges in additions.items():
        merged = []
        for start, end in sorted([*covered[index], *ranges]):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        covered[index] = merged


def finding(phrase, spans):
    return {'phrase': ' '.join(phrase), 'words': len(phrase), 'count': len(spans),
            'passage_count': len({span[0] for span in spans})}


def detect(passages, minimum=3):
    matches = occurrences(passages, minimum)
    ranked = sorted(matches, key=lambda phrase: (-len(matches[phrase]) * len(phrase), -len(phrase), phrase))
    covered, findings = defaultdict(list), []
    for phrase in ranked:
        spans = matches[phrase]
        if sum(not overlaps(span, covered) for span in spans) < minimum:
            continue
        if len(findings) == MAX_FINDINGS:
            return findings, True
        findings.append(finding(phrase, spans))
        cover(spans, covered)
    return findings, False


# Dungeon additions ------------------------------------------------------------------------------

RECENT_REPLIES = 15
WORD_SHARE = 5
SHOWN = 3
# Words too ordinary to count as a habit, on top of the stopwords.
ORDINARY = frozenset("about after again all also am any back because can can't could day don't even get "
                     "go going good got how i'd i'll i'm i've it's just know like lol make more much no not "
                     "now oh ok okay one out really see some still that's think time today tonight up want "
                     "way well what's yeah yes".split())


def filler(passages, names=frozenset()) -> list[dict]:
    """Single words in at least WORD_SHARE of the passages, leaving out ordinary words and names.

    A word written capitalized mid-sentence and never in lowercase counts as a name."""
    seen, lower, capital = Counter(), set(), set()
    for node in passages:
        words = tokens(node['id'], node['text'])
        for index, (word, start, _end, segment) in enumerate(words):
            if node['text'][start].isupper():
                if index and words[index - 1][3] == segment:
                    capital.add(word)
            else:
                lower.add(word)
        seen.update({word for word, *_rest in words})
    skip = STOP | COMMON | ORDINARY | {name.casefold() for name in names} | (capital - lower)
    return [{'phrase': word, 'words': 1, 'count': count, 'passage_count': count}
            for word, count in seen.items() if count >= WORD_SHARE and word not in skip and not word.isdigit()]


def repeats_line(passages, names=frozenset()) -> str | None:
    """One context line naming the companion's most repeated wording in their last replies, or None."""
    phrases = [item for item in detect(passages)[0] if item['passage_count'] >= 3]
    found = []
    for item in sorted(phrases + filler(passages, names), key=lambda item: (-item['passage_count'], -item['words'],
                                                                            item['phrase'])):
        # A word inside a phrase already named adds nothing.
        if len(found) < SHOWN and not (item['words'] == 1 and any(item['phrase'] in chosen['phrase'].split()
                                                                  for chosen in found)):
            found.append(item)
    if not found:
        return None
    listed = ', '.join(f'"{item["phrase"]}" ({item["passage_count"]} of your last {len(passages)} messages)'
                       for item in found)
    return f'You keep repeating: {listed}. Say it differently.'
