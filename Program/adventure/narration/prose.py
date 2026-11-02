"""Checks on what the narrator wrote, run before the player sees it (requirements: "Narrator prompting").

The prompt asks the model to follow Vanta's writing rules; this module checks the ones code can see. Each
finding has a severity:

- 'hard': em dashes in any form. Always fixed: the rewrite pass first, then a mechanical fix that cannot
  fail, so a dash never reaches the page.
- 'strong': the hard dialogue rules (echoes, reported speech, ping-pong dialogue) and the tells the
  blocklist marks as strongest (scene-closers, stock intimacy phrases, thinking tics, performed emotion,
  emotional shorthand, filler, unambiguous AI vocabulary). Any of these asks the model for one rewrite.
- 'watch': words with ordinary literal uses in a game world (a merchant's ledger, a landscape, a tapestry
  on a wall) and the structural patterns ("scrutinize, don't ban"). Logged, never rewritten.

Game windows in code blocks are left alone: they are the game's own text.
"""
import logging
import re
from collections import Counter
from dataclasses import dataclass

log = logging.getLogger(__name__)

HARD, STRONG, WATCH = 'hard', 'strong', 'watch'
PRONOUN = r"(?:he|she|they|i|you|we|his|her|their|my|your|our|him|them|me|us)"
POSSESSIVE = r'(?:his|her|their|my|your|our)'


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    text: str
    hint: str


def _rule(kind: str, severity: str, hint: str, *patterns: str):
    return kind, severity, hint, re.compile(r'\b(?:' + '|'.join(patterns) + r')\b', re.IGNORECASE)


RULES = (
    _rule('scene-closer', STRONG, 'End on an action, an image or a line of dialogue instead.',
          r'and somehow (?:that|it) was enough', r'and that was all that mattered', r'and in that moment',
          rf'in that moment,? {PRONOUN} (?:understood|realized|realised|knew)', r'and for the first time',
          r'and just like that', r'everything else faded', r'the rest of the world (?:fell away|faded|disappeared)',
          rf'and {PRONOUN} realized that', r'as though the world'),
    _rule('stock-intimacy', STRONG, 'Write what this person actually does, or name the feeling.',
          rf'shivers? (?:\w+ )?down {POSSESSIVE} (?:spine|back)', r'breath (?:hitched|hitching|hitches)',
          rf'{POSSESSIVE} breath (?:caught|catching|catches)', r'breath caught in',
          r'electricity (?:coursing|coursed|courses)', r'pulse (?:quickened|quickening|quickens)',
          r'heat (?:pooled|pooling|pools)', r'stomach (?:flipped|flipping|flips|did a flip)',
          r'blood (?:sang|singing)', rf'made {POSSESSIVE} blood sing'),
    _rule('thinking-tic', STRONG, 'Show the thought or the reaction instead of filing it.',
          rf'clocked (?:it|that|this|the|him|her|them|how|{POSSESSIVE})', r'filed (?:it|that|this|the \w+) away',
          r'logged (?:it|that|this)', rf'catalogu?ed (?:it|that|the|every|{POSSESSIVE})',
          rf'(?:{PRONOUN}) noted', r'registered (?:the|his|her|their) (?:hurt|pain|shock|anger|fear|surprise|words)'),
    _rule('shorthand', STRONG, 'Name the feeling plainly.',
          r'a mix(?:ture)? of \w+ and \w+', r'(?:something|somewhere) between \w+ and \w+', r"couldn'?t quite name",
          r"didn'?t have (?:a|the) words? for", r"couldn'?t put (?:it )?into words"),
    _rule('performed-emotion', STRONG, "Write what this person's smile or laugh actually looks like.",
          r'a real (?:smile|laugh)', r'a genuine (?:smile|laugh)', r'laughed a real laugh', r'smiled for real',
          rf"(?:smile|grin) (?:that )?(?:reached|didn'?t reach|did not reach) {POSSESSIVE} eyes",
          r'the first honest thing', r'something unguarded'),
    _rule('filler', STRONG, 'Cut the frame and say the thing.',
          r'there was something about', r'(?:some )?part of (?:him|her|them|me) knew', r'the truth was',
          r'the reality was', rf'if {PRONOUN} (?:was|were) being honest', r"it wasn'?t just \w+,? it was"),
    _rule('reported-speech', STRONG, 'Quote the words that were said.',
          r'(?:said|told \w+|explained|admitted|insisted) that', r'asked (?:\w+ )?(?:if|whether)'),
    _rule('ai-word', STRONG, 'Use the plain word.',
          r'paradigm', r'multifaceted', r'nuanced', r'plethora', r'myriad', r'juxtaposition', r'dichotomy',
          r'epitome', r'palpable', r'fundamentally', r'inherently', r'irrevocably', r'paramount',
          r'facilitat\w*', r'leverag(?:e|ed|es|ing)', r'testament to', r'delv(?:e|ed|es|ing) into (?:the )?(?:depths|complexit\w*|nuances?|mysteries)'),
    _rule('watch-word', WATCH, 'Fine when literal; otherwise use the plain word.',
          r'ledger', r'pivotal', r'tapestry', r'landscape', r'resonat\w*', r'foster\w*', r'trajectory', r'catalyst',
          r'culminat\w*', r'underscor\w*', r'bolster\w*', r'navigat\w*', r'architecture', r'arithmetic',
          r'tangible', r'visceral', r'profound\w*', r'utterly', r'realm', r'robust', r'seamless\w*', r'holistic',
          r'it felt like', r'it was as if', r'has opinions', r'heart (?:hammered|hammering)',
          r'(?:processed|computed|calculated) (?:the|his|her|their|it)'),
)

# Em dashes in every form: the character itself, the horizontal bar, a double hyphen, and a hyphen or en dash
# standing between spaces. An en dash inside a number range (3–4) is not a dash in the prose.
DASH = re.compile(r'[—―]|(?<!-)--(?!-)|(?<=\S) [-–] (?=\S)|(?<=[^\d\s])–|–(?=[^\d\s])')
FENCE = re.compile(r'(```.*?```)', re.DOTALL)
QUOTE = re.compile(r'["“]([^"”]+)["”]')
WORD = re.compile(r"[a-z']+")
STOPWORDS = frozenset(
    "a an the and or but if of to in on at by for with from as is was were be been are it its it's he she they "
    "him her them his their i me my you your we us our that this then than there here not no so do did does "
    "had has have what who when where which while into out up down over just like one all would could "
    "don't didn't can't won't i'm you're know want think mean get got go going come yeah okay well oh now right "
    "really about how why said says asked asks".split())


def prose_parts(text: str) -> list[str]:
    """The text outside code blocks (game windows)."""
    return [part for part in FENCE.split(text) if not part.startswith('```')]


def dialogue_lines(text: str) -> list[str]:
    return [match[1] for match in QUOTE.finditer(text)]


def words(text: str) -> list[str]:
    return WORD.findall(text.lower().replace('’', "'").replace("it's", 'it is'))


def phrases(line: list[str]) -> set[tuple]:
    """The runs of words an echo would share: any four in a row, or three with at least two that carry meaning."""
    fours = {tuple(line[index:index + 4]) for index in range(len(line) - 3)}
    threes = {gram for index in range(len(line) - 2)
              if sum((gram := tuple(line[index:index + 3]))[place] not in STOPWORDS for place in range(3)) >= 2}
    return fours | threes


def echoes(text: str) -> list[Finding]:
    """A line of dialogue that repeats a phrase from the paragraph before, which is usually the other speaker.

    Lines of three words or fewer are left alone: greetings and ritual repeats ("Amen." "Amen.") are allowed.
    """
    found, before = [], []
    for paragraph in re.split(r'\n\s*\n', text):
        lines = [words(line.replace("'s ", ' is ')) for line in dialogue_lines(paragraph)]
        lines = [line for line in lines if len(line) > 3]
        earlier = set().union(*map(phrases, before)) if before else set()
        for line in lines:
            if shared := sorted(phrases(line) & earlier, key=len, reverse=True):
                found.append(Finding('echo', STRONG, ' '.join(shared[0]),
                                     'Answer with new content, a question, an action or silence.'))
                break
        before = lines or before
    return found


def ping_pong(text: str) -> list[Finding]:
    """More than four paragraphs in a row that are nothing but a quoted line."""
    run, longest = 0, 0
    for paragraph in (part.strip() for part in re.split(r'\n\s*\n', text)):
        bare = paragraph and not QUOTE.sub('', paragraph).strip(' \t\n.,!?…')
        run = run + 1 if bare else 0
        longest = max(longest, run)
    if longest > 4:
        return [Finding('ping-pong', STRONG, f'{longest} bare lines of dialogue in a row',
                        'Add an action beat or a tag at least every three lines.')]
    return []


def echo_chamber(text: str) -> list[Finding]:
    """The same content word three or more times within about 200 words, names aside."""
    names = {word.lower() for word in re.findall(r"(?<![.!?\"“]\s)(?<!^)\b[A-Z][a-z']+", text)}
    tokens = [word for word in words(text) if word not in names]
    found, seen = [], set()
    for start in range(0, max(len(tokens) - 1, 1), 50):
        counts = Counter(word for word in tokens[start:start + 200] if word not in STOPWORDS and len(word) > 3)
        for word, count in counts.items():
            if count >= 3 and word not in seen:
                seen.add(word)
                found.append(Finding('echo-chamber', WATCH, word, 'Vary or cut the repeated word.'))
    return found


def punctuation_collapse(text: str) -> list[Finding]:
    """About 500 words without a semicolon, colon, ellipsis or question mark."""
    tokens = text.split()
    for start in range(0, max(len(tokens) - 499, 0), 100):
        if not re.search(r'[;:?…]|\.\.\.', ' '.join(tokens[start:start + 500])):
            return [Finding('punctuation-collapse', WATCH, 'a 500-word stretch', 'Use the whole range of punctuation.')]
    return []


def unasked(text: str) -> list[Finding]:
    """A scene with dialogue and not one question asked aloud."""
    lines = dialogue_lines(text)
    if len(lines) >= 4 and not any('?' in line for line in lines):
        return [Finding('no-question', WATCH, f'{len(lines)} lines of dialogue', 'Let someone ask something.')]
    return []


def check(text: str) -> list[Finding]:
    """Every finding in a narration, in order of severity."""
    prose = '\n\n'.join(prose_parts(text))
    found = [Finding('em-dash', HARD, match[0], 'Use a comma, semicolon, colon, period or ellipsis.')
             for match in DASH.finditer(prose)]
    # Phrases are the narrator's habits: inside quotes they are a character's own voice, and stay.
    narration = QUOTE.sub('""', prose)
    for kind, severity, hint, pattern in RULES:
        found += [Finding(kind, severity, match[0], hint) for match in pattern.finditer(narration)]
    found += echoes(prose) + ping_pong(prose)
    found += echo_chamber(prose) + punctuation_collapse(prose) + unasked(prose)
    order = {HARD: 0, STRONG: 1, WATCH: 2}
    return sorted(found, key=lambda finding: order[finding.severity])


def needs_rewrite(findings: list[Finding]) -> bool:
    return any(finding.severity in (HARD, STRONG) for finding in findings)


def without_dashes(text: str) -> str:
    """The mechanical fix: every dash becomes the punctuation that usually does its job; code blocks untouched."""
    def fix(part: str) -> str:
        if part.startswith('```'):
            return part
        part = re.sub(r'\s*(?:[—―]|--|–)\s*(?=["”’])', '...', part)  # a line cut off mid-word
        part = re.sub(r'^(\s*)(?:[—―]|--|–)\s*', r'\1', part, flags=re.MULTILINE)  # a dash opening a line
        part = re.sub(r'\s*(?:[—―]|(?<!-)--)[ \t]*$', '...', part, flags=re.MULTILINE)  # a thought trailing off
        part = re.sub(r'\s*(?:[—―]|(?<!-)--(?!-))\s*', ', ', part)
        part = re.sub(r'(?<=\S) [-–] (?=\S)', ', ', part)
        part = re.sub(r'(?<=[^\d\s])–|–(?=[^\d\s])', ', ', part)
        part = re.sub(r',\s*([,.;:!?…])', r'\1', part)
        return re.sub(r'([.!?…])\s*,\s*', r'\1 ', part)
    return ''.join(fix(part) for part in FENCE.split(text))


REWRITE = """You are revising one turn of a roleplaying game's narration. Keep every event, outcome, name, \
fact and line of meaning exactly as it is; change only the wording the notes point at. Keep the point of view, \
tense, paragraphing and length. Never use em dashes or double hyphens. Reply with the revised narration only, \
with no comments before or after it."""


def rewrite_request(text: str, findings: list[Finding]) -> list[dict]:
    notes = [f'- {finding.kind}: "{finding.text}". {finding.hint}' for finding in findings
             if finding.severity in (HARD, STRONG)]
    return [{'role': 'user', 'content': 'Narration:\n\n' + text + '\n\nFix these:\n' + '\n'.join(dict.fromkeys(notes))}]


def acceptable(draft: str, revised: str) -> bool:
    """A rewrite is used only if it kept roughly the same length: a model that summarized or ran on is ignored."""
    return bool(revised) and 0.6 <= len(revised) / max(len(draft), 1) <= 1.5


async def polish(text: str, rewrite=None) -> tuple[str, list[Finding]]:
    """The narration ready for the page, and what is still flagged in it.

    `rewrite(system, messages)` returns a model's reply, or is None when the rewrite pass is off (no model, or
    the player skipped it for speed). Either way em dashes are removed.
    """
    findings = check(text)
    if rewrite is not None and needs_rewrite(findings):
        try:
            revised = (await rewrite(REWRITE, rewrite_request(text, findings))).strip()
        except Exception as error:  # noqa: BLE001 - the draft stands; a failed polish never loses a turn
            log.warning('The narration rewrite failed: %s', error)
            revised = ''
        if acceptable(text, revised):
            after = check(revised)
            if sum(f.severity != WATCH for f in after) < sum(f.severity != WATCH for f in findings):
                text, findings = revised, after
    if any(finding.severity == HARD for finding in findings):
        text = without_dashes(text)
        findings = check(text)
    if findings:
        log.info('Narration findings: %s', '; '.join(f'{f.severity} {f.kind} "{f.text}"' for f in findings))
    return text, findings
