"""Townsfolk: the people who work at and hang around the city's places, run by simple rules.

Every place in a city has a few seeded people: staff (the barista, the barkeep, the librarian) and
regulars (the jogger in the park, the old man who reads the paper at the cafe). Each has a name that
fits the city and era, an age, a home neighborhood near the place, a temperament, a quirk, a flaw, a
desire and a goal they are working toward. Nobody is stored: a person is rebuilt from their key
(`town:<city>:<place>:<n>`) the same way every time, so a city of thousands costs nothing until someone
is asked about.

What they do is decided like an old video game's townsperson: a short list of if/then/else rules
(`whereabouts`) reads the hour, the weekday, their shifts and visits, their goal and their desire, and
says where they are and what they are doing. Their goal moves week by week (`story`): a roll each week,
nudged by their temperament and dragged by their flaw, makes progress, stalls or suffers a setback, and
once enough progress is made they reach it and move on to their next goal. No model is involved.

People don't stay forever (dungeon/world/turnover.py): each spot is held by one person after another as they
move away, change jobs or retire and newcomers take their place, so who is at a place or on a street depends on
the day (by default today, by the app clock). Someone who left is still found by their key.
"""
import functools
import json
import re
from datetime import date, datetime

from dungeon.world import catalog, generators, lifespans, turnover
from dungeon.world.wording import regional

MODERN = {'modern', 'future', 'other'}
EPOCH = turnover.EPOCH  # A Monday: goals start moving from here.
MAX_WEEKS = 520
PEOPLE = (2, 3)

# Who works at or hangs around each kind of place: (modern role, period role, staff?).
REGULAR = ('regular', 'regular', False)
ROLES = {
    'cafe': (('barista', 'counter hand', True), ('owner', 'proprietor', True), REGULAR),
    'restaurant': (('server', 'server', True), ('line cook', 'cook', True), ('owner', 'proprietor', True), REGULAR),
    'bar': (('bartender', 'barkeep', True), ('bouncer', 'doorman', True), REGULAR),
    'nightlife': (('bartender', 'barkeep', True), ('DJ', 'fiddler', True), REGULAR),
    'tavern': (('bartender', 'barkeep', True), ('cook', 'cook', True), REGULAR),
    'inn': (('front desk clerk', 'innkeeper', True), ('housekeeper', 'chambermaid', True), REGULAR),
    'market': (('stall vendor', 'stallholder', True), ('butcher', 'butcher', True), REGULAR),
    'library': (('librarian', 'librarian', True), ('library assistant', 'clerk', True), REGULAR),
    'fitness': (('personal trainer', 'trainer', True), ('front desk attendant', 'attendant', True), REGULAR),
    'museum': (('docent', 'guide', True), ('security guard', 'watchman', True), REGULAR),
    'venue': (('box office clerk', 'ticket seller', True), ('stagehand', 'stagehand', True), REGULAR),
    'stadium': (('concessions worker', 'vendor', True), ('groundskeeper', 'groundskeeper', True), REGULAR),
    'shopping': (('shop clerk', 'shop assistant', True), ('store manager', 'shopkeeper', True), REGULAR),
    'landmark': (('tour guide', 'guide', True), ('ticket taker', 'gatekeeper', True), REGULAR),
    'attraction': (('tour guide', 'guide', True), ('ticket taker', 'gatekeeper', True), REGULAR),
    'temple': (('caretaker', 'sexton', True), REGULAR),
    'workshop': (('craftsperson', 'artisan', True), ('apprentice', 'apprentice', True), REGULAR),
    'docks': (('dockworker', 'dockhand', True), ('harbor clerk', "harbormaster's clerk", True), REGULAR),
    'guildhall': (('clerk', 'guild clerk', True), REGULAR),
    'square': (('street vendor', 'hawker', True), ('street musician', 'street musician', False), REGULAR),
    'vet': (('veterinarian', 'animal doctor', True), ('vet tech', "animal doctor's assistant", True), REGULAR),
    # A hamlet found out in the wild (dungeon/hexes.py hamlets): the people who live there.
    'hamlet': (('farmer', 'cottar', True), ('village elder', 'headman', True), REGULAR),
}
# An era's own titles where the period ones above don't fit it, by modern role: the 1920s have soda jerks and
# bandleaders rather than counter hands and fiddlers.
ERA_ROLES = {
    'jazz-age': {'barista': 'counter hand', 'line cook': 'short-order cook', 'DJ': 'bandleader',
                 'bouncer': 'doorman', 'front desk clerk': 'desk clerk', 'stall vendor': 'pushcart peddler',
                 'library assistant': 'library page', 'personal trainer': 'boxing coach',
                 'front desk attendant': 'attendant', 'docent': 'museum guide', 'concessions worker': 'peanut vendor',
                 'shop clerk': 'salesclerk', 'store manager': 'shopkeeper', 'craftsperson': 'tradesman',
                 'harbor clerk': 'harbor clerk', 'street vendor': 'pushcart peddler', 'morning runner': 'early walker',
                 'ticket taker': 'ticket taker'},
    'victorian': {'ticket taker': 'ticket collector'},
    'steampunk': {'ticket taker': 'ticket collector'},
    'frontier': {'ticket taker': 'ticket taker'},
}
# Titles that depend on what the place is, not only its kind, checked in order: (kinds, modern role, words found in
# the place's name, summary or tags, titles). Titles are keyed by era, then 'period' (any other era before today)
# and 'modern'; with no title for the city's era the usual one stands. So the soda jerk works at a soda fountain
# and the baker at a bakery, and the floorwalker only walks a department store's floor.
PLACE_TITLES = (
    (('cafe',), 'barista', ('soda fountain', 'drugstore', 'drug store', 'lunch counter', 'spa', 'ice cream'),
     {'jazz-age': 'soda jerk', 'modern': 'counter server'}),
    (('cafe',), 'barista', ('bakery', 'bakehouse', 'bakers', 'oven', 'pastry', 'konditorei', 'knish', 'panadería'),
     {'period': 'baker', 'modern': 'baker'}),
    (('cafe',), 'barista', ('tea room', 'tearoom', 'tea shop', 'tea parlor', 'tea parlour', 'tea garden', 'tea gardens',
                            'teas', 'lunchroom', 'coffee house', 'coffee room', 'coffee rooms', 'coffee tavern'),
     {'period': 'waiter', 'modern': 'server'}),
    (('shopping',), 'store manager', ('general store', 'mercantile'), {'period': 'storekeeper'}),
    (('shopping',), 'store manager', ('department store',),
     {'jazz-age': 'floorwalker', 'period': 'shopwalker', 'modern': 'floor manager'}),
    (('shopping',), 'store manager', ('books', 'bookshop', 'bookshops', 'bookstall', 'booksellers'),
     {'period': 'bookseller', 'modern': 'bookseller'}),
    (('shopping',), 'store manager', ('antiques',), {'period': 'antiques dealer', 'modern': 'antiques dealer'}),
    (('shopping',), 'store manager', ('apothecary', 'herbs', 'drugstore', 'chemist'),
     {'jazz-age': 'druggist', 'period': 'apothecary'}),
    (('shopping',), 'store manager', ('grocery', 'grocer', 'groceries', 'appetizing'), {'period': 'grocer'}),
    (('shopping',), 'store manager', ('chandlery',), {'period': 'ship chandler', 'modern': 'ship chandler'}),
    (('shopping',), 'store manager', ('pawnshop', 'pawnbroker'), {'period': 'pawnbroker', 'modern': 'pawnbroker'}),
    (('landmark', 'attraction'), 'tour guide', ('lighthouse',),
     {'period': 'lighthouse keeper', 'modern': 'lighthouse keeper'}),
    (('landmark', 'attraction'), 'tour guide', ('coast guard',), {'period': 'surfman', 'modern': 'coast guardsman'}),
    (('landmark', 'attraction'), 'tour guide', ('railroad', 'railway', 'depot', 'terminal'),
     {'jazz-age': 'redcap', 'period': 'porter', 'modern': 'station agent'}),
    (('landmark', 'attraction'), 'tour guide', ('church', 'meetinghouse', 'mission'),
     {'period': 'sexton', 'modern': 'caretaker'}),
    (('landmark', 'attraction'), 'tour guide', ('rides', 'amusements', 'funhouse'),
     {'period': 'barker', 'modern': 'ride operator'}),
    (('landmark', 'attraction'), 'tour guide', ('seances', 'sittings', 'spiritualism'),
     {'period': 'medium', 'modern': 'psychic'}),
    (('landmark', 'attraction'), 'ticket taker', ('gate', 'gates', 'gatehouse'), {'period': 'gatekeeper'}),
    (('landmark', 'attraction'), 'ticket taker', ('free',), {'period': 'watchman', 'modern': 'attendant'}),
)
OUTDOOR = (('groundskeeper', 'groundskeeper', True), ('dog walker', 'dog walker', False),
           ('morning runner', 'early walker', False), ('street musician', 'street musician', False), REGULAR)
for _kind in ('park', 'garden', 'trail', 'beach'):
    ROLES[_kind] = OUTDOOR

# Shift windows by the part of the day a place is open, in minutes after midnight.
SHIFTS = {'morning': (6 * 60, 14 * 60), 'afternoon': (11 * 60, 19 * 60), 'evening': (16 * 60, 24 * 60),
          'late': (18 * 60, 24 * 60), 'day': (8 * 60, 18 * 60)}
LONGEST_SHIFT = 16 * 60
VISITS = {'morning': (7 * 60 + 30, 10 * 60 + 30), 'afternoon': (12 * 60 + 30, 15 * 60 + 30), 'evening': (18 * 60, 21 * 60),
          'late': (21 * 60, 23 * 60 + 30)}
PARTS = (('morning', 5, 12), ('afternoon', 12, 17), ('evening', 17, 21), ('late', 21, 24))

TEMPERAMENTS = {
    'warm': ('warm', 'greeted everyone like an old friend', 0.0),
    'gruff': ('gruff', 'grunted a hello but softened after a minute', 0.0),
    'shy': ('shy', 'barely made eye contact at first', -0.05),
    'chatty': ('chatty', 'talked a mile a minute', 0.0),
    'deadpan': ('deadpan', 'had a bone-dry sense of humor', 0.0),
    'cheerful': ('cheerful', 'was cheerful in a way that was hard not to catch', 0.05),
    'anxious': ('anxious', 'seemed a little on edge', -0.05),
    'easygoing': ('easygoing', 'was completely unhurried about everything', 0.0),
    'driven': ('driven', 'had the look of someone with somewhere to be', 0.15),
    'dreamy': ('dreamy', 'kept drifting off mid-sentence', -0.05),
}
QUIRK_BANK = json.loads((catalog.DATA / 'quirks.json').read_text(encoding='utf-8'))['quirks']
QUIRKS = tuple(item['text'] for item in QUIRK_BANK)
# Flaws: (text, slows their goal down, setback wording with {name}).
FLAWS = {
    'proud': ('too proud to ask for help', False, '{name} turned down help they needed and paid for it'),
    'procrastinator': ('puts everything off until the last minute', True, '{name} let a deadline slip right past'),
    'spender': ('spends money as fast as it comes in', True, '{name} blew their savings on something shiny'),
    'temper': ('has a short fuse', False, '{name} lost their temper with the wrong person'),
    'gossip': ('can\'t keep a secret', False, '{name} let something slip that wasn\'t theirs to tell'),
    'stubborn': ('stubborn to a fault', False, '{name} refused to change course when they should have'),
    'doubter': ('doubts themselves constantly', True, '{name} talked themselves out of it again'),
    'pleaser': ('can\'t say no to anyone', True, '{name} spent the week doing favors for everyone else'),
    'jealous': ('gets jealous easily', False, '{name} fell out with a friend over nothing much'),
    'scattered': ('forgetful and scattered', True, '{name} forgot something important'),
    'grudge': ('holds a grudge forever', False, '{name} let an old grudge get in the way'),
    'reckless': ('acts first and thinks later', False, '{name} jumped in without thinking and it backfired'),
}
DESIRES = {
    'respect': 'to be taken seriously', 'quiet': 'a quiet, settled life', 'company': 'someone to come home to',
    'adventure': 'a little adventure before it\'s too late', 'recognition': 'to be recognized for what they do',
    'needed': 'to be needed', 'security': 'never to worry about money again', 'belonging': 'to belong somewhere',
    'escape': 'to get out of this city someday', 'family': 'to make their family proud',
}


def _more_traits():
    """The rest of the temperaments, flaws and desires live in the phrase bank (world/data/perception.json), each
    with a `town` part giving what the sheet needs, so the bank can grow them without code changes."""
    found = json.loads((catalog.DATA / 'perception.json').read_text(encoding='utf-8'))
    for key, item in found['temperaments'].items():
        if 'town' in item:
            TEMPERAMENTS.setdefault(key, (key, item['town']['impression'], item['town']['lift']))
    for key, item in found['flaws'].items():
        if 'town' in item:
            FLAWS.setdefault(key, (item['town']['text'], item['town']['slows'], item['town']['setback']))
    for key, item in found['desires'].items():
        if 'town' in item:
            DESIRES.setdefault(key, item['town']['text'])


_more_traits()
# Goals come from the bank (world/data/goals.json) as (id, (modern, period wording), steps, (place kind, part of
# day) where they practise or None, progress line, done line); lines start with the person's given name.
GOAL_BANK = json.loads((catalog.DATA / 'goals.json').read_text(encoding='utf-8'))['goals']
GOALS = tuple((item['id'], (item['text'], item['period']), item['steps'],
               tuple(item['practice']) if item['practice'] else None, item['progress'], item['done'])
              for item in GOAL_BANK)
GOAL_INTERESTS = {item['id']: item['interest'] for item in GOAL_BANK}
# How much more often a townsperson draws one of the city's own quirks or goals (its `townsfolk` block) than any
# one shared one, so a handful of them flavour about a quarter of the town.
TOWN_WEIGHT = 5.0
# An era's own wording for some goals, where the period one above doesn't fit it.
ERA_GOALS = {
    'jazz-age': {'race': 'finish the city marathon', 'band': 'get their band a real engagement at a good club',
                 'exam': 'pass a licensing exam', 'strong': 'win the amateur boxing tournament',
                 'dog': 'take in a dog of their own', 'side': 'get a little business going on the side'},
}
GOAL_KINDS = {'park': ('park', 'garden', 'trail'), 'venue': ('venue', 'tavern', 'nightlife'),
              'library': ('library',), 'cafe': ('cafe',), 'gym': ('fitness',), 'market': ('market',),
              'workshop': ('workshop',), 'museum': ('museum',), 'beach': ('beach',), 'temple': ('temple',),
              'restaurant': ('restaurant',)}
COMPANY_SPOTS = ('bar', 'tavern', 'nightlife')
BASE_PROGRESS = 0.4
SETBACK = 0.88
DRAG = 0.15


# Who they are ------------------------------------------------------------------------------------

def modern(data: dict) -> bool:
    return data.get('era', 'modern') in MODERN


def at_place(data: dict, place_id: str, day: date | None = None) -> list[dict]:
    """Everyone at this place on `day` (today when None), the same every time for the same city and day, but for the
    user (`not_you`)."""
    place = catalog.find(data, place_id)
    if not place or place not in data['places']:
        return []
    day = day or turnover.today(data)
    held = [holder(place_terms(data, place, slot, week_of(day)), slot, day) for slot in range(everyone(data, place))]
    return not_you(data, [person(data, place, index) for index in held if index is not None])


def not_you(data: dict, sheets: list[dict]) -> list[dict]:
    """Everyone but the townsperson the user became in this world (`data['you']`, dungeon/worlds.py). Every list
    of townsfolk goes through here (places, residents), so the user never meets themselves;
    `find` still names them, for their own persona."""
    you = data.get('you')
    return [sheet for sheet in sheets if sheet['key'] != you] if you else sheets


def seed_for(data: dict, key: str) -> str:
    """What a person is drawn from: their key, mixed with the companion's own town (`data['town']`, set by
    dungeon/life/network.py) so two companions in one city meet different people. Companions from before
    towns were their own have none and keep the people they already knew."""
    return f"{key}|{data['town']}" if data.get('town') else key


def drawn(sheet: dict) -> str:
    return sheet.get('seed', sheet['key'])


# A place tagged wild (deep forest, a ruin) has no seeded townsfolk; only a city's notables are found there.
WILD = 'wild'


def count(data: dict, place: dict) -> int:
    if WILD in place.get('tags', ()):
        return 0
    seed = seed_for(data, f"town:{data['id']}:{place['id']}")
    return PEOPLE[0] + int(generators.unit(seed, 'count') * (PEOPLE[1] - PEOPLE[0] + 1))


def notables_at(data: dict, place_id: str) -> list[dict]:
    """The city's named people (schema.Notable) placed here, after the seeded ones."""
    return [item for item in data.get('notables', ()) if item['place'] == place_id]


def everyone(data: dict, place: dict) -> int:
    return count(data, place) + len(notables_at(data, place['id']))


def find(data: dict, key: str) -> dict | None:
    """The person a key names in this city, or None."""
    parts = key.split(':')
    if len(parts) != 4 or parts[0] != 'town' or parts[1] != data['id'] or not parts[3].isdigit():
        return None
    index = int(parts[3])
    slot, generation = slot_of(index)
    if parts[2].startswith('~'):
        hood_id = parts[2][1:]
        if not any(hood['id'] == hood_id for hood in data['neighborhoods']) or \
                slot >= resident_count(data, hood_id) or generation and not arrival(data, parts[2], slot, generation):
            return None
        return resident(data, hood_id, index)
    place = catalog.find(data, parts[2])
    if not place or place not in data['places'] or slot >= everyone(data, place) or \
            generation and not arrival(data, place['id'], slot, generation):
        return None
    return person(data, place, index)


@generators.detached
def person(data: dict, place: dict, index: int) -> dict:
    return _build(data, place['id'], index)


def _build(data: dict, place_id: str, index: int) -> dict:
    place = catalog.find(data, place_id)
    key = f"town:{data['id']}:{place['id']}:{index}"
    seed = seed_for(data, key)
    slot, generation = slot_of(index)
    # Whoever holds a notable's spot after them (a pack that lets them go) takes over their role.
    held = _notable(data, place, slot)
    notable = None if generation else held
    role = (held['role'], held['role'], held['staff']) if held else _slot_role(data, place, slot)
    title = held['role'] if held else role_title(data, role, place)
    folk = (notable.get('kind') or lifespans.HUMAN) if notable else folk_of(data, seed)
    age = notable['age'] if notable else seeded_real_age(data, seed, False)
    life = lifespans.life_age(age, lifespans.lifespan_of(folk, data))
    name = _named(notable) if notable else generators.name(data, seed=seed, age=life)
    hoods = [place['neighborhood']] + [hood['id'] for hood in catalog.nearby(data, place['neighborhood'], 3)]
    order = goal_order(data, seed)
    sheet = {
        'key': key, 'seed': seed, 'name': name['given'], 'full': name['full'], 'pronouns': name['pronouns'], 'age': age,
        'heritage': name['culture'] or name['group'],
        'role': title, 'kind': 'staff' if role[2] else 'regular', 'staff': role[2], 'place': {'id': place['id'], 'name': place['name'], 'kind': place['kind'],
                                                   'neighborhood': place['neighborhood']},
        'home': generators.pick(seed, 'home', hoods, [3, 1, 1, 1][:len(hoods)]),
        'occupation': title if role[2] else _occupation(data, seed, life, name['pronouns']),
        'temperament': generators.pick(seed, 'temperament', sorted(TEMPERAMENTS)),
        'quirk': quirk_for(data, seed),
        'flaw': generators.pick(seed, 'flaw', sorted(FLAWS)),
        'desire': generators.pick(seed, 'desire', sorted(DESIRES)),
        'goals': order,
        'night_owl': generators.unit(seed, 'owl') < 0.25,
    }
    if folk != lifespans.HUMAN:
        sheet['folk'] = folk
    if generation:
        sheet['arrived'] = arrival(data, place['id'], slot, generation)
    if notable:
        sheet |= {'notable': notable['id'], 'about': notable['about'], 'occupation': notable['role']}
        if notable.get('wants'):
            sheet['wants'] = notable['wants']
        if notable.get('temperament') in TEMPERAMENTS:
            sheet['temperament'] = notable['temperament']
    parts = place.get('day_parts') or ['afternoon']
    if role[2]:
        # A notable who runs a place keeps it through all its hours, six days in seven (unless their entry gives
        # `part` or `days`).
        off = sorted(generators.pick(seed, f'off-{n}', list(range(7))) for n in range(1 if notable else 2))
        part = (notable.get('part') or 'open') if notable else generators.pick(seed, 'shift', parts)
        window = list(SHIFTS[part]) if part in SHIFTS else open_hours(place.get('day_parts'))
        sheet['shifts'] = {'days': (notable or {}).get('days') or [day for day in range(7) if day not in off]
                           or [0, 1, 2], 'part': part, 'window': window}
    else:
        days = sorted({generators.pick(seed, f'visit-{n}', list(range(7))) for n in range(3)})
        part = generators.pick(seed, 'visit', parts)
        sheet['visits'] = {'days': days, 'part': part, 'window': list(VISITS[part])}
    return sheet


def open_hours(parts: list[str] | None) -> list[int]:
    """The hours a place keeps, from its day parts' shifts (a tavern's afternoon to late), at most LONGEST_SHIFT
    long, ending when its last part does; a place with none keeps the day."""
    if not parts:
        return list(SHIFTS['day'])
    end = max(SHIFTS[part][1] for part in parts)
    return [max(min(SHIFTS[part][0] for part in parts), end - LONGEST_SHIFT), end]


def _notable(data: dict, place: dict, slot: int) -> dict | None:
    """Past the seeded people come the place's notables; anyone further along is drawn like the seeded ones."""
    named = notables_at(data, place['id'])[max(slot - count(data, place), 0):]
    return named[0] if slot >= count(data, place) and named else None


def _slot_role(data: dict, place: dict, slot: int) -> tuple:
    """The role a spot at a place has, drawn for its first holder: a newcomer takes the same one."""
    return _role(place, slot, seed_for(data, f"town:{data['id']}:{place['id']}:{slot}"))


def seeded_age(seed: str, resident: bool) -> int:
    """How old someone is in human terms when they turn up in town (their life age, dungeon/world/lifespans.py)."""
    middle = (generators.unit(seed, 'age-a') + generators.unit(seed, 'age-b')) / 2
    return 18 + round(middle * 66) if resident else 19 + round(middle * 52)


def folk_of(data: dict, seed: str) -> str:
    """Their kind, from the city's share of each kind or the name group their name comes from (Grandport's elves):
    human for most."""
    return generators.kind_of(data, seed)


def seeded_real_age(data: dict, seed: str, resident: bool) -> int:
    """How old someone really is when they turn up: `seeded_age` in their kind's years, so an elven newcomer is
    often centuries old."""
    return lifespans.real_age(seeded_age(seed, resident), lifespans.lifespan_of(folk_of(data, seed), data))


def lifespan_of_seed(data: dict):
    """How long whoever a seed draws lives, for turnover; None when the city has no long-lived people at all."""
    groups, mix = catalog.name_groups(data)
    if not lifespans.shares(data) and not any(groups[key].get('kind') for key in mix):
        return None
    return lambda seed: lifespans.lifespan_of(folk_of(data, seed), data)


# Who holds each spot (dungeon/world/turnover.py) -------------------------------------------------

def slot_of(index: int) -> tuple[int, int]:
    """(the spot, which holder of it) for a person's number in their key."""
    return index % turnover.STRIDE, index // turnover.STRIDE


def staffed(data: dict, place: dict, slot: int) -> bool:
    """Whether whoever holds this spot at the place works there."""
    notable = _notable(data, place, slot)
    return notable['staff'] if notable else _slot_role(data, place, slot)[2]


def place_terms(data: dict, place: dict, slot: int, until: int, last: int = turnover.MOST_GENERATIONS - 1) -> list:
    """Everyone who held this spot at the place up to week `until` (or generation `last`)."""
    notable, staff = _notable(data, place, slot), staffed(data, place, slot)

    def age_of(seed, generation):
        return notable['age'] if notable and not generation else seeded_real_age(data, seed, False)
    return _terms(data, f"town:{data['id']}:{place['id']}", slot, 'staff' if staff else 'regular', age_of, until, last,
                  bool(notable) and not notable.get('can_leave'))


def hood_terms(data: dict, hood_id: str, slot: int, until: int, last: int = turnover.MOST_GENERATIONS - 1) -> list:
    """Everyone who lived in this spot on a street up to week `until` (or generation `last`)."""
    return _terms(data, f"town:{data['id']}:~{hood_id}", slot, 'resident',
                  lambda seed, _generation: seeded_real_age(data, seed, True), until, last)


def _terms(data: dict, prefix: str, slot: int, kind: str, age_of, until: int, last: int, fixed: bool = False) -> list:
    # The user's own townsperson and companions made from townsfolk keep their spot; so does a pack's notable.
    kept = {data.get('you'), *data.get('kept', ())}

    def key(generation):
        return f'{prefix}:{slot + turnover.STRIDE * generation}'
    return turnover.terms(lambda generation: seed_for(data, key(generation)), kind, age_of,
                          lambda generation: (fixed and not generation) or key(generation) in kept, until, last,
                          data.get('era', 'modern'), lifespan_of_seed(data))


def holder(found: list, slot: int, day: date) -> int | None:
    """The number of whoever holds the spot on `day`, or None while it waits for a newcomer."""
    term = turnover.holding(found, week_of(day))
    return None if term is None else slot + turnover.STRIDE * term.generation


def arrival(data: dict, where: str, slot: int, generation: int) -> str | None:
    """The day a newcomer arrived (`where` is a place id, or '~' and a neighborhood id), or None if nobody that far
    down the line ever holds the spot."""
    if where.startswith('~'):
        found = hood_terms(data, where[1:], slot, 10 ** 9, generation)
    else:
        found = place_terms(data, catalog.find(data, where), slot, 10 ** 9, generation)
    term = found[-1] if len(found) > generation else None
    return turnover.week_day(term.arrived).isoformat() if term and term.arrived is not None else None


def terms_of(data: dict, sheet: dict, until: int) -> list:
    """Everyone who held this person's spot up to week `until`, them included."""
    slot, generation = slot_of(int(sheet['key'].rsplit(':', 1)[1]))
    if sheet.get('kind') == 'resident':
        return hood_terms(data, sheet['home'], slot, until, generation)
    return place_terms(data, catalog.find(data, sheet['place']['id']), slot, until, generation)


def gone_line(sheet: dict, data: dict, found: dict) -> str:
    """'Casey moved away from Baltimore', 'Casey left for a job elsewhere', 'Todd retired from Towson Farmers Market', 'Kola
    passed away': how someone who left (`gone`) is spoken of in the world's terms."""
    name, city = sheet['name'], data.get('name') or 'town'
    place = '' if sheet.get('kind') == 'resident' else f" from {sheet['place']['name']}"
    return {'moved': f'{name} moved away from {city}', 'new job': f'{name} left for a job elsewhere',
            'retired': f'{name} retired{place}', 'passed': f'{name} passed away'}[found['why']]


def gone(sheet: dict, data: dict, day: date) -> dict | None:
    """How and when this townsperson left town or their place, if they had by `day`: {why, day, text}."""
    if not sheet['key'].startswith('town:') or sheet['key'] == data.get('you'):
        return None
    generation = slot_of(int(sheet['key'].rsplit(':', 1)[1]))[1]
    found = terms_of(data, sheet, week_of(day))
    term = found[generation] if len(found) > generation else None
    if term is None or term.left is None or term.left > week_of(day):
        return None
    place = '' if sheet.get('kind') == 'resident' else sheet['place']['name']
    return {'why': term.why, 'day': turnover.week_day(term.left).isoformat(), 'text': turnover.gone_text(term.why, place)}


def _role(place: dict, index: int, seed: str) -> tuple:
    """The first person at a staffed place runs it day to day; the second is another role there or a regular,
    the rest are regulars or anyone else the place draws."""
    roles = ROLES.get(place['kind'], (REGULAR,))
    staffed = [role for role in roles if role[2]]
    others = [role for role in roles if not staffed or role != staffed[0]] or list(roles)
    if index == 0 and staffed:
        return staffed[0]
    if index == 1:
        return generators.pick(seed, 'role', others)
    return generators.pick(seed, 'role', [role for role in others if not role[2]] or others)


def _named(notable: dict) -> dict:
    """A notable's name in the shape generators.name gives."""
    given = notable.get('given') or notable['name'].split()[0]
    return {'given': given, 'family': notable['name'].removeprefix(given).strip(), 'full': notable['name'],
            'pronouns': notable['pronouns'], 'group': '', 'culture': None}


def role_title(data: dict, role: tuple, place: dict | None = None) -> str:
    """What the role is called in the city's era, at this place (PLACE_TITLES)."""
    era = data.get('era', '')
    for kinds, modern_role, words, titles in PLACE_TITLES:
        if place and place['kind'] in kinds and role[0] == modern_role and _mentions(place, words):
            title = titles.get(era) or titles.get('modern' if modern(data) else 'period')
            if title:
                return title
    if modern(data):
        return role[0]
    return ERA_ROLES.get(era, {}).get(role[0], role[1])


def _mentions(place: dict, words) -> bool:
    """Whether any of these words or phrases is in the place's name, summary or tags (or is its cost, 'free')."""
    text = ' '.join([place['name'], place.get('summary', ''), *place.get('tags', []), place.get('cost', '')])
    found = f" {' '.join(re.findall(r'[^\W_]+', text.casefold()))} "
    return any(f' {word} ' in found for word in words)


def _occupation(data: dict, key: str, age: int, pronouns: str | None = None) -> str:
    if age >= generators.RETIRED_AT:
        return 'retired'
    # Weighted towards the city's own industries, and stable per career: leaving one out of a city (a surf
    # instructor in Baltimore) moves only the residents who had it, not everyone else. In an era that kept work
    # by gender, the work of their side (generators.fits_side): their name's pronouns, named or not yet.
    if pronouns is None and generators.by_gender(data):
        pronouns = generators.seeded_pronouns(data, key)
    chosen = generators.town_career(data, key, pronouns=pronouns, age=age)
    return chosen['name'].lower() if chosen else ''


def town(data: dict) -> dict:
    """The city's own quirks and goals for its townsfolk (schema.Townsfolk), or none."""
    return data.get('townsfolk') or {'quirks': [], 'goals': []}


def quirk_for(data: dict, seed: str) -> str:
    """A quirk from the shared bank or, more often than any one shared quirk, the city's own."""
    own = [item['text'] for item in town(data)['quirks']]
    return regional(data, generators.pick(seed, 'quirk', [*QUIRKS, *own],
                                                  [1.0] * len(QUIRKS) + [TOWN_WEIGHT] * len(own)))


def quirk_bio(data: dict, text: str) -> str:
    """The first-person dating-profile line for a quirk, shared or the city's own."""
    found = QUIRK_BIOS.get(text) or next((bio for quirk, bio in QUIRK_BIOS.items() if regional(data, quirk) == text),
                                         None)
    return regional(data, found) if found else \
        next((item['bio'] for item in town(data)['quirks'] if item['text'] == text), '')


QUIRK_BIOS = {item['text']: item['bio'] for item in QUIRK_BANK}


def goal_bank(data: dict) -> dict[str, tuple]:
    """Every goal a townsperson here can have by id, as (id, (modern, period wording), steps, practice, progress,
    done, interest, bio): the shared bank, then the city's own (which win on a shared id)."""
    own = {item['id']: (item['id'], (item['text'], item['text']), item['steps'],
                        tuple(item['practice']) if item['practice'] else None, item['progress'], item['done'],
                        item['interest'], item['bio']) for item in town(data)['goals']}
    return SHARED_GOALS | own


SHARED_GOALS = {goal[0]: (*goal, GOAL_INTERESTS[goal[0]], item['bio']) for goal, item in zip(GOALS, GOAL_BANK, strict=True)}


def goal_order(data: dict, seed: str) -> list[str]:
    """The order someone works through goals: a seeded shuffle where the city's own goals come up more often.
    Without any, the order is the plain shuffle by each goal's draw."""
    return list(_goal_order(seed, tuple(item['id'] for item in town(data)['goals'])))


@functools.lru_cache(maxsize=8192)
def _goal_order(seed: str, own: tuple) -> tuple:
    # Every resident sorts a hundred goals by their draws, and a new day reads the same residents again and again.
    def draw(goal_id):
        roll = generators.unit(seed, 'goal', goal_id)
        return 1 - (1 - roll) ** (1 / TOWN_WEIGHT) if goal_id in own else roll
    return tuple(sorted(SHARED_GOALS | dict.fromkeys(own), key=draw))


def goal(sheet: dict, data_or_modern, number: int) -> dict:
    """Their `number`th goal (0 is the first), with its wording for the era."""
    is_modern = data_or_modern if isinstance(data_or_modern, bool) else modern(data_or_modern)
    era = '' if isinstance(data_or_modern, bool) else data_or_modern.get('era', '')
    found = goal_bank(data_or_modern if isinstance(data_or_modern, dict) else {})[sheet['goals'][number % len(sheet['goals'])]]
    goal_id, wording, steps, practice, progress, done, interest, bio = found
    text = wording[0] if is_modern else ERA_GOALS.get(era, {}).get(goal_id, wording[1])
    data = data_or_modern if isinstance(data_or_modern, dict) else None
    return {'id': goal_id, 'text': regional(data, text), 'steps': steps, 'practice': practice, 'interest': interest,
            'bio': regional(data, bio), 'progress': regional(data, progress.format(name=sheet['name'])),
            'done': regional(data, done.format(name=sheet['name']))}


# How their goal goes, week by week -------------------------------------------------------------------

def week_of(day: date) -> int:
    return (day - EPOCH).days // 7


@functools.lru_cache(maxsize=2048)
def _weeks(key: str, temperament: str, flaw: str, weeks: int, steps_key: tuple) -> tuple:
    """Each week's (goal number, progress, beat) from the epoch through `weeks`."""
    lift = TEMPERAMENTS[temperament][2] - (DRAG if FLAWS[flaw][1] else 0.0)
    number, progress, result = 0, 0, []
    for week in range(weeks + 1):
        roll = generators.unit(key, 'week', week)
        steps = steps_key[number % len(steps_key)]
        if roll < BASE_PROGRESS + lift:
            progress, beat = progress + 1, 'progress'
        elif roll >= SETBACK:
            progress, beat = max(0, progress - 1), 'setback'
        else:
            beat = 'stall'
        if progress >= steps:
            result.append((number, steps, 'achieved'))
            number, progress = number + 1, 0
            continue
        result.append((number, progress, beat))
    return tuple(result)


def story(sheet: dict, data: dict, day: date) -> dict:
    """Where their goals stand on `day`: the current goal, progress, this week's beat and goals reached. A newcomer's
    goals move from the week they arrived, so a town keeps moving long after its first people's ten years."""
    start = week_of(date.fromisoformat(sheet['arrived'])) if sheet.get('arrived') else 0
    weeks = min(max(week_of(day) - start, 0), MAX_WEEKS)
    bank = goal_bank(data)
    steps = tuple(bank[goal_id][2] for goal_id in sheet['goals'])
    history = _weeks(drawn(sheet), sheet['temperament'], sheet['flaw'], weeks, steps)
    number, progress, beat = history[-1] if week_of(day) >= start else (0, 0, 'stall')
    reached = [goal(sheet, data, n)['text'] for n in range(number)][-3:]
    if beat == 'achieved':
        finished = goal(sheet, data, number)
        return {'goal': goal(sheet, data, number + 1), 'progress': 0, 'beat': 'achieved', 'line': finished['done'],
                'reached': [*reached, finished['text']][-3:]}
    current = goal(sheet, data, number)
    line = current['progress'] if beat == 'progress' else \
        FLAWS[sheet['flaw']][2].format(name=sheet['name']) if beat == 'setback' else ''
    return {'goal': current, 'progress': progress, 'beat': beat, 'line': line, 'reached': reached}


# Where they are, by rule ---------------------------------------------------------------------------

def part_of_day(minute: int) -> str:
    hour = minute // 60
    return next((part for part, start, end in PARTS if start <= hour < end), 'late')


def inside(window, minute: int) -> bool:
    return window[0] <= minute < window[1]


def asleep(sheet: dict, minute: int) -> bool:
    bed, wake = (60, 9 * 60) if sheet['night_owl'] else (23 * 60, 6 * 60 + 30)
    return minute >= bed or minute < wake if bed > wake else bed <= minute < wake


def spot_near(data: dict, sheet: dict, kinds) -> dict | None:
    hood = sheet['home']
    near = [hood] + [item['id'] for item in catalog.nearby(data, hood, 3)]
    for place in data['places']:
        if place['kind'] in kinds and place['neighborhood'] in near:
            return place
    return None


def whereabouts(sheet: dict, data: dict, moment: datetime) -> dict:
    """Where they are and what they are doing at a local moment, decided by plain rules in order."""
    if sheet.get('kind') == 'resident':
        return resident_whereabouts(sheet, data, moment)
    minute, weekday, day = moment.hour * 60 + moment.minute, moment.weekday(), moment.date()
    here = {'place': sheet['place'], 'at_place': True}
    # A hamlet out in the wild (dungeon/hexes.py hamlets) is where its people live: at home is there.
    home = {**here, 'neighborhood': sheet['home']} if sheet['place']['kind'] == 'hamlet' else \
        {'place': None, 'at_place': False, 'neighborhood': sheet['home']}
    shifts, visits = sheet.get('shifts'), sheet.get('visits')
    state = story(sheet, data, day)
    mood = mood_for(sheet, state)
    # 1. On shift: they are at work, whatever else they would rather do.
    if shifts and weekday in shifts['days'] and inside(shifts['window'], minute):
        busy = 'run off their feet' if part_of_day(minute) in ('evening',) and weekday >= 4 else 'working'
        return {**here, 'doing': f"{busy} as the {sheet['role']}", 'mood': mood}
    # 2. Asleep.
    if asleep(sheet, minute):
        return {**home, 'doing': 'asleep', 'mood': mood}
    # 3. A regular's usual visit.
    if visits and weekday in visits['days'] and inside(visits['window'], minute):
        return {**here, 'doing': f"at their usual spot at {sheet['place']['name']}", 'mood': mood}
    # 4. Working toward their goal, where it takes them.
    practice = state['goal']['practice']
    if practice and part_of_day(minute) == practice[1] and generators.unit(drawn(sheet), 'practice', day) < 0.5:
        spot = spot_near(data, sheet, GOAL_KINDS[practice[0]])
        if spot:
            return {'place': view(spot), 'at_place': spot['id'] == sheet['place']['id'],
                    'doing': f"working on their goal: {state['goal']['text']}", 'mood': mood}
    # 5. Lonely on a weekend evening: out where people are.
    if sheet['desire'] == 'company' and weekday >= 4 and part_of_day(minute) in ('evening', 'late'):
        spot = spot_near(data, sheet, COMPANY_SPOTS)
        if spot:
            return {'place': view(spot), 'at_place': spot['id'] == sheet['place']['id'],
                    'doing': 'out, hoping to meet someone', 'mood': mood}
    # 6. Otherwise at home, or out at work if they have a job somewhere else.
    if not sheet['staff'] and sheet['occupation'] not in ('', 'retired') and weekday < 5 \
            and 9 * 60 <= minute < 17 * 60:
        return {**home, 'doing': f"at work ({sheet['occupation']})", 'mood': mood}
    return {**home, 'doing': 'at home', 'mood': mood}


def view(place: dict) -> dict:
    return {'id': place['id'], 'name': place['name'], 'kind': place['kind'], 'neighborhood': place['neighborhood']}


def mood_for(sheet: dict, state: dict) -> str:
    if state['beat'] == 'achieved':
        return 'over the moon'
    if state['beat'] == 'setback':
        return 'frustrated' if sheet['flaw'] in ('temper', 'stubborn', 'proud') else 'down'
    if state['beat'] == 'progress':
        return 'upbeat'
    return TEMPERAMENTS[sheet['temperament']][0]


def present(data: dict, place_id: str, moment: datetime) -> list[dict]:
    """The people seeded at a place who are there at this local moment."""
    return [sheet for sheet in at_place(data, place_id, moment.date()) if whereabouts(sheet, data, moment)['at_place']]


def first_impression(sheet: dict) -> str:
    return TEMPERAMENTS[sheet['temperament']][1]


def folk_label(data: dict, sheet: dict) -> str | None:
    """Their kind's name ("Vulcan", "Elf") when they aren't human (dungeon/world/lifespans.py), else None."""
    folk = sheet.get('folk')
    found = lifespans.kinds(data).get(folk) if folk and folk != lifespans.HUMAN else None
    return found['label'] if found and found.get('label') else None


def folk_words(data: dict, sheet: dict) -> str:
    """', a Vulcan' or ', an Elf' for a line about someone who isn't human; '' for a human."""
    label = folk_label(data, sheet)
    return f", {'an' if label[0].lower() in 'aeiou' else 'a'} {label}" if label else ''


def neighborhood_name(data: dict, hood_id: str) -> str:
    return next((hood['name'] for hood in data['neighborhoods'] if hood['id'] == hood_id), '')


def window_text(window) -> str:
    def clock(minute):
        return f'{minute // 60 % 24:02d}:{minute % 60:02d}'
    return f'{clock(window[0])}–{clock(window[1])}'


DAY_NAMES = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def routine_text(sheet: dict) -> str:
    plan = sheet.get('shifts') or sheet.get('visits')
    days = ', '.join(DAY_NAMES[day] for day in plan['days'])
    if sheet.get('kind') == 'resident':
        visits = f"drops in at {sheet['place']['name']} {days}, {window_text(plan['window'])}"
        commute = sheet.get('commute')
        if not commute:
            return visits
        leaves = window_text((commute['leave'], commute['leave']))[:5]
        return f"heads out to work around {leaves} on weekdays; {visits}"
    verb = 'works' if sheet.get('shifts') else 'drops in'
    return f"{verb} {days}, {window_text(plan['window'])}"


# Ordinary residents -------------------------------------------------------------------------------
#
# Every neighborhood also has its own residents: neighbors, commuters at the stop, people walking the
# dog. Like the people at places they are rebuilt from a key (`town:<city>:~<neighborhood>:<n>`) and
# never stored. Their rules: asleep, waiting at the stop on the way to work, at work, walking home, a
# regular stop at a nearby spot, working on their goal, out looking for company, the weekly shop, out
# front on a fine evening, else at home. A resident only ever goes to the few places in their `reach`,
# so finding who is at a place looks at the residents of the neighborhoods around it, not the whole city.

RESIDENTS = (40, 80)
HAUNT_KINDS = ('cafe', 'bar', 'tavern', 'restaurant', 'park', 'library', 'fitness', 'market', 'garden', 'square')
# When people leave for work (earliest, latest) and how long they are out, by the career's schedule.
COMMUTES = {'early': ((4 * 60 + 30, 6 * 60), 8 * 60 + 30), 'evening': ((15 * 60, 16 * 60 + 30), 9 * 60),
            'shift-night': ((18 * 60, 19 * 60 + 30), 12 * 60)}
COMMUTE = ((7 * 60, 8 * 60 + 45), 9 * 60 + 30)
STREET_EVENING = (17 * 60 + 30, 20 * 60)


def street(data: dict, hood_id: str) -> dict:
    """A neighborhood's streets as a place: where neighbors run into each other."""
    return {'id': f'~{hood_id}', 'name': neighborhood_name(data, hood_id), 'kind': 'street', 'neighborhood': hood_id}


def resident_count(data: dict, hood_id: str) -> int:
    return RESIDENTS[0] + int(generators.unit(seed_for(data, f"town:{data['id']}:~{hood_id}"), 'count') * (RESIDENTS[1] - RESIDENTS[0] + 1))


def area(data: dict, hood_id: str) -> dict:
    """What residents of one neighborhood have within reach: everyday spots, goal spots and the stop."""
    near = [hood_id] + [hood['id'] for hood in catalog.nearby(data, hood_id, 3)]
    local = [place for place in data['places'] if place['neighborhood'] in near]
    haunts = [place for place in local if place['kind'] in HAUNT_KINDS and place.get('cost', '$') in ('free', '$', '$$')]
    spots = {key: [view(place) for place in local if place['kind'] in kinds] for key, kinds in GOAL_KINDS.items()}
    spots['company'] = [view(place) for place in local if place['kind'] in COMPANY_SPOTS]
    spots['market'] = [view(place) for place in local if place['kind'] == 'market']
    hood = catalog.neighborhood(data, hood_id)
    lines = {item['id']: item['name'] for item in data.get('transit', [])}
    stops = [lines[item] for item in hood.get('transit', []) if item in lines]
    return {'near': near, 'haunts': haunts or local[:3], 'spots': spots, 'stops': stops}


def residents(data: dict, hood_id: str, named: bool = True, day: date | None = None) -> list[dict]:
    """A neighborhood's residents on `day` (today when None); `named=False` skips their names, for quickly checking
    where they are."""
    where = area(data, hood_id)
    return not_you(data, [resident(data, hood_id, index, where, named) for index in living(data, hood_id, day)])


def living(data: dict, hood_id: str, day: date | None = None) -> list[int]:
    """The numbers of everyone living on the neighborhood's streets on `day` (today when None), in order."""
    week = week_of(day or turnover.today(data))
    found = [(slot, turnover.holding(hood_terms(data, hood_id, slot, week), week))
             for slot in range(resident_count(data, hood_id))]
    return [slot + turnover.STRIDE * term.generation for slot, term in found if term]


def resident(data: dict, hood_id: str, index: int, where: dict | None = None, named: bool = True,
             key: str = '') -> dict:
    """A resident by their place in the neighborhood; `key` seeds someone else living there instead (a companion
    who stepped back, dungeon/life/encounters.py)."""
    where = where or area(data, hood_id)
    key = key or f"town:{data['id']}:~{hood_id}:{index}"
    seed = seed_for(data, key)
    folk = folk_of(data, seed)
    age = seeded_real_age(data, seed, True)
    life = lifespans.life_age(age, lifespans.lifespan_of(folk, data))
    occupation = _occupation(data, seed, life)
    haunt = generators.pick(seed, 'haunt', where['haunts']) if where['haunts'] else None
    place = view(haunt) if haunt else street(data, hood_id)
    order = goal_order(data, seed)
    sheet = {
        'key': key, 'seed': seed, 'name': '', 'full': '', 'pronouns': '', 'age': age, 'kind': 'resident',
        'role': occupation or 'local', 'staff': False, 'place': place, 'home': hood_id, 'occupation': occupation,
        'street': street(data, hood_id),
        'spots': {kind: generators.pick(seed, f'spot-{kind}', options) for kind, options in where['spots'].items()},
        'temperament': generators.pick(seed, 'temperament', sorted(TEMPERAMENTS)),
        'quirk': quirk_for(data, seed),
        'flaw': generators.pick(seed, 'flaw', sorted(FLAWS)),
        'desire': generators.pick(seed, 'desire', sorted(DESIRES)),
        'goals': order,
        'night_owl': generators.unit(seed, 'owl') < 0.2,
        'errand_day': int(generators.unit(seed, 'errand') * 7),
    }
    parts = (haunt or {}).get('day_parts') or ['afternoon']
    part = generators.pick(seed, 'visit', parts)
    working = occupation not in ('', 'retired')
    # Someone with a weekday job drops in on weekends, unless their spot is an evening one.
    days = [5, 6] if working and part in ('morning', 'afternoon') else list(range(7))
    sheet['visits'] = {'days': sorted({generators.pick(seed, f'visit-{n}', days) for n in range(2)}), 'part': part,
                       'window': list(VISITS[part])}
    if working:
        schedule = next((career['schedule'] for career in catalog.careers_for(data).values()
                         if career['name'].lower() == occupation), 'office')
        (earliest, latest), hours = COMMUTES.get(schedule, COMMUTE)
        leave = earliest + round(generators.unit(seed, 'leave') * (latest - earliest) / 15) * 15
        stop = generators.pick(seed, 'stop', where['stops']) if where['stops'] else None
        sheet['commute'] = {'days': [0, 1, 2, 3, 4], 'leave': leave, 'back': min(leave + hours, 24 * 60 - 20),
                            'stop': stop}
    sheet['reach'] = sorted({place['id'], sheet['street']['id'],
                             *(spot['id'] for spot in sheet['spots'].values() if spot)})
    if folk != lifespans.HUMAN:
        sheet['folk'] = folk
    if key.startswith('town:') and slot_of(index)[1]:
        sheet['arrived'] = arrival(data, f'~{hood_id}', slot_of(index)[0], slot_of(index)[1])
    if named:
        name = generators.name(data, seed=seed, age=life)
        sheet |= {'name': name['given'], 'full': name['full'], 'pronouns': name['pronouns'], 'heritage': name['culture'] or name['group']}
    return sheet


def reaching(data: dict, place_id: str, day: date | None = None) -> list[dict]:
    """Unnamed residents who might be at this place (or, for '~<neighborhood>', on its streets) on `day`."""
    if place_id.startswith('~'):
        hood_id = place_id[1:]
        return residents(data, hood_id, False, day) if any(h['id'] == hood_id for h in data['neighborhoods']) else []
    place = catalog.find(data, place_id)
    if not place or place not in data['places']:
        return []
    hoods = [place['neighborhood']] + [hood['id'] for hood in catalog.nearby(data, place['neighborhood'], 3)]
    return [sheet for hood_id in hoods for sheet in residents(data, hood_id, False, day) if place_id in sheet['reach']]


def working(sheet: dict, minute: int, weekday: int) -> str | None:
    """On a workday: what they are doing on their street on the way out or back, 'away' while at work, else None."""
    commute = sheet.get('commute')
    if not commute or weekday not in commute['days']:
        return None
    if commute['leave'] - 20 <= minute < commute['leave']:
        return f"waiting for the {commute['stop']}" if commute['stop'] else 'heading out to work'
    if commute['leave'] <= minute < commute['back']:
        return 'away'
    if commute['back'] <= minute < commute['back'] + 20:
        return 'walking home from work'
    return None


def resident_whereabouts(sheet: dict, data: dict, moment: datetime) -> dict:
    """A resident's rules, in order."""
    minute, weekday, day = moment.hour * 60 + moment.minute, moment.weekday(), moment.date()
    state = story(sheet, data, day)
    mood = mood_for(sheet, state)

    def at(place, doing):
        return {'place': place, 'at_place': place['id'] == sheet['place']['id'], 'doing': doing, 'mood': mood}

    home = {'place': None, 'at_place': False, 'neighborhood': sheet['home'], 'mood': mood}
    # 1. Asleep.
    if asleep(sheet, minute):
        return {**home, 'doing': 'asleep'}
    # 2. On the way to work, at work, on the way home.
    workday = working(sheet, minute, weekday)
    if workday == 'away':
        return {**home, 'doing': f"at work ({sheet['occupation']})"}
    if workday:
        return at(sheet['street'], workday)
    # 3. Their usual spot.
    visits = sheet['visits']
    if weekday in visits['days'] and inside(visits['window'], minute):
        return at(sheet['place'], f"at their usual spot at {sheet['place']['name']}")
    # 4. Their goal, where it takes them.
    practice = state['goal']['practice']
    spot = sheet['spots'].get(practice[0]) if practice else None
    if spot and part_of_day(minute) == practice[1] and generators.unit(drawn(sheet), 'practice', day) < 0.5:
        return at(spot, f"working on their goal: {state['goal']['text']}")
    # 5. Lonely on a weekend evening.
    spot = sheet['spots'].get('company')
    if spot and sheet['desire'] == 'company' and weekday >= 4 and part_of_day(minute) in ('evening', 'late'):
        return at(spot, 'out, hoping to meet someone')
    # 6. The weekly shop.
    spot = sheet['spots'].get('market')
    if spot and weekday == sheet['errand_day'] and 10 * 60 <= minute < 12 * 60:
        return at(spot, 'doing the weekly shop')
    # 7. Out front on an evening, else at home.
    if inside(STREET_EVENING, minute) and generators.unit(drawn(sheet), 'out front', day) < 0.3:
        doing = 'walking the dog' if 'dog' in sheet['quirk'] else 'out front, chatting with whoever passes'
        return at(sheet['street'], doing)
    return {**home, 'doing': 'at home'}

