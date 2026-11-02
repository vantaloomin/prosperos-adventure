"""Off-page beats and word getting around (requirements "Off-page beats", "NPC minds: word gets around";
docs/story.md "Off-page beats").

The people the character is connected to keep living while the character is elsewhere. A beat is a Life Card from
the world's beat scene (dungeon/life/cards.py) happening to one of them, {them}:
- **Who.** People the character has met more than once, or who feel strongly about them (any feeling at 2 or more
  either way), who are not in the scene and are not dead.
- **When.** Each story day that passes may bring one (the deck's beat chance at the drama level), up to MOST_DAYS a
  turn; and a beat comes at least every QUIET_TURNS lines, so a long scene does not freeze the world.
- **What it does.** Code applies the card: a fate (wounded, sick, captured, dead, turned, missing, …) that sticks
  to the person (the dead, captured, missing and conscripted are gone from town until something changes it), their
  feelings, rumors. The record keeps the truth as the world's; a death goes in as the world's death.
- **How the character learns of it.** Not at once: what the character would hear (the card's `seen`, as wrong as
  the card says) travels as word, and reaches them a day later on their next line in a town, into the journal as
  belief when it is not the whole truth. A card's rumor about the character or someone else travels the same way.
  With "meanwhile" cutaways on, the narrator also shows the player the beat as it happens.

`pressure` (a person's key) lets another system (the story director) ask for the next beat to land on someone.

All of it is game state, branched with the story (dungeon/timeline.py SAVED); each line's beats are kept with it.
"""
import random
from datetime import date, datetime, timedelta

from dungeon import factions, feelings, happenings, record, table
from dungeon.database import decode, encode, many, optional

QUIET_TURNS = 3
MOST_DAYS = 3
WORD_DAYS = 1
GONE = ('dead', 'captured', 'missing', 'conscripted')
AXES = ('trust', 'affection', 'respect', 'fear', 'desire')
STATE_TEXT = {'wounded': 'hurt', 'sick': 'sick', 'captured': 'taken', 'dead': 'dead', 'turned': 'turned against '
              'the character', 'missing': 'missing', 'indebted': 'in debt', 'wanted': 'wanted by the law',
              'freed': 'free', 'addicted': 'hooked', 'conscripted': 'taken for the army'}


# Who is gone, and who is connected -----------------------------------------------------------------

def fates(connection) -> dict[str, dict]:
    return {row['key']: row for row in many(connection, 'SELECT * FROM story_fates')}


def gone(connection) -> set[str]:
    """The people off the map: dead, taken, missing or conscripted. The townsfolk rules leave them out."""
    return {key for key, row in fates(connection).items() if row['state'] in GONE}


def connected(connection, here: set[str]) -> list[dict]:
    rows = many(connection, 'SELECT * FROM story_people ORDER BY last_met_at DESC')
    dead = {key for key, row in fates(connection).items() if row['state'] == 'dead'}
    return [row for row in rows if row['key'] not in here and row['key'] not in dead
            and (row['meetings'] >= 2 or any(abs(row[axis]) >= 2 for axis in AXES))]


# The off-page clock --------------------------------------------------------------------------------

def offpage(connection) -> dict:
    row = optional(connection, 'SELECT checked_at, quiet FROM story_offpage WHERE id=1')
    return row or {'checked_at': None, 'quiet': 0}


def keep_clock(connection, checked_at: str, quiet: int):
    connection.execute('INSERT INTO story_offpage (id, checked_at, quiet) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE '
                       'SET checked_at=excluded.checked_at, quiet=excluded.quiet', (checked_at, quiet))


def due(connection, now: datetime) -> tuple[int, bool]:
    """The days passed since the last look (each may bring a beat), and whether the turn minimum forces one."""
    clock = offpage(connection)
    days = (now.date() - datetime.fromisoformat(clock['checked_at']).date()).days if clock['checked_at'] else 0
    return min(MOST_DAYS, max(0, days)), clock['quiet'] + 1 >= QUIET_TURNS


# A beat ------------------------------------------------------------------------------------------

def recent(connection, day: date) -> set[str]:
    return {row['card_id'] for row in many(connection, 'SELECT card_id FROM story_beats WHERE at >= ?',
                                           ((day - timedelta(days=14)).isoformat(),))}


def pick(people: list[dict], pressure: str | None, rng) -> dict | None:
    pressed = next((person for person in people if person['key'] == pressure), None)
    return pressed or (rng.choice(people) if people else None)


def fate(connection, person: dict, effect: dict, card: dict, truth: str, logged: str):
    state = effect['state']
    connection.execute('INSERT INTO story_fates (key, name, state, since) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO '
                       'UPDATE SET state=excluded.state, since=excluded.since', (person['key'], person['name'],
                                                                                 state, logged))
    if state == 'dead':
        record.add(connection, 'death', person['name'], truth, logged, truth='world')
    elif state == 'turned':
        feelings.change(connection, person['key'], {'trust': -3, 'affection': -2}, card['title'])


def spread(connection, about: str, text: str, truth: str, heard_at: datetime, message_id: str):
    """Word that will reach the character: what they will hear, and whether it is the whole truth."""
    connection.execute('INSERT INTO story_word (about, text, truth, heard_at, told, message_id) VALUES (?, ?, ?, ?, 0, '
                       '?)', (about, text, truth, heard_at.isoformat(), message_id))


def play(connection, person: dict, drawn: dict, town: str, now: datetime, logged: str, message_id: str) -> str:
    """A beat in play; returns what happened, for a cutaway."""
    card, faction = drawn['card'], drawn.get('faction')
    persona = optional(connection, 'SELECT name FROM persona WHERE id=1')
    names = {'them': person['name'], 'pc': (persona and persona['name']) or 'the character', 'npc': 'someone',
             'town': town, 'faction': faction['name'] if faction else 'the powers'}
    truth, seen = happenings.fill(card['truth'], names), happenings.fill(card['seen'], names)
    record.add(connection, 'fact', person['name'], truth, logged, truth='world')
    spread(connection, person['name'], seen[:1].upper() + seen[1:], 'both' if card['accuracy'] == 'true' else
           'belief', now + timedelta(days=WORD_DAYS), message_id)
    for effect in card['effects']:
        if effect['kind'] == 'fate' and effect['who'] == 'them':
            fate(connection, person, effect, card, truth, logged)
        elif effect['kind'] == 'feeling' and effect['who'] == 'them':
            feelings.change(connection, person['key'], {effect['axis']: effect['shift']}, card['title'])
        elif effect['kind'] == 'reputation' and faction:
            factions.shift(connection, faction, effect['shift'])
    connection.execute('INSERT INTO story_beats (message_id, key, card_id, at) VALUES (?, ?, ?, ?)',
                       (message_id, person['key'], card['id'], now.isoformat()))
    return truth[:1].upper() + truth[1:]


def fire(connection, message_id: str, view: dict, level: dict, now: datetime, logged: str, rng=None,
         pressure: str | None = None) -> list[str]:
    """The beats a line brings, and the cutaways the narrator may show of them."""
    rng = rng or random.SystemRandom()
    clock = offpage(connection)
    if clock['checked_at'] is None:
        keep_clock(connection, now.isoformat(), 0)
        return []
    days, forced = due(connection, now)
    # One chance for each day passed; with no day passed, a long quiet brings one for sure.
    tries = [(f'{message_id}:day:{n}', False) for n in range(days)] or ([(f'{message_id}:quiet', True)] if forced
                                                                        else [])
    here = {person['sheet']['key'] for person in view['people']}
    happened = []
    for seed, force in tries:
        person = pick(connected(connection, here), pressure, rng)
        if person is None:
            break
        captive = {'captive'} if fates(connection).get(person['key'], {}).get('state') == 'captured' else set()
        drawn = happenings.draw(connection, 'beat', seed, view['city']['id'], view['place']['id'], view['data'],
                                level, now.date(), has=captive, skip=recent(connection, now.date()), forced=force)
        if drawn:
            happened.append(play(connection, person, drawn, view['city']['name'], now, logged, message_id))
            pressure = None
    keep_clock(connection, now.isoformat(), 0 if happened else clock['quiet'] + 1)
    if not table.rule(connection, 'cutaways'):
        return []
    return happened


# Word reaching the character --------------------------------------------------------------------------

def heard(connection, now: datetime, logged: str) -> list[str]:
    """The word that has reached town by now, once; it goes in the journal as the character heard it."""
    lines = []
    for row in many(connection, 'SELECT rowid, * FROM story_word WHERE told=0 AND heard_at <= ? ORDER BY heard_at',
                    (now.isoformat(),)):
        connection.execute('UPDATE story_word SET told=1 WHERE rowid=?', (row['rowid'],))
        record.add(connection, 'fact', row['about'], row['text'], logged, truth=row['truth'])
        lines.append(f"Word reaches the character: {row['text']}")
    return lines


def prompt_text(connection) -> str:
    """The connected people who are not as the character last saw them, for the narrator (hidden unless heard)."""
    rows = [row for row in fates(connection).values() if row['state'] in STATE_TEXT]
    if not rows:
        return ''
    return ('## Off the page (kept by the game; the character knows only what word has reached them)\n'
            + '\n'.join(f"- {row['name']} is {STATE_TEXT[row['state']]}." for row in rows))


def cutaway_text(lines: list[str]) -> str:
    return ('## Meanwhile (a cutaway the player turned on: show it briefly, apart from the scene; the character does '
            'not know it)\n' + '\n'.join(f'- {line}' for line in lines)) if lines else ''


def saved(connection, message_id: str) -> list[str] | None:
    row = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='beat'", (message_id,))
    return decode(row['lines']) if row else None


def keep(connection, message_id: str, day: date, lines: list[str]):
    connection.execute("INSERT OR REPLACE INTO story_cards (message_id, scene, day, card_id, lines) VALUES "
                       "(?, 'beat', ?, NULL, ?)", (message_id, day.isoformat(), encode(lines)))

