"""What someone looks like, as one sheet the same every time: the thing that keeps their pictures one person.

A sheet holds their apparent age, height, weight, build, skin, face shape, jaw and chin, nose, eye colour and
shape, hair, facial hair and one feature people notice. Height, build, hair, eye colour, facial hair and the
feature come from the townsperson's seeded looks (dungeon/world/dating.py), so every picture of them
agrees; the rest is drawn here from the same seed. Colouring follows the heritage their
name or description comes from, and weight is worked out from height and build inside a plausible range
(`bmi_limits` in world/data/looks.json), so a roll never pairs 4'10" with 350 lb.

A companion's sheet works like "How others see them" (dungeon/world/perception.py): whatever the user set on
the form wins, field by field, and an empty field is drawn from the companion's id. Where the free-text
appearance already speaks of something (their hair, their eyes), the drawn value is left out, so the picture
never gets two hair colours. Nothing here calls a model.
"""
import functools
import json
import re

from dungeon.world import catalog, dating, generators, intimacy

NUMBERS = ('age', 'height_cm', 'weight_kg')
WORDS = ('build', 'skin', 'face', 'jaw', 'nose', 'eyes', 'eye_shape', 'hair', 'facial_hair', 'feature')
FIELDS = NUMBERS + WORDS
WHO = {'she/her': 'woman', 'he/him': 'man', 'they/them': 'person'}
PRONOUNS = {'woman': 'she/her', 'man': 'he/him', 'nonbinary': 'they/them'}
AGE_WORDS = {'twent': 25, 'thirt': 35, 'fort': 45, 'fift': 55, 'sixt': 65, 'sevent': 75}
# An age spelled out ("Jordan is fifty-nine", "a forty-two-year-old", "Thirty-four."), read the way
# intimacy.own_age reads one: said as what they are, as their age, or opening who they are.
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
UNITS = {word: value for value, word in enumerate('one two three four five six seven eight nine'.split(), start=1)}
_SPELLED = (rf"(eighteen|nineteen|(?:{'|'.join(TENS)})(?:[- ](?:{'|'.join(UNITS)}))?)")
SPELLED_AGE = re.compile(rf"(?:^\s*|\b(?:is|am|aged|age|turned|turning)\s+|['’](?:s|m)\s+|\ba\s+){_SPELLED}"
                         rf"(?=[-\s]*(?:years?\b|y/?o\b|and\b|but\b|[,.;!()–—]|$))", re.IGNORECASE)
# A long-lived kind's age in three or four digits, said as their age: "a 312-year-old", "312 years old", "is 312",
# "an elf, 312.".
LONG_AGE = re.compile(r"\b([1-9]\d{2,3})[- ]years?[- ]old\b|\b(?:is|am|aged|age)\s+([1-9]\d{2,3})\b(?!\s*(?:%|cm|kg|lb))"
                      r"|,\s*([1-9]\d{2,3})(?=\s*(?:[.,;]|$))")
# What the free-text appearance already says, by field: a drawn value for that field is left out.
COVERED = {
    'height_cm': r"\b(?:tall|short|petite|height|lanky|towering|\d'\s?\d|\d{3}\s?cm|feet|foot|footer|ft|inch(?:es)?)\b",
    'weight_kg': r'\b(?:weighs?|weight|lbs?|pounds|kg)\b',
    'build': r'\b(?:slim|slender|skinny|thin|lean|athletic|muscular|curvy|stocky|heavyset|chubby|plump|build|built|'
             r'wiry|broad[- ]shouldered|broad shoulders|full[- ]figured|plus[- ]size|fat|toned|petite|lanky|burly|'
             r'brawny|stout|willowy)\b',
    'skin': r'\b(?:skin|complexion|tanned)\b',
    'face': r'\b(?:oval|round|heart[- ]shaped|square|long|diamond[- ]shaped|angular|narrow) face\b|\bface shape\b',
    'jaw': r'\b(?:jaw|jawline|chin|cheekbones)\b',
    'nose': r'\bnose\b',
    'eyes': r'\beyes?\b',
    'eye_shape': r'\beyes?\b',
    'hair': r'\b(?:hair|haired|bald|shaved head|braids|dreadlocks|locs|buzz ?cut|ponytail|bun|curls|redhead|'
            r'blonde?|brunette)\b',
    'facial_hair': r'\b(?:beard|bearded|stubble|moustache|mustache|goatee|clean[- ]shaven)\b',
    'feature': r'\b(?:freckles?|freckled|dimples?|moles?|scars?|tattoos?|piercings?|pierced|glasses|birthmark)\b',
}


@functools.lru_cache(maxsize=1)
def bank() -> dict:
    return json.loads((catalog.DATA / 'looks.json').read_text(encoding='utf-8'))


def weighted(seed: str, label: str, table: dict):
    return generators.pick(seed, label, list(table), list(table.values()))


def weight_kg(seed: str, height_cm: int, build: str) -> int:
    """Their weight from height and build, held inside the bank's plausible range."""
    centre, spread = bank()['bmi'].get(build, [23.5, 1.5])
    low, high = bank()['bmi_limits']
    bmi = centre + (generators.unit(seed, 'bmi') - 0.5) * 2 * spread
    return round(min(max(bmi, low), high) * (height_cm / 100) ** 2)


def drawn(seed: str, sheet: dict, data: dict) -> dict:
    """Everything a sheet holds, from a townsperson sheet (or a companion's stand-in for one)."""
    found = dating.looks(sheet, data)
    region = dating.region(sheet)
    build = found['build']
    return {
        'age': max(18, int(sheet['age'])), 'height_cm': found['height_cm'],
        'weight_kg': weight_kg(seed, found['height_cm'], build), 'build': build,
        'skin': weighted(seed, 'skin', bank()['skin'].get(region) or bank()['skin']['default']),
        'face': weighted(seed, 'face', bank()['face']), 'jaw': weighted(seed, 'jaw', bank()['jaw']),
        'nose': weighted(seed, 'nose', bank()['nose']),
        'eyes': found['eyes'].removesuffix(' eyes'),
        'eye_shape': weighted(seed, 'eye-shape', bank()['eye_shape'].get(region) or bank()['eye_shape']['default']),
        'hair': found['hair'], 'facial_hair': found.get('beard', ''), 'feature': found['detail'],
    }


def for_sheet(sheet: dict, data: dict) -> dict:
    """A townsperson's whole sheet, with their usual style of dress; a townsperson who becomes a companion keeps it."""
    seed = sheet.get('seed', sheet['key'])
    return {**drawn(seed, sheet, data), 'style': dating.looks(sheet, data)['style']}


# A companion --------------------------------------------------------------------------------------

def described(definition: dict) -> str:
    return ' '.join(str(definition.get(key) or '') for key in ('identity', 'appearance', 'background', 'personality'))


def pronouns_of(definition: dict) -> str:
    """She, he or they, as the description speaks of them (dungeon/characters.named reads it the same way)."""
    words = re.findall(r'[a-z]+', described(definition).lower())
    she = sum(word in ('she', 'her', 'hers', 'woman', 'girl') for word in words)
    he = sum(word in ('he', 'him', 'his', 'man', 'guy') for word in words)
    return 'she/her' if she > he else 'he/him' if he > she else 'they/them'


def age_of(definition: dict, seed: str) -> int:
    """The age their identity gives ("34.", "a 28-year-old", "in her thirties"), else a seeded adult age."""
    text = str(definition.get('identity') or '').lower()
    if (found := LONG_AGE.search(text)) and long_lived(definition):
        return int(found[1] or found[2] or found[3])  # "a 312-year-old elf", "she is 312" (dungeon/world/lifespans.py)
    if found := re.search(r'\b(1[89]|[2-9]\d)\b(?!\s*(?:%|percent|minutes|hours|days|weeks|months|cats|dogs))', text):
        return int(found[1])
    if found := SPELLED_AGE.search(text):
        return spelled(found[1])
    if age := next((age for stem, age in AGE_WORDS.items() if f'{stem}ies' in text), None):
        return age
    return 24 + round(generators.unit(seed, 'looks-age') * 16)


def long_lived(definition: dict) -> bool:
    """Whether their words name a kind that lives well past a hundred (an elf, a dwarf), so a three-digit age is
    theirs."""
    from dungeon.world import lifespans
    span = lifespans.sheet_lifespan(definition)
    return span is None or span > lifespans.LONG_LIVED


def spelled(words: str) -> int:
    """'fifty-nine' as 59, 'nineteen' as 19."""
    if words in ('eighteen', 'nineteen'):
        return 18 + (words == 'nineteen')
    tens, _, unit = words.replace('-', ' ').partition(' ')
    return TENS[tens] + UNITS.get(unit, 0)


def heritage_of(definition: dict) -> str:
    """A heritage key the colouring tables know, from what their description says, or '' for the general mix."""
    text = ' '.join(re.findall(r"[a-z]+", described(definition).lower()))
    for key, words in bank()['heritage_words'].items():
        if any(re.search(rf'\b{word}\b', text) for word in words):
            return key
    return ''


def stand_in(definition: dict, seed: str) -> dict:
    """What dating.looks needs of a townsperson, from a companion's form."""
    return {'key': seed, 'seed': seed, 'age': age_of(definition, seed), 'pronouns': pronouns_of(definition),
            'heritage': heritage_of(definition), 'goals': [''], 'occupation': ''}


def covered(appearance: str) -> set[str]:
    text = (appearance or '').lower()
    return {field for field, pattern in COVERED.items() if re.search(pattern, text)}


def automatic(definition: dict, seed: str) -> dict:
    """What empty fields use: drawn from the seed, without what the appearance text already says."""
    found = drawn(seed, stand_in(definition, seed), {'era': 'modern'})
    skip = covered(definition.get('appearance', ''))
    return {field: (None if field in NUMBERS else '') if field in skip else value for field, value in found.items()}


def written(definition: dict) -> dict:
    """The fields the user set on the form."""
    own = definition.get('looks') or {}
    return {field: own[field] for field in FIELDS if own.get(field) not in (None, '')}


def for_companion(companion_id: str, definition: dict) -> dict:
    """A companion's sheet: what the user set wins, field by field; the rest is drawn from their id, and a drawn
    build or weight follows the height, weight or build the user set (`agreed`)."""
    own = written(definition)
    sheet = agreed({**automatic(definition, companion_id), **own}, own, companion_id, pronouns_of(definition))
    # The age always follows their own words: someone they describe as younger than 18 gets none drawn here.
    return {**sheet, 'age': None} if intimacy.reads_as_minor(definition) else sheet


def agreed(sheet: dict, own: dict, seed: str, pronouns: str) -> dict:
    """A user-set weight picks the build that fits it; a user-set build or height re-works a drawn weight. What
    the user set themselves is never changed, and a field the appearance text covers stays left out."""
    if not sheet.get('height_cm'):
        return sheet
    if 'weight_kg' in own and 'build' not in own and sheet.get('build'):
        return {**sheet, 'build': build_for(own['weight_kg'], sheet['height_cm'], pronouns)}
    if 'weight_kg' not in own and sheet.get('weight_kg') and own.keys() & {'build', 'height_cm'}:
        return {**sheet, 'weight_kg': weight_kg(seed, sheet['height_cm'], sheet.get('build') or '')}
    return sheet


def build_for(kg: int, cm: int, pronouns: str) -> str:
    """The build whose usual body-mass index is nearest this weight and height, among the builds townsfolk are drawn with
    for them (leaving out the ones that name a height)."""
    bmi = kg / (cm / 100) ** 2
    builds = [build for build in dating.BUILDS[dating.GENDER_OF.get(pronouns, 'nonbinary')]
              if build not in ('tall and lean', 'petite')]
    return min(builds, key=lambda build: abs(bank()['bmi'][build][0] - bmi))


# In words -----------------------------------------------------------------------------------------

def height_text(cm: int) -> str:
    inches = round(cm / 2.54)
    return f"{inches // 12}'{inches % 12}\" ({cm} cm)"


def weight_text(kg: int) -> str:
    return f'about {round(kg * 2.20462)} lb ({kg} kg)'


def age_words(age: int) -> str:
    decade, year = divmod(max(age, 20), 10)
    stage = 'early' if year <= 3 else 'mid' if year <= 6 else 'late'
    names = {2: 'twenties', 3: 'thirties', 4: 'forties', 5: 'fifties', 6: 'sixties', 7: 'seventies', 8: 'eighties'}
    return f'{stage} {names.get(decade, "nineties")}'


def height_word(cm: int, who: str) -> str:
    mean = {'woman': 162, 'man': 176}.get(who, 169)
    return 'very tall' if cm >= mean + 15 else 'tall' if cm >= mean + 8 else 'short' if cm <= mean - 8 else ''


def article(phrase: str) -> str:
    return f"{'an' if phrase[:1].lower() in 'aeiou' else 'a'} {phrase}"


# Words a picture model draws literally, as damage: a "broken nose that healed a little crooked" came back from Krea as
# fresh wounds, "a cleft chin" as a cut chin, "chipped nail polish" as chipped paint on clothes. In pictures they are
# said as the shape a camera sees now; profiles and chat keep the words and their history.
SCAR_WORDS = r'(?:(?:thin|faint|small|tiny|little|pale|old|long|short|jagged|white|silvery|deep|raised)\s+)*'
SEEN = (
    (r'\b(?:an?\s+)?(?:(?:once|old|long)[- ])?(?:broken|crooked)\s+nose(?:\s+(?:that|which)\s+(?:has\s+|had\s+)?'
     r'(?:healed|set|mended)(?:\s+(?:a\s+(?:little|bit)|slightly|badly|a\s+touch))?(?:\s+crooked)?)?',
     'a nose that bends slightly to one side'),
    (r'\b(?:an?\s+)?' + SCAR_WORDS + r'scar\s+(?:through|across|splitting)\s+(?:one|her|his|their|the|an?)\s+'
     r'(?:left\s+|right\s+)?eyebrow', 'a thin bare notch through one eyebrow'),
    (r'\b(?:an?\s+)?' + SCAR_WORDS + r'burn\s+scar\b', 'a patch of smoother, paler skin'),
    (r'\b' + SCAR_WORDS + r'burn\s+scars\b', 'patches of smoother, paler skin'),
    (r'\b(?:(?:that|which)\s+(?:has\s+|had\s+)?)?(?:long[- ])?healed(?:\s+over)?\b\s*', ''),
    (r'\b(?:an?\s+)?' + SCAR_WORDS + r'scar\b', 'a faint pale mark'),
    (r'\b' + SCAR_WORDS + r'scars\b', 'faint pale marks'),
    (r'\bscarred\b', 'marked'),
    (r'\b(?:an?\s+)?(?:deeply\s+|slightly\s+)?cleft\s+chin\b', 'a chin with a faint vertical dimple'),
    (r'\b(?:an?\s+)?(?:slightly\s+)?crooked\s+(smile|grin)\b', r'a lopsided \1'),
    (r'\b(?:slightly\s+)?crooked\s+teeth\b', 'slightly uneven teeth'),
    (r'\b(?:an?\s+)?gap-toothed\s+(smile|grin)\b', r'a \1 with a small gap between the front teeth'),
    (r'\bripped\s+jeans\b', 'faded jeans with open knees'),
    (r'\b(?:chipped|scuffed)\s+', ''),
)


def seen(text: str) -> str:
    """The text with damage words said as the shape they describe: "a broken nose that healed a little crooked" is
    "a nose that bends slightly to one side", a scar "a faint pale mark", "a cleft chin" "a chin with a faint
    vertical dimple". Only for picture prompts."""
    for pattern, said in SEEN:
        # "her broken nose" keeps its "her": the article goes with the words only where the text had one.
        text = re.sub(pattern, lambda match, said=said: match.expand(
            said if re.match(r'an?\s', match.group(0), re.IGNORECASE) else said.removeprefix('a ')), text,
            flags=re.IGNORECASE)
    return re.sub(r'\s{2,}', ' ', text)


def picture(sheet: dict, who: str) -> str:
    """The sheet as the opening of a picture's description: 'A tall, athletic woman in her early thirties with
    olive skin, an oval face, a defined jawline, a straight nose, almond-shaped hazel eyes, shoulder-length wavy
    dark brown hair and freckles.' Weight is left to the build word: an image model draws words, not numbers.
    `who` is she, he or they."""
    noun = {'she': 'woman', 'he': 'man'}.get(who, 'person')
    possessive = {'she': 'her', 'he': 'his'}.get(who, 'their')
    build = sheet.get('build') or ''
    build = bank()['build_words'].get(build, build)
    size = [word for word in (height_word(sheet['height_cm'], noun) if sheet.get('height_cm') else '', build)
            if word]
    opening = article(f"{', '.join(size)} {noun}") if size else article(noun)
    if sheet.get('age'):
        # A long-lived kind is drawn the age they look (dungeon/world/lifespans.py): "312" comes back ancient.
        opening += f" in {possessive} {age_words(sheet.get('looks_age') or sheet['age'])}"
    eyes = ' '.join(part for part in (sheet.get('eye_shape'), sheet.get('eyes')) if part)
    parts = [skin_text(sheet),
             article(f"{sheet['face']} face") if sheet.get('face') else '', sheet.get('jaw') or '', sheet.get('nose') or '',
             f'{eyes} eyes' if eyes else '', (sheet.get('hair') or '').replace(', ', ' '), sheet.get('facial_hair') or '',
             sheet.get('feature') or '', sheet.get('glasses') or '', sheet.get('nails') or '',
             sheet.get('age_signs') or '']
    parts = [seen(part) for part in parts]
    if 'nose' in parts[7] and parts[3]:
        parts[3] = ''  # the feature says how their nose looks
    parts = [part for part in parts if part]
    if not parts:
        return f'{opening[:1].upper()}{opening[1:]}.'
    listed = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
    return f'{opening[:1].upper()}{opening[1:]} with {listed}.'


def skin_text(sheet: dict) -> str:
    """'olive skin', with a tan when they have one (dungeon/life/grooming.py)."""
    if not sheet.get('skin'):
        return ''
    return f"{sheet['skin']} skin with {sheet['tan']}" if sheet.get('tan') else f"{sheet['skin']} skin"


def text(sheet: dict) -> str:
    """The sheet for their own prompt, so they can answer "how tall are you?" the way their pictures show them."""
    parts = [f"{sheet['age']} years old" if sheet.get('age') else '',
             height_text(sheet['height_cm']) if sheet.get('height_cm') else '',
             weight_text(sheet['weight_kg']) if sheet.get('weight_kg') else '',
             f"{sheet['build']} build" if sheet.get('build') else '',
             skin_text(sheet),
             f"{sheet['face']} face" if sheet.get('face') else '', sheet.get('jaw') or '', sheet.get('nose') or '',
             ' '.join(part for part in (sheet.get('eye_shape'), sheet.get('eyes'), 'eyes') if part)
             if sheet.get('eyes') or sheet.get('eye_shape') else '',
             sheet.get('hair') or '', sheet.get('facial_hair') or '', sheet.get('feature') or '',
             sheet.get('glasses') or '', sheet.get('nails') or '', sheet.get('age_signs') or '']
    return ', '.join(part for part in parts if part)


def options() -> dict:
    """Suggestions for the form's word fields."""
    skins = dict.fromkeys(skin for table in bank()['skin'].values() for skin in table)
    shapes = dict.fromkeys(shape for table in bank()['eye_shape'].values() for shape in table)
    builds = dict.fromkeys(build for table in dating.BUILDS.values() for build in table)
    eyes = dict.fromkeys(color for table in dating.EYES.values() for color in table)
    return {'build': list(builds), 'skin': list(skins), 'face': list(bank()['face']), 'jaw': list(bank()['jaw']),
            'nose': list(bank()['nose']), 'eyes': list(eyes), 'eye_shape': list(shapes),
            'facial_hair': list(dating.BEARDS), 'feature': list(dating.DETAILS + dating.MODERN_DETAILS)}
