"""Watch: the story plays itself, and stops for the big moments (docs/spec.md Batch 3: "Watch autoplays and pauses
on big moments"; Batch 4: "Cost is held by a turn budget plus a session cap"; "Waiting and pauses": "Every pause says
why and what next").

- **The timer is a command like any other.** The screen counts the user's seconds (`mode_settings.watch_seconds`, 0
  for stepping by hand only) and then sends the timer's Next (`auto`), against the newest turn it knows, through the
  one-writer queue (adventure/rounds/queue.py). Next by hand is the round loop's own Next
  (adventure/round_routes.py), which always plays a turn.
- **Big moments pause it.** The timer's Next is refused while the newest turn was a Watch turn with a big moment the
  user has not gone on from (`paused`): a death, a betrayal (a party member's attack or theft that landed against
  another of the party or the user's character), a chapter's end, a new nemesis, or a moment another step flagged
  in the draft (`draft.extra['moments']`, [{'kind', 'text'}]). Code finds them by comparing the story after the turn
  with what Gather froze (`settings['watch']`), so nothing has to remember to say so. Continue (`go_on`) or Next by
  hand goes on; going back to an earlier turn leaves the pause with the turn it belongs to.
- **The session cap** pauses it too, checked at Idle (adventure/pace.py `capped`): a turn under way finishes, and
  the timer's Next is refused until the cap is raised.

Every pause carries its kind and one line saying why, for the banner ("Paused: Hesk betrayed the party.").
"""
from adventure import chapters, pace, party, record
from adventure.database import decode, many, optional
from adventure.errors import DomainError
from adventure.rounds import engine, queue, turns
from adventure.rounds.contract import Mode, Snapshot, State, TurnResult
from adventure.rules import ladder

# The risky kinds that turn on one's own side (adventure/rounds/resolve.py KINDS).
TURNING = ('attack', 'steal')
KINDS = ('death', 'betrayal', 'chapter', 'nemesis', 'cap')


# Gather: what the story looked like before the turn ------------------------------------------------------------------

def before(connection) -> dict:
    return {'dead': sorted(record.dead(connection)), 'chapter': chapters.pending(connection) is not None,
            'nemeses': sorted(row['name'] for row in many(connection, "SELECT name FROM story_nemeses WHERE "
                                                                      "status='alive'"))}


async def frozen(turn: engine.Turn):
    """Gathering, in Watch: the story as it stood, to find the turn's big moments against."""
    if turn.snapshot.mode == Mode.WATCH:
        with turn.database.connect() as connection:
            turn.snapshot.settings['watch'] = before(connection)


# Big moments ------------------------------------------------------------------------------------------------------

def deaths(connection, was: dict) -> list[dict]:
    gone = record.dead(connection) - set(was.get('dead', []))
    names = {row['subject'].lower(): row['subject'] for row in many(
        connection, "SELECT subject FROM record_entries WHERE kind='death' AND removed=0 ORDER BY rowid")}
    return [{'kind': 'death', 'text': f'{names.get(name, name)} died.'} for name in sorted(gone)]


def betrayals(connection, snapshot: Snapshot, result: TurnResult | None) -> list[dict]:
    """A party member's attack or theft that landed against one of their own: the party or the user's character."""
    if result is None:
        return []
    human = snapshot.human()
    own = party.keys(connection) | ({human.key} if human else set())
    names = {seat.key: seat.name for seat in snapshot.seats}
    found = []
    for roll in result.rolls:
        actor, target = roll.get('actor'), roll.get('target')
        landed = roll.get('band') in ladder.BANDS and ladder.succeeded(roll['band'])
        if roll.get('kind') in TURNING and landed and actor in own and target in own and actor != target:
            found.append({'kind': 'betrayal', 'text': f"{names.get(actor, actor)} betrayed the party."})
    return found[:1]


def nemeses(connection, was: dict) -> list[dict]:
    known = set(was.get('nemeses', []))
    return [{'kind': 'nemesis', 'text': f"{row['name'][:1].upper() + row['name'][1:]} has sworn to come back."}
            for row in many(connection, "SELECT name FROM story_nemeses WHERE status='alive' ORDER BY since")
            if row['name'] not in known]


def moments(connection, row: dict) -> list[dict]:
    """The big moments of a committed Watch turn, as the story stands now."""
    if row['mode'] != Mode.WATCH or row['state'] != State.COMMITTED:
        return []
    snapshot, draft = Snapshot.of(decode(row['snapshot'])), decode(row['draft']) or {}
    was = snapshot.settings.get('watch')
    if was is None:
        return []
    result = TurnResult.of(draft['result']) if draft.get('result') else None
    flagged = [{'kind': str(item.get('kind') or 'moment'), 'text': str(item.get('text') or '')}
               for item in (draft.get('extra') or {}).get('moments', []) if isinstance(item, dict)]
    chapter = [{'kind': 'chapter', 'text': 'The chapter ended.'}] \
        if chapters.pending(connection) is not None and not was.get('chapter') else []
    return [*deaths(connection, was), *betrayals(connection, snapshot, result), *flagged, *nemeses(connection, was),
            *chapter]


def cap(connection) -> int:
    from adventure.rounds.agents import settings as agent_settings
    return agent_settings(connection)['session_cap']


def paused(app, connection) -> dict | None:
    """Why the timer must not go on, if it must not: the session cap, or the newest turn's first big moment."""
    if pace.capped(app.database, cap(connection)):
        return {'kind': 'cap', 'text': 'This session reached its cap.', 'turn_id': queue.head(connection)}
    head = queue.head(connection)
    if head is None or optional(connection, 'SELECT 1 FROM watch_continued WHERE turn_id=?', (head,)):
        return None
    found = moments(connection, turns.get(connection, head))
    return found[0] | {'turn_id': head} if found else None


def go_on(connection, turn_id: str, now: str):
    """The user goes on from the pause on this turn: the timer runs again."""
    connection.execute('INSERT OR IGNORE INTO watch_continued (turn_id, created_at) VALUES (?, ?)', (turn_id, now))


def check_timer(app):
    """The timer's Next may run: the campaign is in Watch and nothing pauses it."""
    from adventure.rounds.seats import settings
    with app.database.connect() as connection:
        if settings(connection)['mode'] != Mode.WATCH:
            raise DomainError('The story is not in Watch.', 409, 'not_watch')
        stop = paused(app, connection)
    if stop is not None:
        raise DomainError(f"Paused: {stop['text']}", 409, 'paused')


def view(app, connection) -> dict:
    from adventure.rounds.modes import settings
    return {'seconds': settings(connection)['watch_seconds'], 'paused': paused(app, connection)}


engine.register(State.GATHERING, 'watch', frozen, after='pick')
