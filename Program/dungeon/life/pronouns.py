"""The companion's own pronouns in rule and template text: storylines, dreams, traditions and day events, Life deck
moments and the reasons an outcome went the way it did.

Templates speak of the companion as "they", which product copy keeps when their pronouns are not known. When their
description says "she" or "he" (dungeon/world/looks.pronouns_of reads it), the phrases that are about the companion
are said with those pronouns, verb included ("she is", not "they is"). Only listed phrases change: a "they" about
someone else in the same line stays. Swaps run when text is read, so lines already written read right too.
"""
from dungeon.world import looks

FORMS = {'she/her': {'they': 'she', 'them': 'her', 'their': 'her', 'theirs': 'hers', 'themselves': 'herself', 'are': 'is', 'were': 'was',
                     'do': 'does', 's': 's'},
         'he/him': {'they': 'he', 'them': 'him', 'their': 'his', 'theirs': 'his', 'themselves': 'himself', 'are': 'is', 'were': 'was',
                    'do': 'does', 's': 's'}}
# A post the companion or a circle member writes speaks of them as "I" (dungeon/life/composer.mine).
FIRST = {'they': 'I', 'them': 'me', 'their': 'my', 'theirs': 'mine', 'themselves': 'myself', 'are': 'am', 'were': 'was',
         'do': 'do', 's': ''}
# Someone else's pronouns in a bank line ("{They} love{s} roses", "{they're} lovely"): their own partner's in their
# love life (dungeon/life/love_life.py). Capitalised keys too; any pronouns not listed read "they".
PERSON = {'they/them': {'they': 'they', 'them': 'them', 'their': 'their', 'theirs': 'theirs', 'themself': 'themselves',
                        "they're": "they're", "they've": "they've", 'are': 'are', 'were': 'were', 'have': 'have',
                        'do': 'do', 's': ''},
          'she/her': {'they': 'she', 'them': 'her', 'their': 'her', 'theirs': 'hers', 'themself': 'herself',
                      "they're": "she's", "they've": "she's", 'are': 'is', 'were': 'was', 'have': 'has', 'do': 'does',
                      's': 's'},
          'he/him': {'they': 'he', 'them': 'him', 'their': 'his', 'theirs': 'his', 'themself': 'himself',
                     "they're": "he's", "they've": "he's", 'are': 'is', 'were': 'was', 'have': 'has', 'do': 'does',
                     's': 's'}}
CAPITALISED = ('they', 'them', 'their', 'theirs', 'themself', "they're", "they've")


def person(pronouns: str | None) -> dict:
    """The fill-ins for someone with these pronouns ('she/her'), capitalised ones included."""
    found = PERSON.get(pronouns or '', PERSON['they/them'])
    return found | {key.capitalize(): found[key].capitalize() for key in CAPITALISED}


def forms(definition: dict) -> dict | None:
    """The companion's pronoun forms, or None when they are not known (the text keeps "they")."""
    return FORMS.get(looks.pronouns_of(definition))


def their(definition: dict) -> str:
    """"their", or "her" / "his" when the companion's pronouns are known."""
    return (forms(definition) or {}).get('their', 'their')


def said(text: str | None, swaps: tuple[tuple[str, str], ...], definition: dict, found: dict | None = None) -> str | None:
    """The text with each phrase about the companion said with their pronouns; `{they}`, `{them}`, `{their}`,
    `{theirs}`, `{themselves}`, `{are}`, `{were}`, `{do}` and `{s}` (a verb's "s": "like{s}") in the new phrase are filled from
    their forms. `found` gives the forms instead (FIRST for "I")."""
    found = (found or forms(definition)) if text else None
    if not found:
        return text
    for old, new in swaps:
        if old in text:
            for key, value in found.items():
                new = new.replace(f'{{{key}}}', value)
            text = text.replace(old, new)
    return text
