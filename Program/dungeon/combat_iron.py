"""Fights under Ironsworn (docs/requirements.md "Combat": "Ironsworn keeps Health and harm"; docs/story.md "Fights
under Ironsworn").

The fight runs as dungeon/combat.py does (one player line is one round, the defeat table by what the foes want),
with Ironsworn's moves from the pack:
- **Foes are the pack's NPCs**, read from a foe's name (a raider is a Raider, a wolf a Wolf, a ley-mad boar a Boar),
  else by how tough the Prospero spec is. Each has its rank, the harm it deals (its rank) and a progress track of ten
  boxes that the character's harm fills: a troublesome foe takes 3 boxes a harm, dangerous 2, formidable 1,
  extreme 2 ticks, epic 1 tick.
- **Initiative.** A fight the character starts gives them initiative; a danger's foe has it. With initiative the
  character's attack is Strike: a strong hit inflicts +1 harm and keeps initiative, a weak hit inflicts harm and
  loses it, a miss loses it. Without, it is Clash: a strong hit inflicts harm and takes initiative, a weak hit
  inflicts harm and the foe strikes back, a miss and the foe strikes. Harm is 1, 2 with a deadly weapon (a sword,
  an axe, a bow).
- **End the Fight.** After a strong hit, once a foe's track has PROGRESS_TRY boxes, code makes the decisive move: the
  challenge dice against the boxes. A strong hit and the foe is out of the fight; a weak hit too, and the character
  Endures Harm; a miss and they pay for it, enduring harm, and the fight goes on.
- **Foes with initiative attack**: the character Endures Harm, -health by the foe's rank, then rolls +health or
  +iron: a strong hit takes +1 momentum, a miss -1. At 0 health a miss means Face Death (+heart): a strong hit and
  death rejects them (the defeat table without death), a weak hit the same with a cost, a miss is death.
- **Health** reads as the game's wound levels (5 unharmed to 0 at death's door, WORDS), and a wound dealt outside a
  fight lowers health to match. **Rest** (Make Camp, a night's sleep) gives +1 health a night, as written.
"""
import re
from functools import cache

from dungeon import ranges, sheet
from dungeon.rules import ironsworn

# Boxes of progress (of ten) a foe's track takes for each harm, by rank; ticks are a quarter box.
TICKS = {1: 12, 2: 8, 3: 4, 4: 2, 5: 1}
BOXES = 10
PROGRESS_TRY = 8
DEADLY = {'sword', 'felling-axe', 'hatchet', 'bow'}
WORDS = ('unharmed', 'bruised', 'hurt', 'battered', 'badly hurt', "at death's door")
# Else a foe by the Prospero spec's Vitality: (most, npc).
BY_VITALITY = ((8, 'ironlanders/common_folk'), (12, 'ironlanders/raider'), (15, 'ironlanders/warrior'),
               (99, 'animals/bear'))
NAMES = {'warden': 'ironlanders/hunter', 'bandit': 'ironlanders/raider', 'thug': 'ironlanders/raider',
         'press-gang': 'ironlanders/raider', 'soldier': 'ironlanders/warrior', 'guard': 'ironlanders/warrior',
         'cultist': 'ironlanders/mystic', 'ghoul': 'horrors/bonewalker', 'skeleton': 'horrors/bonewalker'}


@cache
def npcs() -> dict[str, dict]:
    return {f'{group}/{key}': npc for group, found in ironsworn.pack()['npcs'].items()
            for key, npc in found['contents'].items()}


def npc_for(spec: dict) -> str:
    """The pack's NPC a foe is: named in its spec (`ironsworn`), by a word of its name, else by toughness."""
    if spec.get('ironsworn') in npcs():
        return spec['ironsworn']
    words = re.findall(r"[a-z-]+", spec['name'].lower())
    for word in words:
        if word in NAMES:
            return NAMES[word]
        found = next((key for key in npcs() if key.split('/')[1] == word.replace('-', '_')), None)
        if found:
            return found
    return next(npc for most, npc in BY_VITALITY if spec.get('vitality', 10) <= most)


def foes_from(spec: dict, zone: str) -> list[dict]:
    npc = npc_for(spec)
    count = spec.get('count', 1)
    rank = npcs()[npc]['rank']
    return [{'id': f"{spec['name']}-{number}", 'name': spec['name'] if count == 1 else f"{spec['name']} {number + 1}",
             'npc': npc, 'rank': rank, 'ticks': 0, 'wound': 0, 'zone': zone, 'broken': False, 'out': False}
            | ({'horror': True} if spec.get('horror') else {}) for number in range(count)]


def boxes(foe: dict) -> int:
    return min(BOXES, foe['ticks'] // 4)


def inflict(foe: dict, harm: int):
    foe['ticks'] = min(BOXES * 4, foe['ticks'] + harm * TICKS[foe['rank']])
    foe['wound'] = min(4, boxes(foe) * 4 // BOXES)
    if boxes(foe) >= BOXES:
        out(foe)


def out(foe: dict):
    foe['out'], foe['wound'] = True, 5


def describe(foe: dict) -> str:
    if foe['out']:
        return 'out of the fight'
    return f"{boxes(foe)} of {BOXES} boxes of progress against them"


# The character ------------------------------------------------------------------------------------

def health(connection) -> int | None:
    found = sheet.native(connection) if sheet.ruleset(connection) == ironsworn.ID else None
    return found['health'] if found else None


def level_for(points: int) -> int:
    return max(0, min(5, 5 - points))


def set_health(connection, points: int) -> int:
    found = sheet.native(connection)
    found['health'] = max(0, min(5, points))
    sheet.set_native(connection, found, '')
    return level_for(found['health'])


def follow_level(connection, level: int):
    """A wound level set outside a fight moves health with it."""
    found = sheet.native(connection) if sheet.ruleset(connection) == ironsworn.ID else None
    if found and level_for(found['health']) != level:
        found['health'] = 5 - level
        sheet.set_native(connection, found, '')


def momentum(connection, shift: int):
    found = sheet.native(connection)
    found['momentum'] = max(ironsworn.MOMENTUM_MIN, min(ironsworn.momentum_max(found), found['momentum'] + shift))
    sheet.set_native(connection, found, '')


# Moves --------------------------------------------------------------------------------------------

def harm_of(items: list[dict], action: str) -> int:
    bare = re.search(r'\b(punch|kick|headbutt|elbow|knee|fist|shove|tackle|wrestle)\w*', action, re.I)
    return 1 if bare or not any(row['item_id'] in DEADLY for row in items) else 2


def relabel(connection, roll: dict, move: str):
    """The roll's card names the fight move it was (Strike or Clash), on iron (or edge at range)."""
    skill = re.sub(r'^[^+]*\+', f'{move} +', roll.get('skill') or '')
    connection.execute('UPDATE story_rolls SET skill=? WHERE id=?', (skill, roll['id']))
    roll['skill'] = skill


def strike(connection, state: dict, roll: dict, target: dict, items: list[dict], rng, lines: list[str]):
    """The character's attack: Strike with initiative, Clash without; then End the Fight when it is time."""
    leading = state.get('initiative', 'player') == 'player'
    relabel(connection, roll, 'Strike' if leading else 'Clash')
    target['zone'] = 'engaged'
    harm, band = harm_of(items, roll['action']), roll['band']
    strong = band in ('success', 'critical_success')
    if band in ('failure', 'critical_failure'):
        state['initiative'] = 'foe'
        lines.append(f"The player's character's attack on {target['name']} fails; {target['name']} has the upper hand.")
        return
    dealt = harm + (1 if strong and leading else 0)
    inflict(target, dealt)
    state['initiative'] = 'player' if strong else 'foe'
    lines.append(f"The player's character {'strikes' if leading else 'clashes with'} {target['name']}: {dealt} harm, "
                 f"{describe(target)}" + ('.' if strong else f"; {target['name']} has the upper hand."))
    if strong and not target['out'] and boxes(target) >= PROGRESS_TRY:
        end_the_fight(connection, state, target, rng, lines)


def end_the_fight(connection, state: dict, target: dict, rng, lines: list[str]):
    challenge = [rng.randint(1, 10), rng.randint(1, 10)]
    band = ironsworn.outcome(boxes(target), challenge)
    if band in ('failure', 'critical_failure'):
        lines.append(f"The player's character tries to finish {target['name']} ({boxes(target)} against "
                     f"{challenge[0]} and {challenge[1]}) and pays for it.")
        endure(connection, state, target, rng, lines)
        return
    out(target)
    lines.append(f"The player's character ends the fight with {target['name']} ({boxes(target)} against "
                 f"{challenge[0]} and {challenge[1]}): they are out of it.")
    if band == 'success_cost':
        lines.append("It's worse than it looked: the character takes a blow in the doing.")
        endure(connection, state, target, rng, lines)


def endure(connection, state: dict, foe: dict, rng, lines: list[str]) -> int:
    """Endure Harm from `foe`: -health by its rank, then +health or +iron; returns the wound level after."""
    found = sheet.native(connection)
    before = found['health']
    left = max(0, before - foe['rank'])
    over = foe['rank'] - (before - left)
    found['health'] = left
    stat = 'iron' if found['stats']['iron'] >= left else None
    result = ironsworn.roll(found | {'stats': found['stats'] | {'health': left}}, 'Vitality', 'normal', '', rng,
                            stat or 'health', 'endure_harm')
    state.setdefault('cards', []).append({'action': f"Endure Harm from {foe['name']}", 'stat': 'Vitality',
                                          'result': result})
    shift = 1 if result['band'] in ('success', 'critical_success') else -1 if result['band'] in \
        ('failure', 'critical_failure') else 0
    found['momentum'] = max(ironsworn.MOMENTUM_MIN, min(ironsworn.momentum_max(found), result['momentum'] + shift - over))
    sheet.set_native(connection, found, '')
    lines.append(f"{foe['name'].capitalize()} hits the player's character for {foe['rank']} harm: health {left} of 5.")
    if left == 0 and shift < 0:
        state['brink'] = True
    if foe['rank'] >= 3 or (left == 0 and before > 0):
        # A heavy blow, or one that leaves nothing, can leave a lasting injury (dungeon/injuries.py).
        state['hurt_by'] = foe['name']
    return level_for(left)


def foes_attack(connection, state: dict, standing, guarded: bool, rng, lines: list[str]) -> int:
    """Foes close in; the one with the upper hand attacks (a dodge that landed keeps them off this round)."""
    level = level_for(sheet.native(connection)['health'])
    for foe in standing(state):
        ranges.close(foe, lines)
    attacker = next((foe for foe in standing(state) if foe['zone'] == 'engaged' or foe.get('ranged')), None)
    if attacker and state.get('initiative') == 'foe' and not guarded:
        level = endure(connection, state, attacker, rng, lines)
    elif attacker and guarded and state.get('initiative') == 'foe':
        state['initiative'] = 'player'
        lines.append(f"The player's character turns {attacker['name']}'s attack aside and takes the upper hand.")
    return 5 if state.pop('brink', False) else level


def face_death(connection, state: dict, rng) -> tuple[bool, str]:
    """(alive, how): +heart. A strong hit and death rejects them; a weak hit, they come back owing it; a miss, dead."""
    found = sheet.native(connection)
    result = ironsworn.roll(found, 'Resolve', 'normal', '', rng, 'heart', 'face_death')
    state.setdefault('cards', []).append({'action': 'Face Death', 'stat': 'Resolve', 'result': result})
    if result['band'] in ('success', 'critical_success'):
        return True, 'Death rejects them.'
    if result['band'] == 'success_cost':
        return True, 'Death lets them go, for now, and wants something of them in return.'
    return False, ''


def rest(connection, nights: int) -> list[str]:
    """A night's sleep (Make Camp) gives +1 health a night, up to 5."""
    found = sheet.native(connection)
    if nights <= 0 or found['health'] >= 5:
        return []
    found['health'] = min(5, found['health'] + nights)
    sheet.set_native(connection, found, '')
    return [f"Rest restores the character: health {found['health']} of 5."]
