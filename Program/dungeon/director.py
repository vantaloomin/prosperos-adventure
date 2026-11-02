"""The director, v0: a game master's guiding hand (requirements "The director"; docs/story.md "The director").

Code that holds the campaign's plot state and decides what the world pushes toward. It never decides what the player
does and never changes roll odds.

- **Arcs and the spine.** Each world's arcs for its era (world/data/arcs/<world>.json) are seeded as the campaign
  starts, each at its first stage, with a thread for it. The arc the player bites on hardest (play touching its
  threads) becomes the spine once it has COMMIT bites, in the first three chapters (CHAPTER_LINES lines each); if
  none has by then, the world's default spine. An arc the player later turns to far harder can take its place.
  Arcs not chosen go on in the background.
- **Threads are the GM's notebook** (story_threads): each arc, each quest (jobs, oaths and the town's own) and each
  nemesis opens one, with the arc it feeds, a heat (how recently and strongly play touched it; it cools every line)
  and a bite count, the hidden truth and the words that tell code play touched it. The journal shows the ones the
  character has come across, as they understand them.
- **The hand** (picked at campaign start): Soft, Guiding (the default) or Firm. Arcs move a stage on their own
  clocks (PACE in 100 a story day, twice that for the spine); under Soft that only changes the world's truth, under
  Guiding the arc's people come looking for the character, under Firm it shows in the scene wherever they are.
- **The hidden GM note**, every turn: the pressure the scene is under (from the tension curve), a seed to plant if
  it fits, the threads the people present carry, the antagonist near, and what of the arcs is due. A stage above
  the character's tier only ever reaches them as a clue or a rumor, never its fight.
- **The tension curve.** Each line is a quiet, social, pressure or crisis scene (from its rolls and fight). After
  SLACK quiet lines in a row (fewer the more eventful the drama setting), the note asks for pressure from the
  hottest thread or the arc due; after a crisis it lets the next scene breathe.
- **Side quests leave a mark.** A job offered may link straight into an active arc (LINK in 100), with one of its
  seeds as a tie.
- **Nemeses.** A foe who got away from the character, or beat them, may be promoted (NEMESIS in 100): a grudge, what
  they remember of how the character fights, and a thread. After NEMESIS_DAYS they come back with a plan, through
  the note. One the character kills on the page stays dead.

Seeds and payoffs, adopted details and the arcs' planned beats are dungeon/plotting.py.

All of it is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from dungeon import plotting, record, tiers, world_data
from dungeon.database import decode, encode, identifier, many, optional

ARCS = Path(__file__).parent / 'world' / 'data' / 'arcs'
HANDS = ('soft', 'guiding', 'firm')
DEFAULT_HAND = 'guiding'
PACE = {'soft': 10, 'guiding': 15, 'firm': 20}
CHAPTER_LINES = 20
SPINE_CHAPTERS = 3
COMMIT = 6
PROMOTE = 2
TOUCH, DECAY = 3.0, 0.7
SLACK = {'quiet': 5, 'uneasy': 4, 'eventful': 3, 'merciless': 2}
LINK = 33
NEMESIS = 50
NEMESIS_DAYS = 3
RECENT = 6
# Off only for tests that are about something else (tests/conftest.py).
ACTIVE = True
BEATEN = ('robbed', 'captured', 'thrown_out')
GOT_AWAY = 'fled'


@world_data.memo
def data(world: str) -> dict:
    return world_data.read('arcs', world) or {'arcs': [], 'default_spine': None}


def arc(world: str, arc_id: str) -> dict | None:
    return next((item for item in data(world)['arcs'] if item['id'] == arc_id), None)


def state(connection) -> dict:
    row = optional(connection, 'SELECT * FROM story_director WHERE id=1')
    if row is None:
        return {'world': None, 'hand': DEFAULT_HAND, 'spine_id': None, 'lines': 0, 'recent': [], 'planted': [],
                'last_message': None}
    return row | {'recent': decode(row['recent']), 'planted': decode(row['planted'])}


def save(connection, row: dict):
    connection.execute('INSERT INTO story_director (id, world, hand, spine_id, lines, recent, planted, last_message) '
                       'VALUES (1, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET world=excluded.world, '
                       'hand=excluded.hand, spine_id=excluded.spine_id, lines=excluded.lines, recent=excluded.recent, '
                       'planted=excluded.planted, last_message=excluded.last_message',
                       (row['world'], row['hand'], row['spine_id'], row['lines'], encode(row['recent']),
                        encode(row['planted']), row['last_message']))


def arcs(connection) -> dict[str, dict]:
    return {row['arc_id']: row for row in many(connection, 'SELECT * FROM story_arcs')}


def stage_of(world: str, row: dict) -> dict | None:
    found = arc(world, row['arc_id'])
    return found['stages'][row['stage']] if found and row['stage'] < len(found['stages']) else None


# Threads -----------------------------------------------------------------------------------------

WORD = re.compile(r"[a-z][a-z'-]{3,}")
COMMON = {'the', 'and', 'with', 'from', 'that', 'this', 'into', 'their', 'there', 'about', 'someone', 'something'}


def words_in(*texts: str) -> list[str]:
    return sorted({word for text in texts for word in WORD.findall(text.lower()) if word not in COMMON})


def open_thread(connection, kind: str, title: str, seen: str, truth: str, words: list[str], arc_id: str | None = None,
                known: bool = False, quest_id: str | None = None, now: str = '') -> str:
    thread_id = f'thread-{identifier()[:12]}'
    connection.execute('INSERT INTO story_threads (id, arc_id, kind, title, seen, truth, words, heat, bite, known, '
                       "status, quest_id, opened_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 'open', ?, ?)",
                       (thread_id, arc_id, kind, title, seen, truth, encode(words), int(known), quest_id, now))
    return thread_id


def for_quest(connection, quest_id: str, kind: str, title: str, hook: str, truth: str, ties: list[dict] | str,
              arc_id: str | None = None, giver: str | None = None) -> str:
    """The thread a quest opens; the quest keeps its id (story_quests.thread_id)."""
    ties = decode(ties) if isinstance(ties, str) else ties
    refs = [str(tie.get('ref', '')) for tie in ties if tie.get('kind') != 'faction']
    thread_id = open_thread(connection, 'promise' if kind == 'oath' else 'lead', title, hook, truth,
                            words_in(title, giver or '', *refs), arc_id, known=True, quest_id=quest_id)
    connection.execute('UPDATE story_quests SET thread_id=? WHERE id=?', (thread_id, quest_id))
    return thread_id


def threads(connection, status: str = 'open') -> list[dict]:
    return [row | {'words': decode(row['words'])}
            for row in many(connection, 'SELECT * FROM story_threads WHERE status=? ORDER BY heat DESC, rowid',
                            (status,))]


def close(connection, quest_id: str):
    connection.execute("UPDATE story_threads SET status='closed' WHERE quest_id=?", (quest_id,))


def touched(thread: dict, text: str) -> bool:
    lowered = text.lower()
    return any(re.search(rf'(?<![a-z]){re.escape(word)}(?![a-z])', lowered) for word in thread['words'])


# The campaign ------------------------------------------------------------------------------------

def begin(connection, world: str, hand: str | None = None, now: str = ''):
    """Seed the world's arcs at their first stage, each with its thread, and open threads for the town's quests."""
    for table in ('story_director', 'story_arcs', 'story_threads', 'story_nemeses'):
        connection.execute(f'DELETE FROM {table}')
    save(connection, state(connection) | {'world': world, 'hand': hand or DEFAULT_HAND})
    for item in data(world)['arcs']:
        connection.execute('INSERT INTO story_arcs (arc_id, stage, bite, moved_at, told) VALUES (?, 0, 0, ?, 1)',
                           (item['id'], now))
        open_thread(connection, 'mystery', item['name'], item['seen'], item['stages'][0]['truth'], item['words'],
                    item['id'], now=now)
        for quest_id in item.get('quests', []):
            connection.execute('UPDATE story_quests SET arc_id=? WHERE id=?', (item['id'], quest_id))
    from dungeon import quests  # quests opens threads through this module
    for quest in quests.rows(connection, 'open'):
        for_quest(connection, quest['id'], quest.get('kind') or 'authored', quest['title'], quest['hook'],
                  quest['truth'], quest.get('ties') or [], quest.get('arc_id'))


def spine(connection, world: str) -> str | None:
    """Commit to the arc the player bites on hardest, or the world's default after three chapters; a far harder
    turn toward another arc promotes it."""
    row = state(connection)
    bites = {key: item['bite'] for key, item in arcs(connection).items() if arc(world, key)}
    if not bites:
        return None
    best = max(bites, key=lambda key: (bites[key], key == data(world).get('default_spine')))
    current = row['spine_id']
    if current is None:
        chapter = 1 + row['lines'] // CHAPTER_LINES
        if bites[best] >= COMMIT:
            current = best
        elif chapter > SPINE_CHAPTERS:
            current = data(world).get('default_spine') or best
    elif best != current and bites[best] >= PROMOTE * max(COMMIT, bites.get(current, 0)):
        current = best
    if current != row['spine_id']:
        save(connection, row | {'spine_id': current})
    return current


def pressed(noted: list[str]) -> bool:
    """Whether the line's note asked for pressure; that line then counts as pressure on the curve, so the next slack
    run starts over instead of every line after it asking again."""
    return any('- Pressure: ' in text and '- Pressure: none.' not in text for text in noted)


def scene_kind(rolls: list[dict], fought: list[str], people: list[dict], noted: list[str] = ()) -> str:
    if fought:
        return 'crisis'
    if any(roll.get('threat') for roll in rolls) or pressed(noted):
        return 'pressure'
    return 'social' if people else 'quiet'


def touch(connection, world: str, text: str, kind: str, message_id: str, now: str):
    """After a line is told: threads cool, the ones play touched heat up, and the curve notes the scene's kind.
    Once a line however often it is told."""
    row = state(connection)
    if row['world'] is None or row['last_message'] == message_id:
        return
    connection.execute('UPDATE story_threads SET heat=heat * ?', (DECAY,))
    bitten = set()
    for thread in threads(connection):
        if touched(thread, text):
            connection.execute('UPDATE story_threads SET heat=heat + ?, bite=bite + 1, known=1, touched_at=? WHERE '
                               'id=?', (TOUCH, now, thread['id']))
            bitten.add(thread['arc_id'])
    # An arc is bitten on once a line, however many of its threads the line touched.
    for arc_id in bitten - {None}:
        connection.execute('UPDATE story_arcs SET bite=bite + 1 WHERE arc_id=?', (arc_id,))
    save(connection, row | {'lines': row['lines'] + 1, 'recent': [*row['recent'], kind][-RECENT:],
                            'last_message': message_id})
    spine(connection, world)


def link(connection, world: str, rng=None) -> tuple[str | None, list[dict]]:
    """Whether a job offered links into an active arc, and the seed it leaves as a tie."""
    rng = rng or random.SystemRandom()
    rows = arcs(connection)
    active = state(connection)['spine_id'] or max(rows, key=lambda key: rows[key]['bite'], default=None)
    if active is None or active not in rows or rng.randint(1, 100) > LINK:
        return None, []
    stage = stage_of(world, rows[active])
    return (active, [{'kind': 'clue', 'ref': stage['seed']}]) if stage else (None, [])


def advance(connection, world: str, before: datetime, after: datetime, logged: str, rng=None):
    """Each story day passed, each arc may move a stage on its own clock; the world's truth changes with it."""
    row = state(connection)
    if row['world'] != world or not ACTIVE:
        return
    rng = rng or random.SystemRandom()
    for _ in range(max(0, (after.date() - before.date()).days)):
        for arc_id, item in arcs(connection).items():
            found = arc(world, arc_id)
            if not found or item['stage'] + 1 >= len(found['stages']):
                continue
            chance = PACE[row['hand']] * (2 if arc_id == row['spine_id'] else 1)
            if rng.randint(1, 100) <= chance:
                stage = found['stages'][item['stage'] + 1]
                connection.execute('UPDATE story_arcs SET stage=stage + 1, moved_at=?, told=? WHERE arc_id=?',
                                   (after.isoformat(), int(row['hand'] == 'soft'), arc_id))
                connection.execute("UPDATE story_threads SET truth=? WHERE arc_id=? AND kind='mystery'",
                                   (stage['truth'], arc_id))
                record.add(connection, 'fact', found['name'], stage['truth'], logged, truth='world')


# Nemeses -----------------------------------------------------------------------------------------

def base_name(name: str) -> str:
    return re.sub(r'\s+\d+$', '', name).strip()


def history(connection, events: list[tuple[str, str]], now: datetime, logged: str, rng=None):
    """What a fight left between the character and a foe: one who got away or beat them may become a nemesis; one
    killed on the page stays dead."""
    rng = rng or random.SystemRandom()
    for event, who in events:
        if event == 'kill':
            for nemesis in many(connection, "SELECT * FROM story_nemeses WHERE status='alive'"):
                if base_name(who).lower() in nemesis['name'].lower():
                    connection.execute("UPDATE story_nemeses SET status='dead' WHERE id=?", (nemesis['id'],))
                    connection.execute("UPDATE story_threads SET status='closed' WHERE id=?", (nemesis['thread_id'],))
        elif (event == GOT_AWAY or event in BEATEN) and rng.randint(1, 100) <= NEMESIS:
            promote(connection, who, event, now, logged)


def promote(connection, who: str, event: str, now: datetime, logged: str):
    base = base_name(who)
    known = re.search(r'\b(the|a|an)\b', base.lower()) is None and base[:1].isupper()
    name = base if known else f"the {base} who {'got away' if event == GOT_AWAY else 'beat them'}"
    if optional(connection, "SELECT 1 FROM story_nemeses WHERE name=? AND status='alive'", (name,)):
        return
    used = optional(connection, 'SELECT stat FROM story_marks ORDER BY uses DESC, stat LIMIT 1')
    remembers = used['stat'] if used else 'Vitality'
    grudge = (f'{name} got away from the character, and has not forgiven being made to run.' if event == GOT_AWAY
              else f'{name} beat the character once, and means to finish it.')
    thread_id = open_thread(connection, 'grudge', name[:1].upper() + name[1:], f'{name[:1].upper() + name[1:]} is '
                            'still out there.', grudge, words_in(base), known=True, now=logged)
    connection.execute("INSERT INTO story_nemeses (id, name, grudge, remembers, status, since, thread_id) VALUES "
                       "(?, ?, ?, ?, 'alive', ?, ?)", (f'nemesis-{identifier()[:12]}', name, grudge, remembers,
                                                      now.isoformat(), thread_id))
    record.add(connection, 'fact', name, grudge, logged, truth='world')


def pursue(connection, grudge: str, days: int, now: datetime, logged: str):
    """Someone on the character's trail (a Life Card's pursuer), due to catch up in `days`: a nemesis whose clock
    starts so it comes due then."""
    name = 'whoever is on the character\'s trail'
    if optional(connection, "SELECT 1 FROM story_nemeses WHERE name=? AND status='alive'", (name,)):
        return
    since = now - timedelta(days=max(0, NEMESIS_DAYS - days))
    connection.execute("INSERT INTO story_nemeses (id, name, grudge, remembers, status, since, thread_id) VALUES "
                       "(?, ?, ?, 'Mind', 'alive', ?, NULL)", (f'nemesis-{identifier()[:12]}', name, grudge,
                                                               since.isoformat()))
    record.add(connection, 'fact', name, grudge, logged, truth='world')


def due_nemesis(connection, now: datetime) -> dict | None:
    return next((row for row in many(connection, "SELECT * FROM story_nemeses WHERE status='alive' ORDER BY since")
                 if (now - datetime.fromisoformat(row['since'])).days >= NEMESIS_DAYS), None)


# The hidden GM note ------------------------------------------------------------------------------

def slack(recent: list[str], drama: str) -> bool:
    needed = SLACK.get(drama, SLACK['uneasy'])
    return len(recent) >= needed and all(kind in ('quiet', 'social') for kind in recent[-needed:])


def pressure(connection, world: str, row: dict, rows: dict, hot: list[dict], drama: str, now: datetime) -> list[str]:
    """What the tension curve asks of the scene: room to breathe after a crisis, pressure after a slack run."""
    if row['recent'] and row['recent'][-1] == 'crisis':
        return ['Pressure: none. After that, let this scene breathe; nothing new comes at the character yet.']
    if not slack(row['recent'], drama):
        return []
    if nemesis := due_nemesis(connection, now):
        return [f"Pressure: {nemesis['name']} comes back, with a plan. They remember how the character fights (their "
                f"{nemesis['remembers']}) and have prepared for it. {nemesis['grudge']}"]
    if hot and hot[0]['heat'] > 0:
        return [f"Pressure: the story has gone slack. Bring {hot[0]['title']} back into it: {hot[0]['truth']}"]
    if row['spine_id'] and (stage := stage_of(world, rows[row['spine_id']])):
        return [f"Pressure: the story has gone slack. Let the spine of the story press in: {stage['word']}"]
    return []


def due(connection, world: str, row: dict, rows: dict) -> list[str]:
    """The arc stages that moved since the last note, as the hand delivers them; each is told once."""
    character, lines = tiers.tier(connection, world), []
    for arc_id, item in rows.items():
        found, stage = arc(world, arc_id), stage_of(world, item)
        if not found or not stage or item['told']:
            continue
        push = ('Its people and clocks come looking for the character: bring it to them where it fits.'
                if row['hand'] == 'guiding' else 'Show it in this scene, wherever the character is.')
        if stage['tier'] > character:
            lines.append(f"Due ({found['name']}): {stage['word']} It is beyond the character: it reaches them only as "
                         'a clue or a rumor, never its fight.')
        else:
            lines.append(f"Due ({found['name']}): {stage['truth']} {push}")
            # The arc's plan for the stage (dungeon/plotting.py), drafted or the world's own.
            if (beat := plotting.next_beat(connection, arc_id, item['stage'])) and beat != stage['word']:
                lines.append(f"Next beat ({found['name']}): {beat}")
        connection.execute('UPDATE story_arcs SET told=1 WHERE arc_id=?', (arc_id,))
    return lines


def seed(connection, world: str, row: dict, rows: dict) -> list[str]:
    """A seed from the arc in focus (the spine, or the one bitten hardest), once each."""
    focus = row['spine_id'] or max(rows, key=lambda key: rows[key]['bite'], default=None)
    stage = focus and stage_of(world, rows[focus])
    if not stage or stage['seed'] in row['planted']:
        return []
    save(connection, state(connection) | {'planted': [*row['planted'], stage['seed']]})
    # Logged against its arc and the truth it points to, to pay off later (dungeon/plotting.py).
    plotting.plant(connection, focus, stage['seed'], stage['truth'])
    return [f"Seed, if it fits the scene: {stage['seed']}"]


def around(world: str, node_id: str, row: dict, rows: dict, hot: list[dict], people: list[dict]) -> list[str]:
    """The threads the people present carry, and the antagonist of an arc in play near here."""
    lines = []
    for person in people:
        name = person['sheet'].get('full') or person['sheet'].get('name') or ''
        if name and (carried := next((thread for thread in hot if touched(thread, name)), None)):
            lines.append(f"{name} carries a thread ({carried['title']}): {carried['truth']}")
    for arc_id, item in rows.items():
        found = arc(world, arc_id)
        if found and node_id in found['antagonist']['where'] and (arc_id == row['spine_id'] or item['bite']):
            lines.append(f"Nearby: {found['antagonist']['name']}, {found['antagonist']['agenda']}.")
    return lines


def note(connection, world: str, node_id: str, people: list[dict], drama: str, now: datetime) -> str:
    """The hidden GM note for a line: pressure, a payoff due, what is due, a seed, and who and what is near."""
    row = state(connection)
    if row['world'] != world or not ACTIVE:
        return ''
    rows, hot = arcs(connection), threads(connection)
    lines = (pressure(connection, world, row, rows, hot, drama, now) + plotting.payoff(connection, rows)
             + due(connection, world, row, rows)
             + seed(connection, world, row, rows) + around(world, node_id, row, rows, hot, people))
    if not lines:
        return ''
    return ("## The game master's note (hidden; work in what fits the scene and the dice, never against them, and "
            'never mention it)\n' + '\n'.join(f'- {line}' for line in lines))


# The journal -------------------------------------------------------------------------------------

def journal(connection) -> list[dict]:
    """The threads the character has come across that are not quests, as they understand them."""
    return [{'id': row['id'], 'kind': row['kind'], 'title': row['title'], 'seen': row['seen']}
            for row in threads(connection) if row['known'] and not row['quest_id']]
