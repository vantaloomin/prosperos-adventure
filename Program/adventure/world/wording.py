"""American wording for the shared phrase banks in American settings.

The shared banks (goals, quirks, perception and life details in world/data) are written in British English, which
suits London, Calderwick or Camelot but not a Maine harbor town or 1920s Massachusetts. `regional` turns their
British spellings and a few British-only things (a prize marrow, the parish rolls) into American ones when the
city is in the United States; everywhere else the text is left as written.
"""
import re

AMERICAN = re.compile(r'^(?:us|usa|u\.s\.a?\.?|united states(?: of america)?|america)$', re.IGNORECASE)
# British spelling stems, matched at the start of a word: "neighbourhood", "favourites", "travelled".
STEMS = {
    'neighbour': 'neighbor', 'colour': 'color', 'favourit': 'favorit', 'honour': 'honor', 'harbour': 'harbor',
    'flavour': 'flavor', 'humour': 'humor', 'behaviour': 'behavior', 'labour': 'labor', 'rumour': 'rumor',
    'travell': 'travel', 'jewellery': 'jewelry', 'pyjama': 'pajama', 'programme': 'program', 'instalment': 'installment',
}
# -ise verbs, only with a verb ending: "realised" but not "realistic".
VERBS = {'organis': 'organiz', 'reorganis': 'reorganiz', 'realis': 'realiz', 'recognis': 'recogniz', 'apologis': 'apologiz',
         'memoris': 'memoriz'}
# Whole words: "mum" leaves "museum" and "grey" leaves "greyhound" alone.
WORDS = {
    'mum': 'mom', 'mums': 'moms', 'grey': 'gray', 'cosy': 'cozy', 'theatre': 'theater', 'theatres': 'theaters',
    'centre': 'center', 'centres': 'centers', 'practise': 'practice', 'practised': 'practiced',
    'practises': 'practices', 'practising': 'practicing', 'jumper': 'sweater', 'jumpers': 'sweaters',
    'allotment': 'garden plot', 'queue': 'line', 'queues': 'lines', 'catalogue': 'catalog', 'catalogues': 'catalogs',
    'rota': 'schedule', 'rotas': 'schedules', 'lorry': 'truck', 'lorries': 'trucks', 'drink-driving': 'drunk-driving',
    'tachograph': 'logbook',
    'at the pictures': 'at the movies', 'to the pictures': 'to the movies',
    # British-only things.
    'prize marrow': 'prize pumpkin', 'prize-winning marrow': 'prize-winning pumpkin', 'giant marrow': 'giant pumpkin',
    'parish vestry': 'town council', 'parish rolls': 'church records', 'every street in the parish': 'every street in town',
    'parish trivia night': 'church trivia night', 'for the parish': 'for the neighborhood',
}


def american(data: dict | None) -> bool:
    return bool(data) and bool(AMERICAN.match((data.get('country') or '').strip()))


def _either(items) -> str:
    return '|'.join(re.escape(item) for item in sorted(items, key=len, reverse=True))


PATTERN = re.compile(rf"\b(?:(?P<word>{_either(WORDS)})\b|(?P<verb>{_either(VERBS)})(?=e|ing|ation)|"
                     rf"(?P<stem>{_either(STEMS)}))", re.IGNORECASE)


def _swap(match: re.Match) -> str:
    found = match.group(0)
    swap = {**WORDS, **VERBS, **STEMS}[found.lower()]
    return swap[:1].upper() + swap[1:] if found[:1].isupper() else swap


def americanize(text: str) -> str:
    return PATTERN.sub(_swap, text)


def regional(data: dict | None, text: str) -> str:
    """The text in the city's own English: American spelling and things in the United States, else as written."""
    return americanize(text) if text and american(data) else text


def regional_all(data: dict | None, value):
    """`regional` through a sheet's lines: strings, and the lists and dicts holding them."""
    if not american(data):
        return value
    if isinstance(value, str):
        return americanize(value)
    if isinstance(value, list):
        return [regional_all(data, item) for item in value]
    if isinstance(value, dict):
        return {key: regional_all(data, item) for key, item in value.items()}
    return value
