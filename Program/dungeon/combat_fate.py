"""Fate's harm (docs/requirements.md "Fate"; Fate Accelerated and Condensed under CC-BY-3.0).

Under Fate a fight still runs on the shared rounds (dungeon/combat.py), but a blow on the character is Fate's:
- **The attack.** Each foe still standing rolls four Fate dice plus its rating on the ladder (RATING, from how good
  a fighter it is), against the character's defence: four Fate dice plus Quick, or Careful when they guard (+1 more
  for guarding, and +1 against a shot from far off). A defence that ties or beats it holds. Otherwise the shifts it
  wins by, plus the foe's weapon, are the harm.
- **Absorbing it** (Fate Accelerated): three stress boxes worth 1, 2 and 3 shifts, at most one box a hit, and the
  consequences, mild 2, moderate 4 and severe 6, each a wound in words, taken by code as cheaply as covers the hit:
  a box alone, else the lightest consequences (with a box if that is enough). What can't be absorbed takes the
  character out: they fall, and the defeat table decides what the winners do (dungeon/combat.py defeat).
- **The wound level** follows what is marked, so everything else reads it as before: stress alone is Grazed, a
  mild consequence Hurt, moderate Wounded, severe Maimed. A wound dealt outside a fight (a Life Card, a fall) marks
  the consequence for its level.
- **Recovery.** Stress clears with a night's sleep (dungeon/rules/fate.py refreshed). A consequence heals with
  nights of rest: mild 1, moderate 3, severe 7 (HEALS), counted from when it was taken.
"""
import itertools

from dungeon import ranges, sheet
from dungeon.rules import fate

BOXES = (1, 2, 3)
HEALS = {'mild': 1, 'moderate': 3, 'severe': 7}
LEVEL = {'mild': 2, 'moderate': 3, 'severe': 4}
WOUND = {'mild': 'Bruised and winded by {name}', 'moderate': 'Badly cut by {name}',
         'severe': 'Broken bones from {name}'}
OUTSIDE = {'mild': 'Bruised and sore', 'moderate': 'A painful wound', 'severe': 'A grievous injury'}
TAKEN_OUT = 5


def played(connection) -> dict | None:
    """The character's Fate sheet, when the campaign plays Fate."""
    return sheet.native(connection) if sheet.ruleset(connection) == fate.ID else None


def rating(foe: dict) -> int:
    """A foe on the ladder: Average, Fair for a fair fighter, Good for a skilled one."""
    return 1 + (foe.get('vitality', 0) >= 50) + (foe.get('vitality', 0) >= 70)


def level_for(found: dict) -> int:
    marked = [LEVEL[slot] for slot, text in found.get('consequences', {}).items() if text]
    return max(marked + [1 if any(found.get('stress', [])) else 0])


def absorb(found: dict, shifts: int) -> tuple[int | None, list[str]] | None:
    """The cheapest way to absorb a hit: (the stress box used, the consequences taken); None when nothing covers it."""
    boxes = [None] + [index for index, marked in enumerate(found['stress']) if not marked]
    free = [slot for slot, text in found['consequences'].items() if not text]
    ways = []
    for count in range(len(free) + 1):
        for slots in itertools.combinations(free, count):
            for box in boxes:
                worth = sum(fate.CONSEQUENCES[slot] for slot in slots) + (BOXES[box] if box is not None else 0)
                if worth >= shifts:
                    ways.append((sum(fate.CONSEQUENCES[slot] for slot in slots), worth, box, list(slots)))
    if not ways:
        return None
    _, _, box, slots = min(ways, key=lambda way: (way[0], way[1]))
    return box, slots


def take(found: dict, shifts: int, name: str) -> tuple[str, bool]:
    """A hit on the character, absorbed or taking them out. Changes `found`; returns the line and whether they are
    taken out."""
    way = absorb(found, shifts)
    if way is None:
        return f"{name.capitalize()} hits the player's character for {shifts} shifts, more than they can take: " \
               'taken out.', True
    box, slots = way
    if box is not None:
        found['stress'][box] = True
    healing = found.setdefault('healing', {})
    for slot in slots:
        found['consequences'][slot] = WOUND[slot].format(name=name)
        healing[slot] = HEALS[slot]
    took = [f'{BOXES[box]}-shift stress'] if box is not None else []
    took += [f"a {slot} consequence, “{found['consequences'][slot]}”" for slot in slots]
    return f"{name.capitalize()} hits the player's character for {shifts} shift{'s' if shifts > 1 else ''}: " \
           f"absorbed with {' and '.join(took)}.", False


def defence(found: dict, guarded: bool, far: bool, rng) -> int:
    approach = 'Careful' if guarded else 'Quick'
    return sum(rng.choice((-1, 0, 1)) for _ in range(4)) + found['approaches'][approach] + int(guarded) + int(far)


def foes_attack(connection, state: dict, standing, guarded: bool, rng, lines: list[str]) -> int:
    """Each foe still standing (and free to) closes in or attacks; returns the character's wound level after."""
    found = played(connection)
    for foe in standing(state):
        if ranges.close(foe, lines):
            continue
        attack = sum(rng.choice((-1, 0, 1)) for _ in range(4)) + rating(foe)
        shifts = attack - defence(found, guarded, foe.get('zone') == 'far', rng)
        if shifts <= 0:
            lines.append(f"{foe['name'].capitalize()} attacks and misses.")
            continue
        severe = found['consequences'].get('severe')
        line, out = take(found, shifts + max(0, foe.get('weapon', 0)), foe['name'])
        lines.append(line)
        # A severe consequence can leave a lasting injury (dungeon/injuries.py), as a maiming does.
        if found['consequences'].get('severe') != severe:
            state['hurt_by'] = foe['name']
        if out:
            sheet.set_native(connection, found, '')
            return TAKEN_OUT
    sheet.set_native(connection, found, '')
    return level_for(found)


def follow_level(connection, level: int):
    """A wound level set outside a fight: healed (0) clears everything; a worse one marks its consequence."""
    found = played(connection)
    if not found or level == level_for(found) or level >= TAKEN_OUT:
        return
    if level == 0:
        found |= {'stress': [False] * fate.STRESS, 'consequences': dict.fromkeys(fate.CONSEQUENCES, ''),
                  'healing': {}}
    elif level > level_for(found) and level == 1:
        found['stress'][0] = True
    elif level > level_for(found):
        slot = next(slot for slot, at in LEVEL.items() if at == level)
        found['consequences'][slot] = found['consequences'][slot] or OUTSIDE[slot]
        found.setdefault('healing', {})[slot] = HEALS[slot]
    else:
        for slot, at in LEVEL.items():
            if at > level:
                found['consequences'][slot] = ''
                found.get('healing', {}).pop(slot, None)
    sheet.set_native(connection, found, '')


def rest(connection, nights: int) -> list[str]:
    """Nights of rest heal consequences; returns the wounds healed, for the narrator."""
    found = played(connection)
    if not found or nights <= 0:
        return []
    healing, healed = found.setdefault('healing', {}), []
    for slot, text in found['consequences'].items():
        if not text:
            continue
        healing[slot] = healing.get(slot, HEALS[slot]) - nights
        if healing[slot] <= 0:
            healed.append(text)
            found['consequences'][slot] = ''
            healing.pop(slot)
    sheet.set_native(connection, found, '')
    return [f"Rest heals the character's consequence: {text}." for text in healed]
