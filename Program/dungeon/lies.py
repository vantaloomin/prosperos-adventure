"""NPCs keep secrets and lie, and detection is rolled (requirements "NPCs keep secrets and lie").

When the player's line questions someone in the scene who has something to hide, code decides they lie, and rolls
the character's insight (Mind, in any ruleset: dungeon/sheet.py check) against how practised a liar they are: a
city's notables are hard to read, anyone else normal. Caught, the narrator shows the tell; believed, the narrator
writes the lie with no tell, and the record keeps the lie as the world's truth only, hidden from the character
(the narrator's words to the character go in as their belief, dungeon/record.py).

Something to hide is a notable's `secret`, wants that keep something hidden ("nobody asking questions", "without
ever saying why"), or the hidden truth of an open job they gave. Someone who trusts the character (feelings trust
TRUSTING or more) tells them the truth. Each person is read once a story day: the rest of the day they keep to the
lie the character believed, or are known to be lying (story_cards, scene 'lie', card_id the person's key). A near
miss (failure with an upside) leaves the character uneasy: the narrator shows a small wrong note, no more.
"""
import re

from dungeon import combat, feelings, record, sheet
from dungeon.database import decode, encode, many, optional

ASKED = re.compile(r"\?|\b(ask\w*|question\w*|press\w*|quiz\w*|interrogat\w*|inquir\w*|tell me|what do you know|"
                   r"who (is|was|did)|where (is|was|did)|why (is|was|did|do)|did you|have you|do you know|swear)\b",
                   re.I)
HIDING = re.compile(r"\b(without|nobody|no one|never (saying|telling)|unseen|not be seen|looking the other way|"
                    r"secret\w*|hid\w*|cover\w*)\b", re.I)
TRUSTING = 3
SUCCESS = ('success_cost', 'success', 'critical_success')
# A near miss: the character is not fooled outright, only uneasy.
UNEASY = ('failure_upside',)


def target(people: list[dict], text: str) -> dict | None:
    """Whom the line questions: someone named in it, else the only person there."""
    named = [person for person in people if combat.aimed(person, text)]
    return named[0] if named else people[0] if len(people) == 1 else None


def hidden(connection, data: dict, person: dict) -> str | None:
    """What they have to hide, in the narrator's words, or None."""
    found = person['sheet']
    notable = next((item for item in data.get('notables', []) if item.get('id') == found.get('notable')), {})
    if notable.get('secret'):
        return notable['secret']
    if found.get('wants') and HIDING.search(found['wants']):
        return f"what they are after: {found['wants']}"
    job = optional(connection, "SELECT truth FROM story_quests WHERE status='open' AND lower(giver)=lower(?) "
                               'AND truth IS NOT NULL', (found['full'],))
    return f"the truth of the work they gave: {job['truth']}" if job else None


def read_today(connection, key: str, day: str) -> dict | None:
    row = optional(connection, "SELECT lines FROM story_cards WHERE scene='lie' AND card_id=? AND day=?", (key, day))
    return {'lines': decode(row['lines'])} if row else None


def turn(connection, message_id: str, view: dict, text: str, day: str, now: str, rng=None) -> list[str]:
    """The line's lie, decided once: who lies, and whether the character sees through it."""
    kept = many(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='lie'", (message_id,))
    if kept:
        return decode(kept[0]['lines'])
    if not ASKED.search(text) or not (person := target(view['people'], text)):
        return []
    found = person['sheet']
    if feelings.of(view['known'].get(found['key']))['trust'] >= TRUSTING:
        return []
    what = hidden(connection, view['data'], person)
    if not what:
        return []
    name = found['full']
    if (earlier := read_today(connection, found['key'], day)) is not None:
        lines = [f"{name} keeps to the same story as before. {earlier['lines'][-1]}"]
    else:
        result = sheet.check(connection, 'Mind', 'hard' if found.get('notable') else 'normal',
                             f'see through {name}', rng)
        if result['band'] in SUCCESS:
            lines = [f"{name} lies to keep hidden {what}.",
                     f"The player's character sees through it: show the tell plainly (a look away, a story that "
                     f"doesn't hold). {name} sticks to the lie unless pressed hard."]
            record.add(connection, 'fact', name, f"The player's character caught {name} in a lie.", now)
        elif result['band'] in UNEASY:
            lines = [f"{name} lies to keep hidden {what}.",
                     "The player's character can't say what, but something in it doesn't sit right: show a small "
                     'wrong note (a pause, a too-easy answer) without giving the lie away.']
            record.add(connection, 'fact', name, f"Something {name} said didn't sit right with the player's "
                       'character.', now)
        else:
            lines = [f"{name} lies to keep hidden {what}.",
                     "The player's character believes it: write the lie as told, smooth and natural, with no tell "
                     'and no hint to the reader that it is false.']
            record.add(connection, 'secret', name, f"{name} lied to the player's character to keep hidden {what}.",
                       now, truth='world')
    connection.execute('INSERT OR REPLACE INTO story_cards (message_id, scene, day, card_id, lines) VALUES '
                       "(?, 'lie', ?, ?, ?)", (message_id, day, found['key'], encode(lines)))
    return lines


def prompt_text(lines: list[str]) -> str:
    return ('## A lie (decided by the game; never say outright that it is a lie)\n'
            + '\n'.join(f'- {line}' for line in lines)) if lines else ''
