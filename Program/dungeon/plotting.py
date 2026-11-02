"""The director, full: seeds and payoffs, adopted details and arc beats planned a stage at a time (requirements "The
director"; docs/story.md "The director: seeds, adopted details and planned beats"). Director v0 is dungeon/director.py.

- **Seeds pay off (the Chekhov list, story_seeds).** Every seed the GM note plants is logged against its thread and
  the hidden truth it points to, with a payoff window of WINDOW lines. Code checks after each narration which
  planted seeds reached the page (by their words). When a seed's thread is hot or its arc is due, or its window is
  closing, the note asks for it to come back; once it does, it is paid. A seed whose window ends unpaid is retired,
  and the GM view shows it so; the player can also cash one in (ask for it next) or retire it there.
- **Adopted details.** When the Continuity model says the player's line engaged with something the narrator made up
  (a stranger at the bar, a symbol on a door), the director may give it a meaning tied to the hottest arc thread:
  the director model drafts it when one is chosen, else code ties it to the thread's own truth. The meaning is
  checked against the record (nothing about the dead acting) and kept as hidden truth and as a seed already on the
  page, so it pays off like any other.
- **Beats planned a stage at a time, Mabry style (story_arc_beats).** When an arc reaches a stage with no plan, the
  director model (job `director`, off unless chosen) drafts BEATS candidate beats from the stage's truth, the hottest
  threads and the world's own beats; code keeps those that name none of the dead and stay within the stage, and
  falls back to the stage's own seed and word. The plan is hidden; with the GM view on, the player can cut and
  reorder it. When the arc is due, the note gives the next beat.

All of it is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import json
import random
import re

from dungeon import director, record
from dungeon.database import decode, encode, identifier, many, optional
from dungeon.errors import require
from dungeon.text_models import config_for, routes

JOB = 'director'
WINDOW = 30
CLOSING = 5
REACHED = 2
ADOPT = 50
BEATS = 3
WORD = re.compile(r"[a-z][a-z'-]{3,}")
COMMON = {'the', 'and', 'with', 'from', 'that', 'this', 'into', 'their', 'there', 'about', 'someone', 'something', 'they', 'them', 'what', 'when', 'where', 'which', 'will', 'were', 'have', 'been', 'over',
                            'under', 'than', 'then', 'into', 'onto', 'your', 'very', 'just', 'like'}

DRAFT = """You help a game master plan the next stage of a story arc in a tabletop roleplaying game. You never write \
the story itself. Given the arc, the truth of its new stage and the threads the player cares about, draft {count} \
candidate beats: short things the world could do next to bring this stage into play (a person who comes looking, an \
event, a discovery). Each is one sentence. Use only the people, groups and places named here, and keep each person \
where they are; bring in no one from another story. Never decide what the player's character does. Answer with JSON \
only: {{"beats": ["...", "..."]}}"""
DRAFT_SHAPE = record.strict({'beats': {'type': 'array', 'items': {'type': 'string'}}})
MEANING = """You help a game master. The player has taken an interest in a detail the narrator made up. Give it a \
hidden meaning that ties it to the thread below, in one or two sentences, consistent with the thread's truth and \
contradicting nothing in it. Never decide what the player's character does. Answer with JSON only: {"truth": "..."}"""
MEANING_SHAPE = record.strict({'truth': {'type': 'string'}})
ENGAGED_ASK = ('\n\nOnly if the player\'s line took an interest in a detail the narrator had made up (a stranger, a '
               'symbol, an odd object) that the game has no story for yet, add "engaged": ["the detail, in a few '
               'words"] to your answer.')
ENGAGED_SCHEMA = {'engaged': {'type': 'array', 'items': {'type': 'string'}}}


def words_of(text: str) -> set[str]:
    return {word for word in WORD.findall(text.lower()) if word not in COMMON}


def landed(seed_words: list[str], text: str) -> bool:
    """Whether a seed reached the page: enough of its own words are in the narration."""
    found = words_of(text)
    return len(set(seed_words) & found) >= min(REACHED, len(seed_words))


def model(connection) -> dict | None:
    return config_for(connection, JOB) if routes(connection).get(JOB) else None


# Seeds -------------------------------------------------------------------------------------------

def plant(connection, arc_id: str | None, text: str, truth: str, status: str = 'planted', message_id: str = ''):
    line = director.state(connection)['lines']
    thread = optional(connection, "SELECT id FROM story_threads WHERE arc_id=? AND kind='mystery'", (arc_id,))
    connection.execute('INSERT INTO story_seeds (id, arc_id, thread_id, text, truth, words, status, planted_line, '
                       'until_line, message_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (f'seed-{identifier()[:12]}', arc_id, thread and thread['id'], text, truth,
                        encode(sorted(words_of(text))), status, line, line + WINDOW, message_id))


def seeds(connection, status: str | None = None) -> list[dict]:
    where = 'WHERE status=?' if status else ''
    return [row | {'words': decode(row['words'])}
            for row in many(connection, f'SELECT * FROM story_seeds {where} ORDER BY planted_line, rowid',
                            (status,) if status else ())]


def after_line(connection, text: str, message_id: str):
    """After a narration: planted seeds that reached the page, asked-for payoffs that came back, and seeds whose
    window ended unpaid retired."""
    line = director.state(connection)['lines']
    for row in seeds(connection):
        if row['status'] == 'planted' and landed(row['words'], text):
            connection.execute("UPDATE story_seeds SET status='reached', message_id=? WHERE id=?", (message_id, row['id']))
        elif row['status'] == 'asked' and landed(row['words'], text):
            connection.execute("UPDATE story_seeds SET status='paid' WHERE id=?", (row['id'],))
        elif row['status'] in ('planted', 'reached', 'asked') and line > row['until_line'] + CLOSING:
            connection.execute("UPDATE story_seeds SET status='retired' WHERE id=?", (row['id'],))


def payoff(connection, rows: dict) -> list[str]:
    """The seed that should come back now: its thread hot or its arc due, or its window closing; once a note."""
    line = director.state(connection)['lines']
    hot = {row['id'] for row in director.threads(connection) if row['heat'] >= director.TOUCH}
    for row in seeds(connection, 'reached'):
        arc_due = row['arc_id'] in rows and not rows[row['arc_id']]['told']
        if row['thread_id'] in hot or arc_due or line >= row['until_line'] - CLOSING:
            connection.execute("UPDATE story_seeds SET status='asked' WHERE id=?", (row['id'],))
            return [f"Payoff: bring back what was planted earlier ({row['text']}). It points to this: {row['truth']}"]
    return []


def cash_in(connection, seed_id: str):
    """The GM view asks for a seed to come back with the next note."""
    require(record.gm_view(connection), 'Turn on the GM view to plan the story.', 409)
    line = director.state(connection)['lines']
    changed = connection.execute("UPDATE story_seeds SET status='reached', until_line=? WHERE id=? AND status IN "
                                 "('planted', 'reached', 'asked', 'retired')", (line, seed_id)).rowcount
    require(changed == 1, 'That seed is not there.', 404)


def retire(connection, seed_id: str):
    require(record.gm_view(connection), 'Turn on the GM view to plan the story.', 409)
    require(connection.execute("UPDATE story_seeds SET status='retired' WHERE id=?", (seed_id,)).rowcount == 1,
            'That seed is not there.', 404)


# Adopted details ---------------------------------------------------------------------------------

def engaged(answer: str) -> list[str]:
    data = record.read_json(answer or '')
    items = data.get('engaged') if isinstance(data, dict) else None
    return [str(item).strip()[:120] for item in items or [] if isinstance(item, str) and item.strip()][:1]


def unknown(connection, detail: str) -> bool:
    """A detail the game has no story for yet: no thread or seed already uses its words."""
    found = words_of(detail)
    if not found:
        return False
    taken = [set(row['words']) for row in seeds(connection)] + [set(row['words']) for row in director.threads(connection)]
    return not any(found & words for words in taken)


async def adopt(state, details: list[str], message_id: str, rng=None):
    """The director may give a detail the player engaged with a meaning, tied to the hottest arc thread."""
    rng = rng or random.SystemRandom()
    database = state.database
    with database.connect() as connection:
        if director.state(connection)['world'] is None:
            return
        hot = [row for row in director.threads(connection) if row['arc_id']]
        details = [detail for detail in details if unknown(connection, detail)]
        config = model(connection)
    if not details or not hot or rng.randint(1, 100) > ADOPT:
        return
    detail, thread = details[0], hot[0]
    truth = f"{detail[:1].upper() + detail[1:]} is tied to {thread['title']}: {thread['truth']}"
    if config is not None:
        try:
            answer = await record.schema_first(state, config, MEANING, f"The detail: {detail}\n\nThe thread: "
                                               f"{thread['title']}. Its truth: {thread['truth']}", MEANING_SHAPE,
                                               lambda answer: bool((record.read_json(answer) or {}).get('truth')))
            truth = str((record.read_json(answer) or {}).get('truth') or truth).strip()[:500]
        except Exception:  # noqa: BLE001 - code's own meaning stands.
            pass
    with database.connect(write=True) as connection:
        if any(name in truth.lower() for name in record.dead(connection) if len(name) > 2):
            return
        plant(connection, thread['arc_id'], detail, truth, 'reached', message_id)
        record.add(connection, 'fact', detail[:120], truth, database.now(), truth='world')


# Planned beats -----------------------------------------------------------------------------------

def beats(connection, arc_id: str, stage: int) -> list[dict]:
    return many(connection, 'SELECT * FROM story_arc_beats WHERE arc_id=? AND stage=? ORDER BY position, rowid',
                (arc_id, stage))


def unplanned(connection, world: str) -> list[tuple[str, int, dict]]:
    result = []
    for arc_id, row in director.arcs(connection).items():
        stage = director.stage_of(world, row)
        if stage and not beats(connection, arc_id, row['stage']):
            result.append((arc_id, row['stage'], stage))
    return result


def checked_beats(connection, drafted: list, foreign: set[str] = frozenset()) -> list[str]:
    """The drafted beats kept: none naming the dead, none using another arc's own words (its cast and places)."""
    dead = [name for name in record.dead(connection) if len(name) > 2]
    return [str(text).strip()[:300] for text in drafted if isinstance(text, str) and str(text).strip()
            and not any(name in text.lower() for name in dead) and not words_of(text) & foreign][:BEATS]


# A capitalized word not opening a sentence: a name (its possessive dropped).
NAME = re.compile(r"(?<![.!?:]\s)(?<!^)(?<![.!?:]\s\")\b([A-Z][a-z-]{2,})(?:'s)?\b")


def names_in(found: dict) -> set[str]:
    """The proper names an arc's own text uses (its cast, groups and places), lowercased."""
    text = '  '.join([found.get('seen', ''), str((found.get('antagonist') or {}).get('name', ''))]
                     + [str(stage.get(key, '')) for stage in found['stages'] for key in ('truth', 'seed', 'word')])
    names = set()
    for part in re.split(r'(?<=[.!?:])\s+|\s{2,}', text):
        names |= {name.lower() for name in NAME.findall(part)}
    return names - COMMON


def foreign_words(world: str, arc_id: str) -> set[str]:
    """Names that belong to the world's other arcs and not to this one, so a beat cannot borrow their cast."""
    found = director.data(world)['arcs']
    # A word the arcs also use in lower case ("keep", "new") is no name.
    plain = set(WORD.findall(json.dumps([{key: value for key, value in arc.items() if key != 'words'} for arc in found])))
    own = {name for arc in found if arc['id'] == arc_id for name in names_in(arc)}
    return {name for arc in found if arc['id'] != arc_id for name in names_in(arc)} - own - plain


def drafting(found: dict, stage: dict, hot: list[dict]) -> str:
    """What the director model is given for one arc's stage: the arc, where it plays, and only its own threads."""
    where = ', '.join((found.get('antagonist') or {}).get('where') or [])
    # Only threads tied to this arc: an untied side quest's secrets (Sereth's herb bundles) are no other arc's beat.
    own = [row for row in hot if row.get('arc_id') == found['id']][:3]
    return (f"The arc: {found['name']}." + (f" It plays in: {where}." if where else '')
            + f"\nIts new stage: {stage['truth']}\nThe world's own beat: {stage['word']}\n"
            + ('The threads of this arc the player cares about: '
               + '; '.join(f"{row['title']} ({row['truth']})" for row in own) if own else ''))


def store(connection, arc_id: str, stage: int, texts: list[str], source: str):
    for position, text in enumerate(texts):
        connection.execute('INSERT INTO story_arc_beats (id, arc_id, stage, text, position, cut, used, source) VALUES '
                           '(?, ?, ?, ?, ?, 0, 0, ?)', (f'beat-{identifier()[:12]}', arc_id, stage, text, position, source))


async def plan(state):
    """Each arc stage with no plan yet gets its beats: drafted by the director model, else the stage's own."""
    database = state.database
    with database.connect() as connection:
        world = director.state(connection)['world']
        waiting = unplanned(connection, world) if world and director.ACTIVE else []
        config = model(connection)
        hot = director.threads(connection)
    for arc_id, number, stage in waiting:
        drafted = []
        if config is not None:
            asking = drafting(director.arc(world, arc_id), stage, hot)
            try:
                answer = await record.schema_first(state, config, DRAFT.format(count=BEATS), asking, DRAFT_SHAPE,
                                                   lambda answer: isinstance((record.read_json(answer) or {}).get('beats'), list))
                drafted = (record.read_json(answer) or {}).get('beats') or []
            except Exception:  # noqa: BLE001 - the stage's own beats stand.
                drafted = []
        with database.connect(write=True) as connection:
            if beats(connection, arc_id, number):
                continue
            kept = checked_beats(connection, drafted, foreign_words(world, arc_id))
            store(connection, arc_id, number, kept or [stage['word'], stage['seed']], 'model' if kept else 'world')


def next_beat(connection, arc_id: str, stage: int) -> str:
    """The next beat of an arc's plan, used once."""
    row = next((row for row in beats(connection, arc_id, stage) if not row['cut'] and not row['used']), None)
    if row is None:
        return ''
    connection.execute('UPDATE story_arc_beats SET used=1 WHERE id=?', (row['id'],))
    return row['text']


def change_beat(connection, beat_id: str, cut: bool | None = None, position: int | None = None):
    """The GM view cuts a drafted beat, brings it back, or moves it in the order."""
    require(record.gm_view(connection), 'Turn on the GM view to plan the story.', 409)
    row = optional(connection, 'SELECT * FROM story_arc_beats WHERE id=?', (beat_id,))
    require(row is not None, 'That beat is not there.', 404)
    if cut is not None:
        connection.execute('UPDATE story_arc_beats SET cut=? WHERE id=?', (int(cut), beat_id))
    if position is not None:
        others = [item for item in beats(connection, row['arc_id'], row['stage']) if item['id'] != beat_id]
        others.insert(max(0, min(len(others), position)), row)
        for index, item in enumerate(others):
            connection.execute('UPDATE story_arc_beats SET position=? WHERE id=?', (index, item['id']))


def view(connection) -> dict:
    """For the GM view: the Chekhov list and each arc's planned beats for its stage."""
    planned = []
    for arc_id, row in director.arcs(connection).items():
        planned.append({'arc_id': arc_id, 'stage': row['stage'],
                        'beats': [{'id': item['id'], 'text': item['text'], 'cut': bool(item['cut']),
                                   'used': bool(item['used']), 'source': item['source']}
                                  for item in beats(connection, arc_id, row['stage'])]})
    return {'seeds': [{'id': row['id'], 'text': row['text'], 'truth': row['truth'], 'status': row['status'],
                       'arc_id': row['arc_id']} for row in seeds(connection)],
            'plans': planned}
