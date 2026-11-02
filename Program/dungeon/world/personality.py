"""Personality sliders: five traits every character and townsperson has, each low, in between or high (v0.11).

The app rolls them from a seed, so people around town differ from each other and stay the same from one day to
the next ("the world exists outside of User"). Nothing asks the user to choose; they can change any slider later.

- Each slider remembers where its level came from: `rolled` (the seed; "Roll again" changes it), `idea` (the
  character's own words settle it: "shy", "kind", "always late"; Roll again leaves it) or `you` (the user moved it;
  it stays put until they hand it back to the roll).
- At least two traits land away from the middle, so nobody comes out beige.
- The model only ever reads behaviour ("talks first, fills silences"), never a trait name, and a slider in the
  middle sends nothing (`behaviour`).
- Perception picks (dungeon/world/perception.py: temperament, habit, flaw, self-story) that clash with a slider
  are not drawn (`fits`), so an organized person does not get "always late" as their habit.
- Townsfolk read the levels their sheet's temperament and flaw already say, and roll the rest (`for_sheet`); an
  edit the user made on their profile (table townsfolk_personality) wins.

Tested in the prompt-tweaks run (Test 3 in /mnt/project-files/companion-prompt-tweaks/report.md): a rolled
personality made drafts less stereotyped and more varied, once the user's own words win and the perception picks
fit. The words are data (world/data/personality.json). No model is involved.
"""
import json
import re
from functools import cache

from dungeon.world import catalog, generators

LEVELS = (0, 1, 2)
MIDDLE = 1
SOURCES = ('rolled', 'idea', 'you')
LEAST_AWAY = 2
# Words right before a keyword that turn it around: "not shy", "never late".
NEGATIONS = {'not', 'never', 'no', "isn't", "wasn't", "aren't", 'hardly', 'rarely', 'less', 'barely', 'nor'}
# The sheet fields whose words can settle a slider; the background tells of other people as often as of them.
IDEA_FIELDS = ('identity', 'personality', 'voice')
# The type shortcut's letters: which slider each sets, and which letter means high.
TYPE_LETTERS = (('social', 'E', 'I'), ('curiosity', 'N', 'S'), ('warmth', 'F', 'T'), ('order', 'J', 'P'))


@cache
def bank() -> dict:
    return json.loads((catalog.DATA / 'personality.json').read_text(encoding='utf-8'))


def traits() -> list[dict]:
    return bank()['traits']


def keys() -> tuple[str, ...]:
    return tuple(trait['key'] for trait in traits())


def level_name(level: int) -> str:
    return 'low' if level == 0 else 'high' if level == 2 else 'middle'


# Reading words ----------------------------------------------------------------------------------------

def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:['’-][a-z0-9]+)*", text.casefold().replace('’', "'"))


def said(words: list[str], phrase: str) -> bool:
    """Whether the phrase appears as whole words and isn't turned around ("not shy") or a figure of speech ("kind
    of", "the quiet of the morning")."""
    wanted = tokens(phrase)
    size = len(wanted)
    for start in range(len(words) - size + 1):
        if words[start:start + size] != wanted:
            continue
        before = words[max(0, start - 2):start]
        after = words[start + size] if start + size < len(words) else ''
        if not NEGATIONS.intersection(before) and after != 'of':
            return True
    return False


def from_words(text: str) -> dict[str, int]:
    """The levels the text settles: a pole's words alone set it; words for both poles mean in between."""
    words = tokens(text)
    found = {}
    for trait in traits():
        low = any(said(words, word) for word in trait['keywords']['low'])
        high = any(said(words, word) for word in trait['keywords']['high'])
        if low or high:
            found[trait['key']] = MIDDLE if low and high else 2 if high else 0
    return found


def idea_text(definition: dict) -> str:
    return ' '.join([*(str(definition.get(key) or '') for key in IDEA_FIELDS), *(definition.get('flaws') or [])])


# Rolling ------------------------------------------------------------------------------------------------

def roll(seed: str, fixed: dict[str, int]) -> dict[str, int]:
    """Levels for every trait not in `fixed`, by seed, with at least two traits away from the middle overall."""
    levels = dict(fixed)
    free = [key for key in keys() if key not in fixed]
    for key in free:
        levels[key] = min(2, int(generators.unit(seed, f'personality-{key}') * 3))
    away = sum(level != MIDDLE for level in levels.values())
    for key in sorted(free, key=lambda key: generators.unit(seed, f'personality-push-{key}')):
        if away >= LEAST_AWAY:
            break
        if levels[key] == MIDDLE:
            levels[key] = 2 if generators.unit(seed, f'personality-side-{key}') < 0.5 else 0
            away += 1
    return levels


def slider(level: int, source: str) -> dict:
    return {'level': level, 'source': source}


def clean(raw) -> dict[str, dict]:
    """Stored sliders that are well formed; anything else is dropped and filled in again."""
    if not isinstance(raw, dict):
        return {}
    return {key: slider(value['level'], value.get('source', 'rolled')) for key, value in raw.items()
            if key in keys() and isinstance(value, dict) and value.get('level') in LEVELS
            and value.get('source', 'rolled') in SOURCES}


def kept(stored: dict, words: dict[str, int], key: str) -> dict | None:
    """A trait's slider when something already decides it: the user's own setting, then the sheet's words, then
    an earlier roll or idea. Words that agree with a roll leave it Rolled; words that differ win."""
    found = stored.get(key)
    if found and found['source'] == 'you':
        return found
    if key in words and not (found and found['source'] == 'rolled' and found['level'] == words[key]):
        return slider(words[key], 'idea')
    return found


def settle(definition: dict, seed: str, words: dict[str, int] | None = None) -> dict[str, dict]:
    """Every trait's slider for a character: what the sheet stores, what its words settle (`words` overrides
    reading them, for the quick start's idea), and the rest rolled by seed. The same sheet and seed always give the
    same sliders, so a character saved before sliders existed gets the same ones every time they are read."""
    stored = clean(definition.get('personality_sliders'))
    found = from_words(idea_text(definition)) if words is None else words
    result = {key: value for key in keys() if (value := kept(stored, found, key))}
    rolled = roll(seed, {key: value['level'] for key, value in result.items()})
    return {key: result.get(key) or slider(rolled[key], 'rolled') for key in keys()}


def reroll(sliders: dict, seed: str) -> dict[str, dict]:
    """Roll again: only the Rolled sliders change."""
    current = clean(sliders)
    fixed = {key: value['level'] for key, value in current.items() if value['source'] != 'rolled'}
    rolled = roll(seed, fixed)
    return {key: current[key] if key in fixed else slider(rolled[key], 'rolled') for key in keys()}


def levels_of(sliders: dict) -> dict[str, int]:
    return {key: value['level'] for key, value in clean(sliders).items()}


# Types ----------------------------------------------------------------------------------------------------

def from_type(code: str, sliders: dict) -> dict[str, dict]:
    """A four-letter type sets four sliders as the user's own; How they handle stress and anything the idea
    settles stay. Codes only, no brand names."""
    code = code.strip().upper()
    if len(code) != 4 or any(letter not in (high, low) for letter, (_key, high, low) in zip(code, TYPE_LETTERS)):
        raise ValueError(f'{code or "That"} is not a four-letter type.')
    current = clean(sliders)
    for letter, (key, high, _low) in zip(code, TYPE_LETTERS):
        if (current.get(key) or {}).get('source') != 'idea':
            current[key] = slider(2 if letter == high else 0, 'you')
    return current


def type_of(levels: dict[str, int]) -> str | None:
    """The four-letter type the sliders read as, when none of those four sits in the middle."""
    if any(levels.get(key, MIDDLE) == MIDDLE for key, _high, _low in TYPE_LETTERS):
        return None
    return ''.join(high if levels[key] == 2 else low for key, high, low in TYPE_LETTERS)


# What people see and what the model reads ----------------------------------------------------------------

def label(trait: dict, level: int) -> str:
    return trait['low'] if level == 0 else trait['high'] if level == 2 else 'In between'


def chips(levels: dict[str, int]) -> list[str]:
    """The summary: the pole words of every trait away from the middle."""
    return [label(trait, levels[trait['key']]) for trait in traits() if levels.get(trait['key'], MIDDLE) != MIDDLE]


def behaviour(levels: dict[str, int]) -> list[str]:
    """What the model reads: one line of behaviour per trait away from the middle, never a trait name."""
    return [trait['model'][levels[trait['key']]] for trait in traits()
            if levels.get(trait['key'], MIDDLE) != MIDDLE and trait['model'][levels[trait['key']]]]


def form_traits() -> list[dict]:
    """What the form shows for each slider: its name, the words at each end and what each stop looks like."""
    return [{field: trait[field] for field in ('key', 'name', 'low', 'high', 'shows')} for trait in traits()]


def view(sliders: dict) -> dict:
    """The sliders as the form and the profiles show them."""
    levels = levels_of(sliders)
    return {'sliders': clean(sliders), 'chips': chips(levels), 'type': type_of(levels)}


# Fitting perception picks ---------------------------------------------------------------------------------

def implied(facet: str, entry_id: str) -> dict[str, str]:
    """The slider poles a perception bank entry speaks to ({'order': 'high'} for "makes lists")."""
    return bank()['implies'].get(facet, {}).get(entry_id, {})


def fits(facet: str, entry_id: str, levels: dict[str, int] | None) -> bool:
    """Whether the entry suits the sliders: it may not speak to the opposite pole of a trait away from the middle."""
    if not levels:
        return True
    for key, pole in implied(facet, entry_id).items():
        level = levels.get(key, MIDDLE)
        if level != MIDDLE and pole != level_name(level):
            return False
    return True


def fitting(facet: str, options: list[str], levels: dict[str, int] | None) -> list[str]:
    """The options that suit the sliders, or all of them if none would."""
    found = [option for option in options if fits(facet, option, levels)]
    return found or options


# Townsfolk ------------------------------------------------------------------------------------------------

def sheet_words(sheet: dict) -> dict[str, int]:
    """The levels a townsperson's temperament and flaw already say; where they disagree, in between."""
    found: dict[str, set[str]] = {}
    for facet in ('temperament', 'flaw'):
        for key, pole in implied(facet, sheet.get(facet) or '').items():
            found.setdefault(key, set()).add(pole)
    return {key: MIDDLE if len(poles) > 1 else 2 if 'high' in poles else 0 for key, poles in found.items()}


def for_sheet(seed: str, sheet: dict, edited: dict | None = None) -> dict[str, dict]:
    """A townsperson's sliders: the user's edits on their profile, then what their sheet says, then rolled. All of
    them read as Rolled to the user: the app picked them either way."""
    fixed = {**sheet_words(sheet), **levels_of(edited or {})}
    rolled = roll(seed, fixed)
    mine = clean(edited or {})
    return {key: mine.get(key) or slider(rolled[key], 'rolled') for key in keys()}
