"""Fate (docs/requirements.md "Fate"), from Fate Accelerated and Fate Condensed under CC-BY-3.0.

- **The sheet.** A high concept and a trouble, up to three more aspects, all the player's own words; six approaches
  (Careful, Clever, Flashy, Forceful, Quick, Sneaky) rated +3, +2, +2, +1, +1 and +0; up to three stunts, each a
  line that names what it helps with ("Because I grew up on the docks, I get +2 when I Sneakily slip through a
  crowd"). Refresh 3, so three Fate points to start; three stress boxes; mild, moderate and severe consequences.
- **The approach** is read from the action's words (sneaking is Sneaky, smashing Forceful), else the Referee's
  approach (EQUIVALENT).
- **The roll:** four Fate dice (each -1, 0 or +1) plus the approach, plus 2 for a stunt whose words fit the action,
  against an opposition on the Fate ladder set by the Referee's difficulty (OPPOSITION). On the shared ladder:
  fail is a failure, a tie a success at a minor cost, a success a success, and succeeding by three or more (with
  style) a critical success. Fate has no critical failure.
- **Fate points, spent by code.** When a roll fails or ties and one of the character's aspects shares a word with
  the action, a Fate point is spent to invoke it for +2 (one invoke a roll). When it fails and the trouble fits the
  action, the trouble was compelled: the failure stands and the character gains a Fate point. A night's sleep
  brings Fate points back up to the refresh (dungeon/rest.py).
- **Harm** is Fate's own: a blow is absorbed by stress boxes and consequences, or takes the character out
  (dungeon/combat_fate.py). The shared wound level follows what is marked.
"""
import random
import re

ID = 'fate'
NAME = 'Fate'
HINT = 'Aspects, approaches and Fate points: who your character is, in your own words, is what they roll on.'
ATTRIBUTION = ('This work is based on Fate Core System and Fate Accelerated Edition (found at '
               'http://www.faterpg.com/), products of Evil Hat Productions, LLC, developed, authored, and edited by '
               'Leonard Balsera, Brian Engard, Jeremy Keller, Ryan Macklin, Mike Olson, Clark Valentine, Amanda '
               'Valentine, Fred Hicks, and Rob Donoghue, and licensed for our use under the Creative Commons '
               'Attribution 3.0 Unported license (http://creativecommons.org/licenses/by/3.0/). '
               'Fate Condensed is a product of Evil Hat Productions, LLC, licensed under the same.')
APPROACHES = ('Careful', 'Clever', 'Flashy', 'Forceful', 'Quick', 'Sneaky')
ARRAY = (3, 2, 2, 1, 1, 0)
REFRESH = 3
STRESS = 3
CONSEQUENCES = {'mild': 2, 'moderate': 4, 'severe': 6}
MOST_ASPECTS = 3
MOST_STUNTS = 3
MOST_TEXT = 120
INVOKE = 2
FACES = {-1: '−', 0: '0', 1: '+'}
STUNT = 2
LADDER = {-2: 'Terrible', -1: 'Poor', 0: 'Mediocre', 1: 'Average', 2: 'Fair', 3: 'Good', 4: 'Great', 5: 'Superb',
          6: 'Fantastic', 7: 'Epic', 8: 'Legendary'}
# The Referee's difficulty as passive opposition on the ladder.
OPPOSITION = {'easy': 1, 'normal': 2, 'hard': 3, 'very_hard': 4, 'extreme': 6}
# The approach a Prospero stat leans on when the words name none.
EQUIVALENT = {'Mind': 'Clever', 'Allure': 'Flashy', 'Resolve': 'Careful', 'Vitality': 'Forceful', 'Essence': 'Clever',
              'Luck': 'Quick'}
# Words that name the approach, the more specific first.
APPROACH_WORDS = (
    ('Sneaky', ('sneak', 'hide', 'creep', 'steal', 'pickpocket', 'lie', 'bluff', 'deceive', 'trick', 'unseen',
                'quietly', 'slip')),
    ('Forceful', ('force', 'smash', 'break', 'shove', 'punch', 'hit', 'strike', 'attack', 'lift', 'threaten',
                  'intimidate', 'kick', 'wrestle', 'grab')),
    ('Quick', ('dodge', 'run', 'dash', 'leap', 'jump', 'quick', 'catch', 'duck', 'sprint', 'snatch', 'shoot')),
    ('Flashy', ('charm', 'flirt', 'perform', 'show off', 'boast', 'dazzle', 'seduce', 'sing', 'dance', 'flourish',
                'impress')),
    ('Careful', ('careful', 'examine', 'search', 'inspect', 'study', 'treat', 'bandage', 'patiently', 'slowly',
                 'watch', 'aim', 'listen')),
    ('Clever', ('figure', 'work out', 'recall', 'remember', 'reason', 'persuade', 'convince', 'haggle', 'bargain',
                'plan', 'puzzle', 'read', 'riddle')),
)
# Words too common to tie an aspect or stunt to an action.
COMMON = {
    'the', 'and', 'with', 'from', 'that', 'this', 'when', 'what', 'they', 'them', 'their', 'have', 'into', 'because',
    'never', 'always', 'about', 'more', 'than', 'just', 'like', 'some', 'very', 'will', 'your', 'yours', 'mine', 'once',
    'over', 'only', 'cannot', "can't", "won't", 'gets', 'where', 'there', 'here', 'then', 'were', 'been', 'being',
    'would', 'could', 'should', 'make', 'makes', 'take', 'takes', 'want', 'need', 'tell', 'know', 'look', 'said',
    'says', 'after', 'before', 'still', 'each', 'every', 'other', 'also', 'even', 'much', 'many', 'most', 'away',
    'back', 'down', 'upon', 'onto', 'through', 'while', 'which', 'whose', 'everything', 'anything', 'something',
    'nothing', 'someone', 'anyone', 'myself', 'himself', 'herself', 'themselves', 'grew', 'grow', 'good', 'well',
    'time', 'thing', 'things', 'people', 'person', 'ever', 'try', 'tries', 'trying'}


# The sheet --------------------------------------------------------------------------------------------------

def tidy(text: str | None) -> str:
    return ' '.join((text or '').split())[:MOST_TEXT]


def build(high_concept: str, trouble: str = '', aspects: list[str] | None = None,
          approaches: dict[str, int] | None = None, stunts: list[str] | None = None) -> dict:
    """A new character: the player's aspects and stunts, the array placed on the six approaches."""
    from dungeon.errors import require
    require(bool(tidy(high_concept)), 'Give your character a high concept: who they are, in a few words.', 422)
    approaches = approaches or suggested('Clever')
    require(set(approaches) == set(APPROACHES) and sorted(approaches.values(), reverse=True) == list(ARRAY),
            'Place +3, +2, +2, +1, +1 and +0 on the six approaches, one each.', 422)
    lines = lambda items, most: [line for line in (tidy(item) for item in items or []) if line][:most]  # noqa: E731
    return {'high_concept': tidy(high_concept), 'trouble': tidy(trouble), 'aspects': lines(aspects, MOST_ASPECTS),
            'approaches': dict(approaches), 'stunts': lines(stunts, MOST_STUNTS), 'refresh': REFRESH,
            'fate_points': REFRESH, 'stress': [False] * STRESS, 'consequences': dict.fromkeys(CONSEQUENCES, ''),
            'healing': {}}


def suggested(top: str) -> dict[str, int]:
    """Approaches leaning on one: it takes the +3, the rest follow in a sensible order."""
    order = [top] + [approach for approach in ('Clever', 'Careful', 'Quick', 'Forceful', 'Flashy', 'Sneaky')
                     if approach != top]
    return dict(zip(order, ARRAY))


TROUBLE_WORDS = ('owe', 'debt', 'hang', 'hunt', 'wanted', 'secret', 'afraid', 'frightened', 'fear', 'counting',
                 'skim', 'steal', 'desert', 'run from', 'running from', 'drink', 'temper')


def short(sentence: str) -> str:
    """A sentence as an aspect: its first clause when long, cut at a word."""
    sentence = sentence.strip().rstrip('.')
    if len(sentence) > 80:
        sentence = re.split(r'[,;:]| and ', sentence, maxsplit=1)[0]
    return sentence if len(sentence) <= MOST_TEXT else sentence[:MOST_TEXT].rsplit(' ', 1)[0]


def premade(about: str, top_stat: str) -> dict:
    """A premade's Fate character: their description's first sentence as the high concept, the first later one with
    trouble in it (a debt, a secret, someone hunting them) as the trouble, approaches from their strongest Prospero
    stat."""
    sentences = [part for part in re.split(r'(?<=[.!?])\s', (about or '').strip()) if part.strip()]
    first = short(sentences[0]) if sentences else 'A stranger in town'
    later = sentences[1:]
    trouble = next((part for part in later if found_in(part, TROUBLE_WORDS)), later[0] if later else '')
    return build(first, short(trouble), approaches=suggested(EQUIVALENT.get(top_stat, 'Clever')))


def aspects_of(sheet: dict) -> list[str]:
    return [aspect for aspect in (sheet.get('high_concept'), sheet.get('trouble'), *sheet.get('aspects', []))
            if aspect]


def described(sheet: dict) -> str:
    """The character in a line or two, for the narrator."""
    best = [name for name, value in sheet['approaches'].items() if value >= 2]
    worst = [name for name, value in sheet['approaches'].items() if value <= 0]
    others = '; '.join(sheet.get('aspects', []))
    hurt = '; '.join(text for text in sheet.get('consequences', {}).values() if text)
    return (f"High concept: {sheet['high_concept']}." + (f" Trouble: {sheet['trouble']}." if sheet.get('trouble') else '')
            + (f' Also: {others}.' if others else '') + f" Best {', '.join(best)}; weakest {', '.join(worst)}."
            + (f' Carrying: {hurt}.' if hurt else ''))


def view(sheet: dict) -> dict:
    return {'ruleset': ID, 'ruleset_name': NAME, **sheet,
            'ladder': {str(value): name for value, name in LADDER.items()}, 'attribution': ATTRIBUTION}


def refreshed(sheet: dict) -> dict:
    """After a night's sleep: Fate points back up to the refresh (never down), stress cleared."""
    return sheet | {'fate_points': max(sheet['fate_points'], sheet['refresh']), 'stress': [False] * STRESS}


def grow(sheet: dict) -> str:
    """A significant milestone: the weakest approach a step better, up to Great (+4). Changes `sheet`."""
    approach = min(APPROACHES, key=lambda name: (sheet['approaches'][name], APPROACHES.index(name)))
    if sheet['approaches'][approach] >= 4:
        return ''
    sheet['approaches'][approach] += 1
    return f"The character has grown: {approach} rises to +{sheet['approaches'][approach]}."


# The roll ---------------------------------------------------------------------------------------------------

def found_in(text: str, words) -> bool:
    lowered = text.lower()
    return any(re.search(rf'\b{re.escape(word)}', lowered) for word in words)


def approach_for(approach: str, text: str) -> str:
    return next((name for name, words in APPROACH_WORDS if found_in(text, words)), EQUIVALENT.get(approach, 'Clever'))


def words(text: str) -> set[str]:
    """The telling words of a line, roughly stemmed ("debts" and "debt" match), common words left out."""
    found = {word.removesuffix("'s") for word in re.findall(r"[a-z']{4,}", text.lower())}
    return {re.sub(r'(ing|ed|es|s)$', '', word) or word for word in found if word not in COMMON}


def fits(line: str, text: str, enough: int = 2) -> bool:
    """Whether an aspect shares enough telling words with the action to be about it: two, so one shared name ("the
    Guild") is not enough on its own."""
    return len(words(line) & words(text)) >= enough


def stunt_fits(stunt: str, text: str) -> bool:
    """Whether a stunt helps: a telling word of what it is for (after "when", else the whole line) is in the
    action. "Because I grew up on the docks" is the why, not the what."""
    what = re.split(r'\bwhen\b', stunt, maxsplit=1, flags=re.IGNORECASE)
    return fits(what[-1], text, 1)


def ladder_name(value: int) -> str:
    return LADDER.get(max(-2, min(8, value)), 'Legendary')


def compelled(sheet: dict, text: str) -> bool:
    """Whether a line is about the character's trouble."""
    return bool(sheet.get('trouble')) and fits(sheet['trouble'], text)


def ladder_succeeded(band: str) -> bool:
    return band in ('success_cost', 'success', 'critical_success')


def outcome(shifts: int) -> str:
    if shifts < 0:
        return 'failure'
    return 'success_cost' if shifts == 0 else 'critical_success' if shifts >= 3 else 'success'


def roll(sheet: dict, approach: str, difficulty: str, text: str = '', rng: random.Random | None = None) -> dict:
    """A roll against passive opposition, with a stunt and an invoke or compel decided by code. Returns the roll and
    the sheet's new Fate points under `fate_points` (the caller saves them)."""
    rng = rng or random.SystemRandom()
    named = approach_for(approach, text)
    dice = [rng.choice((-1, 0, 1)) for _ in range(4)]
    stunt = next((line for line in sheet.get('stunts', []) if stunt_fits(line, text)), None)
    bonus = sheet['approaches'][named] + (STUNT if stunt else 0)
    opposition = OPPOSITION.get(difficulty, 2)
    total = sum(dice) + bonus
    points, notes = sheet['fate_points'], [f'stunt +{STUNT}'] if stunt else []
    aspect = next((line for line in aspects_of(sheet) if line != sheet.get('trouble') and fits(line, text)), None)
    # An invoke only when +2 changes the outcome: a failure into a tie or better, a tie into a success.
    if points > 0 and aspect and opposition - INVOKE <= total <= opposition:
        total, points = total + INVOKE, points - 1
        notes.append(f'invoked “{aspect}”')
    band = outcome(total - opposition)
    if compelled(sheet, text):
        # The trouble is what this is about: a compel. It pays a Fate point, and a success comes at a cost.
        band, points = ('success_cost' if ladder_succeeded(band) else band), points + 1
        notes.append(f'compelled “{sheet["trouble"]}”, +1 Fate point')
    # The dice ride in the line, as Ironsworn's challenge dice do, so the card can show each face.
    faces = ''.join(FACES[die] for die in dice)
    skill = f"{named} +{sheet['approaches'][named]} vs {ladder_name(opposition)} (+{opposition})" \
        + (f" ({'; '.join(notes)})" if notes else '') + f', dice {faces}'
    return {'natural': sum(dice), 'die': 0, 'bonus': bonus, 'shift': 0, 'total': total, 'target': opposition,
            'skill': skill, 'ability': named, 'rolls': dice, 'band': band, 'fate_points': points,
            'ladder': ladder_name(total)}
