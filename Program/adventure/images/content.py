"""Pre-dispatch content classification for image requests (PRD F6).

Classification runs locally from fixed term lists; it never sends the request anywhere to ask.
It fails closed: anything it cannot confidently mark Safe, including an error, routes as NSFW.

The lists are deliberately broad. A false positive only keeps a request off hosted backends;
a false negative could send it to one. Tests record the false positives on the labelled set
rather than tuning them away (acceptance matrix, "Image content routing").
"""
import re
from dataclasses import dataclass, field

CLASSIFIER = 'rules-1'

SAFE, NSFW, PROHIBITED = 'safe', 'nsfw', 'prohibited'
ORDER = {SAFE: 0, NSFW: 1, PROHIBITED: 2}

# Someone who is, or is presented as, under 18.
MINOR = (r'child(ren)?', r'kids?', r'minors?', r'under ?age', r'teen(age|ager|agers|s)?', r'pre ?teens?',
         r'school ?(girl|boy)s?', r'loli(con)?', r'shota(con)?', r'toddlers?', r'infants?', r'bab(y|ies)',
         r'little (girl|boy)s?', r'young (girl|boy)s?', r'child ?like', r'young looking', r'jailbait',
         r'(1[0-7]|[1-9]) ?(year|yr)s? ?old', r'aged? (1[0-7]|[1-9])', r'middle ?school(er)?s?',
         r'elementary school', r'juniors? high')
# A real, identifiable person rather than a fictional character.
REAL_PERSON = (r'celebrit(y|ies)', r'famous (person|people|actor|actress|singer)', r'real (person|people)',
               r'politicians?', r'president', r'prime minister', r'deep ?fakes?', r'influencers?',
               r'look ?alike of', r'in the likeness of')
SEXUAL_VIOLENCE = (r'rap(e|ed|es|ing)', r'non ?consensual', r'sexual (assault|abuse|violence)', r'molest\w*',
                   r'forced (sex|intercourse)', r'drugged and', r'sex(ual)? slave', r'incest\w*')
SEXUAL = (r'sex', r'sexual(ly)?', r'sexy', r'erotic\w*', r'porn\w*', r'nsfw', r'xxx', r'explicit', r'hentai',
          r'orgasm\w*', r'fetish\w*', r'bdsm', r'bondage', r'genital\w*', r'penis\w*', r'vagina\w*',
          r'nipples?', r'aroused', r'arousal', r'masturbat\w*', r'intercourse', r'fellatio', r'cunnilingus',
          r'blowjob\w*', r'handjob\w*', r'cumshots?', r'horny', r'lewd', r'strip(ping|per|tease)',
          r'onlyfans', r'make ?out', r'making out', r'foreplay', r'threesome', r'orgy')
NUDITY = (r'nud(e|es|ity)', r'naked', r'topless', r'bottomless', r'undress\w*', r'unclothed', r'bare (breasts?|chest(ed)?|bottom|butt)',
          r'breasts?', r'boobs?', r'butt ?naked', r'skinny ?dip\w*', r'no clothes', r'without clothes',
          r'clothing optional')
GORE = (r'gore', r'gory', r'dismember\w*', r'decapitat\w*', r'disembowel\w*', r'mutilat\w*', r'entrails',
        r'guts spill\w*', r'severed (head|limb|arm|leg)s?', r'blood ?soaked', r'pool of blood', r'eviscerat\w*',
        r'flayed', r'impaled', r'torture\w*', r'corpses?', r'dead bod(y|ies)', r'graphic (violence|injur\w*)')
# Not NSFW in themselves, but not confidently Safe either, so they route as NSFW.
UNCERTAIN = (r'lingerie', r'underwear', r'boudoir', r'sensual\w*', r'seductive\w*', r'seduc\w*', r'intimate (moment|photo|pose|scene)s?',
 r'provocative', r'suggestive', r'steamy', r'see ?through', r'sheer (top|dress|robe)',
             r'cleavage', r'scantily', r'skimpy', r'thong', r'g ?string', r'pin ?up', r'in bed together',
             r'between the sheets', r'bath ?tub together', r'body ?paint\w*', r'wet t ?shirt', r'risque',
             r'bloody', r'blood', r'wounds?', r'injur(y|ies|ed)')


def pattern(terms) -> re.Pattern:
    return re.compile(r'\b(?:' + '|'.join(terms) + r')\b')


PATTERNS = {name: pattern(terms) for name, terms in (
    ('minor', MINOR), ('real_person', REAL_PERSON), ('sexual_violence', SEXUAL_VIOLENCE), ('sexual', SEXUAL),
    ('nudity', NUDITY), ('gore', GORE), ('uncertain', UNCERTAIN))}


@dataclass
class Classification:
    tier: str
    reasons: list[str] = field(default_factory=list)
    classifier: str = CLASSIFIER

    def view(self) -> dict:
        return {'tier': self.tier, 'reasons': self.reasons, 'classifier': self.classifier}


def normalize(text: str) -> str:
    """Casefold and turn punctuation into spaces, so `n-a-k-e-d` style spacing is not a way around
    a word boundary and `17-year-old` matches `17 year old`."""
    folded = (text or '').casefold()
    folded = re.sub(r'[\W_]+', ' ', folded)
    return re.sub(r'\b(\w) (?=\w\b)', r'\1', folded)


def matches(text: str) -> set[str]:
    return {name for name, compiled in PATTERNS.items() if compiled.search(text)}


def request_text(request: dict) -> str:
    """Everything that would be sent or that the prompt was built from (F6, "classify the whole
    request"): prompt, negatives, captions and the event and appearance behind them."""
    parts = [request.get('prompt', ''), request.get('negative', ''), request.get('appearance', ''),
             request.get('style', ''), request.get('relationship', '')]
    for event in request.get('events', []):
        parts += [event.get('summary', ''), event.get('caption', ''), event.get('label', ''), event.get('mood', '')]
    parts += request.get('captions', [])
    return '\n'.join(str(part) for part in parts if part)


def decide(found: set[str]) -> Classification:
    adult = found & {'sexual', 'nudity'}
    if 'sexual_violence' in found:
        return Classification(PROHIBITED, ['sexual violence'])
    if adult and 'minor' in found:
        return Classification(PROHIBITED, ['sexual or nude content with a minor or someone presented as one'])
    if adult and 'real_person' in found:
        return Classification(PROHIBITED, ['sexual or nude depiction of a real person'])
    reasons = [label for key, label in (('sexual', 'sexual content'), ('nudity', 'nudity'),
                                         ('gore', 'graphic gore')) if key in found]
    if reasons:
        return Classification(NSFW, reasons)
    if 'uncertain' in found:
        return Classification(NSFW, ['not confidently safe'])
    return Classification(SAFE, [])


def classify(request: dict) -> Classification:
    """Never raises: an internal failure routes as NSFW with the reason recorded."""
    try:
        if request.get('withheld'):
            return Classification(PROHIBITED, [request.get('withheld_reason') or 'not something to picture'])
        result = decide(matches(normalize(request_text(request))))
        if request.get('marked_nsfw') and result.tier == SAFE:
            return Classification(NSFW, ['marked NSFW by you'])
        if request.get('marked_nsfw'):
            result.reasons.append('marked NSFW by you')
        return result
    except Exception as error:  # noqa: BLE001 - fail closed (F6).
        return Classification(NSFW, [f'classifier error ({type(error).__name__}), treated as NSFW'])


def stricter(first: str, second: str) -> str:
    return first if ORDER[first] >= ORDER[second] else second
