"""Local politics in play: the town's issues and factions as they stand on the story's day, with the player's
changes, and where the people the character meets stand (dungeon/world/politics.py has the rules; ported from
Prospero's Companion, 2026-11-02).

- **The Table sets how much goes on** (rule `politics`): off, quiet (one big question, few local quarrels), true to
  life, or lively. The campaign's drama level (dungeon/happenings.py `drama`) makes local quarrels likelier and lets
  fewer of them fizzle out.
- **The world's factions are the town's first factions.** The powers that hold the town on the travel map
  (dungeon/factions.py `local`) back sides by their kind, carry pull by their tier and start from their own allies
  and rivals; the era's town groups (the temple, the watch) fill in what they leave uncovered. A win or a loss moves
  a faction's pull for a while, and issues won or lost together warm or cool two factions. Nothing here moves a
  clock or the character's standing: those stay with factions.py.
- **People take sides by their work and character**: the townsfolk who stand for the town (its split), the people
  in the scene and everyone the character has met there. The narrator is told the issues, how the town leans and
  what the people present think, and never how an open issue ends.
- **Anything can be changed** (the Talk of the town widget, with the GM view on): add an issue or put one away,
  rename it or its sides, say how far it has got or how it went, set anyone's view, add a faction, rename one,
  change its pull or members, say which side it backs, and how two factions stand. Kept per city for this campaign
  (story.clear wipes them), and not branched: a change stays when a line is rewound, as the Table's rules do.

A local issue settles by seeded dice (`settle`), with its odds and why kept in the answer, shown with the odds on.
"""
from datetime import date, datetime, timedelta

from dungeon import consequences, factions, happenings, story_people
from dungeon import table as campaign_table
from dungeon.database import decode, encode, identifier, many, optional
from dungeon.errors import DomainError, require
from dungeon.life import cards
from dungeon.world import politics, townsfolk

LEVELS = ('off', 'quiet', 'true_to_life', 'lively')
DEFAULT = 'true_to_life'
# Tests turn politics off where it would change unrelated prompts (tests/conftest.py).
ACTIVE = True
# Fizzling out, by drama: a quiet world lets more quarrels die down.
FIZZLE = (0.5, 0.3, 0.18, 0.1)
# A win or a loss moves a faction's pull for this long; issues settled this recently warm or cool factions.
PULL_DAYS, RELATION_DAYS = 180, 90
TABLES = ('politics_issues', 'politics_factions', 'politics_views', 'politics_relations')


def level(connection) -> int:
    chosen = campaign_table.rule(connection, 'politics') or DEFAULT
    return LEVELS.index(chosen) if chosen in LEVELS else LEVELS.index(DEFAULT)


def drama(connection, data: dict) -> int:
    found = happenings.drama(connection, data)
    return cards.DRAMA.index(found) if found in cards.DRAMA else 1


# --- Where ---

def powers(city_id: str, place_id: str) -> list[dict] | None:
    """The world's factions holding the town (dungeon/factions.py), or None when the place is out on the road, not in
    a town. A city on no travel map (a custom city) is a town with no world powers."""
    if city_id.endswith('-road'):
        return None  # The Road (world/data/cities/<world>-road.json): the towns not yet built out, reached on foot.
    found = happenings.where(city_id, place_id)
    if found is None:
        return []
    return factions.local(found['world'], found['node']) if found['town'] else None


def in_town(data: dict, place_id: str) -> bool:
    return bool(data.get('neighborhoods')) and powers(data['id'], place_id) is not None


# --- Stored changes ---

def stored(connection, table: str, column: str, city_id: str) -> dict[str, dict]:
    return {row[column]: {**decode(row['data']), 'origin': row['origin'], 'dismissed': bool(row['dismissed'])}
            for row in many(connection, f'SELECT * FROM {table} WHERE city_id=?', (city_id,))}


def view_overrides(connection, city_id: str) -> dict[tuple[str, str], int]:
    return {(row['issue_id'], row['person']): row['view']
            for row in many(connection, 'SELECT * FROM politics_views WHERE city_id=?', (city_id,))}


def relation_overrides(connection, city_id: str) -> dict[tuple[str, str], int]:
    return {(row['first'], row['second']): row['stance']
            for row in many(connection, 'SELECT * FROM politics_relations WHERE city_id=?', (city_id,))}


# --- Issues as they stand ---

NEVER = '9999-12-31'


def edited(issue: dict, edit: dict | None) -> dict:
    """A seeded issue with the player's changes: its title, its sides' names, how it settled, or ended early."""
    if not edit:
        return issue
    found = {**issue, 'edited': True}
    for key in ('title', 'question'):
        if edit.get(key):
            found[key] = edit[key]
    names = edit.get('sides') or []
    found['sides'] = [{**side, 'name': names[index] if index < len(names) and names[index] else side['name']}
                      for index, side in enumerate(issue['sides'])]
    for key in ('outcome', 'ended'):
        if edit.get(key) is not None:
            found[key] = edit[key]
    if edit.get('stage') and 'dates' in issue:
        found['dates'] = staged(issue['dates'], edit['stage'], date.fromisoformat(edit['stage_on']))
        found['stage_by'] = 'you'
    return found


def staged(dates: dict, stage: str, day: date) -> dict:
    """An issue's dates with `stage` reached by `day` and the stages after it pushed back, keeping their gaps."""
    at = politics.STAGES.index(stage)
    found = {key: min(value, day.isoformat()) if politics.STAGES.index(key) <= at else value
             for key, value in dates.items()}
    later = politics.STAGES[at + 1:]
    if later and found[later[0]] <= day.isoformat():
        shift = day + timedelta(days=1) - date.fromisoformat(found[later[0]])
        for key in later:
            if found[key] < NEVER:
                found[key] = (date.fromisoformat(found[key]) + shift).isoformat()
    return found


def user_issue(issue_id: str, edit: dict) -> dict:
    """An issue the player added: open from the day they added it until they end it or say how it went."""
    sides = [{'name': name, 'stand': stand, 'backers': [], 'jobs': [], 'words': []}
             for name, stand in zip(edit['sides'], edit['stands'], strict=True)]
    return {'id': issue_id, 'kind': 'local', 'template': None, 'title': edit['title'], 'question': edit['question'],
            'sides': sides, 'origin': 'user', 'real': False, 'hood': None, 'place': None, 'person': None,
            'started': edit['started'], 'outcome': edit.get('outcome'), 'ended': edit.get('ended'),
            'beats_text': {}, 'dates': user_dates(edit), 'stage_by': 'you' if edit.get('stage') else None}


def user_dates(edit: dict) -> dict:
    dates = {'whispers': edit['started'], 'open': edit['started'], 'heated': NEVER,
             'settled': edit.get('ended') or NEVER}
    return staged(dates, edit['stage'], date.fromisoformat(edit['stage_on'])) if edit.get('stage') else dates


def ended(issue: dict) -> bool:
    return issue.get('outcome') is not None or bool(issue.get('ended'))


def city_issues(connection, data: dict, day: date, level_: int, drama_: int) -> list[dict]:
    """Every issue live in the town on `day`, the era's first, then local ones newest first."""
    if not level_:
        return []
    edits = stored(connection, 'politics_issues', 'issue_id', data['id'])
    found = [edited(issue, edits.get(issue['id'])) for issue in politics.era_issues(data, day, level_)]
    found = [issue for issue in found if not edits.get(issue['id'], {}).get('dismissed')]
    seeded = [edited(issue, edits.get(issue['id'])) for issue in politics.seeded_locals(data, day, level_, drama_)]
    own = [user_issue(issue_id, edit) for issue_id, edit in edits.items() if edit['origin'] == 'user'
           and edit.get('started', '9999') <= day.isoformat()]
    local = [issue for issue in [*seeded, *own] if not edits.get(issue['id'], {}).get('dismissed')
             and politics.live(issue, day)]
    return found + sorted(local, key=lambda issue: issue['started'], reverse=True)


# --- Factions as they stand ---

def city_factions(connection, data: dict, held_by: list[dict]) -> list[dict]:
    """The town's factions with the player's changes, and the ones the player added; put-away ones left out."""
    edits = stored(connection, 'politics_factions', 'faction_id', data['id'])
    found = []
    for faction in politics.factions(data, held_by):
        edit = edits.get(faction['id']) or {}
        if not edit.get('dismissed'):
            found.append(faction_edited(faction, edit))
    for faction_id, edit in edits.items():
        if edit['origin'] == 'user' and not edit.get('dismissed'):
            found.append(faction_edited({'id': faction_id, 'name': edit['name'], 'kind': edit.get('kind') or 'faction',
                                         'tags': [], 'pull': 2, 'about': '', 'jobs': [], 'members': [], 'places': [],
                                         'allies': [], 'rivals': [], 'origin': 'user'}, edit))
    return found


def faction_edited(faction: dict, edit: dict) -> dict:
    found = {**faction, 'added': list(edit.get('added', [])), 'removed': list(edit.get('removed', [])),
             'sides': dict(edit.get('lines', {}))}
    for key in ('name', 'kind', 'about', 'pull'):
        if edit.get(key) not in (None, ''):
            found[key] = edit[key]
    found['base_pull'] = found['pull']
    return found


def belongs(person: dict, faction: dict) -> bool:
    if person['key'] in faction.get('removed', ()):
        return False
    return person['key'] in faction.get('added', ()) or politics.joins(person, faction)


def member_of(person: dict, factions_: list[dict]) -> list[dict]:
    return [faction for faction in factions_ if belongs(person, faction)]


def faction_line(faction: dict, issue: dict) -> int | None:
    """The side a faction takes: the player's say-so, else its kinds' (world/politics.py `line`)."""
    if issue['id'] in faction.get('sides', {}):
        return faction['sides'][issue['id']]
    return politics.line(faction, issue)


# --- How the town splits and how an issue settles ---

def split(issue: dict, people: list[dict], factions_: list[dict], beats: list[dict], overrides: dict) -> dict:
    """How the townsfolk who stand for the town see an issue: counts for each side and of those who don't care."""
    counts = {'first': 0, 'second': 0, 'neither': 0}
    read = with_lines(issue, factions_)
    for person in people:
        view = overrides.get((issue['id'], person['key']))
        if view is None:
            view = politics.view_of(person, read, member_of(person, factions_), beats)
        counts['first' if view > 0 else 'second' if view < 0 else 'neither'] += 1
    return counts


def with_lines(issue: dict, factions_: list[dict]) -> dict:
    """The issue as views read it, with any side a faction was told to take counted as backing it."""
    sides = [{**side, 'backers': list(side.get('backers', []))} for side in issue['sides']]
    for faction in factions_:
        if issue['id'] in faction.get('sides', {}):
            sides[faction['sides'][issue['id']]]['backers'] += faction['tags'] or [f"faction:{faction['id']}"]
    return {**issue, 'sides': sides}


def outcome_odds(issue: dict, counts: dict, factions_: list[dict], drama_: int) -> list[dict]:
    """Odds for the three ways a local issue can go, with the reasons that moved them."""
    texts = issue['beats_text']
    viewed = counts['first'] + counts['second'] or 1
    weights = [max(counts['first'] / viewed, 0.05), max(counts['second'] / viewed, 0.05)]
    reasons = [[f"{round(100 * counts['first'] / viewed)}% of people with a view wanted to "
                f"{issue['sides'][0]['stand']}"],
               [f"{round(100 * counts['second'] / viewed)}% of people with a view wanted to "
                f"{issue['sides'][1]['stand']}"]]
    for faction in factions_:
        side = faction_line(faction, issue)
        if side is not None:
            weights[side] *= 1 + 0.12 * faction['pull']
            reasons[side].append(f"{faction['name']} backed it")
    total_people = sum(counts.values()) or 1
    weights.append(FIZZLE[drama_] + 0.4 * counts['neither'] / total_people)
    reasons.append(['most people did not much care'] if counts['neither'] * 2 > total_people else [])
    labels = [texts.get('won') or f"It went the way of those who wanted to {issue['sides'][0]['stand']}.",
              texts.get('lost') or f"It went the way of those who wanted to {issue['sides'][1]['stand']}.",
              texts.get('fizzled') or 'It fizzled out.']
    total = sum(weights)
    return [{'option': index, 'odds': round(weight / total, 3), 'reasons': why, 'label': label}
            for index, (weight, why, label) in enumerate(zip(weights, reasons, labels, strict=True))]


def settle(issue: dict, counts: dict, factions_: list[dict], drama_: int) -> dict:
    options = outcome_odds(issue, counts, factions_, drama_)
    if issue.get('outcome') is not None:
        return {'options': options, 'picked': issue['outcome'], 'picked_by': 'user'}
    return {'options': options, 'picked': consequences.roll(f"politics:{issue['id']}", options), 'picked_by': 'dice'}


# --- Faction fortunes ---

def results(issues: list[dict], day: date, days: int) -> list[tuple[dict, int]]:
    """Issues settled one way or the other within `days` of `day`, with the side that won."""
    since = (day - timedelta(days=days)).isoformat()
    return [(issue, issue['settled']['picked']) for issue in issues
            if issue.get('settled') and issue['settled']['picked'] < 2
            and since <= issue['settled_on'] <= day.isoformat()]


def fortunes(factions_: list[dict], issues: list[dict], day: date) -> None:
    """Pull rises with a recent win and falls with a recent loss, one step at most either way."""
    won = results(issues, day, PULL_DAYS)
    for faction in factions_:
        score = sum((1 if side == faction_line(faction, issue) else -1) for issue, side in won
                    if faction_line(faction, issue) is not None)
        faction['pull'] = min(max(faction['base_pull'] + max(min(score, 1), -1), 1), 5)
        faction['change'] = faction['pull'] - faction['base_pull']


def stance(data: dict, first: dict, second: dict, day: date, drama_: int, won: list, overrides: dict) -> dict:
    a, b = sorted((first['id'], second['id']))
    if (a, b) in overrides:
        return {'stance': overrides[(a, b)], 'by': 'you'}
    found = politics.drifted(data, first, second, day, drama_)
    together = sum(1 if faction_line(first, issue) == faction_line(second, issue) else -1 for issue, _ in won
                   if faction_line(first, issue) is not None and faction_line(second, issue) is not None)
    return {'stance': min(max(found + max(min(together, 1), -1), -2), 2), 'by': 'world'}


def relations(data: dict, factions_: list[dict], issues: list[dict], day: date, drama_: int, overrides: dict) -> list:
    won = results(issues, day, RELATION_DAYS)
    return [{'a': first['id'], 'b': second['id'], **stance(data, first, second, day, drama_, won, overrides)}
            for index, first in enumerate(factions_) for second in factions_[index + 1:]]


# --- The whole picture ---

def town(connection, data: dict, place_id: str, day: date) -> dict:
    """The town's politics on `day`: its live issues (with how the town splits and how settled ones went), its
    factions (with pull and who they stand with) and the levels it runs at."""
    level_, drama_ = level(connection), drama(connection, data)
    held_by = powers(data['id'], place_id)
    if not data.get('neighborhoods') or held_by is None:
        level_ = 0
    factions_ = city_factions(connection, data, held_by) if level_ else []
    overrides = view_overrides(connection, data['id'])
    people = politics.sample(data, day) if level_ else []
    issues = [shown(issue, day, people, factions_, overrides, drama_)
              for issue in city_issues(connection, data, day, level_, drama_)]
    fortunes(factions_, issues, day)
    links = relations(data, factions_, issues, day, drama_, relation_overrides(connection, data['id']))
    return {'level': level_, 'drama': drama_, 'city': {'id': data['id'], 'name': data['name']}, 'issues': issues,
            'factions': factions_, 'relations': links, 'overrides': overrides}


def shown(issue: dict, day: date, people: list, factions_: list, overrides: dict, drama_: int) -> dict:
    """One issue with its stage, beats, split and, once settled, how it went."""
    if issue['kind'] == 'era':
        beats = issue['beats']
        found = {**issue, 'stage': 'ended' if ended(issue) else issue['stage']}
    else:
        beats = politics.local_beats(issue, day) if issue['origin'] != 'user' else []
        found = {**issue, 'stage': politics.stage_on(issue, day), 'beats': beats}
    found['split'] = split(issue, people, factions_, beats, overrides)
    if issue['kind'] == 'local' and (found['stage'] == 'settled' or issue.get('outcome') is not None):
        at_heat = min(issue['dates']['heated'], day.isoformat())
        counts = split(issue, people, factions_, [beat for beat in beats if beat['on'] <= at_heat], overrides)
        found['settled'] = settle(issue, counts, factions_, drama_)
        found['settled_on'] = issue.get('ended') or min(issue['dates']['settled'], day.isoformat())
        found['stage'] = 'settled'
        found['beats'] = [*beats, {'on': found['settled_on'], 'stage': 'settled', 'favors': None,
                                   'text': found['settled']['options'][found['settled']['picked']]['label']}]
    elif ended(issue):
        found['stage'] = 'settled'
        found['settled_on'] = issue.get('ended')
        found['settled'] = None
    return found


# --- People ---

def person_of(sheet: dict) -> dict:
    return politics.townsperson(sheet) | {'kind': 'townsfolk', 'role': sheet.get('occupation') or sheet.get('role')}


def met(connection, data: dict) -> list[dict]:
    """The people the character has met in this town (dungeon/story_people.py), as the view rules read them."""
    found = []
    for row in story_people.known(connection).values():
        if row['city_id'] == data['id'] and (sheet := townsfolk.find(data, row['key'])):
            found.append(person_of(sheet) | {'name': row['name'] or sheet.get('full')})
    return found


def view(person: dict, issue: dict, factions_: list[dict], overrides: dict) -> dict:
    """Someone's view on an issue: the player's say-so, else the rules'."""
    set_by_you = overrides.get((issue['id'], person['key']))
    if set_by_you is not None:
        return {'view': set_by_you, 'by': 'you'}
    return {'view': politics.view_of(person, with_lines(issue, factions_), member_of(person, factions_)),
            'by': 'world'}


def views(person: dict, picture: dict) -> dict:
    return {issue['id']: view(person, issue, picture['factions'], picture['overrides']) for issue in picture['issues']}


# --- The narrator ---

HEADING = ('## Talk of the town (kept by the game: what people here argue about and where the people in the scene '
           'stand; keep to their views, bring politics up only when it fits, and never decide how an open issue ends)')


def leaning(issue: dict) -> str:
    counts = issue['split']
    first, second = counts['first'], counts['second']
    if not first + second:
        return 'Around town hardly anyone cares'
    if abs(first - second) <= 0.1 * (first + second):
        return 'Around town people are split down the middle'
    side = issue['sides'][0 if first > second else 1]['name']
    tail = ', though most people do not much care' if counts['neither'] > first + second else ''
    return f'Around town it leans {side}{tail}'


def latest(issue: dict) -> str:
    beat = issue['beats'][-1] if issue.get('beats') else None
    if not beat:
        return ''
    day = date.fromisoformat(beat['on'])
    return f" Latest ({day:%b} {day.day}): {beat['text'].rstrip('.')}."


def backing(issue: dict, factions_: list[dict]) -> str:
    lines = []
    for index, side in enumerate(issue['sides']):
        names = [faction['name'] for faction in factions_ if faction_line(faction, issue) == index]
        if names:
            lines.append(f" Backing {side['name']}: {', '.join(names)}.")
    return ''.join(lines)


def issue_line(issue: dict, factions_: list[dict], here: list[dict]) -> str:
    if issue['stage'] == 'settled':
        how = issue['settled']['options'][issue['settled']['picked']]['label'] if issue.get('settled') else 'It is over.'
        return f"- {issue['title']} (settled): {how}"
    stage = {'whispers': ' (only a rumor so far)', 'heated': ' (it is getting heated)'}.get(issue['stage'], '')
    held = ''.join(f" {person['name']} {politics.view_text(person['views'][issue['id']]['view'], issue)}."
                   for person in here if person['views'][issue['id']]['view'])
    return (f"- {issue['title']}{stage}: {issue['question']} {leaning(issue)}.{backing(issue, factions_)}{held}"
            f"{latest(issue)}")


def prompt_text(connection, view_: dict) -> str:
    """The narrator's section for the scene: the town's live issues, the factions backing each side and the views of
    the people present, by name."""
    if not ACTIVE:
        return ''
    data = view_['data']
    picture = town(connection, data, view_['place']['id'], datetime.fromisoformat(view_['local_time']).date())
    if not picture['issues']:
        return ''
    here = [person_of(person['sheet']) | {'name': person['sheet'].get('full') or person['sheet']['name']}
            for person in view_['people'] if person['sheet'].get('key', '').startswith('town:')]
    for person in here:
        person['views'] = views(person, picture)
    lines = [issue_line(issue, picture['factions'], here) for issue in picture['issues']]
    return '\n'.join([HEADING, *lines])


# --- The widget ---

def on(connection, data: dict, place_id: str) -> bool:
    """Whether Talk of the town has anything to show here: politics on, and the story in a town."""
    return bool(level(connection)) and in_town(data, place_id)


def widget(connection, data: dict, place_id: str, day: date, dice_shown: bool) -> dict:
    """Talk of the town: the issues, the factions and where the people the character has met here stand. The odds of
    a settled issue only with the odds shown."""
    picture = town(connection, data, place_id, day)
    people = met(connection, data) if picture['level'] else []
    for person in people:
        person['views'] = views(person, picture)
        person['factions'] = [faction['id'] for faction in member_of(person, picture['factions'])]
    held = {faction['id'] for faction in politics_powers(picture)}
    found_factions = [{key: faction.get(key) for key in ('id', 'name', 'kind', 'about', 'pull', 'base_pull', 'change',
                                                         'origin')}
                      | {'members': sorted(person['key'] for person in people if faction['id'] in person['factions']),
                         'sides': faction.get('sides', {}), 'power': faction['id'] in held}
                      for faction in picture['factions']]
    issues = []
    for issue in picture['issues']:
        settled = issue.get('settled')
        if settled and not dice_shown:
            settled = {**settled, 'options': [{'option': item['option'], 'label': item['label']}
                                              for item in settled['options']]}
        issues.append({key: issue.get(key) for key in ('id', 'kind', 'title', 'question', 'sides', 'stage', 'beats',
                                                       'split', 'settled_on', 'real', 'origin', 'started', 'stage_by')}
                      | {'settled': settled, 'edited': bool(issue.get('edited')),
                         'sides': [{'name': side['name'], 'stand': side['stand']} for side in issue['sides']],
                         'lines': {faction['id']: faction_line(faction, issue) for faction in picture['factions']}})
    return {'level': picture['level'], 'level_name': LEVELS[level(connection)], 'city': picture['city'],
            'issues': issues, 'factions': found_factions, 'relations': picture['relations'],
            'people': [{key: person.get(key) for key in ('key', 'name', 'role', 'factions', 'views')}
                       for person in people]}


def politics_powers(picture: dict) -> list[dict]:
    return [faction for faction in picture['factions'] if faction.get('origin') == 'world']


# --- The player's changes ---

def require_issue(connection, data: dict, place_id: str, issue_id: str, day: date) -> dict:
    found = next((issue for issue in town(connection, data, place_id, day)['issues'] if issue['id'] == issue_id), None)
    if found is None:
        row = optional(connection, 'SELECT * FROM politics_issues WHERE city_id=? AND issue_id=?',
                       (data['id'], issue_id))
        require(row is not None, 'That issue is not going on in this town.', 404)
        return user_issue(issue_id, decode(row['data'])) if row['origin'] == 'user' else {'id': issue_id}
    return found


def save_issue(connection, city_id: str, issue_id: str, origin: str, data: dict, timestamp: str, dismissed=False):
    connection.execute(
        'INSERT INTO politics_issues (city_id, issue_id, origin, data, dismissed, created_at, updated_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(city_id, issue_id) DO UPDATE SET data=excluded.data, '
        'dismissed=excluded.dismissed, updated_at=excluded.updated_at',
        (city_id, issue_id, origin, encode(data), int(dismissed), timestamp, timestamp))


def add_issue(connection, data: dict, body: dict, day: date, timestamp: str) -> str:
    """An issue of the player's own, open from today; sides need a name, and say what each side wants."""
    names = [name.strip() for name in body['sides']]
    require(len(names) == 2 and all(names) and names[0].casefold() != names[1].casefold(),
            'Give the two sides different names.', 422)
    stands = [(stand or '').strip() or f'side with {name}'
              for name, stand in zip(names, body.get('stands') or ['', ''], strict=True)]
    issue_id = f'own-{identifier()[:12]}'
    save_issue(connection, data['id'], issue_id, 'user', {
        'title': body['title'].strip(), 'question': (body.get('question') or '').strip() or body['title'].strip(),
        'sides': names, 'stands': stands, 'started': day.isoformat()}, timestamp)
    return issue_id


def change_issue(connection, data: dict, place_id: str, issue_id: str, changes: dict, day: date,
                 timestamp: str) -> None:
    """Rename an issue or its sides, say how it settled (0 or 1 for a side, 2 fizzled; None undoes it), say how far a
    local one has got, end it, or put it away for good."""
    issue = require_issue(connection, data, place_id, issue_id, day)
    row = optional(connection, 'SELECT * FROM politics_issues WHERE city_id=? AND issue_id=?', (data['id'], issue_id))
    current = decode(row['data']) if row else {}
    origin = row['origin'] if row else 'edit'
    if 'outcome' in changes:
        require(changes['outcome'] is None or issue.get('kind') == 'local' or changes['outcome'] == 2
                or origin == 'user', 'A big question of the era does not settle; end it instead.', 422)
    for key in ('title', 'question', 'outcome'):
        if key in changes:
            current[key] = changes[key]
    if 'stage' in changes:
        require(issue.get('kind') == 'local', 'History sets how hot a big question of the era gets.', 422)
        current['stage'], current['stage_on'] = changes['stage'], day.isoformat()
    if changes.get('sides'):
        current['sides'] = [name.strip() for name in changes['sides']][:2]
    if 'ended' in changes:
        current['ended'] = day.isoformat() if changes['ended'] else None
    save_issue(connection, data['id'], issue_id, origin, current, timestamp,
               changes.get('dismissed', bool(row and row['dismissed'])))


def remove_issue(connection, data: dict, place_id: str, issue_id: str, day: date, timestamp: str) -> None:
    """Delete the player's own issue, or put a seeded one away so it never comes back."""
    if connection.execute("DELETE FROM politics_issues WHERE city_id=? AND issue_id=? AND origin='user'",
                          (data['id'], issue_id)).rowcount:
        connection.execute('DELETE FROM politics_views WHERE city_id=? AND issue_id=?', (data['id'], issue_id))
        return
    change_issue(connection, data, place_id, issue_id, {'dismissed': True}, day, timestamp)


def set_view(connection, city_id: str, issue_id: str, person: str, value: int | None, timestamp: str) -> None:
    if value is None:
        connection.execute('DELETE FROM politics_views WHERE city_id=? AND issue_id=? AND person=?',
                           (city_id, issue_id, person))
        return
    require(value in politics.VIEWS, 'A view runs from -2 to 2.', 422)
    connection.execute('INSERT INTO politics_views (city_id, issue_id, person, view, updated_at) VALUES (?, ?, ?, ?, ?) '
                       'ON CONFLICT(city_id, issue_id, person) DO UPDATE SET view=excluded.view, '
                       'updated_at=excluded.updated_at', (city_id, issue_id, person, value, timestamp))


def save_faction(connection, city_id: str, faction_id: str, origin: str, data: dict, timestamp: str,
                 dismissed=False):
    connection.execute(
        'INSERT INTO politics_factions (city_id, faction_id, origin, data, dismissed, created_at, updated_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(city_id, faction_id) DO UPDATE SET data=excluded.data, '
        'dismissed=excluded.dismissed, updated_at=excluded.updated_at',
        (city_id, faction_id, origin, encode(data), int(dismissed), timestamp, timestamp))


def add_faction(connection, data: dict, place_id: str, body: dict, timestamp: str) -> str:
    name = body['name'].strip()
    require(bool(name), 'Give the faction a name.', 422)
    taken = {faction['name'].casefold()
             for faction in city_factions(connection, data, powers(data['id'], place_id) or [])}
    require(name.casefold() not in taken, f'{data["name"]} already has {name}.', 409)
    faction_id = 'own-' + '-'.join(''.join(ch for ch in name.lower() if ch.isalnum() or ch == ' ').split())[:40]
    save_faction(connection, data['id'], faction_id, 'user', {
        'name': name, 'kind': (body.get('kind') or '').strip() or 'faction', 'about': (body.get('about') or '').strip(),
        'pull': body.get('pull') or 2}, timestamp)
    return faction_id


def change_faction(connection, data: dict, place_id: str, faction_id: str, changes: dict, timestamp: str) -> None:
    """Rename a faction, change what it is about or its pull, add or take away a member, say which side it takes on an
    issue, or put it away. A world power renamed here is renamed in this town's talk only."""
    known_ids = {faction['id'] for faction in politics.factions(data, powers(data['id'], place_id) or [])}
    row = optional(connection, 'SELECT * FROM politics_factions WHERE city_id=? AND faction_id=?',
                   (data['id'], faction_id))
    if row is None and faction_id not in known_ids:
        raise DomainError('That faction is not in this town.', 404, 'unknown_faction')
    current = decode(row['data']) if row else {}
    for key in ('name', 'kind', 'about', 'pull'):
        if changes.get(key) not in (None, ''):
            current[key] = changes[key].strip() if isinstance(changes[key], str) else changes[key]
    members(current, changes)
    if changes.get('issue'):
        lines = dict(current.get('lines', {}))
        if changes.get('side') is None:
            lines.pop(changes['issue'], None)
        else:
            lines[changes['issue']] = changes['side']
        current['lines'] = lines
    save_faction(connection, data['id'], faction_id, row['origin'] if row else 'edit', current, timestamp,
                 changes.get('dismissed', bool(row and row['dismissed'])))


def members(current: dict, changes: dict) -> None:
    added, removed = set(current.get('added', [])), set(current.get('removed', []))
    if changes.get('add_member'):
        added.add(changes['add_member'])
        removed.discard(changes['add_member'])
    if changes.get('remove_member'):
        removed.add(changes['remove_member'])
        added.discard(changes['remove_member'])
    current['added'], current['removed'] = sorted(added), sorted(removed)


def remove_faction(connection, data: dict, place_id: str, faction_id: str, timestamp: str) -> None:
    if connection.execute("DELETE FROM politics_factions WHERE city_id=? AND faction_id=? AND origin='user'",
                          (data['id'], faction_id)).rowcount:
        connection.execute('DELETE FROM politics_relations WHERE city_id=? AND (first=? OR second=?)',
                           (data['id'], faction_id, faction_id))
        return
    change_faction(connection, data, place_id, faction_id, {'dismissed': True}, timestamp)


def set_relation(connection, city_id: str, a: str, b: str, value: int | None, timestamp: str) -> None:
    require(a != b, 'Pick two different factions.', 422)
    first, second = sorted((a, b))
    if value is None:
        connection.execute('DELETE FROM politics_relations WHERE city_id=? AND first=? AND second=?',
                           (city_id, first, second))
        return
    require(value in politics.STANCES, 'How two factions stand runs from -2 to 2.', 422)
    connection.execute('INSERT INTO politics_relations (city_id, first, second, stance, updated_at) '
                       'VALUES (?, ?, ?, ?, ?) ON CONFLICT(city_id, first, second) DO UPDATE SET '
                       'stance=excluded.stance, updated_at=excluded.updated_at',
                       (city_id, first, second, value, timestamp))


def clear(connection) -> None:
    for name in TABLES:
        connection.execute(f'DELETE FROM {name}')

