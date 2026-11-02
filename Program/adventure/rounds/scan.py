"""The draft scan (docs/spec.md "The draft scan and the Reviewer"): every Writer post is checked in code against the
house rules (adventure/rounds/house_rules.py) before it is committed.

A finding is one of three severities, prose.py's own:

- **hard**: a house rule code can see is broken. Forbidden punctuation, an outlawed word, phrase or name, a number
  with a game term on it outside a System pane ("12 hit points"), the dice or a roll mentioned. A draft with one is
  never committed: settle() asks for a rewrite and scans again, twice at most; what is left after that is fixed by
  code, mechanically for punctuation and by cutting the sentence for the rest. A cut is listed for the turn report,
  where the user can Rewrite the passage (adventure/passages.py).
- **strong**: prose.py's hard dialogue rules and strongest tells (scene-closers among them), a closing line that
  sums the scene up, and the user's character saying lines they never declared, which is the turn running past its
  stop point. Each is worth a rewrite while one is asked for; what stays goes in the turn report.
- **watch**: a soft warning for the turn report only: prose.py's watch list, a plain number in the narration, a name
  shaped like a model-made one, the point of view slipping, thoughts not set the house way, and a post far off the
  length the Table asks for.

The scan also reports the word count and a density read. Names the world or the record already holds are canon and
never outlawed: the caller passes them as `canon` (adventure/world/naming.py allowed_words). System panes are the
game's own text, as code writes it from the record, and are never scanned.
"""
import logging
import re
from dataclasses import dataclass, field

from adventure.narration import prose
from adventure.narration.prose import HARD, STRONG, WATCH, Finding
from adventure.rounds import house_rules
from adventure.rounds.house_rules import Rulebook
from adventure.world import naming

log = logging.getLogger(__name__)

# How many times a draft is sent back before code fixes what is left.
REWRITES = 2
ORDER = {HARD: 0, STRONG: 1, WATCH: 2}
# Words a post should have for each of the Table's lengths (adventure/narration/prompt.py LENGTHS); a post below
# half the least or over half again the most gets a warning.
WORDS = {'short': (150, 250), 'medium': (300, 500), 'long': (800, 1500)}

GAME_TERMS = (r'hp|hit points?|health points?|xp|exp|experience points?|damage|dmg|mana|mp|stamina|gold pieces?|gp|'
              r'sp|cp|dc|ac|points? of \w+|levels?|percent|%')
GAME_NUMBER = re.compile(rf'(?<![\w.])(?:[+-]?\d+(?:/\d+)?\s*(?:{GAME_TERMS})\b|[+-]\d+(?![\w.:/])|\d+\s*/\s*\d+'
                         rf'(?:\s*(?:{GAME_TERMS}))?\b|(?:{GAME_TERMS})\s*(?:of\s*)?\d+\b)', re.IGNORECASE)
NUMBER = re.compile(r'(?<![\w.:])\d+(?:[:.,]\d+)*')
# A year or a clock time is ordinary narration.
ORDINARY_NUMBER = re.compile(r'^(?:1\d{3}|20\d{2}|\d{1,2}[:.]\d{2})$')
DICE = re.compile(r'\b(?:d(?:4|6|8|10|12|20|100)|\d+d\d+|nat(?:ural)? (?:1|20|one|twenty)|saving throws?|'
                  r'(?:skill|ability|perception|stealth|insight|attack|dice|die) (?:check|roll)s?|'
                  r'roll(?:s|ed)? (?:a |an )?(?:\d+|natural|critical|high|low)|critical (?:success|failure|fail|hit)|'
                  r'success at a cost|the dice (?:said|decided|were|came|favou?red)|modifiers?)\b', re.IGNORECASE)
# A closing line that tells the reader what the scene meant, or promises the next one.
SUMMING_UP = re.compile(r"\b(?:for now|for the first time in (?:a long time|years|weeks|days)|tomorrow would|"
                        r"(?:it|this) was (?:only )?(?:just )?the beginning|whatever came next|what(?:ever)? (?:lay|lies)"
                        r" ahead|(?:a )?long night ahead|it would have to (?:do|be enough)|nothing would ever be the "
                        r"same)\b", re.IGNORECASE)
SPEECH = (r'(?:say|says|said|ask|asks|asked|tell|tells|told|reply|replies|replied|answer|answers|answered|'
          r'whisper|whispers|whispered|mutter|mutters|muttered|shout|shouts|shouted|call|calls|called|snap|snaps|'
          r'snapped|add|adds|added)')
SENTENCE = re.compile(r'[^.!?…\n]*(?:[.!?…]+["”’)]*|$)')
PANE = re.compile(r'```.*?```', re.DOTALL)
FIX_MARK = {'!': '.', ';': ',', ':': ',', '…': '...', '?': '.'}


@dataclass(frozen=True)
class Stop:
    """Where the turn stops, as code can check it: in Play, the user's character, by name, and what they declared
    this turn. A line in their mouth that is not in what they declared is the post running past their decision."""
    name: str
    declared: str


@dataclass(frozen=True)
class Scan:
    findings: tuple[Finding, ...]
    words: int
    density: dict

    @property
    def hard(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == HARD)

    @property
    def soft(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.severity != HARD)

    @property
    def clean(self) -> bool:
        return not self.hard

    def report(self) -> dict:
        """What the turn report shows of the scan."""
        return {'words': self.words, 'density': self.density,
                'findings': [{'kind': item.kind, 'severity': item.severity, 'text': item.text, 'hint': item.hint}
                             for item in self.findings]}


@dataclass(frozen=True)
class Settled:
    """A draft ready to commit: its text, the last scan (with no hard failure in it), how many rewrites it took,
    and any sentences code cut because two rewrites left a hard failure in them."""
    text: str
    scan: Scan
    rewrites: int = 0
    cut: tuple[str, ...] = field(default_factory=tuple)


# Where to look -------------------------------------------------------------------------------------

def outside_panes(text: str) -> str:
    """The prose: everything but the System panes, which are blanked out so nothing joins across one."""
    return PANE.sub('\n\n', text)


def narration_only(text: str) -> str:
    """The prose without what anyone says aloud."""
    return prose.QUOTE.sub('""', text)


def phrase_pattern(entry: str) -> re.Pattern:
    """A word or phrase as the user wrote it, matched whole and in any case; spaces match any run of space."""
    body = r'\s+'.join(re.escape(part) for part in entry.split())
    return re.compile(rf'(?<!\w){body}(?!\w)', re.IGNORECASE)


# The checks ----------------------------------------------------------------------------------------

def punctuation(text: str, book: Rulebook) -> list[Finding]:
    """Each forbidden mark. Em dashes are prose.py's own check, which knows a number range from a dash."""
    found = []
    for entry in book.punctuation:
        if entry != 'em dash':
            found += [Finding('punctuation', HARD, match[0], f'The house rules forbid "{entry}".')
                      for match in re.finditer(re.escape(entry), text)]
    return found


def outlawed(text: str, book: Rulebook) -> list[Finding]:
    found = []
    for kind, entries in (('outlawed-word', book.words), ('outlawed-phrase', book.phrases)):
        for entry in entries:
            found += [Finding(kind, HARD, match[0], 'The house rules outlaw it; say it another way.')
                      for match in phrase_pattern(entry).finditer(text)]
    return found


def names(text: str, book: Rulebook, canon: str) -> list[Finding]:
    """Outlawed names (hard) and names shaped like model-made ones (watch); canon is never either."""
    allowed = {word.casefold() for word in naming.WORD.findall(canon or '')}
    outlaw = {name.casefold() for name in book.names}
    found = []
    for word in dict.fromkeys(naming.WORD.findall(text)):
        if word.casefold() in allowed:
            continue
        if word.casefold() in outlaw:
            found.append(Finding('outlawed-name', HARD, word, 'The house rules outlaw this name; use another.'))
        elif naming.coined(word):
            found.append(Finding('coined-name', WATCH, word, 'It reads as made up; a plainer name may fit better.'))
    return found


def numbers(narration: str) -> list[Finding]:
    """Game numbers outside a pane (hard), then any other number in the narration (watch); dialogue may say one."""
    found = [Finding('game-number', HARD, match[0].strip(), 'Numbers go in a System pane; tell it in the story.')
             for match in GAME_NUMBER.finditer(narration)]
    taken = ' '.join(finding.text for finding in found)
    found += [Finding('number', WATCH, match[0], 'Ordinary narration carries no numbers.')
              for match in NUMBER.finditer(narration)
              if not ORDINARY_NUMBER.match(match[0]) and match[0] not in taken]
    return found


def dice(text: str) -> list[Finding]:
    return [Finding('dice', HARD, match[0], 'Never mention dice or rolls; the reader feels the result in the story.')
            for match in DICE.finditer(text)]


def summing_up(text: str) -> list[Finding]:
    """A last paragraph that tells the reader what the scene meant, past the scene-closers prose.py knows."""
    parts = [part for part in re.split(r'\n\s*\n', text) if part.strip()]
    if not parts:
        return []
    last = narration_only(parts[-1])
    return [Finding('summing-up', STRONG, match[0], 'End on an action, an image or a line of dialogue instead.')
            for match in SUMMING_UP.finditer(last)]


def past_stop(text: str, stop: Stop | None, pov: str) -> list[Finding]:
    """Lines the user's character speaks in the post that are not in what they declared (strong)."""
    if stop is None:
        return []
    subject = {'second': r'you', 'first': r'I'}.get(pov) or '|'.join(
        re.escape(part) for part in dict.fromkeys([stop.name, stop.name.split()[0]]) if part)
    if not subject:
        return []
    tag = re.compile(rf'(?:\b(?:{subject})\s+(?:\w+ly\s+)?{SPEECH}\b|\b{SPEECH}\s+(?:{subject})\b)')
    declared = set(prose.words(stop.declared))
    found = []
    for paragraph in re.split(r'\n\s*\n', text):
        for match in prose.QUOTE.finditer(paragraph):
            around = paragraph[max(0, match.start() - 60):match.start()] + paragraph[match.end():match.end() + 60]
            if not tag.search(around):
                continue
            content = [word for word in prose.words(match[1]) if word not in prose.STOPWORDS and len(word) > 2]
            if len(content) >= 3 and sum(word in declared for word in content) < len(content) / 2:
                found.append(Finding('past-stop', STRONG, match[1][:80],
                                     "Only the player's character's declared lines are theirs; end before their "
                                     'next decision.'))
    return found


def point_of_view(narration: str, pov: str) -> list[Finding]:
    addressed = len(re.findall(r"\byou(?:r|rs|rself|'re|'d|'ll|'ve)?\b", narration, re.IGNORECASE))
    told = len(prose.words(narration))
    if pov != 'second' and addressed >= 2:
        return [Finding('pov', WATCH, f'"you" {addressed} times in the narration',
                        f'The house rules ask for {house_rules.narration_prompt.POINTS_OF_VIEW[pov]}.')]
    if pov == 'second' and told >= 80 and not addressed:
        return [Finding('pov', WATCH, 'no "you" in the narration', 'The house rules ask for second person.')]
    return []


def thoughts(text: str, book: Rulebook) -> list[Finding]:
    italics = list(re.finditer(r"(?<![*\w])(['‘]?)\*([^*\n]+)\*(['’]?)", narration_only(text)))
    if book.thoughts == 'quoted-italics':
        wrong = [match for match in italics if not (match[1] and match[3])]
    elif book.thoughts == 'italics':
        wrong = [match for match in italics if match[1] and match[3]]
    else:
        wrong = italics
    return [Finding('thoughts', WATCH, match[0], f'Thoughts go {house_rules.THOUGHTS[book.thoughts]}.')
            for match in wrong]


def length(count: int, book: Rulebook) -> list[Finding]:
    least, most = WORDS.get(book.length, WORDS['short'])
    if count < least / 2 or count > most * 1.5:
        return [Finding('length', WATCH, f'{count} words', f'The Table asks for {least} to {most} words.')]
    return []


def density(text: str) -> dict:
    """A plain read of how the post sits on the page: how much is said aloud, sentence and paragraph lengths."""
    every = prose.words(text)
    spoken = sum(len(prose.words(line)) for line in prose.dialogue_lines(text))
    sentences = [part for part in SENTENCE.findall(text) if prose.words(part)]
    parts = [part for part in re.split(r'\n\s*\n', text) if prose.words(part)]
    sentence = len(every) / max(len(sentences), 1)
    paragraph = len(every) / max(len(parts), 1)
    read = 'dense' if sentence > 24 or paragraph > 110 else 'sparse' if paragraph < 25 else 'even'
    return {'read': read, 'dialogue': round(spoken / max(len(every), 1), 2), 'sentence': round(sentence, 1),
            'paragraph': round(paragraph, 1), 'paragraphs': len(parts)}


def scan(text: str, book: Rulebook = Rulebook(), *, canon: str = '', stop: Stop | None = None) -> Scan:
    """Every finding in a draft, hard first, with its word count and density read."""
    body = outside_panes(text)
    narration = narration_only(body)
    count = len(prose.words(body))
    # prose.py's em dash check is the house rule while the book forbids em dashes, and goes when the user lifts it.
    found = [finding for finding in prose.check(body) if finding.kind != 'em-dash' or 'em dash' in book.punctuation]
    found += punctuation(body, book)
    found += outlawed(body, book) + names(body, book, canon) + numbers(narration) + dice(body)
    found += summing_up(body) + past_stop(body, stop, book.pov) + point_of_view(narration, book.pov)
    found += thoughts(body, book) + length(count, book)
    unique = list(dict.fromkeys(found))
    return Scan(tuple(sorted(unique, key=lambda item: ORDER[item.severity])), count, density(body))


# Settling a draft ----------------------------------------------------------------------------------

def mechanical(text: str, finding: Finding) -> tuple[str, str]:
    """The fix that cannot fail, for a hard failure two rewrites left: the mark replaced, or the sentence that holds
    it cut. Returns the text and what was cut ('' for a mark)."""
    if finding.kind == 'em-dash':
        return prose.without_dashes(text), ''
    if finding.kind == 'punctuation':
        return replace_outside_panes(text, re.escape(finding.text), FIX_MARK.get(finding.text, '')), ''
    return cut_sentence(text, finding.text)


def replace_outside_panes(text: str, pattern: str, instead: str) -> str:
    return ''.join(part if part.startswith('```') else re.sub(pattern, instead, part)
                   for part in re.split(r'(```.*?```)', text, flags=re.DOTALL))


def cut_sentence(text: str, quoted: str) -> tuple[str, str]:
    """The text without the first sentence outside a pane that holds `quoted` (or, failing that, without `quoted`
    itself, so a cut always takes it out), and what was cut."""
    pattern = phrase_pattern(quoted)
    parts = re.split(r'(```.*?```)', text, flags=re.DOTALL)
    for index, part in enumerate(parts):
        if part.startswith('```') or not pattern.search(part):
            continue
        sentence = next((item for item in SENTENCE.findall(part) if pattern.search(item)), '')
        parts[index] = tidy(part.replace(sentence, '', 1) if sentence else pattern.sub('', part, count=1))
        return ''.join(parts), (sentence or quoted).strip()
    return text, ''


def tidy(text: str) -> str:
    """Prose after a cut: no doubled spaces, no space opening or closing a line, no more than one blank line. The
    line breaks at either end stay, so a pane next to it stays on its own lines."""
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'(?m)^[ \t]+|[ \t]+$', '', text)
    return re.sub(r'\n{3,}', '\n\n', text)


def weight(found: Scan) -> tuple[int, int]:
    return len(found.hard), sum(item.severity == STRONG for item in found.findings)


def wants_rewrite(found: Scan, rewrites: int) -> bool:
    """A rewrite is asked while a hard failure is left; a strong tell is worth only the first."""
    return rewrites < REWRITES and (bool(found.hard) or (rewrites == 0 and weight(found)[1] > 0))


def rewrite_system(book: Rulebook) -> str:
    return f'{prose.REWRITE}\n\n{house_rules.text(book, scope=False)}'


async def settle(text: str, book: Rulebook = Rulebook(), rewrite=None, *, canon: str = '',
                 stop: Stop | None = None) -> Settled:
    """The draft ready to commit, never with a hard failure in it.

    `rewrite(system, messages)` returns a model's reply, or is None when no rewrite can run (no model, no time).
    A rewrite is asked while the draft has a hard failure, or (the first time only) a strong tell, and kept only when
    it is about as long (prose.acceptable) and leaves less wrong (weight). Whatever hard failure is left, code fixes.
    """
    found, rewrites = scan(text, book, canon=canon, stop=stop), 0
    while rewrite is not None and wants_rewrite(found, rewrites):
        rewrites += 1
        try:
            revised = (await rewrite(rewrite_system(book), prose.rewrite_request(text, list(found.findings)))).strip()
        except Exception as error:  # noqa: BLE001 - the draft stands and code fixes it; a rewrite never loses a turn
            log.warning('The draft rewrite failed: %s', error)
            break
        after = scan(revised, book, canon=canon, stop=stop) if prose.acceptable(text, revised) else None
        if after is not None and weight(after) < weight(found):
            text, found = revised, after
    return by_hand(text, found, book, rewrites, canon, stop)


def by_hand(text: str, found: Scan, book: Rulebook, rewrites: int, canon: str, stop: Stop | None) -> Settled:
    """Code's own fixes for the hard failures left, one at a time until none is left."""
    cut = []
    while not found.clean:
        fixed, taken = mechanical(text, found.hard[0])
        if fixed == text:  # nothing matched where the scan found it: drop the found text wherever it is
            fixed, taken = text.replace(found.hard[0].text, '', 1), found.hard[0].text
        if fixed == text:
            log.warning('The scan found "%s" but code could not take it out.', found.hard[0].text)
            break
        cut += [taken] if taken else []
        text, found = fixed, scan(fixed, book, canon=canon, stop=stop)
    if cut:
        log.info('Cut from the draft for the house rules: %s', '; '.join(cut))
    return Settled(text.strip() if cut else text, found, rewrites, tuple(cut))
