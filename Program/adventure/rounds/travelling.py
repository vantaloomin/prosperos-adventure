"""Where the party goes, and who goes their own way (docs/spec.md "Travel and splitting the party").

- **A lead proposes.** In Play the lead is the user's character; in Author and Watch it is the party's leader, set
  on the cast page (`party_lead`) and by default the first seat (`lead`). At Gather the lead is frozen with the
  snapshot (`settings['travel']['lead']`). When the lead's declared move sets out somewhere (adventure/travel.py
  LEAVING), that move is the turn's travel line (`line`): Dungeon's directions, hex searches and journeys take it as
  they take the player's line. The Author nudges the destination like any other beat.
- **Anyone can refuse and split off.** After React (`split`), a party member running on an agent who declared they
  stay, refuse or go their own way (STAYING) does not follow: they split off where the party leaves them. Program
  party members follow, by Dungeon's party rules. Splitting is committed by turn (`split_off`), read through the
  turn's place on the timeline, so going back undoes it.
- **Until they meet again.** A character apart is out of the scene and lives as an off-page thread (code rolls, their
  agent writes their lines, adventure/rounds/offpage.py) until the party is where they split off, or one of them
  declares they rejoin. At Gather, straight after 'present', those apart are taken out of `snapshot.present`
  (`elsewhere`), so they neither declare nor take an agent slot; `gathered` then lists who is away and who is back.
"""
import re

from adventure import party, travel
from adventure.database import identifier, many, optional
from adventure.errors import require
from adventure.rounds import engine, memory, seats
from adventure.rounds.contract import Mind, Mode, Point, State
from adventure.rounds.modes import users_character

STAYING = re.compile(r"\b(stay\w*|remain\w*|refus\w*|won't (go|come|follow)|will not (go|come|follow)|"
                     r"part(s|ing)? ways|split\w* off|go\w* (my|his|her|their) own way|head\w* elsewhere|"
                     r"turn\w* back alone|keep\w* (my|his|her|their) distance)\b", re.I)
REJOINING = re.compile(r'\b(rejoin\w*|catch\w* up (with|to)|come\w* back to (them|the party|the others)|'
                       r'find\w* (them|the party|the others))\b', re.I)


# The lead -----------------------------------------------------------------------------------------------------------

def leader(connection) -> str | None:
    row = optional(connection, 'SELECT seat_key FROM party_lead WHERE id=1')
    return row['seat_key'] if row else None


def set_leader(connection, key: str | None, now: str) -> str | None:
    """The party's leader in Author and Watch, or None for the first seat."""
    require(key is None or seats.seat(connection, key) is not None, 'That character has no seat.', 404)
    connection.execute('INSERT INTO party_lead (id, seat_key, updated_at) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE '
                       'SET seat_key=excluded.seat_key, updated_at=excluded.updated_at', (key, now))
    return leader(connection)


def lead(connection, snapshot) -> str | None:
    """Who proposes where the party goes this turn."""
    if snapshot.mode == Mode.PLAY:
        return users_character(connection, snapshot)
    chosen = leader(connection)
    if chosen and snapshot.seat(chosen) is not None:
        return chosen
    return snapshot.seats[0].key if snapshot.seats else None


def line(turn: engine.Turn) -> str | None:
    """The turn's travel line: the lead's declared move, when it sets out somewhere."""
    key = (turn.snapshot.settings.get('travel') or {}).get('lead')
    declared = turn.draft.declarations.get(key) if key else None
    return declared.intent if declared and travel.LEAVING.search(declared.intent) else None


# Who is apart -------------------------------------------------------------------------------------------------------

def rows(connection, point: Point) -> list[dict]:
    clause, values = memory.where(connection, point)
    clause = clause.replace('branch_id', 't.branch_id').replace('seq', 't.seq')
    return many(connection, 'SELECT s.* FROM split_off s JOIN round_turns t ON t.id = s.turn_id WHERE '
                            f"t.state='committed' AND {clause} ORDER BY t.seq, s.rowid", values)


def apart(connection, point: Point) -> dict[str, dict]:
    """Who has split off from the party as of `point`, with where they were left."""
    away: dict[str, dict] = {}
    for row in rows(connection, point):
        if row['kind'] == 'left':
            away[row['character_key']] = {'city_id': row['city_id'], 'place_id': row['place_id']}
        else:
            away.pop(row['character_key'], None)
    return away


# Steps --------------------------------------------------------------------------------------------------------------

async def elsewhere(turn: engine.Turn):
    """Gathering, after 'present': those who split off are out of the scene until the party is where they were left."""
    from adventure import story
    snapshot = turn.snapshot
    with turn.database.connect() as connection:
        away = apart(connection, snapshot.point)
        here = story.scene_row(connection)
    gone = {key for key, where in away.items() if where != here}
    if gone:
        snapshot.present = [key for key in snapshot.present if key not in gone]


async def gathered(turn: engine.Turn):
    """Gathering: the lead, and who comes back this turn because the party is where they split off."""
    from adventure import story
    snapshot = turn.snapshot
    with turn.database.connect() as connection:
        key = lead(connection, snapshot)
        away = apart(connection, snapshot.point)
        here = story.scene_row(connection)
    back = [other for other, where in away.items() if where == here]
    snapshot.settings['travel'] = {'lead': key, 'apart': sorted(set(away) - set(back)), 'rejoined': back,
                                   'from': here}


async def split(turn: engine.Turn):
    """After React: when the lead sets out, the party agents who declared they stay split off; those apart who
    declared they rejoin come back."""
    snapshot, draft = turn.snapshot, turn.draft
    held = snapshot.settings.get('travel') or {}
    staged = draft.extra.setdefault('travel', {'line': None, 'split': [], 'rejoined': list(held.get('rejoined', []))})
    staged['line'] = line(turn)
    with turn.database.connect() as connection:
        mine = party.keys(connection)
    for key, declared in draft.declarations.items():
        seat = snapshot.seat(key)
        if seat is None or seat.mind != Mind.AGENT:
            continue
        if key in held.get('apart', []) and REJOINING.search(declared.intent) and key not in staged['rejoined']:
            staged['rejoined'].append(key)
        elif staged['line'] and key in mine and key != held.get('lead') and STAYING.search(declared.intent) \
                and key not in staged['split']:
            staged['split'].append(key)


def committed(connection, turn: engine.Turn):
    staged = turn.draft.extra.get('travel') or {}
    rejoined = staged.get('rejoined', (turn.snapshot.settings.get('travel') or {}).get('rejoined', []))
    if not staged.get('split') and not rejoined:
        return
    # Where the party was when the turn began: where those who split off were left, and where the others met them.
    here = (turn.snapshot.settings.get('travel') or {}).get('from') or {'city_id': '', 'place_id': ''}
    for kind, keys in (('rejoined', rejoined), ('left', staged.get('split', []))):
        for key in keys:
            connection.execute('INSERT INTO split_off (id, turn_id, character_key, kind, city_id, place_id, created_at) '
                               'VALUES (?, ?, ?, ?, ?, ?, ?)', (identifier(), turn.id, key, kind, here['city_id'],
                                                                here['place_id'], turn.database.now()))


engine.register(State.GATHERING, 'apart', elsewhere, after='present')
engine.register(State.GATHERING, 'travel', gathered, after='pick')
engine.register(State.REACTING, 'split', split, after='react')
engine.on_commit('travel', committed)
