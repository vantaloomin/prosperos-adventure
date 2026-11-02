"""Given names grounded in what babies were actually called in the year a person was born.

The data (given_names.json, written by scripts/world/given_names.py) holds each culture's most popular
given names per birth year or cohort and its common family names. A name group in names.json links to
cultures with weights, so a 58-year-old in Baltimore is more likely a Lisa or a Kevin and a 24-year-old a
Brianna or a Tyler. The same data lists names that read as invented by a language model (Elara, Voss, Vex);
nothing here produces them, and any name a model writes is checked against them.
"""
import json
import re
from functools import cache
from importlib import resources

from dungeon.world import catalog
from dungeon.world.schema import GivenNames

# Where no city is known, names come from the modern bank as an American city would mix them.
DEFAULT_CITY = {'id': '', 'era': 'modern', 'country': 'United States', 'names': None}
# How far either side of the target birth year a name may come from, so peers don't all share one year's list.
SPREAD = 3
WORD = re.compile(r"[A-Z][A-Za-z'’-]+")


@cache
def data() -> dict:
    text = (catalog.DATA / 'given_names.json').read_text(encoding='utf-8')
    return GivenNames.model_validate_json(text).model_dump()


def present_year(city: dict | None = None) -> int | None:
    """The year ages count back from: the city's own, else its era's. None for an era without birth-year lists
    (medieval, fantasy), where names come from the bank's own lists."""
    if city is None:
        return data()['present_year']
    own = (city.get('names') or {}).get('year')
    return own or data()['era_years'].get(city.get('era', 'modern'))


def culture(key: str) -> dict:
    return data()['cultures'][key]


def local_culture(country: str | None) -> str:
    """The culture whose names are local in this country; the United States lists where none fits."""
    return data()['countries'].get((country or '').strip().lower(), 'us')


@cache
def zone_countries() -> dict[str, str]:
    """Each time zone's country, from the tz database's own tables (tzdata's zone.tab and iso3166.tab)."""
    try:
        base = resources.files('tzdata').joinpath('zoneinfo')
        rows = [[line.split('\t') for line in (base / name).read_text(encoding='utf-8').splitlines()
                 if line and not line.startswith('#')] for name in ('iso3166.tab', 'zone.tab')]
    except (ModuleNotFoundError, OSError):
        return {}
    names = {row[0]: row[1].strip() for row in rows[0] if len(row) > 1}
    return {row[2].strip(): names[row[0]] for row in rows[1] if len(row) > 2 and row[0] in names}


def country_for_zone(timezone: str | None) -> str | None:
    """The country a city's time zone is in, spelled as the name data knows it when it can be ("Korea (South)" is
    South Korea), so a city with no country of its own still gets local names: Seoul's people are Korean."""
    found = zone_countries().get(timezone or '')
    if not found:
        return None
    inner = re.fullmatch(r'(.+?) \((.+)\)', found)
    spellings = [f'{inner.group(2)} {inner.group(1)}', inner.group(1), inner.group(2)] if inner else [found]
    return next((spelling for spelling in spellings if spelling.casefold() in data()['countries']), spellings[0])


def links(group: dict, city: dict) -> dict[str, float]:
    """The cultures a name group draws given names from in this city, with weights. Empty for eras without
    birth-year lists."""
    if present_year(city) is None:
        return {}
    local, known = local_culture(city.get('country')), data()['cultures']
    weights: dict[str, float] = {}
    for key, weight in (group.get('cultures') or {}).items():
        key = local if key == 'local' else key
        if key in known and weight > 0:
            weights[key] = weights.get(key, 0) + weight
    return weights


def cohort(key: str, year: int) -> dict:
    """The cohort covering a birth year, else the nearest one."""
    cohorts = culture(key)['cohorts']
    return min(cohorts, key=lambda item: (0 if item['start'] <= year <= item['end'] else
                                          min(abs(year - item['start']), abs(year - item['end'])), -item['start']))


def rank_weights(names: list) -> list[float]:
    """Popular names come up more often: the first is about ten times as likely as the hundredth."""
    return [1 / (rank + 10) for rank in range(len(names))]


# --- Invented-sounding names --------------------------------------------------------------------

@cache
def invented() -> frozenset[str]:
    names = data()['invented']
    return frozenset(word.casefold() for word in [*names['given'], *names['family']])


# Shapes language models reach for when they coin a name: fantasy beginnings (Kael-, Vael-, Lyr-, Zeph-) and
# endings (-yra, -ithra), and evocative compounds for family names (Ravencrest, Duskwhisper, Stormvale).
COINED_GIVEN = re.compile(r'^(kael|vael|vaer|cael|lyr(a|ae|e)|zeph|nyx|vex|seraph|sylv[aei]r|elys|elar|eryn|vey|xyl|'
                          r'thal[aeiou]r|aeri|aeryn|ael)|(yra|yrin|ithra|ara?th|ys{2})$', re.I)
COINED_FAMILY = re.compile(r'^(raven|shadow|storm|night|moon|star|dusk|dawn|silver|frost|ember|thorn|wolf|black|'
                           r'iron|ash|winter|bright|grim|hollow|mist|sun)(wood|crest|vale|fall|mere|bane|wind|whisper|'
                           r'shade|heart|blade|song|fire|forge|thorne?|weaver|hollow|ridge|veil|born|walker|helm|'
                           r'shadow|mantle|ward|haven)$', re.I)
# Ordinary words that can start a sentence and happen to fit a shape above.
NOT_NAMES = re.compile(r'(ed|ing|ly|less|ness|ful)$', re.I)


@cache
def known() -> frozenset[str]:
    """Every word of every name in the shipped lists: real names, however unusual, are never flagged."""
    words = set()
    for item in data()['cultures'].values():
        for cohort in item['cohorts']:
            words.update(word for name in [*cohort['feminine'], *cohort['masculine']] for word in name.split())
        words.update(word for name in item['surnames'] for word in name.split())
    for bank in catalog.names()['banks'].values():
        for group in bank.values():
            for key in ('feminine', 'masculine', 'neutral', 'family'):
                words.update(word for name in group[key] for word in name.split())
    return frozenset(word.casefold() for word in words)


def coined(word: str) -> bool:
    """Whether a capitalised word reads as invented: on the list, or shaped like a model-made name and found in
    none of the real name lists."""
    folded = word.casefold()
    if folded in invented():
        return True
    if folded in known() or NOT_NAMES.search(word):
        return False
    return bool(COINED_GIVEN.search(word) or COINED_FAMILY.search(word))


def is_invented(name: str) -> bool:
    """Whether any word of a name reads as invented (Elara, Voss, Vex, Vaeryn Duskmere)."""
    return any(coined(word) for word in WORD.findall(name or ''))


def invented_in(text: str, allowed: str = '') -> list[str]:
    """Capitalised words in a model's text that read as invented names, except ones in `allowed` (what the
    user typed and the world data), in order of first use."""
    permitted = {word.casefold() for word in WORD.findall(allowed or '')}
    found = [word for word in WORD.findall(text or '') if word.casefold() not in permitted and coined(word)]
    return list(dict.fromkeys(found))


def allowed_words(*parts) -> str:
    """Text to pass as `allowed`: anything the user typed or the world data contains (as JSON)."""
    return ' '.join(part if isinstance(part, str) else json.dumps(part, ensure_ascii=False) for part in parts if part)


# --- Family names that change with gender ---------------------------------------------------------

# Polish and Russian family names take a feminine ending for women (Kowalski → Kowalska, Ivanov → Ivanova).
FEMININE_ENDINGS = {'poland': (('dzki', 'dzka'), ('cki', 'cka'), ('ski', 'ska')),
                    'russia': (('skiy', 'skaya'), ('sky', 'skaya'), ('ov', 'ova'), ('ev', 'eva'), ('in', 'ina'))}


def gendered(culture: str | None, family: str, pronouns: str) -> str:
    """The form of a family name a woman of this culture would use."""
    if pronouns != 'she':
        return family
    for ending, feminine in FEMININE_ENDINGS.get(culture or '', ()):
        if family.endswith(ending):
            return family[:-len(ending)] + feminine
    return family


def base_family(culture: str | None, family: str) -> str:
    """The listed (masculine) form of a family name, so a woman's relatives share the same name."""
    for ending, feminine in FEMININE_ENDINGS.get(culture or '', ()):
        if family.endswith(feminine) and family[:-len(feminine)] + ending in culture_surnames(culture):
            return family[:-len(feminine)] + ending
    return family


@cache
def culture_surnames(key: str) -> frozenset[str]:
    return frozenset(culture(key)['surnames'])
