"""Who stops the character leaving (requirements "Leaving a scene"; docs/story.md "Leaving").

A fight holds the character: the "Go somewhere else" menu refuses, a line that walks off is not a walk, and only a
line that flees gets away, on a roll (dungeon/combat.py FLEE). A prisoner stays held until they get free.

Outside a fight, someone there with a reason may try to keep the character from going. Code decides who, from their
feelings (dungeon/feelings.py), and only for people met who are not in the character's party:
- Hostile: they hate or deeply distrust the character (affection or trust HOSTILE or lower) and are not afraid of
  them (fear AFRAID or lower). They block the way.
- Fond: they are fond of or want the character (affection or desire FOND or more). They plead with them to stay.
The strongest feeling holds; the stronger it is, the harder the roll: getting past someone hostile is Vitality when
the line pushes past, Allure when it talks its way out, else Resolve; leaving someone fond is Resolve, or Allure when
the line talks. A success gets away (at a cost, the feeling sours a step); a failure keeps the character in the scene
this line, and the narrator writes them being stopped. The next line can try again.

A line leaves when it goes somewhere (dungeon/story.py walked_to), sets out on a journey (dungeon/travel.py
setting_out) or just walks out ("I leave", "I storm off"). It is decided once, as the line is sent, and kept with it
(story_cards, scene 'leave'); the roll card follows the line's own rolls. The menu refuses to move the character while
someone would stop them: the player says how they go, in the story.

The Table's `leaving` rule sets who can stop the character: 'anyone' (the people above and fights, the default),
'fights' (only a fight holds them) or 'nobody' (a line that flees a fight always gets away, and the menu walks away
from one). Being held prisoner is not leaving and stays as it is.
"""
import re

from dungeon import combat, feelings, party, record, sheet, table
from dungeon.database import decode, encode, optional

RULES = ('anyone', 'fights', 'nobody')
HOSTILE, AFRAID, FOND = -3, 1, 4
# How hard it is to get away by how strong the feeling is.
DIFFICULTY = {3: 'normal', 4: 'hard', 5: 'very_hard'}
SUCCESS = ('success_cost', 'success', 'critical_success')
LEAVING = re.compile(r"\b(?:leave|leaves|leaving|walk(?:s|ing)? (?:out|off|away)|storm(?:s|ing)? (?:out|off)|"
                     r"head(?:s|ing)? out|get(?:s|ting)? out of here|go(?:es)? home|turn(?:s|ing)? to go|"
                     r"make (?:my|our) exit|excuse (?:myself|ourselves)|take (?:my|our) leave|say (?:my )?goodbyes?|"
                     r"slip(?:s|ping)? out|back(?:s|ing)? out of the|out the door)\b", re.I)
PUSHING = re.compile(r'\b(push\w*|shov\w*|barg\w*|shoulder\w*|forc\w*|run|runs|running|bolt\w*|dash\w*|break\w* '
                     r'free|wrench\w*|yank\w*|tear\w* (?:my|free)|sprint\w*)\b', re.I)
TALKING = re.compile(r'\b(talk\w*|explain\w*|promis\w*|apologi\w*|reassur\w*|sweet-?talk\w*|charm\w*|excuse|convinc\w*|'
                     r'persuad\w*|tell (?:him|her|them)|say|says)\b', re.I)


def rule(connection) -> str:
    found = table.rule(connection, 'leaving')
    return found if found in RULES else 'anyone'


def free_from_fights(connection) -> bool:
    """Whether the Table lets the character walk out of a fight: a flight always gets away."""
    return rule(connection) == 'nobody'


def leaves(text: str) -> bool:
    return bool(LEAVING.search(text))


def holder(view: dict, kept_by_party: set[str]) -> dict | None:
    """Who there would stop the character leaving, if anyone: {name, key, why ('hostile' or 'fond'), strength}."""
    found = None
    for person in view['people']:
        key = person['sheet']['key']
        if key in kept_by_party or key not in view['known']:
            continue
        felt = feelings.of(view['known'][key])
        hostile = max(-felt['affection'], -felt['trust'])
        fond = max(felt['affection'], felt['desire'])
        if hostile >= -HOSTILE and felt['fear'] <= AFRAID:
            why, strength = 'hostile', hostile
        elif fond >= FOND:
            why, strength = 'fond', fond
        else:
            continue
        if found is None or strength > found['strength']:
            found = {'name': person['sheet']['full'], 'key': key, 'why': why, 'strength': strength}
    return found


def blocking(connection, view: dict) -> dict | None:
    """Who would stop the character leaving now, under the Table's rule (none in a fight: it holds them itself)."""
    if rule(connection) != 'anyone' or combat.fight(connection) is not None or combat.captors(connection):
        return None
    return holder(view, party.keys(connection))


def approach(found: dict, text: str) -> tuple[str, str]:
    """The roll's stat and what it tries."""
    first = found['name'].split()[0]
    if found['why'] == 'hostile':
        stat = 'Vitality' if PUSHING.search(text) else 'Allure' if TALKING.search(text) else 'Resolve'
        return stat, f'get past {first}, who means to stop them leaving'
    return ('Allure' if TALKING.search(text) else 'Resolve'), f'leave though {first} begs them to stay'


def decide(connection, message_id: str, view: dict, text: str, going: bool, now: str, rng=None) -> dict | None:
    """The line's try at leaving, decided once: who stops it and how the roll lands. Returns {'stopped', 'lines',
    'roll', 'carded'} (kept with the line), or None when nothing stands in the way."""
    if (kept := read(connection, message_id)) is not None:
        return kept
    if not (going or leaves(text)) or (found := blocking(connection, view)) is None:
        return None
    stat, action = approach(found, text)
    difficulty = DIFFICULTY[min(5, max(3, found['strength']))]
    result = sheet.check(connection, stat, difficulty, action, rng)
    name, band = found['name'], result['band']
    if found['why'] == 'hostile':
        trying = f"{name} means to stop the player's character leaving and steps in their way."
        away = "The character gets past them and away."
        cost = (f"The character gets away, but not cleanly: {name} gets a hand on them, or a last word that will be "
                'remembered.', {'affection': -1})
        held = (f"{name} stops them: write it (a body in the doorway, a grip on the arm, a threat). The character is still "
                'here and goes nowhere this line (kept by the game).')
    else:
        trying = f"{name} doesn't want the player's character to go and begs them to stay."
        away = 'The character goes all the same.'
        cost = (f"The character goes, and it hurts {name}: show it.", {'affection': -1, 'trust': -1})
        held = (f"{name} keeps them: the character can't bring themselves to leave yet. Write {name} holding on. The "
                'character is still here and goes nowhere this line (kept by the game).')
    if band in ('success', 'critical_success'):
        lines = [trying, away]
    elif band == 'success_cost':
        lines = [trying, cost[0]]
        feelings.change(connection, found['key'], cost[1], 'The character left when I wanted them to stay.'
                        if found['why'] == 'fond' else 'The character got past me.')
    else:
        lines = [trying, held]
        record.add(connection, 'fact', name, f"{name} stopped the player's character leaving.", now)
    stopped = band not in SUCCESS
    kept = {'stopped': stopped, 'lines': lines, 'roll': {'action': action, 'stat': stat, 'difficulty': difficulty,
                                                          'result': result}, 'carded': False}
    keep(connection, message_id, kept, view)
    return kept


def keep(connection, message_id: str, kept: dict, view: dict):
    connection.execute('INSERT OR REPLACE INTO story_cards (message_id, scene, day, card_id, lines) VALUES '
                       "(?, 'leave', ?, NULL, ?)", (message_id, view['local_time'][:10], encode(kept)))


def read(connection, message_id: str) -> dict | None:
    row = optional(connection, "SELECT day, lines FROM story_cards WHERE message_id=? AND scene='leave'", (message_id,))
    return decode(row['lines']) | {'day': row['day']} if row else None


def stopped(connection, message_id: str) -> bool:
    """Whether someone kept the character from leaving on this line: they go nowhere."""
    kept = read(connection, message_id)
    return bool(kept and kept['stopped'])


def card(connection, message_id: str, now: str) -> list[dict]:
    """The leaving roll as a roll card after the line's own, made once; returns it (as the turn's rolls are) the
    first time only."""
    kept = read(connection, message_id)
    if not kept or kept['carded']:
        return []
    roll = kept.pop('roll')
    found = combat.card_for(connection, message_id, roll, now)
    connection.execute("UPDATE story_cards SET lines=? WHERE message_id=? AND scene='leave'",
                       (encode({**{key: value for key, value in kept.items() if key != 'day'}, 'roll': roll,
                                'carded': True}), message_id))
    if found is None:
        return []
    return [dict(optional(connection, 'SELECT * FROM story_rolls WHERE id=?', (found,)))]


def lines(connection, message_id: str) -> list[str]:
    kept = read(connection, message_id)
    return kept['lines'] if kept else []


def prompt_text(found: list[str]) -> str:
    return ('## Leaving (decided by the game)\n' + '\n'.join(f'- {line}' for line in found)) if found else ''
