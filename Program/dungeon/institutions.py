"""Institutions: a school, a guild, an army the character belongs to (requirements "Quests and factions": institutions
are factions, their demands are quests, the result is a track; docs/story.md "Institutions").

Each world's institutions are in world/data/institutions/<world>.json (or its package's engine data).

- **Enrolment.** A premade's `enrolled` names the institution and classes they start in; a character made in a
  world with a `default` institution starts in it with its `core` classes. The player can join or leave later.
- **Terms and the class schedule.** Classes meet on fixed days and hours during each term (month and day, every
  year, or once on set dates). When the story clock passes a class's start while the character is enrolled in it, they were there if the
  scene is at the class's place (or anywhere in the institution's town when the class names no place), and missed it
  otherwise. Skipping is a real choice: each class missed is in the record and pulls the term's attendance down.
- **Demands are quests.** Recurring demands (`every_days`: assignments, labs, club duties, a guild's dues) and
  once-a-term ones (`week`: exams) open as quests with deadlines on the story clock, tied to the institution.
  The Continuity model decides whether each is done, as for any quest (dungeon/quests.py).
- **Grades.** Each settled demand is a mark (done 90, failed 60, missed 0), weighted; attendance is one more mark
  with its own weight. The term's weighted average gives a letter and a grade point (A 4.0 to F 0). A demand failed
  or missed costs standing with the institution's faction; one done earns the work's share of the tier track like
  any job (dungeon/tiers.py).
- **The narrator is told** what is on today (and when), what is due and how the character's grades stand, and never
  invents a class or a deadline that is not here.

Enrolment, attendance and grades are game state, branched with the story (dungeon/timeline.py SAVED).
"""
import re
from datetime import date, datetime, timedelta

from dungeon import factions, record, world_data
from dungeon.database import decode, encode, many, optional

DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
MARKS = {'done': 90, 'failed': 60, 'missed': 0}
LETTERS = ((90, 'A', 4.0), (80, 'B', 3.0), (70, 'C', 2.0), (60, 'D', 1.0), (0, 'F', 0.0))
ATTENDANCE_WEIGHT = 2
# A long sleep or journey checks at most this much of the schedule.
MOST_DAYS = 21
DUE_HOUR = 9
SOON_HOURS = 3


@world_data.memo
def data(world: str) -> dict:
    return world_data.read('institutions', world) or {'institutions': []}


def institutions(world: str) -> list[dict]:
    return data(world)['institutions']


def find(world: str, institution_id: str) -> dict | None:
    return next((item for item in institutions(world) if item['id'] == institution_id), None)


# Terms and classes --------------------------------------------------------------------------------

def _day(year: int, month_day: str) -> date:
    month, day = (int(part) for part in month_day.split('-'))
    return date(year, month, day)


def term_at(institution: dict, when: date) -> dict | None:
    """The term running on a day: its name with the year, and its first and last days. A term with `start` and `end`
    dates runs once; one with `from` and `to` (month and day) runs every year."""
    for term in institution.get('terms', []):
        if 'start' in term:
            start, end = date.fromisoformat(term['start']), date.fromisoformat(term['end'])
            if start <= when <= end:
                return {'name': term['name'], 'start': start, 'end': end}
            continue
        for year in (when.year - 1, when.year):
            start = _day(year, term['from'])
            end = _day(year + (1 if term['to'] < term['from'] else 0), term['to'])
            if start <= when <= end:
                return {'name': f"{term['name']} {start.year}", 'start': start, 'end': end}
    return None


def class_times(institution: dict, chosen: list[str], start: datetime, end: datetime) -> list[tuple[dict, datetime]]:
    """Each meeting of the chosen classes that begins after `start` and by `end`, in term, in order."""
    found = []
    day = start.date()
    last = min(end.date(), day + timedelta(days=MOST_DAYS))
    while day <= last:
        if term_at(institution, day):
            for item in institution.get('classes', []):
                if item['id'] in chosen and DAYS[day.weekday()] in item['days']:
                    hour, minute = (int(part) for part in item['start'].split(':'))
                    at = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
                    if start < at <= end:
                        found.append((item, at))
        day += timedelta(days=1)
    return sorted(found, key=lambda pair: pair[1])


# Enrolment ----------------------------------------------------------------------------------------

def enrolled(connection) -> list[dict]:
    return [row | {'classes': decode(row['classes'])} for row in
            many(connection, 'SELECT * FROM story_enrollment ORDER BY enrolled_at')]


def enroll(connection, world: str, institution_id: str, classes: list[str] | None, now: datetime) -> dict | None:
    """The character joins an institution, in the classes named (its `core` classes when none are)."""
    institution = find(world, institution_id)
    if institution is None:
        return None
    known = {item['id'] for item in institution.get('classes', [])}
    chosen = [item for item in (classes if classes is not None else institution.get('core', [])) if item in known]
    connection.execute('INSERT INTO story_enrollment (institution_id, world, classes, enrolled_at) VALUES (?, ?, ?, ?) '
                       'ON CONFLICT(institution_id) DO UPDATE SET classes=excluded.classes',
                       (institution_id, world, encode(chosen), now.isoformat(timespec='minutes')))
    return institution


def leave(connection, institution_id: str):
    connection.execute('DELETE FROM story_enrollment WHERE institution_id=?', (institution_id,))


def begin(connection, world: str, premade: dict | None, now: datetime):
    """A new campaign's enrolment: the premade's own, or the world's default institution for a made character."""
    if premade is not None:
        for item in premade.get('enrolled', []):
            enroll(connection, world, item['institution'], item.get('classes'), now)
        return
    for institution in institutions(world):
        if institution.get('default'):
            enroll(connection, world, institution['id'], None, now)


# The clock moves -----------------------------------------------------------------------------------

def attend(connection, institution: dict, term: str, present: bool):
    column = 'attended' if present else 'missed'
    connection.execute(f'INSERT INTO story_attendance (institution_id, term, {column}) VALUES (?, ?, 1) '
                       f'ON CONFLICT(institution_id, term) DO UPDATE SET {column}={column} + 1',
                       (institution['id'], term))


def there(institution: dict, item: dict, city_id: str, place_id: str) -> bool:
    if item.get('place_id'):
        return place_id == item['place_id']
    return city_id == institution.get('city_id')


def demand_due(institution: dict, demand: dict, now: datetime) -> tuple[str, datetime] | None:
    """A demand that opens now: its key (the demand and when, so it opens once) and its deadline."""
    term = term_at(institution, now.date())
    if term is None:
        return None
    started = datetime.combine(term['start'], datetime.min.time()).replace(hour=DUE_HOUR)
    if 'week' in demand:
        due = started + timedelta(weeks=demand['week'])
        opens = due - timedelta(days=demand.get('notice_days', 7))
        return (f"{demand['id']}@{term['name']}", due) if opens <= now < due else None
    every = demand.get('every_days', 7)
    issued = started + timedelta(days=every * ((now - started).days // every))
    due = issued + timedelta(days=demand.get('due_days', every))
    open_now = now < due and due.date() <= term['end']
    return (f"{demand['id']}@{issued.date().isoformat()}", due) if open_now else None


def open_demands(connection, institution: dict, city_id: str, now: datetime):
    from dungeon import quests  # quests settle through here; demands open through there.
    issued = {row['demand'] for row in many(connection, 'SELECT demand FROM story_quests WHERE institution=?',
                                            (institution['id'],))}
    for demand in institution.get('demands', []):
        found = demand_due(institution, demand, now)
        if found is None or found[0] in issued:
            continue
        key, due = found
        quest_id = quests.create(connection, 'job', city_id, demand['title'], demand.get('hook', ''),
                                 demand.get('truth', ''), demand.get('missed', ''), due.isoformat(timespec='minutes'),
                                 faction_id=institution.get('faction'), giver=institution['name'])
        connection.execute('UPDATE story_quests SET institution=?, demand=?, weight=? WHERE id=?',
                           (institution['id'], key, demand.get('weight', 1), quest_id))


def advance(connection, before: datetime, after: datetime, city_id: str, place_id: str, logged: str):
    """Classes the clock has passed, attended or missed, and the demands that open."""
    for row in enrolled(connection):
        institution = find(row['world'], row['institution_id'])
        if institution is None:
            continue
        for item, at in class_times(institution, row['classes'], before, after):
            present = there(institution, item, city_id, place_id)
            attend(connection, institution, term_at(institution, at.date())['name'], present)
            if not present:
                record.add(connection, 'fact', 'The character',
                           f"missed {item['name']} on {at.strftime('%A %d %B')}", logged)
        open_demands(connection, institution, institution.get('city_id') or city_id, after)


def settled(connection, quest: dict, status: str) -> list[str]:
    """A demand's mark for the term its deadline falls in, and the standing it costs when failed or missed
    (dungeon/quests.py settle)."""
    row = optional(connection, 'SELECT world FROM story_enrollment WHERE institution_id=?', (quest['institution'],))
    institution = find(row['world'], quest['institution']) if row else find_anywhere(quest['institution'])
    if institution is None:
        return []
    term = term_at(institution, datetime.fromisoformat(quest['due_at']).date()) if quest.get('due_at') else None
    mark = MARKS.get(status, 0)
    connection.execute('INSERT INTO story_grades (institution_id, term, title, weight, mark) VALUES (?, ?, ?, ?, ?)',
                       (institution['id'], term['name'] if term else '', quest['title'], quest.get('weight') or 1, mark))
    lines = [f"{quest['title']} for {institution['name']}: {status}, a mark of {mark}"]
    if status != 'done' and (faction := institution.get('faction') and factions.anywhere(institution['faction'])):
        lines.append(factions.shift(connection, faction, -1))
    return [line for line in lines if line]


def find_anywhere(institution_id: str) -> dict | None:
    return next((found for world in world_data.keys('institutions') if (found := find(world, institution_id))), None)


# Grades -------------------------------------------------------------------------------------------

def letter(average: float) -> tuple[str, float]:
    return next((name, point) for floor, name, point in LETTERS if average >= floor)


def grades(connection, institution: dict, term: str) -> dict | None:
    """The term's weighted average with attendance as one more mark, its letter and grade point; None with no marks
    yet."""
    marks = many(connection, 'SELECT weight, mark FROM story_grades WHERE institution_id=? AND term=?',
                 (institution['id'], term))
    seen = optional(connection, 'SELECT attended, missed FROM story_attendance WHERE institution_id=? AND term=?',
                    (institution['id'], term))
    held = seen and seen['attended'] + seen['missed']
    if held:
        weight = institution.get('attendance_weight', ATTENDANCE_WEIGHT)
        marks.append({'weight': weight, 'mark': round(100 * seen['attended'] / held)})
    total = sum(item['weight'] for item in marks)
    if not total:
        return None
    average = sum(item['weight'] * item['mark'] for item in marks) / total
    name, point = letter(average)
    return {'average': round(average), 'letter': name, 'gpa': point, 'attended': seen['attended'] if seen else 0,
            'missed': seen['missed'] if seen else 0}


def today(institution: dict, chosen: list[str], now: datetime) -> list[dict]:
    """The rest of today's classes."""
    end = datetime.combine(now.date(), datetime.max.time())
    return [{'id': item['id'], 'name': item['name'], 'at': at.strftime('%H:%M'), 'place_id': item.get('place_id'),
             'soon': (at - now) <= timedelta(hours=SOON_HOURS)}
            for item, at in class_times(institution, chosen, now - timedelta(minutes=1), end)]


# A line that heads to class: "I head to my first class", "off to the lecture".
TO_CLASS = re.compile(r'\b(?:class|classes|lecture|seminar|lesson|tutorial|lab)\b', re.I)
# A class still counts as the one to go to this long after it starts (a late arrival).
LATE = timedelta(minutes=30)


def class_place(connection, city_id: str, text: str, now: datetime) -> str | None:
    """The room of the character's next class today in this city, for a line that heads to class; none when the
    line names no class or none is left today."""
    if not TO_CLASS.search(text):
        return None
    end = datetime.combine(now.date(), datetime.max.time())
    for row in enrolled(connection):
        institution = find(row['world'], row['institution_id'])
        if institution is None or institution.get('city_id', city_id) != city_id:
            continue
        coming = [(item, at) for item, at in class_times(institution, row['classes'], now - LATE, end)
                  if item.get('place_id')]
        if coming:
            return coming[0][0]['place_id']
    return None


# A line that goes on after a class: "after class I go for coffee", "I sit through the lecture".
AFTER_CLASS = re.compile(r'\bafter (?:my |the |this )?(?:class|lecture|seminar|lesson|tutorial|lab)\b|'
                         r'\b(?:attend|sit through|stay for|sit in on)\b[^.!?]*\b(?:class|lecture|seminar|lesson|'
                         r'tutorial|lab)\b', re.I)
CLASS_MINUTES = 75


def until_class_ends(connection, city_id: str, place_id: str, text: str, now: datetime) -> int:
    """Minutes to the end of the class held here now or next today, for a line that goes on after it (playtest
    m6b: "after class I go to Commons Coffee" left before the class began); 0 for any other line."""
    if not AFTER_CLASS.search(text):
        return 0
    end_of_day = datetime.combine(now.date(), datetime.max.time())
    for row in enrolled(connection):
        institution = find(row['world'], row['institution_id'])
        if institution is None or institution.get('city_id', city_id) != city_id:
            continue
        for item, at in class_times(institution, row['classes'], now - timedelta(minutes=CLASS_MINUTES), end_of_day):
            if item.get('place_id') in (None, place_id):
                hour, minute = (int(part) for part in item.get('end', '').split(':')) if item.get('end') else (0, 0)
                ends = at.replace(hour=hour, minute=minute) if item.get('end') else at + timedelta(minutes=CLASS_MINUTES)
                if ends > now:
                    return int((ends - now).total_seconds() // 60)
    return 0


def view(connection, now: datetime) -> list[dict]:
    """Each institution the character is in: the term, the rest of today's classes, and the term's grades."""
    out = []
    for row in enrolled(connection):
        institution = find(row['world'], row['institution_id'])
        if institution is None:
            continue
        term = term_at(institution, now.date())
        out.append({'id': institution['id'], 'name': institution['name'], 'term': term['name'] if term else None,
                    'classes': [{'id': item['id'], 'name': item['name']} for item in institution.get('classes', [])
                                if item['id'] in row['classes']],
                    'today': today(institution, row['classes'], now) if term else [],
                    'grades': grades(connection, institution, term['name']) if term else None})
    return out


def prompt_text(connection, now: datetime) -> str:
    """For the narrator: what the character is enrolled in, what is on today, and how their grades stand. What is due
    is among the quests."""
    lines = []
    for item in view(connection, now):
        if not item['term']:
            lines.append(f"The character belongs to {item['name']}; it is out of term.")
            continue
        on = '; '.join(f"{entry['name']} at {entry['at']}" for entry in item['today']) or 'no more classes today'
        graded = item['grades']
        standing = f" Grades so far: {graded['letter']} ({graded['average']}), {graded['missed']} classes missed." \
            if graded else ''
        lines.append(f"The character is enrolled at {item['name']} ({item['term']}). Today: {on}.{standing}")
    if not lines:
        return ''
    return '## School and duties\n' + '\n'.join(lines) + '\nOnly these classes exist; never invent another.'
