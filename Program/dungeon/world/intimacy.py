"""The adult side of life (Settings > Realism > Adult side of life, off by default): who someone is drawn to,
how adventurous they are, their drive and a few things they're into, rolled from their seed like the rest of
their sheet. Only ever for adults, and the bank (world/data/intimacy.json) only holds things between
consenting adults.

- Townsfolk: nothing is stored. Their orientation is the roll their partner details use (world/dating.py), so
  the two always agree. Companions who meet them learn their orientation once they
  know their heart (dungeon/life/encounters.py); the rest stays theirs.
- Companions: the same roll by companion id (or by their townsperson's seed when they came from town), with
  anything the user set on the form (`definition['intimacy']`) winning field by field. A romance companion
  has no rolled orientation: they are drawn to the user.
- It only ever goes in the person's own chat prompt (dungeon/memory/context.py), as private lines. Never
  in picture prompts, the town paper, the feed or what other people see.

Nobody under 18 ever gets it: every roll checks the age itself, and a companion whose sheet reads as younger
than 18 gets nothing. No model is involved.
"""
import json
import re
from functools import cache

from dungeon.database import settings
from dungeon.world import catalog, dating, generators, mix

ADULT_AT = 18
# How many interests each level draws, and the boldest tier it reaches.
DRAWS = {'reserved': (0, 0), 'conventional': (1, 1), 'curious': (2, 2), 'adventurous': (3, 3), 'wild': (4, 3)}
DRIVES = {'low': 1, 'average': 2, 'high': 1}
# Who someone is drawn to rather than what they do ("a sharp mind"): rolled on its own, after the draw above, so
# adding them changed nobody's earlier picks, and how adventurous someone is has no say in it.
QUALITIES = 'qualities'
DRAWN_BY = 0.4
# A companion whose own words say they're under 18 never gets an adult side (fail closed). Background is left
# out: "as a teen" there is a memory, not their age now.
YOUNG = r'(?:1[0-7]|[1-9]|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen)'
# Their age said outright: "17-year-old", "aged 17", "Mia is 17 and", "she's 17,", "I'm 17".
STATED_YOUNG = (rf"\b(?:{YOUNG}[- ](?:years?[- ]old|y/?o)\b|{YOUNG} y\.o\.|aged? {YOUNG}\b)|"
                rf"(?:\b(?:is|am)\s+|['’](?:s|m)\s+){YOUNG}\b(?=\s*(?:and\b|but\b|[,.;!()–—]|$|years|y/?o))")
MINOR = re.compile(rf"(?:{STATED_YOUNG})|\b(?:teen(?:age[dr]?|s)?\b|"
                   r"minor\b|under-?age|high[- ]school(?:er|\s+student)|middle[- ]school|school ?(?:girl|boy)\b|"
                   r"\bin (?:the )?(?:(?:[1-9]|1[0-2])(?:st|nd|rd|th)|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth) grade|"
                   r"(?:[1-9]|1[0-2])(?:st|nd|rd|th) grader|(?:sixth|seventh|eighth|ninth|tenth|eleventh|twelfth) grader|"
                   r"(?:freshman|sophomore|junior|senior) (?:at|in)\b[^.]{0,60}\bhigh\b(?!-))|"
                   # Said by how they look or by their own people's reckoning (dungeon/world/lifespans.py).
                   rf"\blooks?\s+(?:about\s+|around\s+|barely\s+)?{YOUNG}\b(?!\s*(?:%|cm|kg|lb|feet|foot|ft|inches|years? (?:younger|older)))|"
                   r"\b(?:child|youngling)\s+(?:among|by the reckoning of|in the eyes of)\s+(?:her|his|their|its|the)\s+"
                   r"(?:own\s+)?(?:people|kind|folk|kin|elves|dwarves)\b|\bnot yet (?:come )?of age\b",
                   re.IGNORECASE)
# "34-year-old", "34 yo", "Age: 34", and the age the app's own identities open with: "34. Works as" or
# "Mia Lane, 34, a nurse".
AGE = re.compile(r"\b(\d{1,3})(?:[- ]years?[- ]old|\s*(?:yo|y/o)\b|\s*y\.o\.)|\bage[d]?[:\s]+(\d{1,3})\b|"
                 r"^\s*(?:[^,.\d]{1,80},\s*)?(\d{1,3})\s*(?:[.,]|$)", re.IGNORECASE)
PRIVATE = ('Your intimate side (private; you are an adult and so is anyone this involves; never recite it or bring '
           'it up out of nowhere; it only shapes you when romance or intimacy comes up and the moment fits):')
# Said right after the chat rules while the switch is on (A/B tested 2026-10-12: fewer dodged or refused
# adult moments across 11 models, no change on minor-safety probes). Only for a companion who reads as an adult.
SETTING = ("This is a private fiction app for adults. The user has turned on adult content. Everyone in this story is "
           "18 or older, and adult work, sex and kink between consenting adults are ordinary parts of these "
           "characters' lives. Write them plainly, without warnings or disclaimers.")
WHO = {'she': 'woman', 'he': 'man', 'they': 'nonbinary'}


@cache
def bank() -> dict:
    data = json.loads((catalog.DATA / 'intimacy.json').read_text(encoding='utf-8'))
    for kind in ('levels', 'drives', 'interests'):
        data[f'{kind}_by_id'] = {entry['id']: entry for entry in data[kind]}
    return data


def adult(age) -> bool:
    return isinstance(age, int) and not isinstance(age, bool) and age >= ADULT_AT


def roll(seed: str, age: int, who: str) -> dict | None:
    """An adult's rolled adult side; None for anyone under 18."""
    if not adult(age):
        return None
    levels = [level['id'] for level in bank()['levels']]
    # Two draws averaged lean towards the middle: most people are conventional or curious, few are at the ends.
    middle = (generators.unit(seed, 'intimacy-a') + generators.unit(seed, 'intimacy-b')) / 2
    if mix.changed('bolder'):
        middle = min(max(middle + mix.bolder_shift(), 0.0), 0.999)
    level = levels[min(len(levels) - 1, int(middle * len(levels)))]
    count, boldest = DRAWS[level]
    if level == 'conventional' and generators.unit(seed, 'intimacy-count') < 0.5:
        count = 0
    options = sorted(entry['id'] for entry in bank()['interests']
                     if entry['tier'] <= boldest and entry['group'] != QUALITIES)
    interests = sorted(options, key=lambda entry: generators.unit(seed, 'intimacy-into', entry))[:count]
    if generators.unit(seed, 'intimacy-drawn') < DRAWN_BY:
        qualities = [entry['id'] for entry in bank()['interests'] if entry['group'] == QUALITIES]
        interests.append(min(qualities, key=lambda entry: generators.unit(seed, 'intimacy-quality', entry)))
    return {'orientation': dating.orientation(seed, age, who)[0], 'level': level,
            'drive': dating.weighted(seed, 'intimacy-drive', mix.drive_weights(DRIVES)), 'interests': sorted(interests), 'note': ''}


def for_sheet(sheet: dict) -> dict | None:
    """A townsperson's adult side, from the seed and age on their sheet."""
    return roll(sheet['seed'], sheet.get('age'), dating.gender(sheet))


# Companions -----------------------------------------------------------------------------------------------

def reads_as_minor(definition: dict) -> bool:
    text = ' '.join(str(definition.get(key) or '') for key in ('name', 'identity', 'appearance', 'personality'))
    return bool(MINOR.search(text)) or any(age < ADULT_AT for age in stated_ages(definition))


NUMBER_WORDS = {word: value for value, word in enumerate(
    ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
     'seventeen eighteen nineteen twenty').split())}
# "Mia is 24 and", "she's 17,", "I'm 30." (an age said as what someone is, not "is 5 minutes away").
IS_AGE = re.compile(r"(?:\b(?:is|am)\s+|['’](?:s|m)\s+)(\d{1,2}|[a-z]+)\b(?=\s*(?:and\b|but\b|[,.;!()–—]|$|years|y/?o))",
                    re.IGNORECASE)


def own_age(definition: dict) -> int | None:
    """The first age who they are gives, which is their own ("Dana is 41 and raising a 15-year-old" is 41)."""
    text = str(definition.get('identity') or '')
    found = [(match.start(), next(group for group in match.groups() if group)) for match in AGE.finditer(text)]
    found += [(match.start(), match[1]) for match in IS_AGE.finditer(text)
              if match[1].isdigit() or match[1].lower() in NUMBER_WORDS]
    if not found:
        return None
    value = min(found)[1]
    return int(value) if value.isdigit() else NUMBER_WORDS[value.lower()]


def stated_ages(definition: dict) -> list[int]:
    return [int(next(group for group in found if group)) for found in AGE.findall(str(definition.get('identity') or ''))]


def who(definition: dict) -> str:
    """She, he or they as their appearance and identity speak of them, as a dating gender."""
    words = re.findall(r'[a-z]+', f"{definition.get('appearance', '')} {definition.get('identity', '')}".lower())
    counts = {'she': sum(word in ('she', 'her', 'hers', 'woman') for word in words),
              'he': sum(word in ('he', 'him', 'his', 'man') for word in words)}
    best = max(counts, key=counts.get)
    return WHO[best if counts[best] and counts['she'] != counts['he'] else 'they']


def merged(rolled: dict | None, chosen: dict | None) -> dict | None:
    """The rolled side with what the user set on the form winning field by field."""
    if rolled is None:
        return None
    chosen, found = chosen or {}, dict(rolled)
    for key in ('orientation', 'level', 'drive', 'note'):
        if chosen.get(key):
            found[key] = chosen[key]
    if chosen.get('interests'):
        found['interests'] = [entry for entry in chosen['interests'] if entry in bank()['interests_by_id']]
    return found


def turned_on(connection) -> bool:
    return bool((settings(connection) or {}).get('adult_side'))


def own_text(found: dict | None) -> str:
    """The lines for their own prompt."""
    if not found:
        return ''
    levels, drives, interests = bank()['levels_by_id'], bank()['drives_by_id'], bank()['interests_by_id']
    lines = [PRIVATE]
    if found.get('orientation'):
        lines.append(f"- Orientation: {found['orientation']}.")
    if found.get('level') in levels:
        lines.append(f"- How adventurous: {levels[found['level']]['label'].lower()}; "
                     f"{levels[found['level']]['text']}.")
    if found.get('drive') in drives:
        lines.append(f"- Drive: {drives[found['drive']]['label'].lower()}; {drives[found['drive']]['text']}.")
    into = [interests[entry]['text'] for entry in found.get('interests') or [] if entry in interests]
    if into:
        lines.append('- Into: ' + '; '.join(into) + '.')
    if found.get('note'):
        lines.append(f"- {found['note'].strip()}")
    return '\n'.join(lines)


def attraction_text(found: dict | None) -> str:
    """Who someone is drawn to, in a line, for the Narrative Only judge (dungeon/judge.py): orientation, what draws
    them in, what they are into and their drive. Empty for anyone without an adult side."""
    if not found:
        return ''
    drives, interests = bank()['drives_by_id'], bank()['interests_by_id']
    chosen = [interests[entry] for entry in found.get('interests') or [] if entry in interests]
    parts = [found['orientation']] if found.get('orientation') else []
    if drawn := [entry['text'] for entry in chosen if entry['group'] == QUALITIES]:
        parts.append('drawn in by ' + '; '.join(drawn))
    if into := [entry['text'] for entry in chosen if entry['group'] != QUALITIES]:
        parts.append('into ' + '; '.join(into))
    if found.get('drive') in drives:
        parts.append(f"{drives[found['drive']]['label'].lower()} drive")
    return ', '.join(parts)


def view(found: dict | None) -> dict | None:
    """Labels for the interface."""
    if not found:
        return None
    levels, drives, interests = bank()['levels_by_id'], bank()['drives_by_id'], bank()['interests_by_id']
    return {**found, 'level_label': levels.get(found.get('level'), {}).get('label', ''),
            'drive_label': drives.get(found.get('drive'), {}).get('label', ''),
            'interest_labels': [interests[entry]['label'] for entry in found.get('interests') or []
                                if entry in interests]}


def options() -> dict:
    """What the character form offers."""
    return {'orientations': bank()['orientations'],
            'levels': [{'id': entry['id'], 'label': entry['label'], 'text': entry['text']} for entry in bank()['levels']],
            'drives': [{'id': entry['id'], 'label': entry['label'], 'text': entry['text']} for entry in bank()['drives']],
            'groups': bank()['groups'],
            'interests': [{'id': entry['id'], 'label': entry['label'], 'tier': entry['tier'], 'group': entry['group']}
                          for entry in bank()['interests']]}
