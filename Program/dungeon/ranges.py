"""Range bands and named areas in a fight (requirements "Combat": "Positioning: zones, grid optional").

Every ruleset keeps each foe at a range band, engaged, near or far, and the fight keeps the named area the character
fights from ("the stairs", "the bar"):
- A foe not engaged spends its turn closing one band (far to near, near to engaged), unless it fights at range (a
  danger's archers, `ranged` in its spec): then it shoots from where it stands.
- The character's blow reaches a near foe (and engages it) but not a far one: the line closes to near instead. A
  shot or a throw reaches any band and leaves the target where it is.
- A line that backs off ("I fall back to the stairs", "I step back out of reach") and lands its roll breaks away from
  every engaged foe, who must close again (not in the same round: a foe shaken off loses its turn); one that names a place to go moves the fight's area there. A move to a
  place this way is not an escape: running away is (dungeon/combat.py FLEE).
"""
import re

BANDS = ('engaged', 'near', 'far')
RANGED = re.compile(r'\b(shoot\w*|shot|loos\w*|fires?|firing|throw\w*|threw|hurl\w*|sling\w*|arrows?|bolts?|bow|'
                    r'crossbow|pistol|gun|rifle|musket|javelin|spear at)\b', re.I)
BACK = re.compile(r'\b(fall\w* back|back\w* (away|off|up)|step\w* back|pull\w* back|withdraw\w*|get\w* clear|'
                  r'put\w* (some )?distance|disengag\w*|out of (his|her|their|its) reach|out of reach|'
                  r'retreat\w* (to|behind|up|into|onto|across)|take\w* cover|duck\w* behind)\b', re.I)
MOVE = re.compile(r"\b(?:to|onto|behind|up|into|across|toward|towards|over to|by)\s+(the\s+(?:[a-z'-]+\s+){0,2}?"
                  r"[a-z'-]+)\b(?=\s*(?:$|[,.;!]|and\b|then\b|while\b|where\b|so\b|to\b|for\b))", re.I)


def ranged(action: str) -> bool:
    return bool(RANGED.search(action))


def backing(action: str) -> bool:
    return bool(BACK.search(action))


def area(action: str) -> str | None:
    """The named area a line moves the character to ("the stairs")."""
    found = MOVE.search(action)
    return found.group(1).lower() if found else None


def close(foe: dict, lines: list[str]) -> bool:
    """A foe's move at range: True when it spends the turn closing a band, False when it can attack (engaged, or
    a ranged foe shooting from where it stands)."""
    zone = foe.get('zone', 'engaged')
    if foe.pop('shaken', False) and zone != 'engaged':
        # Shaken off this round (break_away): it gathers itself and closes again next round.
        lines.append(f"{foe['name'].capitalize()} is left behind for now.")
        return True
    if zone == 'engaged' or foe.get('ranged'):
        return False
    foe['zone'] = BANDS[BANDS.index(zone) - 1]
    lines.append(f"{foe['name'].capitalize()} {'closes in' if foe['zone'] == 'engaged' else 'comes nearer'}.")
    return True


def reach(foe: dict, action: str, lines: list[str]) -> bool:
    """Whether the character's attack reaches the foe. A blow at a far foe closes to near instead."""
    if ranged(action) or foe.get('zone') != 'far':
        return True
    foe['zone'] = 'near'
    lines.append(f"The player's character closes on {foe['name']}, still too far off to strike this round.")
    return False


def break_away(state: dict, action: str, landed: bool, lines: list[str]):
    """A line that backs off: landed, every engaged foe is left at near, and the fight moves to the area named."""
    if not landed:
        lines.append("The player's character tries to back off and cannot shake them.")
        return
    for foe in state['foes']:
        if foe.get('zone') == 'engaged':
            foe |= {'zone': 'near', 'shaken': True}
    if moved := area(action):
        state['area'] = moved
    where = f" to {state['area']}" if moved else ''
    lines.append(f"The player's character breaks away{where}: the foes must close again.")


def positions(state: dict, standing: list[dict]) -> str:
    """Where everyone stands, for the narrator ("The player's character is at the stairs. bandit: engaged; archer:
    far, shooting.")."""
    where = f"The player's character is at {state['area']}. " if state.get('area') else ''
    foes = '; '.join(f"{foe['name']}: {foe.get('zone', 'engaged')}{', shooting' if foe.get('ranged') else ''}"
                     for foe in standing)
    return f'{where}Ranges: {foes}.' if foes else where.strip()
