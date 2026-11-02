"""Local politics: the questions a town argues about, who thinks what, and the factions behind them (ported from
Prospero's Companion, 2026-11-02; dungeon/politics.py puts it in play).

Each town has, at any time:
- a few big questions of its era (`era_issues`): Prohibition in a jazz-age city, the crown's war tax in a fantasy
  realm. Real ones (a city's real year) never settle against history; they just flare up now and then.
- a few local issues (`local_issues`), seeded from the city and the month: a template from the shared bank
  (world/data/politics.json) filled with the town's own neighbourhoods, places and townsfolk. Each runs whispers,
  open, heated, settled over three to six weeks and settles by seeded dice whose odds come from how the town splits
  and how much pull each side's factions have (dungeon/politics.py `outcome_odds`).
- factions (`factions`): first the world's own powers that hold the town (dungeon/factions.py, the realm, the guild,
  the elves past the border stones), read by their kind (`world_kinds`) and tier; then the era's town groups (the
  temple, the watch, the thieves' guild) for any part of town life no power covers; or a city's own from its
  `politics` block. How two factions stand starts from the powers' own allies and rivals, drifts month by month and
  moves with the issues they win and lose together.

Everyone has a view on every live issue (`view_of`), worked out from their job, their faction, their character and
where they live, nudged as the issue moves. Nothing here is stored and no model is involved: the same town and day
always give the same answer.
"""
import json
import re
from datetime import date, timedelta
from functools import cache

from dungeon.world import catalog, naming, townsfolk
from dungeon.world.generators import pick, unit

DATA = catalog.DATA / 'politics.json'
# Seeded issues are worked out from the start of last year: the same answer all year, whatever the story's date (a
# fantasy campaign's calendar or 2009), and no live issue changes when a new year moves the start on.
HISTORY_YEARS = 1
STAGES = ('whispers', 'open', 'heated', 'settled')
# Days from one stage of a local issue to the next: (fewest, most).
STAGE_DAYS = {'open': (4, 10), 'heated': (6, 14), 'settled': (6, 14)}
# How long a settled issue is still talked about, and how long a template rests before it comes back to a city.
TALKED_ABOUT, REST_MONTHS = 21, 8
# Local issues expected to start each month, by the Realism level (off, quiet, true to life, lively) and the drama.
LOCAL_RATE = (0.0, 0.45, 0.85, 1.3)
DRAMA_RATE = (0.6, 1.0, 1.3, 1.7)
# How many big questions of the era a city argues about at once, by the Realism level.
ERA_COUNT = (0, 1, 2, 3)
# A view: -2 strongly for the second side ... 2 strongly for the first.
VIEWS = (-2, -1, 0, 1, 2)
STANCES = (-2, -1, 0, 1, 2)
STANCE_LABELS = {-2: 'At open odds', -1: 'Rivals', 0: 'Keep their distance', 1: 'Friendly', 2: 'Allies'}
SLOT = re.compile(r'\{(office2?|institution|trade|place|hood|person)\}')


@cache
def bank() -> dict:
    return json.loads(DATA.read_text(encoding='utf-8'))


@cache
def _compiled(group: str) -> dict[str, re.Pattern]:
    return {key: re.compile(rf'\b(?:{pattern})', re.I) for key, pattern in bank()[group].items()}


def style(data: dict) -> str:
    return bank()['eras'].get(data.get('era') or 'modern', 'modern')


def words(data: dict) -> dict:
    return bank()['styles'][style(data)]


def own(data: dict) -> dict:
    """The city's own politics: its `politics` block (a package's or a custom city's)."""
    return data.get('politics') or {}


# --- A city's own block ---

LIMITS = {'factions': 20, 'questions': 10, 'issues': 30}


def clean(data: dict) -> list[str]:
    """Check a city's `politics` block in place: a bad entry is dropped with a note and the city still loads."""
    block = data.pop('politics', None)
    if block is None:
        return []
    if not isinstance(block, dict):
        return ['Dropped the politics: it needs factions, questions or issues.']
    found, notes = {'credit': str(block.get('credit') or '')[:400], 'own_factions': bool(block.get('own_factions'))}, []
    for group, check in (('factions', clean_faction), ('questions', clean_question), ('issues', clean_issue)):
        kept = [entry for entry in map(check, (block.get(group) or [])[:LIMITS[group]]) if entry]
        dropped = len((block.get(group) or [])[:LIMITS[group]]) - len(kept)
        if dropped:
            notes.append(f'Left out {dropped} political {group} that were missing a name or their two sides.')
        found[group] = kept
    if any(found[group] for group in LIMITS):
        data['politics'] = found
    return notes


def _text(value, most: int = 200) -> str:
    return str(value or '').strip()[:most]


def _ids(value) -> list[str]:
    return [str(item) for item in value if isinstance(item, str)][:40] if isinstance(value, list) else []


def clean_side(raw) -> dict | None:
    if not isinstance(raw, dict) or not _text(raw.get('name')):
        return None
    return {'name': _text(raw['name'], 40), 'stand': _text(raw.get('stand')) or f"side with {_text(raw['name'], 40)}",
            'jobs': _ids(raw.get('jobs')), 'words': _ids(raw.get('words')), 'backers': _ids(raw.get('backers')),
            'locals': bool(raw.get('locals'))}


def clean_faction(raw) -> dict | None:
    if not isinstance(raw, dict) or not _text(raw.get('id')) or not _text(raw.get('name')):
        return None
    pull = raw.get('pull') if isinstance(raw.get('pull'), int) else 2
    return {'id': _text(raw['id'], 80), 'name': _text(raw['name'], 80), 'kind': _text(raw.get('kind'), 40) or 'faction',
            'tags': _ids(raw.get('tags')), 'pull': min(max(pull, 1), 5), 'about': _text(raw.get('about'), 400),
            'jobs': _ids(raw.get('jobs')), 'members': _ids(raw.get('members')), 'places': _ids(raw.get('places')),
            'allies': _ids(raw.get('allies')), 'rivals': _ids(raw.get('rivals'))}


def clean_question(raw) -> dict | None:
    sides = [clean_side(item) for item in raw.get('sides', [])] if isinstance(raw, dict) else []
    if not isinstance(raw, dict) or not _text(raw.get('id')) or not _text(raw.get('title')) or len(sides) != 2 \
            or not all(sides):
        return None
    beats = [[_text(beat[0]), 1 if beat[1] else 0] for beat in raw.get('beats') or []
             if isinstance(beat, list) and len(beat) == 2 and _text(beat[0])]
    years = raw.get('years') if isinstance(raw.get('years'), list) and len(raw['years']) == 2 else None
    return {'id': _text(raw['id'], 80), 'title': _text(raw['title'], 80), 'question': _text(raw.get('question')),
            'sides': sides, 'beats': beats[:30], 'years': years, 'real': bool(raw.get('real'))}


def clean_issue(raw) -> dict | None:
    sides = [clean_side(item) for item in raw.get('sides', [])] if isinstance(raw, dict) else []
    beats = raw.get('beats') if isinstance(raw, dict) and isinstance(raw.get('beats'), dict) else {}
    if not isinstance(raw, dict) or not _text(raw.get('id')) or not _text(raw.get('title')) or len(sides) != 2 \
            or not all(sides):
        return None
    return {'id': _text(raw['id'], 80), 'styles': list(bank()['styles']), 'title': _text(raw['title'], 80),
            'question': _text(raw.get('question')), 'sides': sides,
            'beats': {key: _text(beats.get(key)) for key in ('whispers', 'open', 'heated', 'won', 'lost', 'fizzled')}}


# --- Factions ---

def from_power(power: dict) -> dict:
    """A world faction (dungeon/factions.py) as town politics reads it: its tags from its own `tags`, the bank's `world_tags` or its kind,
    its pull from its tier, and its own allies and rivals."""
    tags = power.get('tags') or bank()['world_tags'].get(power['id']) or bank()['world_kinds'].get(power.get('kind', ''), [])
    return {'id': power['id'], 'name': power['name'], 'kind': power.get('kind') or 'faction', 'tags': list(tags),
            'pull': min(max(power.get('tier', 1) + 1, 1), 5), 'about': power.get('summary', ''), 'jobs': [],
            'members': [], 'places': [], 'allies': list(power.get('allies', [])),
            'rivals': list(power.get('rivals', [])), 'origin': 'world'}


def factions(data: dict, powers: list[dict] = ()) -> list[dict]:
    """The town's factions: the world's powers that hold it (dungeon/factions.py `local`), the city's own, then the
    era's town groups for any part of town life they leave uncovered (a group with a tag no power and none of the
    city's own has). A city's block with `own_factions` leaves the era's out."""
    mine = own(data)
    found = [from_power(power) for power in powers]
    taken = {item['id'] for item in found}
    found += [{**item, 'origin': 'city'} for item in mine.get('factions', []) if item['id'] not in taken]
    if not mine.get('own_factions'):
        covered = {tag for item in found for tag in item['tags']}
        taken = {item['id'] for item in found}
        found += [{'about': '', 'members': [], 'places': [], 'allies': [], 'rivals': [], 'jobs': [], **item,
                   'origin': 'era'} for item in bank()['factions'][style(data)]
                  if item['id'] not in taken and not set(item['tags']) <= covered]
    return found


def base_stance(first: dict, second: dict) -> int:
    """How two factions stand before anything happens: named allies or rivals, else what their kinds make them."""
    if second['id'] in first.get('allies', ()) or first['id'] in second.get('allies', ()):
        return 2
    if second['id'] in first.get('rivals', ()) or first['id'] in second.get('rivals', ()):
        return -1
    pairs = {kind: {frozenset(pair) for pair in bank()['relations'][kind]} for kind in ('allies', 'rivals')}
    crossed = {frozenset((a, b)) for a in first['tags'] for b in second['tags'] if a != b}
    if crossed & pairs['rivals']:
        return -1
    return 1 if crossed & pairs['allies'] else 0


def line(faction: dict, issue: dict) -> int | None:
    """Which side a faction takes on an issue (0 or 1), or None when neither side is its fight."""
    overlap = [len(set(faction['tags']) & set(side.get('backers', ()))) for side in issue['sides']]
    if overlap[0] == overlap[1]:
        return None
    return 0 if overlap[0] > overlap[1] else 1


def months(first: date, last: date):
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def start_of(day: date) -> date:
    return date(day.year - HISTORY_YEARS, 1, 1)


def drifted(data: dict, first: dict, second: dict, day: date, drama: int) -> int:
    """A pair's stance after its monthly drift up to `day`: a small seeded walk that keeps drifting back toward
    where they started."""
    base = stance = base_stance(first, second)
    chance = 0.06 * DRAMA_RATE[drama]
    a, b = sorted((first['id'], second['id']))
    for year, month in months(start_of(day), day):
        seed = f"{data['id']}:{a}:{b}:{year:04d}-{month:02d}"
        roll = unit(seed, 'drift')
        if roll < chance:
            stance -= 1
        elif roll > 1 - chance:
            stance += 1
        elif stance != base and unit(seed, 'back') < 0.3:
            stance += 1 if stance < base else -1
        stance = min(max(stance, -2), 2)
    return stance


# --- Issues ---

def present_year(data: dict) -> int | None:
    return naming.present_year(data) if data.get('era') not in ('medieval', 'fantasy') else None


def in_years(question: dict, year: int | None) -> bool:
    years = question.get('years')
    return not years or (year is not None and years[0] <= year <= years[1])


def era_questions(data: dict, day: date) -> list[dict]:
    """The era's questions this city could argue about, in the order it takes them up: real questions of its year
    first (the city's own before the era's), then the city's own, then the era's in a seeded order that changes
    each year."""
    year = present_year(data)
    mine = [item for item in own(data).get('questions', []) if in_years(item, year)]
    shared = [item for item in bank()['questions'][style(data)] if in_years(item, year)
              and (data.get('setting') == 'real' or not item.get('real'))]
    dated = [item for item in [*mine, *shared] if item.get('real') and item.get('years')]
    rest = sorted((item for item in shared if item not in dated),
                  key=lambda item: unit(f"{data['id']}:{day.year}", item['id']))
    ordered = dated + [item for item in mine if item not in dated] + rest
    return list({item['id']: item for item in ordered}.values())


def fill(text: str, slots: dict) -> str:
    return SLOT.sub(lambda match: slots.get(match.group(1)) or match.group(0), text or '')


def era_issue(data: dict, question: dict, day: date) -> dict:
    """A big question as it stands on `day`: always open, flaring up with a seeded beat most months."""
    hoods, places = data.get('neighborhoods') or [{}], data.get('places') or [{}]
    beats = []
    for year, month in months(start_of(day), day):
        seed = f"{data['id']}:{question['id']}:{year:04d}-{month:02d}"
        if not question['beats'] or unit(seed, 'beat') >= 0.6:
            continue
        on = date(year, month, 1 + int(unit(seed, 'day') * 27))
        recent = {beat['text'] for beat in beats[-2:]}
        text, favors = pick(seed, 'which', [beat for beat in question['beats'] if fill(beat[0], {}) not in recent
                                            and beat[0] not in recent] or question['beats'])
        slots = {'hood': pick(seed, 'hood', hoods).get('name', ''), 'place': pick(seed, 'place', places).get('name', '')}
        if on <= day:
            beats.append({'on': on.isoformat(), 'text': fill(text, slots), 'favors': favors})
    heated = bool(beats) and beats[-1]['on'] >= (day - timedelta(days=7)).isoformat()
    return {'id': f"era-{question['id']}", 'kind': 'era', 'title': question['title'], 'question': question['question'],
            'sides': [dict(side) for side in question['sides']], 'real': question.get('real', False),
            'stage': 'heated' if heated else 'open', 'beats': beats[-6:], 'hood': None, 'origin': 'seeded',
            'settled': None, 'started': None}


def era_issues(data: dict, day: date, level: int) -> list[dict]:
    return [era_issue(data, question, day) for question in era_questions(data, day)[:ERA_COUNT[level]]]


def templates(data: dict) -> list[dict]:
    return [*own(data).get('issues', []), *(item for item in bank()['local'] if style(data) in item['styles'])]


def needs(template: dict) -> set[str]:
    text = ' '.join([template['title'], template['question'], *template['beats'].values(),
                     *(side['name'] + ' ' + side['stand'] for side in template['sides'])])
    return set(SLOT.findall(text))


def place_for(data: dict, template: dict, seed: str) -> dict | None:
    kinds = template.get('places')
    found = [place for place in data.get('places', []) if not kinds or place.get('kind') in kinds]
    return pick(seed, 'place', found)


def slots_for(data: dict, template: dict, seed: str, start: date) -> dict | None:
    """The words a template's blanks take in this city, or None when the city has nothing to fill one with."""
    wanted, said = needs(template), words(data)
    hood = pick(seed, 'hood', data.get('neighborhoods') or [])
    place = place_for(data, template, seed) if 'place' in wanted else None
    if ('place' in wanted and not place) or ({'hood', 'person'} & wanted and not hood):
        return None
    slots = {'office': said['office'][0], 'office2': pick(seed, 'office2', said['office2']),
             'institution': pick(seed, 'institution', said['institutions']), 'trade': pick(seed, 'trade', said['trades']),
             'hood': hood['name'] if hood else '', 'hood_id': hood['id'] if hood else None,
             'place': place['name'] if place else '', 'place_id': place['id'] if place else None}
    if 'person' in wanted:
        people = first_residents(data, hood['id'], start, 6)
        person = pick(seed, 'person', people)
        if not person:
            return None
        slots |= {'person': person['full'], 'person_key': person['key']}
    return slots


def stage_dates(seed: str, start: date) -> dict[str, str]:
    found, on = {'whispers': start.isoformat()}, start
    for stage in STAGES[1:]:
        low, high = STAGE_DAYS[stage]
        on += timedelta(days=low + int(unit(seed, stage) * (high - low + 1)))
        found[stage] = on.isoformat()
    return found


def local_issue(data: dict, template: dict, seed: str, start: date, slots: dict) -> dict:
    dates = stage_dates(seed, start)
    sides = [{**side, 'name': fill(side['name'], slots), 'stand': fill(side['stand'], slots)} for side in template['sides']]
    return {'id': f"local-{seed.split(':', 1)[1].replace(':', '-')}", 'kind': 'local', 'template': template['id'],
            'title': fill(template['title'], slots), 'question': fill(template['question'], slots), 'sides': sides,
            'beats_text': {key: fill(text, slots) for key, text in template['beats'].items()},
            'dates': dates, 'hood': slots.get('hood_id'), 'place': slots.get('place_id'),
            'person': slots.get('person_key'), 'origin': 'seeded', 'real': False, 'started': start.isoformat()}


def month_issues(data: dict, year: int, month: int, level: int, drama: int, rested: dict) -> list[dict]:
    seed = f"{data['id']}:{year:04d}-{month:02d}"
    expected, found = LOCAL_RATE[level] * DRAMA_RATE[drama], []
    pool = templates(data)
    for slot in (0, 1):
        if unit(seed, 'local', slot) >= expected - slot:
            continue
        fresh = [item for item in pool if rested.get(item['id'], (0, 0)) < (year, month)]
        template = pick(f'{seed}:{slot}', 'template', fresh)
        start = date(year, month, 1 + int(unit(seed, 'start', slot) * 27))
        slots = template and slots_for(data, template, f'{seed}:{slot}', start)
        if not slots:
            continue
        back = month + REST_MONTHS
        rested[template['id']] = (year + (back - 1) // 12, (back - 1) % 12 + 1)
        found.append(local_issue(data, template, f'{seed}:{slot}', start, slots))
    return found


_SEEDED: dict[tuple, list[dict]] = {}


def seeded_locals(data: dict, through: date, level: int, drama: int) -> list[dict]:
    """Every local issue started by `through`, oldest first, from the city, the month and the levels alone."""
    first = start_of(through)
    key = (data['id'], data.get('data_version', ''), data.get('town', ''), level, drama, first.isoformat(),
           through.year, through.month)
    if key not in _SEEDED:
        if len(_SEEDED) > 64:
            _SEEDED.clear()
        rested, found = {}, []
        for year, month in months(first, through):
            found += month_issues(data, year, month, level, drama, rested)
        _SEEDED[key] = found
    return [issue for issue in _SEEDED[key] if issue['started'] <= through.isoformat()]


def stage_on(issue: dict, day: date) -> str:
    today = day.isoformat()
    return [stage for stage in STAGES if issue['dates'][stage] <= today][-1]


def live(issue: dict, day: date) -> bool:
    """Started, and not settled so long ago that people have stopped talking about it."""
    today = day.isoformat()
    ended = issue.get('ended') or issue['dates']['settled']
    return issue['dates']['whispers'] <= today and (ended > today or
                                                   (date.fromisoformat(ended) + timedelta(days=TALKED_ABOUT)) > day)


def local_beats(issue: dict, day: date) -> list[dict]:
    """What has happened so far, one line a stage; the settled line says how it went once `outcome` is known."""
    found = []
    for stage in STAGES[:3]:
        if issue['dates'][stage] <= day.isoformat():
            found.append({'on': issue['dates'][stage], 'text': issue['beats_text'][stage], 'stage': stage,
                          'favors': 0 if stage != 'heated' else int(unit(issue['id'], 'heated') < 0.5)})
    return found


# --- Views ---

def strength(person: dict) -> float:
    """How hard someone holds a view: the stubborn and the driven hold them hard, the easygoing hardly at all."""
    tempers = bank()['tempers']
    factor = 1.0
    if person.get('temperament') in tempers['strong'] or person.get('flaw') in tempers['strong_flaws']:
        factor *= 1.5
    if person.get('temperament') in tempers['mild']:
        factor *= 0.6
    if 'strong' in person.get('groups', ()):
        factor *= 1.4
    return factor


def jobs_of(text: str) -> set[str]:
    return {group for group, pattern in _compiled('jobs').items() if pattern.search(text or '')}


def words_of(text: str) -> set[str]:
    return {group for group, pattern in _compiled('words').items() if pattern.search(text or '')}


def side_pull(side: dict, person: dict) -> float:
    """How much one side's reasons pull on this person: their work, the words in their description, where they live.
    A companion's own card was written on purpose, so its words count double."""
    words = 1.2 if person.get('kind') == 'companion' else 0.6
    weight = 0.9 * len(set(side.get('jobs', ())) & person['jobs']) + words * len(set(side.get('words', ())) & person['groups'])
    if side.get('locals') and person.get('home') and person['home'] == person.get('issue_hood'):
        weight += 1.2
    return weight


def change_lean(person: dict) -> float:
    """Whether someone leans toward change (the first side) or keeping things as they are."""
    tempers, lean = bank()['tempers'], 0.0
    if person.get('desire') in tempers['change'] or person['groups'] & {'rebel', 'idealist'}:
        lean += 0.35
    if person.get('desire') in tempers['keep'] or person['groups'] & {'cautious'}:
        lean -= 0.35
    age = person.get('age') or 40
    return lean + (0.2 if age < 30 else -0.2 if age > 60 else 0.0)


def faction_pull(issue: dict, member_of: list[dict]) -> float:
    pull = 0.0
    for faction in member_of:
        side = line(faction, issue)
        if side is not None:
            pull += 1.3 if side == 0 else -1.3
    return pull


def beat_shift(person: dict, issue: dict, beats: list[dict]) -> float:
    """A beat moves some people toward the side it favors, the mildly held more easily."""
    shift = 0.0
    for beat in beats:
        chance = 0.3 if issue['kind'] == 'local' else 0.12
        if unit(person['key'], issue['id'], beat['on'], 'moved') < chance:
            shift += 0.5 if beat['favors'] == 0 else -0.5
    return shift


def score(person: dict, issue: dict, member_of: list[dict], beats: list[dict]) -> float:
    """Above zero leans to the first side, below to the second; `view_of` rounds it to a view."""
    person = {**person, 'issue_hood': issue.get('hood')}
    base = (unit(person['key'], issue['id'], 'base') - 0.5) * 1.6
    leaning = side_pull(issue['sides'][0], person) - side_pull(issue['sides'][1], person) + change_lean(person)
    return (base + leaning + faction_pull(issue, member_of) + beat_shift(person, issue, beats)) * strength(person)


def view_from(value: float) -> int:
    if value >= 1.3:
        return 2
    if value >= 0.45:
        return 1
    if value > -0.45:
        return 0
    return -1 if value > -1.3 else -2


def view_of(person: dict, issue: dict, member_of: list[dict], beats: list[dict] | None = None) -> int:
    return view_from(score(person, issue, member_of, issue.get('beats', []) if beats is None else beats))


def view_text(view: int, issue: dict) -> str:
    """A view in words, about a third person: "wants to keep the country dry, and says so"."""
    if view == 0:
        return "doesn't much care either way"
    side = issue['sides'][0 if view > 0 else 1]
    return f"wants to {side['stand']}, and says so" if abs(view) == 2 else f"would rather {side['stand']}"


def view_label(view: int, issue: dict) -> str:
    """A view for a chip: "Strongly Dry", "Leans Wet", "Doesn't much care"."""
    if view == 0:
        return "Doesn't much care"
    side = issue['sides'][0 if view > 0 else 1]['name']
    return f'Strongly: {side}' if abs(view) == 2 else f'Leans: {side}'


# --- People ---

def townsperson(sheet: dict) -> dict:
    """A townsperson as the view rules read them."""
    text = ' '.join(str(sheet.get(key) or '') for key in ('occupation', 'role'))
    return {'key': sheet['key'], 'name': sheet.get('full') or sheet.get('name'), 'jobs': jobs_of(text),
            'groups': set(), 'temperament': sheet.get('temperament'), 'flaw': sheet.get('flaw'),
            'desire': sheet.get('desire'), 'age': sheet.get('age'), 'home': sheet.get('home'),
            'notable': sheet.get('notable'), 'place': (sheet.get('place') or {}).get('id'), 'staff': sheet.get('staff')}


def joins(person: dict, faction: dict) -> bool:
    """Whether someone belongs to a faction by rule: named as a member, working at its places, or by their work
    (some of those who do that work, by a seeded roll)."""
    if person.get('notable') and person['notable'] in faction.get('members', ()):
        return True
    if person.get('staff') and person.get('place') in faction.get('places', ()):
        return True
    if faction.get('name') and person.get('text') and re.search(
            rf"\b{re.escape(re.sub(r'^the ', '', faction['name'], flags=re.I))}\b", person['text'], re.I):
        return True
    return bool(set(faction.get('jobs', ())) & person['jobs']) and unit(person['key'], faction['id'], 'joins') < 0.35


def first_residents(data: dict, hood_id: str, day: date, count: int) -> list[dict]:
    """The first few people living in a neighbourhood on `day`, without building everyone else who lives there."""
    where = townsfolk.area(data, hood_id)
    numbers = townsfolk.living(data, hood_id, day)[:count + 1]
    return townsfolk.not_you(data, [townsfolk.resident(data, hood_id, index, where) for index in numbers])[:count]


_SAMPLES: dict[tuple, list[dict]] = {}


def sample(data: dict, day: date) -> list[dict]:
    """The townsfolk whose views stand for the town: the first residents of every neighbourhood, and the notables.
    Townsfolk come and go week by week (world/turnover.py), so a week's sample is kept."""
    key = (data['id'], data.get('data_version', ''), data.get('town', ''), data.get('you', ''),
           tuple(data.get('kept', ())), townsfolk.week_of(day))
    if key not in _SAMPLES:
        if len(_SAMPLES) > 32:
            _SAMPLES.clear()
        people = []
        for hood in data.get('neighborhoods', []):
            people += first_residents(data, hood['id'], day, 5)
        people += [found for key in notable_keys(data).values() if (found := townsfolk.find(data, key))]
        _SAMPLES[key] = [townsperson(sheet) for sheet in people]
    return _SAMPLES[key]


def notable_keys(data: dict) -> dict[str, str]:
    """Each of the city's notables by id, with the key they have in this town: their spot comes after the seeded
    people at their place."""
    keys = {}
    for place in data.get('places', ()):
        seeded = townsfolk.count(data, place)
        for offset, notable in enumerate(townsfolk.notables_at(data, place['id'])):
            keys[notable['id']] = f"town:{data['id']}:{place['id']}:{seeded + offset}"
    return keys
