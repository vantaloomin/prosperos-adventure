"""Compaction that keeps what's live (docs/spec.md "Keeping records readable").

Older messages are folded into the story so far (adventure/record.py `fold`), and a chapter that ends is summarized
for its "previously" (adventure/chapters.py `summarize`). Before either summary is used, code checks it: every name,
every number and every kept quote (a promise, oath, threat or confession said aloud, and any quote the summary before
already kept) in the words being folded must still be in it. A draft that drops one is asked again once, told what it
dropped; whatever the better draft still leaves out is added after it word for word, so a fold is never blocked and
nothing live is lost.

The record, rulings, quests and memories are stored apart and never deleted (summaries are written on top), so the
open threads, hidden truths, rulings and live promises held there stay reachable by construction; this check covers
what lives only in the words being folded.
"""
import re
from dataclasses import dataclass

from adventure.database import many, optional

# A number as the story writes it: 40, 3.5, 9:30, 1,200.
NUMBER = re.compile(r'(?<![\w.:,])\d+(?:[:.,]\d+)*')
# The small numbers a summary may write as words.
WORDS = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
         'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty')
QUOTE = re.compile(r'["“]([^"“”]{3,300})["”]')
# Words said aloud that bind or threaten someone later: these are kept word for word.
PLEDGE = re.compile(r"\b(promise[sd]?|swear|swore|sworn|vow(?:ed|s)?|oath|owe[sd]?|debt|bargain|deal|my word|"
                    r"kill you|you'll pay|confess(?:ed)?|never tell|on my (?:life|honou?r|mother|name))\b", re.I)
NAME = re.compile(r"^[A-Z][\w'-]*(?: [A-Z][\w'-]*)*$")
# Never more than this many things to keep from one fold, so the question stays readable.
MOST = 40

AGAIN = """

Your last draft dropped things that must stay in the story so far. Write the summary again and keep each of these, \
names and numbers as given and quoted words exactly as said:
{items}"""
ALSO = 'Also kept: {items}.'


@dataclass(frozen=True)
class Kept:
    kind: str  # 'name', 'number' or 'quote'
    text: str

    def shown(self) -> str:
        return f'"{self.text}"' if self.kind == 'quote' else self.text


def plain(text: str) -> str:
    """Text as the check compares it: straight quotes, one space, no case."""
    text = text.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return ' '.join(text.split()).casefold()


def known_names(connection) -> list[str]:
    """The names the game knows: the player's character, the people met, and the record's named subjects."""
    persona = optional(connection, 'SELECT name FROM persona WHERE id=1')
    names = [persona['name']] if persona and persona['name'] else []
    names += [row['name'] for row in many(connection, 'SELECT name FROM story_people')]
    names += [row['subject'] for row in many(connection, 'SELECT DISTINCT subject FROM record_entries WHERE removed=0')]
    return list(dict.fromkeys(name.strip() for name in names if NAME.match(name.strip())))


def numbers(text: str) -> list[str]:
    return list(dict.fromkeys(NUMBER.findall(text)))


def quotes(text: str, pledges_only: bool = True) -> list[str]:
    found = (' '.join(match.split()) for match in QUOTE.findall(text))
    return list(dict.fromkeys(quote for quote in found if not pledges_only or PLEDGE.search(quote)))


def live(connection, before: str, folded: str) -> list[Kept]:
    """What the summary must keep: the names and numbers in the summary before and the words being folded, the
    pledges said aloud in those words, and every quote the summary before already kept."""
    source = f'{before}\n{folded}'
    named = [Kept('name', name) for name in known_names(connection)
             if re.search(rf'(?<!\w){re.escape(name)}(?!\w)', source)]
    counted = [Kept('number', number) for number in numbers(source)]
    said = [Kept('quote', quote) for quote in dict.fromkeys(quotes(before, False) + quotes(folded))]
    return (said + named + counted)[:MOST]


def holds(item: Kept, text: str) -> bool:
    if item.kind == 'quote':
        return plain(item.text).rstrip('.,!?') in plain(text)
    if item.kind == 'number':
        if re.search(rf'(?<![\d.:,]){re.escape(item.text)}(?![\d])', text):
            return True
        small = int(item.text) if item.text.isdigit() and int(item.text) < len(WORDS) else None
        return small is not None and re.search(rf'\b{WORDS[small]}\b', text, re.I) is not None
    return re.search(rf'(?<!\w){re.escape(item.text)}(?!\w)', text, re.I) is not None


def dropped(items: list[Kept], text: str) -> list[Kept]:
    return [item for item in items if not holds(item, text)]


def again(missing: list[Kept]) -> str:
    """Added to the summarizer's instructions when its draft dropped something."""
    return AGAIN.format(items='\n'.join(f'- {item.shown()}' for item in missing))


def also(text: str, missing: list[Kept]) -> str:
    """The summary with what it still leaves out added after it, word for word."""
    if not missing:
        return text
    line = ALSO.format(items='; '.join(item.shown() for item in missing))
    return f'{text}\n\n{line}' if text else line


async def checked(draft, items: list[Kept], text_of=lambda answer: answer):
    """The answer to use and what it still drops: `draft(note)` is asked once with no note and, when its summary
    (read by `text_of`) drops something live, once more with what it dropped. The draft that drops less is kept; a
    failed second ask keeps the first. The caller adds what is still dropped after the summary (`also`)."""
    answer = await draft('')
    missing = dropped(items, text_of(answer))
    if missing and text_of(answer):
        try:
            second = await draft(again(missing))
        except Exception:  # noqa: BLE001 - the first draft is kept, with what it dropped added after it.
            second = None
        if second is not None and text_of(second) and len(dropped(items, text_of(second))) < len(missing):
            answer, missing = second, dropped(items, text_of(second))
    return answer, missing
