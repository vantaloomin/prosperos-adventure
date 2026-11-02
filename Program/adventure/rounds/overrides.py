"""Roll overrides from the GM view (docs/spec.md "Rolls, overrides and the turn report": "From the GM view, in any
mode, the user can override a roll's result. The override is logged with the turn and the reason, the turn is
marked, and the affected passage is rewritten; after commit it is a correction. Overrides are off in Ironman.").

An override names one roll of a turn's result (its position in `TurnResult.rolls`), the band it should land on and
why. Nothing is rolled again; only that roll's band changes, and everything that reads the roll reads the new band:

- **Before Commit** the turn's draft changes: the roll, its outcome and the brief, so the Writer renders it so.
- **After Commit** the kept roll changes too (story_rolls for the player's own line, round_rolls for anyone
  else's), and the passage is flagged on the reply with what changed, for Rewrite or a correction
  (adventure/rounds/corrections.py) to bring the prose in line.

Every override is kept in `round_overrides` (turn, roll, from, to, reason, when) and marks the turn 'override', as a
turn the GM view was open on is marked, so the turn report and the dice log can say so.
"""
from adventure import chapters
from adventure.database import decode, encode, identifier, many, optional
from adventure.errors import require
from adventure.rounds import resolve, turns
from adventure.rounds.contract import State, TurnResult
from adventure.rounds.draft import Draft
from adventure.rules import ladder

MARK = 'override'
MOST_REASON = 300


def allowed(connection) -> bool:
    return not chapters.ironman(connection)


def override(connection, turn_id: str, position: int, band: str, reason: str, now: str) -> dict:
    """Override one roll of a turn; returns the override as logged."""
    require(allowed(connection), 'Rolls stand in Ironman.', 409, 'ironman')
    require(band in ladder.BANDS, 'That is not a result a roll can land on.', 422)
    require(reason.strip(), 'Say why the roll is overridden.', 422)
    row = turns.get(connection, turn_id)
    require(row['state'] != State.DISCARDED, 'That turn was thrown away.', 409)
    draft = Draft.of(decode(row['draft']))
    result = draft.result
    require(result is not None and 0 <= position < len(result.rolls), 'That turn has no such roll.', 404)
    roll = result.rolls[position]
    was = roll['band']
    roll['band'] = band
    names = {seat['key']: seat['name'] for seat in (decode(row['snapshot']) or {}).get('seats', [])}
    result.outcomes[position] = resolve.outcome(roll, names) if position < len(result.outcomes) else {}
    redone(result, names)
    committed = row['state'] == State.COMMITTED
    if committed:
        kept(connection, turn_id, roll, position, band, result.rolls)
        flagged(connection, turn_id, roll, names, band)
    turns.keep(connection, turn_id, draft=draft.data())
    turns.mark(connection, turn_id, MARK)
    logged = {'id': identifier(), 'turn_id': turn_id, 'position': position, 'actor': roll['actor'],
              'action': roll['action'], 'from_band': was, 'to_band': band, 'reason': reason.strip()[:MOST_REASON],
              'after_commit': int(committed), 'created_at': now}
    connection.execute(f"INSERT INTO round_overrides ({', '.join(logged)}) VALUES ({', '.join('?' * len(logged))})",
                       tuple(logged.values()))
    return logged


def redone(result: TurnResult, names: dict[str, str]):
    """The brief's outcome and math lines from the rolls as they stand now; the lies heard after them stay."""
    lines = [resolve.outcome_line(roll, names) for roll in result.rolls]
    result.brief.outcomes = lines + result.brief.outcomes[len(lines):]
    result.brief.math = [resolve.math_line(roll, names) for roll in result.rolls]


def kept(connection, turn_id: str, roll: dict, position: int, band: str, rolls: list[dict]):
    """The roll as it was kept at Commit, changed: the player's own in story_rolls, anyone else's in round_rolls
    (where the player's own come first in the result and are not counted)."""
    if roll.get('kind') == resolve.LINE:
        connection.execute('UPDATE story_rolls SET band=? WHERE id=?', (band, roll.get('id')))
        return
    among = position - sum(item.get('kind') == resolve.LINE for item in rolls[:position])
    connection.execute('UPDATE round_rolls SET band=? WHERE turn_id=? AND position=?', (band, turn_id, among))


def flagged(connection, turn_id: str, roll: dict, names: dict[str, str], band: str):
    """The reply the turn told, flagged: its prose may still tell the roll as it landed before."""
    row = turns.get(connection, turn_id)
    reply = optional(connection, "SELECT id, text, flags FROM story_messages WHERE reply_to=? AND role='narrator' "
                                 "AND status='complete' ORDER BY seq DESC LIMIT 1", (row['anchor_id'],))
    if reply is None or not reply['text']:
        return
    why = (f"A roll was overridden: {names.get(roll['actor'], roll['actor'])}'s \"{roll['action']}\" now lands as "
           f"{ladder.LABELS[band]}. Tell it that way.")
    flags = [flag for flag in decode(reply['flags']) or [] if flag.get('passage') != reply['text']]
    connection.execute('UPDATE story_messages SET flags=? WHERE id=?', (encode(
        [*flags, {'passage': reply['text'], 'why': [why], 'dead': {}}]), reply['id']))


def logged(connection, turn_id: str) -> list[dict]:
    return many(connection, 'SELECT * FROM round_overrides WHERE turn_id=? ORDER BY created_at', (turn_id,))

