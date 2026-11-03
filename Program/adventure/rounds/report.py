"""The checks in a round's Writing step, the turn report and the status line (docs/spec.md "The draft scan and the
Reviewer", "Rolls, overrides and the turn report").

**Gathering** freezes the house rulebook into the snapshot (`settings['house_rules']`), with whether the Reviewer runs,
so the Writer, the Reviewer, the scan and a re-ask all read the rules as they stood when the turn began.

**Writing** ends with `checks`, straight after the Writer's step ('write'): any pane the Writer wrote is taken out, the
Reviewer runs when it is on (adventure/rounds/reviewer.py), then the scan (adventure/rounds/scan.py settle), which
always runs, and code adds its own System panes after the post (adventure/rounds/panes.py). What is committed is the settled post, never a
draft with a hard failure in it. What the checks found and fixed is staged in `draft.extra['w5']` and committed
with the turn's draft.

**The turn report** is read from the committed turn itself (its snapshot and draft in round_turns), so it needs no
table of its own and always matches what was committed: what the user set, each roll and what it produced in plain
words (with the numbers unless the Table hides rolls), the numbers that changed, the Writer's inventions, the scan
and Reviewer fixes, the corrections made since, off-page beats, open questions, and the decision left to the user. Motives appear only where the
mode shows them (Author and Watch) or the GM view is open; in Play the user sees their own character's.

**The status line** is always visible: the turn just played, what is pending, and when off-page beats are next due.
W6 draws both.
"""
from dataclasses import fields

from adventure import beats, table
from adventure.database import decode, many
from adventure.narration import prompt as narration_prompt
from adventure.rounds import agents, context, corrections, engine, house_rules, panes, reviewer, scan, turns
from adventure.rounds.contract import Mind, Mode, Snapshot, State, TurnResult, plain
from adventure.rounds.draft import Draft
from adventure.rounds.house_rules import Rulebook
from adventure.world import naming

# How many of the story's last posts the Reviewer reads for continuity.
BEFORE = 3


# Gathering: the rules as they stand ----------------------------------------------------------------------------------

def book_of(data: dict | None) -> Rulebook:
    """A rulebook from its frozen form in a snapshot; the defaults for a turn frozen before there was one."""
    names = {item.name for item in fields(Rulebook)}
    given = {key: tuple(value) if isinstance(value, list) else value for key, value in (data or {}).items()
             if key in names}
    return Rulebook(**given)


def frozen(connection) -> dict:
    """What the checks need frozen at Gather: the book in force and whether the Reviewer runs."""
    chosen = house_rules.stored(connection).get('reviewer')
    return {'house_rules': plain(house_rules.now(connection)),
            'reviewer': reviewer.enabled(agents.settings(connection) | {'reviewer': chosen}),
            'panes': bool(table.rules(connection).get('show_odds'))}


def solo(turn: engine.Turn) -> bool:
    """Today's game: a player's line with no agents at the table (adventure/rounds/solo.py, telling.py), which keeps
    prose.py's own checks exactly as it always had."""
    return 'solo' in turn.draft.extra and not turn.snapshot.agents()


async def gather(turn: engine.Turn):
    if solo(turn):
        return
    with turn.database.connect() as connection:
        turn.snapshot.settings |= frozen(connection)


# Writing: the checks -------------------------------------------------------------------------------------------------

def stop_for(turn: engine.Turn) -> scan.Stop | None:
    """In Play, the user's character and what they declared: a line of theirs they never said is past the stop."""
    human = turn.snapshot.human()
    if turn.snapshot.mode != Mode.PLAY or human is None:
        return None
    declared = turn.draft.declarations.get(human.key)
    said = [declared.intent, *(line.text for line in declared.lines)] if declared else []
    replies = [reply.get('text') or '' for seat, reply in turn.draft.replies.items() if seat == human.key]
    return scan.Stop(human.name, ' '.join([*said, *replies]))


def canon(connection, turn: engine.Turn) -> str:
    """Every name the story already holds, which the scan never outlaws: the seats, the people met, the record and
    the city's own data."""
    from adventure import story
    people = [row['name'] for row in many(connection, 'SELECT name FROM story_people')]
    subjects = [row['subject'] for row in many(connection, 'SELECT subject FROM record_entries WHERE removed=0')]
    try:
        city = story.city_data(connection, story.scene_row(connection)['city_id'])
    except Exception:  # noqa: BLE001 - no city yet: the names above are the canon
        city = None
    return naming.allowed_words(' '.join(seat.name for seat in turn.snapshot.seats), ' '.join(people),
                                ' '.join(subjects), city)


def before(connection, turn: engine.Turn) -> list[str]:
    """The last posts on the turn's branch, oldest first, for the Reviewer's continuity check."""
    from adventure import timeline
    where, values = timeline.visible(connection, turn.point.branch)
    rows = many(connection, f"SELECT text FROM story_messages WHERE role='narrator' AND status='complete' AND {where} "
                            'ORDER BY seq DESC LIMIT ?', (*values, BEFORE))
    return [row['text'] for row in reversed(rows)]


def model(turn: engine.Turn):
    """`complete(system, messages)` on the story's model, or None when none is set up."""
    from adventure import story, text_models
    with turn.database.connect() as connection:
        config = text_models.config_for(connection, story.JOB)
    if config is None:
        return None
    return lambda system, messages: story.complete(turn.app, config, system, messages)


async def checks(turn: engine.Turn):
    """The post as it will be committed: without any pane the Writer wrote, reviewed when the Reviewer is on, settled
    by the scan, then with code's own panes after it (adventure/rounds/panes.py)."""
    if solo(turn) or not turn.draft.post.strip():
        return
    post = panes.stripped(turn.draft.post)
    book, settings = book_of(turn.snapshot.settings.get('house_rules')), turn.snapshot.settings
    complete = model(turn)
    with turn.database.connect() as connection:
        known, earlier = canon(connection, turn), before(connection, turn)
    notes = []
    if complete is not None and settings.get('reviewer'):
        brief = turn.draft.result.brief if turn.draft.result else None
        notes = await reviewer.review(complete, book, brief, post, earlier)
        post, notes = await reviewer.apply(complete, book, post, notes)
    settled = await scan.settle(post, book, complete, canon=known, stop=stop_for(turn))
    math = list(turn.draft.result.brief.math) if turn.draft.result and settings.get('panes') else []
    turn.draft.post = panes.placed(settled.text, panes.rolls(book, math))
    turn.draft.extra['w5'] = {'scan': settled.scan.report(), 'cut': list(settled.cut), 'rewrites': settled.rewrites,
                              'review': notes}


engine.register(State.GATHERING, 'house_rules', gather, after='pick')
engine.register(State.WRITING, 'checks', checks, after='write')


# The turn report -----------------------------------------------------------------------------------------------------

def roll_line(roll: dict, numbers: bool) -> dict:
    """One roll in plain words: who acted, what was at stake, the stat, and what it produced."""
    band = roll.get('band', '')
    line = {'actor': roll.get('actor', ''), 'action': roll.get('action', ''), 'stat': roll.get('stat', ''),
            'result': narration_prompt.BANDS.get(band, band.replace('_', ' '))}
    if numbers:
        line |= {key: roll[key] for key in ('natural', 'bonus', 'total', 'difficulty', 'die') if key in roll}
    return line


def motives(result: TurnResult, mode: str, gm_view: bool, own: str | None) -> list[dict]:
    """The declared motives this reader may see: everyone's in Author, Watch or the GM view, the user's own in Play."""
    shown = [item for item in result.declarations if item.motive and
             (gm_view or mode != Mode.PLAY or item.seat == own)]
    return [{'seat': item.seat, 'motive': item.motive} for item in shown]


def report(connection, turn_id: str, gm_view: bool = False) -> dict:
    """The report of a committed turn, from its own row."""
    row = turns.get(connection, turn_id)
    snapshot = Snapshot.of(decode(row['snapshot']))
    draft = Draft.of(decode(row['draft']))
    result = draft.result or TurnResult()
    human = snapshot.human()
    own = human.key if human is not None and human.mind == Mind.HUMAN else None
    numbers = bool(table.rules(connection).get('show_odds'))
    staged, written = draft.extra.get('w5') or {}, draft.extra.get('w4') or {}
    declared = draft.declarations.get(own) if own else None
    struck = corrections.struck(connection, row['id'])
    return {
        'turn_id': row['id'], 'number': row['number'] + 1, 'mode': row['mode'], 'state': row['state'],
        'marks': decode(row['marks']) or [],
        'set': {'intent': declared.intent if declared else '', 'lines': [line.text for line in declared.lines]
                if declared else [], 'beats': list(result.brief.beats)},
        'rolls': [roll_line(roll, numbers) for roll in result.rolls],
        'numbers': list(result.brief.math),
        'inventions': [item | {'struck': (item.get('name') or '').casefold() in struck}
                       for item in written.get('inventions') or [] if isinstance(item, dict)],
        'corrections': corrections.of_turn(connection, row['id']),
        'checks': {'scan': staged.get('scan') or {}, 'cut': staged.get('cut') or [],
                   'rewrites': staged.get('rewrites', 0), 'review': staged.get('review') or []},
        'offpage': list(written.get('offpage') or []),
        'questions': list((draft.extra.get('w3') or {}).get('questions') or []),
        'motives': motives(result, row['mode'], gm_view or context.missed_shown(connection, row['mode']), own),
        'next': result.brief.stop_point,
    }


def status(connection) -> dict:
    """The always-visible status line: the turn just played, what is pending, when off-page beats are next due."""
    last = many(connection, "SELECT id, number, committed_at FROM round_turns WHERE state='committed' "
                            'ORDER BY committed_at DESC, rowid DESC LIMIT 1')
    open_turn = turns.under_way(connection)
    pending = None
    if open_turn is not None:
        waiting = (decode(open_turn['draft']) or {}).get('awaiting')
        pending = {'turn_id': open_turn['id'], 'state': open_turn['state'],
                   'seat': waiting['seat'] if open_turn['state'] == State.AWAITING_USER and waiting else None}
    quiet = beats.offpage(connection)['quiet']
    return {'last': {'turn_id': last[0]['id'], 'number': last[0]['number'] + 1} if last else None,
            'pending': pending, 'offpage_within': max(1, beats.QUIET_TURNS - quiet)}
