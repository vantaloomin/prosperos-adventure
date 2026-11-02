"""Life details: the small facts and stories a townsperson can bring up, drawn by seed from a bank, no model.

Each townsperson (dungeon/world/townsfolk.py) gets, worked out from their sheet whenever asked and never stored:

- where they come from ("grew up on a farm a few hours inland", "was born and raised in Fells Point"),
- their work history: how long they have been at the job they have now and one or two jobs before it, from the
  city's careers for the era ("worked as a line cook for six years, then the kitchen closed"),
- a family detail or two, fitted to their age, maybe a pet with a name, and two small tastes or pastimes,
- a handful of stories from their past ("the time they won a pie-eating contest by accident").

People at one place, or on one street, draw their stories without replacement, so neighbours don't tell the same
ones. The companion learns these a meeting at a time (`revealed`, used by dungeon/life/encounters.py): where they
are from at the first meeting, work and a taste at the second, family and pets at the third, then one story per
meeting after that. The bank is data (world/data/life_details.json), so it can grow without code changes.
"""
import json
from functools import cache

from dungeon.world import catalog, generators, lifespans, perception, townsfolk, wording

STORIES = 4
STRETCH = 6  # Stories set aside for each person in a group, so the young can skip some.
LIKES = 2
PET_CHANCE = 0.45
SECOND_FAMILY_CHANCE = 0.5
WORK_FROM = 18
# Meetings before the companion knows each part (the first meeting is 1).
KNOWS_ORIGIN, KNOWS_WORK, KNOWS_HOME, FIRST_STORY = 1, 2, 3, 4
# How a story is told about them: "the time she won a ribbon"; with they/them pronouns the verb agrees (`agreed`).
SUBJECTS = {'she/her': 'she', 'he/him': 'he'}
THEY_VERBS = {'was': 'were', "wasn't": "weren't", 'has': 'have', "hasn't": "haven't", 'is': 'are'}
NUMBERS = ('no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve')


@cache
def bank() -> dict:
    data = json.loads((catalog.DATA / 'life_details.json').read_text(encoding='utf-8'))
    for kind in ('origins', 'family', 'pets', 'likes', 'anecdotes'):
        ids = [entry['id'] for entry in data[kind]]
        if len(ids) != len(set(ids)):
            raise ValueError(f'life_details.json repeats an id in {kind}.')
    return data


def phrases(item: dict, field: str, modern: bool) -> list[str]:
    if not modern and field in (item.get('period') or {}):
        return item['period'][field]
    return item[field]


def fits(item: dict, age: int) -> bool:
    return item.get('min_age', 0) <= age <= item.get('max_age', 200)


def years(count: int) -> str:
    words = NUMBERS[count] if count < len(NUMBERS) else str(count)
    return f"{words} year{'' if count == 1 else 's'}"


def article(word: str) -> str:
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def origin(data: dict, sheet: dict, seed: str, modern: bool) -> str:
    home = sheet.get('home') or (sheet.get('place') or {}).get('neighborhood')
    hoods = [townsfolk.neighborhood_name(data, home)] if home else []
    if home:
        hoods += [hood['name'] for hood in catalog.nearby(data, home, 3)]
    options = [item for item in bank()['origins'] if fits(item, sheet['age'])
               and ('{hood}' not in ' '.join(item['seen']) or hoods)]
    item = generators.pick(seed, 'details-origin', options)
    text = generators.pick(seed, 'details-origin-text', phrases(item, 'seen', modern))
    return text.replace('{hood}', generators.pick(seed, 'details-hood', hoods) or '').replace('{city}', data['name'])


def worked(data: dict, sheet: dict) -> list[str]:
    """The careers (lowercase names) this townsperson could have worked: in an era that kept work by gender, those of
    their side (generators.fits_side)."""
    offered = catalog.everyday(catalog.careers_for(data)).values()
    side = generators.fits_side(data, sheet.get('pronouns'))
    return sorted(career['name'].lower() for career in offered if not side or side(career))


def retired_from(data: dict, sheet: dict, seed: str) -> str | None:
    """The career (lowercase name) a retired townsperson retired from."""
    careers = worked(data, sheet)
    past = [career for career in careers if career != (sheet.get('occupation') or '').lower()]
    return generators.pick(seed, 'details-retired', past)


def work(data: dict, sheet: dict, seed: str) -> list[str]:
    """How long at the current job (staff), or retirement, and the jobs before it, newest first."""
    span = max(sheet['age'] - WORK_FROM, 0)
    careers = worked(data, sheet)
    current = (sheet.get('occupation') or '').lower()
    past = [career for career in careers if career != current]
    lines, used = [], 0
    if current == 'retired' and past:
        career = retired_from(data, sheet, seed)
        tenure = max(5, round(span * (0.4 + 0.4 * generators.unit(seed, 'details-retired-years'))))
        lines.append(f'retired after {years(tenure)} as {article(career)}')
        past.remove(career)
        used = tenure
    elif sheet.get('staff') and sheet.get('place'):
        tenure = max(1, round(min(span, 25) * generators.unit(seed, 'details-tenure')))
        lines.append(f"has worked at {sheet['place']['name']} for {years(tenure)}")
        used = tenure
    room = span - used
    count = 0 if room < 3 else 1 if room < 15 or generators.unit(seed, 'details-jobs') < 0.5 else 2
    for n in range(count):
        if not past:
            break
        career = generators.pick(seed, f'details-job-{n}', past)
        past.remove(career)
        length = 1 + round((min(room, 12) - 1) * generators.unit(seed, f'details-job-years-{n}'))
        leaving = generators.pick(seed, f'details-leaving-{n}', bank()['leaving'])
        lines.append(f"{'before that, ' if lines else ''}worked as {article(career)} for {years(length)}, then {leaving}")
        room -= length
    return lines


def family(sheet: dict, seed: str) -> list[str]:
    options = [item for item in bank()['family'] if fits(item, sheet['age'])]
    order = sorted(options, key=lambda item: generators.unit(seed, 'details-family', item['id']))
    chosen = order[:2 if generators.unit(seed, 'details-family-two') < SECOND_FAMILY_CHANCE else 1]
    return [generators.pick(seed, f"details-family-{item['id']}", item['seen']) for item in chosen]


def pet(seed: str, modern: bool) -> str | None:
    found = pet_identity(seed)
    if found is None:
        return None
    item = next(item for item in bank()['pets'] if item['id'] == found[0])
    text = generators.pick(seed, 'details-pet-text', phrases(item, 'seen', modern))
    return text.replace('{pet}', found[1])


def pet_identity(seed: str) -> tuple[str, str] | None:
    """(bank id, name) of the townsperson's pet, or None: dungeon/life/pets.py gives it a life."""
    if generators.unit(seed, 'details-pet') >= PET_CHANCE:
        return None
    item = generators.pick(seed, 'details-pet-kind', bank()['pets'])
    return item['id'], generators.pick(seed, 'details-pet-name', bank()['pet_names'])


def pet_of(sheet: dict) -> tuple[str, str] | None:
    """A townsperson's pet as pet_identity gives it; a companion living in town has none here."""
    if sheet.get('cast') or not sheet['key'].startswith('town:'):
        return None
    return pet_identity(townsfolk.drawn(sheet))


def likes(seed: str, modern: bool) -> list[str]:
    order = sorted(bank()['likes'], key=lambda item: generators.unit(seed, 'details-like', item['id']))
    return [generators.pick(seed, f"details-like-{item['id']}", phrases(item, 'seen', modern))
            for item in order[:LIKES]]


def stories(data: dict, sheet: dict, seed: str, modern: bool) -> list[str]:
    group = perception.group_of(data, sheet)
    everyone = bank()['anecdotes']
    if group:
        # Everyone in the group gets their own stretch of one shuffle, so stories don't repeat there until the
        # bank runs out; a story they are too young for is skipped within their own stretch.
        order = sorted(everyone, key=lambda item: generators.unit(group[0], 'details-story', item['id']))
        start = group[1] * STRETCH
        stretch = [order[(start + n) % len(order)] for n in range(min(STRETCH, len(order)))]
    else:
        stretch = sorted(everyone, key=lambda item: generators.unit(seed, 'details-story', item['id']))
    chosen = [item for item in stretch if fits(item, sheet['age'])][:STORIES]
    if len(chosen) < STORIES:
        spare = sorted((item for item in everyone if fits(item, sheet['age']) and item not in chosen),
                       key=lambda item: generators.unit(seed, 'details-story-spare', item['id']))
        chosen += spare[:STORIES - len(chosen)]
    return [generators.pick(seed, f"details-story-{item['id']}", phrases(item, 'told', modern)) for item in chosen]


def for_sheet(data: dict, sheet: dict) -> dict:
    """Everything there is to know about a townsperson's life so far. A companion living in town (`cast`) has their
    own character sheet instead, so gets nothing here."""
    if sheet.get('cast') or not sheet['key'].startswith('town:'):
        return {}
    seed, modern = townsfolk.drawn(sheet), townsfolk.modern(data)
    # What fits their age reads it in human terms (dungeon/world/lifespans.py): an elf of 225 is in mid-life, not
    # past every detail's age. How long they have worked keeps their real years.
    aged = {**sheet, 'age': lifespans.life_age(sheet['age'], lifespans.lifespan_of(sheet.get('folk'), data))}
    return wording.regional_all(data, {
        'origin': origin(data, aged, seed, modern), 'work': work(data, sheet, seed), 'family': family(aged, seed),
        'pet': pet(seed, modern), 'likes': likes(seed, modern), 'stories': stories(data, aged, seed, modern)})


def revealed(data: dict, sheet: dict, times: int) -> dict:
    """What a companion has picked up after `times` meetings: facts as short clauses, and the stories told."""
    found = for_sheet(data, sheet)
    if not found or times < KNOWS_ORIGIN:
        return {'facts': [], 'stories': []}
    facts = [found['origin']]
    if times >= KNOWS_WORK:
        facts += [*found['work'], found['likes'][0]]
    if times >= KNOWS_HOME:
        facts += [*found['family'], *([found['pet']] if found['pet'] else []), *found['likes'][1:]]
    told = found['stories'][:max(0, times - FIRST_STORY + 1)]
    return {'facts': facts, 'stories': told}


def newly_told(data: dict, sheet: dict, times: int) -> str | None:
    """The story told at meeting number `times`, if one was."""
    if times < FIRST_STORY:
        return None
    told = revealed(data, sheet, times)['stories']
    return told[-1] if len(told) == times - FIRST_STORY + 1 else None


def agreed(story: str, who: str) -> str:
    """A story's opening verb agreeing with "they": "they were elected", not "they was elected"."""
    first, _space, rest = story.partition(' ')
    return f"{THEY_VERBS.get(first, first)} {rest}".strip() if who == 'they' else story


def background(data: dict, sheet: dict) -> str:
    """All of it as a few sentences, for a townsperson becoming a companion (dungeon/cast.py)."""
    found = for_sheet(data, sheet)
    if not found:
        return ''
    name = sheet['name']
    parts = [f"{name} {found['origin']}."]
    if found['work']:
        parts.append(f"{name} {'; '.join(found['work'])}.")
    home = [*found['family'], *([found['pet']] if found['pet'] else [])]
    if home:
        parts.append(f"{name} {'; '.join(home)}.")
    parts.append(f"{name} {' and '.join(found['likes'])}.")
    if found['stories']:
        who = SUBJECTS.get(sheet.get('pronouns', ''), 'they')
        told = [f'{who} {agreed(story, who)}' for story in found['stories']]
        parts.append(f"Stories {name} likes to tell: the time {'; the time '.join(told)}.")
    return ' '.join(parts)
