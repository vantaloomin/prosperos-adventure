"""The party (requirements "NPCs and party": always autonomous, influenced like real people, never commanded;
"Play screen": party and relationships; "Off-page beats": absent party members).

Someone the character asks along ("come with me, Hesk", "will you join us?") decides for themselves, by code:
- bonded to the character (adventure/bonds.py), or trusting and liking them enough (trust and affection adding up to
  WILLING), they come;
- wary of them (adding up to less than 0), they won't;
- in between, the character's Allure is rolled, hard (adventure/sheet.py check, any ruleset): it lands, they come.

A party member goes where the character goes, in town and out, and is in every scene with them (story_party keeps
their townsfolk sheet, so they are themselves in another city too). They still act on their own: the narrator is
told so. They leave when asked to ("go home, Hesk", "we part ways"), when their feelings sour (trust and affection
adding up to SOUR or less), or when an off-page beat takes them (dead, taken, missing: adventure/beats.py). At most
MOST travel with the character at once.

A character running on an agent (docs/spec.md, code and model boundary follow-ups) is limited by the same feelings, so a
wary one won't come however they are asked; anyone else is asked whether they come (adventure/rounds/joining.py), and
their answer stands in place of the bond, warmth and Allure roll. An agent that gives no answer falls back to the rule
above. Souring never sends them away: they leave by their own declared move, and only after a warning sign
(adventure/rounds/directing.py). Being told to go still parts them.

The party is game state, branched with the story (story_party is in adventure/timeline.py SAVED); each line's asking
and parting is kept with it (story_cards, scene 'party').
"""
import re
from datetime import date

from adventure import beats, combat, feelings, sheet, story_people
from adventure.database import decode, encode, many, optional

ASK = re.compile(r"\b((come|travel|ride|walk|go) (along )?with (me|us)|join (me|us)|come along|follow me|"
                 r"(be|become) my (companion|guide|sword)|want to come)\b", re.I)
PART = re.compile(r"\b(go home|go back home|part ways|we part|you can go|leave us|stay (here|behind)|"
                  r"wait (here|for me)|(our|your) (road|journey) ends)\b", re.I)
WILLING, SOUR = 3, -2
MOST = 3
DOING = 'travelling with the character'
SUCCESS = ('success_cost', 'success', 'critical_success')


def members(connection) -> list[dict]:
    """Who travels with the character, first to join first; the gone (adventure/beats.py) are left out."""
    gone = beats.gone(connection)
    return [row | {'sheet': decode(row['sheet'])} for row in many(
        connection, 'SELECT * FROM story_party ORDER BY joined, name') if row['key'] not in gone]


def keys(connection) -> set[str]:
    return {row['key'] for row in members(connection)}


def present(connection, place: dict) -> list[dict]:
    """The party as people in the scene, wherever it is."""
    return [{'sheet': row['sheet'], 'place': place, 'at_place': False, 'doing': DOING, 'mood': 'steady',
             'party': True,
             'note': ' They travel with the player\'s character as a companion, of their own will: they act on their '
                     'own and can be talked round, never ordered.'} for row in members(connection)]


def warmth(known: dict, key: str) -> int:
    felt = feelings.of(known.get(key))
    return felt['trust'] + felt['affection']


def invitee(view: dict, text: str) -> dict | None:
    """Whom a line asks along, if it asks: the one it names, else the only one there (the party aside)."""
    if PART.search(text) or not ASK.search(text):
        return None
    there = [person for person in view['people'] if not person.get('party')]
    named = [person for person in there if combat.aimed(person, text)]
    return named[0] if named else there[0] if len(there) == 1 else None


def askable(connection, view: dict, text: str) -> dict | None:
    """Whom a line asks along when the feelings leave it to them: the party has room and they are not wary of the
    character. An agent asked this way decides for themselves (adventure/rounds/joining.py)."""
    person = invitee(view, text)
    if person is None or len(members(connection)) >= MOST or wary(view['known'], person['sheet']['key']):
        return None
    return person


def wary(known: dict, key: str) -> bool:
    """Not bonded to the character, and trusting and liking them less than not at all: they won't come."""
    return not (known.get(key) or {}).get('bond') and warmth(known, key) < 0


def asked(connection, view: dict, text: str, now: str, rng, choices: dict[str, bool] | None = None) -> list[str]:
    """Asking someone along: whom the line names (else the only one there), who decides for themselves. A character
    on an agent who answered (`choices`, by key) decides by that answer in place of the bond, warmth and Allure roll;
    the party's room and their wariness still come first."""
    person = invitee(view, text)
    if person is None:
        return []
    found, known = person['sheet'], view['known']
    name = found['full']
    if len(members(connection)) >= MOST:
        return [f"{name} is not asked along in the end: the character already has {MOST} companions."]
    bonded = (known.get(found['key']) or {}).get('bond')
    choice = (choices or {}).get(found['key'])
    if wary(known, found['key']):
        return [f"{name} won't come along: they don't trust the character enough. Play the refusal."]
    if choice is False:
        return [f"{name} turns the character down, by their own choice. Play the refusal, in their own words."]
    if choice is None and not bonded and warmth(known, found['key']) < WILLING:
        result = sheet.check(connection, 'Allure', 'hard', f'win {name} over to come along', rng)
        if result['band'] not in SUCCESS:
            return [f"{name} turns the character down, for now. Play the refusal, with their own reasons."]
    story_people.meet(connection, found, view['city']['id'], now, date.fromisoformat(view['local_time'][:10]))
    connection.execute('INSERT OR REPLACE INTO story_party (key, name, city_id, sheet, joined) VALUES (?, ?, ?, ?, ?)',
                       (found['key'], name, view['city']['id'], encode(found), now))
    return [f"{name} agrees to come along with the character, from now on, of their own will."]


def parted(connection, text: str) -> list[str]:
    """Telling a companion to go: the one the line names, else the only one."""
    party = members(connection)
    named = [row for row in party if combat.aimed({'sheet': row['sheet']}, text)]
    row = named[0] if named else party[0] if len(party) == 1 else None
    if row is None:
        return []
    leave(connection, row['key'])
    return [f"{row['name']} leaves the character's company and goes back to their own life."]


def soured(connection, known: dict, agents: set[str] = frozenset()) -> list[str]:
    """Companions who have had enough of the character walk away; an agent among them chooses for themselves."""
    lines = []
    for row in members(connection):
        if row['key'] not in agents and warmth(known, row['key']) <= SOUR:
            leave(connection, row['key'])
            lines.append(f"{row['name']} has had enough of the character and leaves their company. Show them go.")
    return lines


def leave(connection, key: str):
    connection.execute('DELETE FROM story_party WHERE key=?', (key,))


def turn(connection, message_id: str, view: dict, text: str, day: str, now: str, rng=None,
         agents: set[str] = frozenset(), choices: dict[str, bool] | None = None) -> list[str]:
    """The line's asking along and parting, decided once; `choices` are the answers of agents asked along."""
    kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='party'", (message_id,))
    if kept:
        return decode(kept['lines'])
    lines = soured(connection, view['known'], agents)
    if PART.search(text):
        lines += parted(connection, text)
    elif ASK.search(text):
        lines += asked(connection, view, text, now, rng, choices)
    if lines:
        connection.execute("INSERT OR REPLACE INTO story_cards (message_id, scene, day, card_id, lines) VALUES "
                           "(?, 'party', ?, NULL, ?)", (message_id, day, encode(lines)))
    return lines


def prompt_text(lines: list[str]) -> str:
    return '## The party (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''
