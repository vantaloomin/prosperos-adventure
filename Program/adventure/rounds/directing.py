"""The director in a round (docs/spec.md "The turn loop" step 2; Batch 2: "An agent can do anything when it turns,
but signs come first"; "Factions and nemeses": "A nemesis becomes an agent").

The director is code, as in Dungeon (adventure/director.py). In a round it gives the Writer only what a character
could see on the page, never the secret behind it: the Writer's context takes these as its signs to place
(adventure/rounds/context.py `writer`, `signs`), and what lies behind each stays in the snapshot for the GM view.

- **Warning signs before a betrayal** (`brewing`, at Gather). A party member running on an agent is turning when
  their feelings toward the user's character have soured (trust and affection together at SOUR or lower) or their
  own motives of the last RECENT turns speak of turning on the party. The director then owes a sign for them this
  turn: the sign itself ("Hesk's purse is heavier than it should be"), picked by code from the kind of betrayal and
  seeded by the turn, never the motive or the plan.
- **Signs come first** (`signs_first`, after React). A party member's declared attack or theft against one of their
  own, or slipping away from the party, goes through only if a sign for them was placed on an earlier turn on this
  branch. Otherwise they hold back this turn: the attempt becomes a sign of it, their motive and lines stand, and
  the sign is placed now, so the betrayal can come next turn and is fair in hindsight. One that goes through is a big
  moment Watch stops for (`draft.extra['moments']`), and a desertion that goes through takes them out of the party
  at Commit. This is the only way an agent leaves on their own: souring feelings never send one away
  (adventure/party.py).
- **Kept by turn** (`betrayal_signs`): each sign placed, for whom and of what kind, read through its turn's place on
  the timeline, so going back forgets it with the turn and every branch reads its own.
- **A nemesis becomes an agent** (`seat_nemesis`, called as the director promotes one) in a campaign that plays
  with agents. Its seat is made an agent's, once: if the user later demotes it by hand, a new grudge does not undo that. The agents' 'pick' puts nemeses ahead
  of characters picked by role and names who dropped to a Program mind (adventure/rounds/declare.py).
"""
import random
import re
from dataclasses import replace

from adventure import party
from adventure.database import identifier, many, optional
from adventure.rounds import engine, memory, seats
from adventure.rounds.contract import Mind, Point, State
from adventure.rounds.modes import users_character

# Trust and affection added up at or below this, toward the user's character: the agent is turning.
SOUR = -4
# Own motives this many turns back still count.
RECENT = 3
# At most this many signs a turn.
MOST = 2
TURNING = (
    ('steal', re.compile(r'\b(steal\w*|stole|rob\w*|pocket\w*|filch\w*|pilfer\w*|take (the|their|his|her) (coin|gold|'
                         r'purse|pack|map|key)\w*)\b', re.I)),
    ('attack', re.compile(r'\b(kill\w*|murder\w*|stab\w*|attack\w*|poison\w*|strike \w+ down|cut \w+ down|'
                          r'throat)\b', re.I)),
    ('desert', re.compile(r'\b(desert\w*|abandon\w*|slip\w* away|leave (them|the party|the others)|run off|'
                          r'steal\w* away in the night)\b', re.I)),
    ('turn', re.compile(r'\b(betray\w*|sell (them|him|her) out|turn\w* on|double-cross\w*|inform\w* on|'
                        r'hand (them|him|her) over)\b', re.I)),
)
SIGNS = {
    'steal': ("{name}'s purse is heavier than it should be.", "{name} lingers by the packs when no one is looking.",
              "{name} has a new ring and no story for where it came from."),
    'attack': ("{name} keeps a hand near their blade, even at rest.",
               "{name} has taken to sitting where they can see everyone's back.",
               "{name} sharpens a knife long after it is sharp."),
    'desert': ("{name}'s pack is tied and ready, as if for a long road.",
               "{name} keeps looking back down the road they came by.",
               "{name} asks, too casually, how far it is to the next town."),
    'turn': ("{name} goes quiet whenever the plan comes up.", "{name} won't meet anyone's eye tonight.",
             "{name} was seen talking with a stranger who left in a hurry."),
}
HELD = {'steal': '{name} hesitates, hand hovering, and lets the moment pass for now.',
        'attack': '{name} hesitates, hand on their weapon, and does not strike yet.',
        'desert': '{name} lingers at the edge of camp, but stays for now.',
        'turn': '{name} holds their tongue, for now.'}


def kind_of(text: str) -> str | None:
    return next((kind for kind, words in TURNING if words.search(text or '')), None)


def sign_for(kind: str, name: str, seed: str) -> str:
    return random.Random(seed).choice(SIGNS[kind]).format(name=name)


def own_side(connection, snapshot) -> set[str]:
    """The party and the user's character."""
    human = users_character(connection, snapshot)
    return party.keys(connection) | ({human} if human else set())


def signed_before(connection, point: Point) -> set[str]:
    """Whose betrayal has had a sign placed on a turn before `point`, on its branch."""
    clause, values = memory.where(connection, point)
    clause = clause.replace('branch_id', 't.branch_id').replace('seq', 't.seq')
    return {row['character_key'] for row in many(
        connection, "SELECT s.character_key FROM betrayal_signs s JOIN round_turns t ON t.id = s.turn_id WHERE "
                    f"t.state='committed' AND {clause}", values)}


# Gather -------------------------------------------------------------------------------------------------------------

def turning(connection, snapshot, key: str) -> str | None:
    """The kind of betrayal `key` is working toward, if any: from their own recent motives, else soured feelings."""
    now = snapshot.number
    motives = [row['text'] for row in memory.recall(connection, key, snapshot.point, limit=200)
               if row['kind'] == 'motive' and now - row['number'] <= RECENT]
    for text in motives:
        if found := kind_of(text):
            return found
    human = users_character(connection, snapshot)
    if human is None or human == key:
        return None
    held = memory.toward(connection, key, human, snapshot.point)
    return 'turn' if held['trust'] + held['affection'] <= SOUR else None


async def brewing(turn: engine.Turn):
    """Gathering: the warning signs owed this turn, as signs for the Writer, with what lies behind them kept apart."""
    snapshot = turn.snapshot
    with turn.database.connect() as connection:
        mine = party.keys(connection)
        owed = [(seat, kind) for seat in snapshot.agents() if seat.key in mine
                and (kind := turning(connection, snapshot, seat.key))]
    held = snapshot.settings.setdefault('director', {'signs': [], 'behind': []})
    for seat, kind in owed[:MOST]:
        sign = sign_for(kind, seat.name, f'{snapshot.turn_id}:{seat.key}')
        held['signs'].append(sign)
        held['behind'].append({'key': seat.key, 'kind': kind, 'sign': sign})


# After React: signs come first --------------------------------------------------------------------------------------

def aimed_at_own(text: str, snapshot, own: set[str], actor: str) -> bool:
    for seat in snapshot.seats:
        if seat.key in own and seat.key != actor:
            names = {seat.name, seat.name.split(' ')[0]}
            if any(len(name) > 2 and re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', text, re.I) for name in names):
                return True
    return bool(re.search(r'\b(the party|the others|my companions|the group)\b', text, re.I))


def betrayal(declared, snapshot, own: set[str]) -> str | None:
    """The kind of betrayal a declaration attempts against the actor's own side, if it does."""
    kind = kind_of(declared.intent)
    if kind is None:
        return None
    if kind == 'desert':
        return kind
    return kind if aimed_at_own(declared.intent, snapshot, own, declared.seat) else None


async def signs_first(turn: engine.Turn):
    """A party member's betrayal with no sign placed before is held back this turn, and its sign placed now."""
    snapshot, draft = turn.snapshot, turn.draft
    with turn.database.connect() as connection:
        own = own_side(connection, snapshot)
        signed = signed_before(connection, snapshot.point)
    held = snapshot_director(turn)
    for key, declared in list(draft.declarations.items()):
        seat = snapshot.seat(key)
        if seat is None or seat.mind != Mind.AGENT or key not in own:
            continue
        kind = betrayal(declared, snapshot, own)
        if kind is None:
            continue
        if key in signed:
            # Its signs came first: it goes through, and Watch stops for it (adventure/rounds/watch.py).
            draft.extra.setdefault('moments', []).append({'kind': 'betrayal', 'text': f'{seat.name} turned on the party.'})
            draft.extra.setdefault('director', {}).setdefault('through', []).append({'key': key, 'kind': kind})
            continue
        draft.extra.setdefault('director', {}).setdefault('held', {})[key] = declared.intent
        # A new declaration in place of the old: what the character first declared stays as it was (draft.declared).
        draft.declarations[key] = replace(declared, intent=HELD[kind].format(name=seat.name))
        if not any(item['key'] == key for item in held['behind']):
            sign = sign_for(kind, seat.name, f'{snapshot.turn_id}:{key}')
            held['signs'].append(sign)
            held['behind'].append({'key': key, 'kind': kind, 'sign': sign})


def snapshot_director(turn: engine.Turn) -> dict:
    """The director's part of the turn: signs placed after Gather are staged in the draft (the snapshot is frozen),
    starting from those Gather froze."""
    staged = turn.draft.extra.setdefault('director', {})
    if 'signs' not in staged:
        frozen = turn.snapshot.settings.get('director') or {}
        staged['signs'] = list(frozen.get('signs', []))
        staged['behind'] = [dict(item) for item in frozen.get('behind', [])]
    return staged


def signs(turn: engine.Turn) -> list[str]:
    """What the Writer is to place this turn: the signs, never what lies behind them."""
    staged = turn.draft.extra.get('director') or {}
    if 'signs' in staged:
        return list(staged['signs'])
    return list((turn.snapshot.settings.get('director') or {}).get('signs', []))


# Commit -------------------------------------------------------------------------------------------------------------

def committed(connection, turn: engine.Turn):
    staged = turn.draft.extra.get('director') or {}
    placed = staged.get('behind') if 'behind' in staged else (turn.snapshot.settings.get('director') or {}).get(
        'behind', [])
    # A desertion its signs came before: they leave the party (adventure/party.py).
    for item in staged.get('through') or []:
        if item['kind'] == 'desert':
            party.leave(connection, item['key'])
    for item in placed or []:
        connection.execute('INSERT INTO betrayal_signs (id, turn_id, character_key, kind, sign, created_at) VALUES '
                           '(?, ?, ?, ?, ?, ?)', (identifier(), turn.id, item['key'], item['kind'], item['sign'],
                                                  turn.database.now()))


# Nemeses ------------------------------------------------------------------------------------------------------------

def seat_nemesis(connection, name: str, now: str) -> str | None:
    """A new nemesis runs on an agent: its seat (a person of the story by that name, else one of its own) becomes an
    agent's, the first time only, so the user's demoting it by hand stands."""
    if optional(connection, 'SELECT 1 FROM nemesis_seats WHERE name=?', (name,)):
        return None
    if not any(seat.mind == Mind.AGENT for seat in seats.seats(connection)):
        return None  # a campaign with no agents plays as Dungeon does
    known = optional(connection, 'SELECT key FROM story_people WHERE lower(name)=lower(?)', (name,))
    key = known['key'] if known else f"nemesis-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:60]}"
    current = seats.seat(connection, key)
    if current is None or current.mind == Mind.PROGRAM:
        seats.set_seat(connection, key, current.name if current else name[:1].upper() + name[1:], now,
                       mind=Mind.AGENT)
    connection.execute('INSERT INTO nemesis_seats (name, seat_key, created_at) VALUES (?, ?, ?)', (name, key, now))
    return key


engine.register(State.GATHERING, 'director', brewing, after='pick')
engine.register(State.REACTING, 'signs_first', signs_first, after='react')
engine.on_commit('director', committed)
