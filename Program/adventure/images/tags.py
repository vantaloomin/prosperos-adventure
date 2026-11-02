"""Prompts as booru tags, for the SDXL anime models trained on them (Illustrious, NoobAI, Pony).

Every prompt the app writes is a paragraph for photo models: "Sett, a man in his mid thirties with tan skin, ...
He is sitting at a cafe table. He is the only person in the picture." An Illustrious model reads that as loose
words: it drew Sett as a woman, or as two half figures side by side (Vanta, 2026-10-29). These models want short
comma-separated tags, the subject count and gender first ("solo, 1boy, male focus"), quality tags at the start,
and a negative prompt of their own. The paragraph is turned into tags here, by rules and without a model, at
dispatch, after the content check has read the paragraph (adapters/comfyui.py).
"""
import re

# The quality tags each kind of model was trained with. Illustrious and NoobAI share theirs; Pony has its scores.
ILLUSTRIOUS = 'masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest'
PONY = 'score_9, score_8_up, score_7_up, source_anime'
NEGATIVE = ('lowres, worst quality, low quality, bad quality, bad anatomy, bad hands, extra digits, fewer digits, '
            'extra limbs, jpeg artifacts, signature, watermark, username, logo, text, blurry, child')
PONY_NEGATIVE = f'score_4, score_5, score_6, {NEGATIVE}'
SOLO_NEGATIVE = 'multiple people, 2boys, 2girls, multiple views, split screen, clone, duplicate'
# The other gender's tags go in the negative, since these models draw a woman unless told not to.
GENDERS = {'1boy': ('1boy, male focus', '1girl, female focus'), '1girl': ('1girl', '1boy, male focus'),
           '1other': ('1other', '')}
PONY_FILE = re.compile(r'pony|pdxl', re.IGNORECASE)

# Sentences that tell a photo model something no tag can: the reference picture's instruction, the camera.
DROPPED = re.compile(r'^(?:The attached reference picture|Shot at eye level|Slight wide-angle|Phone-camera look)')
ONLY = re.compile(r'^(She|He|They) (?:is|are) the only person in the picture$')
THIS_IS = re.compile(r'^This is (.+)$')
VIEW = re.compile(r'first-person phone photo of what')
MALE = re.compile(r'\b(?:man|guy|boy|male|gentleman|he|his|him)\b', re.IGNORECASE)
FEMALE = re.compile(r'\b(?:woman|lady|girl|female|she|her|hers)\b', re.IGNORECASE)
COMPANY = re.compile(r'\bwith (?:a |an |the |his |her |their )?(?:friends?|family|partner|date|kids?|children|everyone)'
                     r'\b|\btogether\b|\bcrowd\b|\bguests\b|\bwith [A-Z][a-z]+\b')
AGE = re.compile(r'\b(?:in (?:his|her|their) )?(?:early |mid |late |mid-)?(twenties|thirties|forties|fifties|sixties|'
                 r'seventies|eighties)\b')
OLDER = {'forties': ('mature male', 'mature female'), 'fifties': ('mature male', 'mature female'),
         'sixties': ('old man', 'old woman'), 'seventies': ('old man', 'old woman'), 'eighties': ('old man', 'old woman')}
# Joins inside a phrase that part two things a tag model reads best apart: "coat over bare chest".
JOINS = re.compile(r'\s+(?:over|with|wearing|at|under|holding|on top of)\s+|\s+and\s+(?!white\b)|'
                   r'\s+in\s+(?=(?:a|an|the)\s)')
LEADING = re.compile(r'^(?:(?:she|he|they) (?:is|are|has|have|was)\s+|(?:his|her|their) face shows\s+|wearing\s+|'
                     r'and\s+|a |an |the |his |her |their |some )+', re.IGNORECASE)
SUBJECT = re.compile(r'\b(?:man|woman|person|guy|lady|boy|girl)$')
BODY = {'tall', 'short', 'muscular', 'slim', 'slender', 'curvy', 'petite', 'athletic', 'chubby', 'plump', 'lean',
        'toned', 'stocky', 'lanky', 'broad-shouldered', 'thin', 'skinny', 'burly'}
# What the app's framings, poses and light say, as the tags these models know. A phrase can say several.
SHOTS = (
    (r'medium shot', 'cowboy shot'),
    (r'waist-up', 'upper body'),
    (r'head and shoulders portrait', 'portrait'),
    (r'close-up of the face|head and shoulders filling', 'portrait, close-up'),
    (r'^close-up$', 'close-up'),
    (r'full-body', 'full body'),
    (r'side profile', 'profile, from side'),
    (r'three-quarter view', 'three-quarter view'),
    (r'looking back over the shoulder', 'looking back'),
    (r'selfie', 'selfie, holding phone, looking at viewer'),
    (r'face and shoulders', 'portrait'),
    (r'facing the camera|looking into the lens|looking at the camera', 'looking at viewer'),
    (r'plain light grey background', 'simple background, grey background'),
    (r'plain .*background|studio background', 'simple background'),
    (r'early-morning light', 'morning, soft lighting'),
    (r'golden hour|golden evening light', 'sunset, golden hour'),
    (r'midday daylight|morning daylight', 'day, sunlight'),
    (r'late-afternoon light', 'afternoon, warm lighting'),
    (r'^night\b|street ?lights', 'night'),
    (r'\brain(?:y|-wet)?\b', 'rain'),
    (r'cold winter day', 'winter'),
    (r'summer day', 'summer'),
    (r'window light|soft natural light|natural light|soft even light|softly lit', 'soft lighting'),
    (r'lamp light|warm lamps', 'warm lighting'),
    (r'laughing', 'laughing, open mouth'),
    (r'neutral expression', 'expressionless'),
    (r'thoughtful expression', 'thinking'),
)
# Words of the photo paragraph with nothing to draw.
FILLER = re.compile(r'fictional|everyday moment|in the frame|filling the frame|turned slightly to one side|'
                    r"arm's length|front camera|nobody in focus|^view$|^photo$|^illustration$|^anime$|^anime illustration$|"
                    r'photograph|^candid$|^(?:nose|face|jaw|body)$')


def flavor(config: dict) -> str:
    """Pony's quality tags for a Pony checkpoint, Illustrious's for every other tag-trained one."""
    return 'pony' if PONY_FILE.search(str(config.get('ckpt_name') or '')) else 'illustrious'


def convert(prompt: str, negative: str, name: str | None = None, style: str | None = None,
            kind: str = 'illustrious') -> tuple[str, str]:
    """The prompt and negative prompt as tags: quality, then who (solo, 1boy, their name), then the rest in the
    paragraph's order. `style` is the line the prompt opens with (the backend's Prompt style)."""
    style = (style or '').strip().rstrip('.')
    text = prompt.strip()
    opening = ''
    if style and text.startswith(style):
        opening, text = style, text[len(style):].lstrip(' ,.')
    if kind == 'pony' and opening == ILLUSTRIOUS:
        opening = PONY  # the family's default line on a Pony checkpoint
    sentences = [part.strip().rstrip('.') for part in re.split(r'(?<=[.!?])\s+', text) if part.strip()]
    who, alone, named = None, False, (name or '').strip()
    kept = []
    for sentence in sentences:
        found = ONLY.match(sentence)
        if found:
            who, alone = {'She': '1girl', 'He': '1boy', 'They': '1other'}[found[1]], True
        elif THIS_IS.match(sentence):
            named = named or THIS_IS.match(sentence)[1]
        elif not DROPPED.match(sentence):
            kept.append(sentence)
    body = ' . '.join(kept)
    view = bool(VIEW.search(body))
    who = None if view else who or gender(body)
    alone = alone or not (view or COMPANY.search(body))
    tags = [*opening_tags(opening, kind), *subject_tags(who, alone, view), *name_tags('' if view else named),
            *age_tags(body, who), *phrase_tags(kept, named)]
    return ', '.join(unique(tags)), negative_for(negative, kind, who, alone and not view)


def gender(text: str) -> str | None:
    """1boy or 1girl from the paragraph's first gendered word, or None when it says neither."""
    male, female = MALE.search(text), FEMALE.search(text)
    if male and (not female or male.start() < female.start()):
        return '1boy'
    return '1girl' if female else None


def opening_tags(opening: str, kind: str) -> list[str]:
    """The Prompt style line as tags, without words of a photo style these models cannot use, after the model's
    quality tags when the line has none of its own."""
    quality = split(PONY if kind == 'pony' else ILLUSTRIOUS)
    own = [part for part in split(opening.lower()) if not FILLER.search(part)]
    known = set(split(ILLUSTRIOUS)) | set(split(PONY))
    return own if known & set(own) else [*quality, *own]


def subject_tags(who, alone, view) -> list[str]:
    if view:
        return ['scenery', 'no humans']
    return [*(['solo'] if alone and who else []), *split(GENDERS[who][0] if who else '')]


def name_tags(name: str) -> list[str]:
    tag = re.sub(r'[^\w\s.\'-]', '', name).strip().lower()
    return [tag] if tag else []


def age_tags(text: str, who) -> list[str]:
    found = AGE.search(text)
    older = OLDER.get(found[1]) if found else None
    if not older or who not in ('1boy', '1girl'):
        return []
    return [older[0] if who == '1boy' else older[1]]


def phrase_tags(sentences: list[str], name: str) -> list[str]:
    tags = []
    for sentence in sentences:
        for phrase in re.split(r',\s*|\s+\.\s+', sentence):
            tags.extend(tags_of(phrase, name))
    return tags


def tags_of(phrase: str, name: str) -> list[str]:
    """One phrase of the paragraph as tags: a known framing or light as its tags, else its parts, each without the
    articles, pronouns and subject words ("tall muscular man" is "tall, muscular")."""
    phrase = phrase.strip().strip('.').lower()
    shots = [tag for pattern, tags in SHOTS if re.search(pattern, phrase) for tag in split(tags)]
    if shots:
        return shots
    if not phrase or FILLER.search(phrase) or phrase == name.lower() or AGE.search(phrase) and SUBJECT.search(
            AGE.sub('', phrase).strip()):
        return []
    result = []
    for part in JOINS.split(phrase):
        part = SUBJECT.sub('', LEADING.sub('', AGE.sub('', part).strip())).strip(' .')
        words = part.split()
        result += [word for word in words if word in BODY]
        rest = ' '.join(word for word in words if word not in BODY)
        if rest and rest != name.lower() and not FILLER.search(rest):
            result.append(rest)
    return result


def negative_for(negative: str, kind: str, who, alone) -> str:
    """The model's own negative, the other gender and more people when the picture is of one person, then any
    words of the app's own negative not already there."""
    parts = split(PONY_NEGATIVE if kind == 'pony' else NEGATIVE)
    if alone:
        parts += split(SOLO_NEGATIVE)
    if who:
        parts += split(GENDERS[who][1])
    return ', '.join(unique([*parts, *split(negative)]))


def split(text: str) -> list[str]:
    return [part.strip() for part in text.split(',') if part.strip()]


def unique(tags: list[str]) -> list[str]:
    seen = set()
    return [tag for tag in tags if not (tag in seen or seen.add(tag))]
