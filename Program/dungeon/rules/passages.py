"""Rule passages (requirements "Rule passages"): the few lines of rule text that fit what just happened, for the
narrator.

Code has already decided every result. A passage only helps the narrator describe one the way the ruleset means it:
a weak hit's troublesome cost, what Grappled stops a creature doing. The prompt layer says so, and the results above
it stay fixed.

- **Which text.** Ironsworn: the move rolled, its trigger and the outcome it landed on (strong hit, weak hit, miss).
  5E (SRD 5.2): the skill or spell rolled, any condition the fight lines name, and the gameplay toolbox's sections.
  Percentile (BRP): the spell cast (the pack's skills carry no text, and a major wound's text is already in the fight
  lines). Prospero, Fate and Narrative Only have no rule text in a pack, so they get none.
- **How it is picked.** By what the turn resolved first: each roll's label starts with the move, skill or spell it
  rolled. Only when nothing matched does the player's line pick, by a toolbox section or condition named in it as a
  whole word. No model, no embeddings.
- **Small.** At most MOST passages and MOST_WORDS words a turn, and no one passage more than PASSAGE_WORDS; a
  compact model (dungeon/narration/prompt.py COMPACT_BELOW_TOKENS) gets COMPACT_MOST and COMPACT_WORDS. Each passage
  is cut to its first sentences that fit.
- **Indexed once** per ruleset, when first asked for.
- The Table's `rule_text` ("Give the narrator rule text", on by default) turns it off.

The text is the packs' own licensed content, under the notices they already carry (packs/*/README.md).
"""
import re
from functools import cache

from dungeon.narration.prompt import COMPACT_BELOW_TOKENS
from dungeon.rules import brp, ironsworn, srd52

MOST, MOST_WORDS = 3, 250
COMPACT_MOST, COMPACT_WORDS = 1, 100
# No one passage takes more than this, so a long toolbox section leaves room for the rest.
PASSAGE_WORDS = 120
# A passage cut shorter than this is left out rather than sent as a stub.
LEAST_WORDS = 12
HEAD = ('## Rules that apply\nHow the rules describe what happened. The results above are fixed; use this only to '
        'describe them.')
# The Ironsworn outcome each band of the shared ladder is.
OUTCOMES = {'critical_success': 'strong_hit', 'success': 'strong_hit', 'success_cost': 'weak_hit',
            'failure': 'miss', 'critical_failure': 'miss'}
SENTENCE = re.compile(r'(?<=[.!?])\s+')


def flat(text: str) -> str:
    """One paragraph: list marks, emphasis and line breaks gone."""
    return re.sub(r'\s+', ' ', ironsworn.plain(text)).strip()


@cache
def index(ruleset: str) -> dict:
    """The ruleset's passages: `named` (looked up by what a roll resolved) and `spoken` (found in the player's line),
    each {name, text, outcomes?}; `conditions` by lower-case name."""
    named, spoken, conditions = [], [], {}
    if ruleset == ironsworn.ID:
        for move in ironsworn.moves().values():
            named.append({'name': move['name'], 'text': flat(move['trigger']['text']),
                          'outcomes': {key: flat(value['text']) for key, value in (move.get('outcomes') or {}).items()}})
    elif ruleset == srd52.ID:
        rules = srd52.pack('rules')
        named += [{'name': skill['name'], 'text': skill['example_uses']}
                  for skill in rules['skills']]
        named += [{'name': spell['name'], 'text': flat(spell['description'])} for spell in srd52.pack('spells')]
        for condition in rules['conditions']:
            conditions[condition['name'].lower()] = {'name': condition['name'], 'text': flat(condition['description'])}
        spoken += [{'name': section['title'], 'text': flat(section['text'])}
                   for section in sections(rules['gameplay_toolbox']['sections']) if section.get('text')]
        spoken += list(conditions.values())
    elif ruleset == brp.ID:
        named += [{'name': spell['name'], 'text': spell['summary']}
                  for spell in brp.spells().values()]
    # The longest name first, so "Secure an Advantage" is found before a shorter name it starts with.
    named.sort(key=lambda passage: -len(passage['name']))
    return {'named': named, 'spoken': spoken, 'conditions': conditions}


def sections(items: list[dict]) -> list[dict]:
    """A toolbox's sections and the sections inside them."""
    return [found for item in items for found in (item, *sections(item.get('sections') or []))]


def by_roll(found: dict, row: dict) -> dict | None:
    """The passage a roll's label names ("Face Danger +edge vs 3 and 7", "Stealth", "Fire Bolt (spell)")."""
    label = (row.get('skill') or '').lower()
    passage = next((passage for passage in found['named'] if label.startswith(passage['name'].lower())
                    and not label[len(passage['name']):][:1].isalpha()), None)
    if passage is None:
        return None
    outcome = (passage.get('outcomes') or {}).get(OUTCOMES.get(row.get('band'), ''))
    return {'name': passage['name'], 'text': f"{passage['text']} {outcome}" if outcome else passage['text']}


def whole_word(name: str, text: str) -> bool:
    return re.search(rf'\b{re.escape(name.lower())}\b', text.lower()) is not None


def chosen(ruleset: str, rolls: list[dict], line: str, fought: list[str]) -> list[dict]:
    """The passages for this turn, most fitting first: the rolls', then the conditions the fight lines name, then (only
    when nothing matched) the sections and conditions the player's line names."""
    found = index(ruleset)
    picked = [passage for row in rolls if row.get('ruleset') == ruleset and (passage := by_roll(found, row))]
    said = ' '.join(fought)
    picked += [passage for name, passage in found['conditions'].items() if whole_word(name, said)]
    if not picked:
        picked = [passage for passage in found['spoken']
                  if whole_word(passage['name'], line) or whole_word(passage['name'].rstrip('s'), line)]
    unique = {}
    for passage in picked:
        unique.setdefault(passage['name'], passage)
    return list(unique.values())


def cut(text: str, words: int) -> str:
    """The first sentences of `text` that fit in `words`; a first sentence too long is cut short."""
    kept, used = [], 0
    for sentence in SENTENCE.split(text):
        size = len(sentence.split())
        if used + size > words:
            if not kept:
                kept.append(' '.join(sentence.split()[:words]) + '…')
            break
        kept.append(sentence)
        used += size
    return ' '.join(kept)


def text(ruleset: str, rolls: list[dict], line: str, fought: list[str], context_tokens: int | None = None,
         on: bool = True) -> str:
    """The `## Rules that apply` layer, or '' when it is off or nothing applies."""
    if not on:
        return ''
    compact = bool(context_tokens) and context_tokens < COMPACT_BELOW_TOKENS
    most, left = (COMPACT_MOST, COMPACT_WORDS) if compact else (MOST, MOST_WORDS)
    lines = []
    for passage in chosen(ruleset, rolls, line, fought)[:most]:
        room = min(PASSAGE_WORDS, left) - len(passage['name'].split())
        if room < LEAST_WORDS:
            break
        said = cut(passage['text'], room)
        lines.append(f"- {passage['name']}: {said}")
        left -= len(passage['name'].split()) + len(said.split())
    return '\n'.join([HEAD, *lines]) if lines else ''
