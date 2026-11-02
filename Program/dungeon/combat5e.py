"""Fights under 5E (docs/requirements.md "Combat": "5e keeps HP"; docs/story.md "Fights under 5E").

The fight runs as dungeon/combat.py does (one player line is one round, foes close in and attack, morale, the defeat
table by what the foes want), with 5E's numbers from the SRD 5.2.1 pack:
- **Foes are SRD stat blocks.** A foe names its monster (`srd52` in its spec), else one is read from its name ("road
  bandit" is a Bandit, "ward-ghoul" a Ghoul), else picked by how tough the Prospero spec is. Each foe has its AC, hit
  points rolled from the block's formula, and the block's first attack.
- **The player's attack** keeps the dice the turn already rolled for it: the natural d20 plus the attack bonus
  (Strength, or Dexterity for a finesse or ranged weapon, plus proficiency when the class has the weapon) against the
  target's AC. A natural 20 is a critical hit (the damage dice twice), a natural 1 always misses. Damage is the
  carried weapon's die plus the same ability (an unarmed strike is 1 + Strength). The roll's card is rewritten to
  show the attack and the AC.
- **Spells.** An action naming a known damaging spell is cast at a foe: a spell attack (the turn's d20 + the spell
  attack bonus) against AC, or the foe's save against the spell save DC (a failure takes the damage, a success half,
  nothing from a cantrip). Cantrips grow at levels 5, 11 and 17. A healing spell heals the character
  (dungeon/sheet.py cast, which also spends the slot).
- **XP.** A won fight gives each beaten foe's XP (down or broken); a milestone gives the level's high encounter budget
  (dungeon/growth.py). Enough XP is a level, at once (srd52.advance).
- **Dodging** needs no roll: the foes attack with disadvantage that round. Getting away keeps its roll.
- **Foes attack** with their bonus against the character's AC and roll their damage. Hit points are the sheet's; the
  wound words the rest of the game reads (Grazed to Dying) follow the hit points (`level_for`).
- **Morale:** when a foe is badly hurt or down, the others make a Wisdom save, DC 10; a failure breaks them.
- **At 0 hit points the character makes death saves** (d20, 10 or more a success; three of either decides; a
  natural 20 is back up with 1 hit point, a natural 1 two failures). Three failures is death; stable, the defeat
  table decides the rest, without death.
- **A long rest** (a night's sleep) restores every hit point, as written.
"""
import json
import math
import random
import re
from functools import cache

from dungeon import ranges, sheet
from dungeon.rules import srd52

# Monsters by the words in a foe's name, the more specific first.
FOE_WORDS = (('ghoul', 'ghoul'), ('skeleton', 'skeleton'), ('zombie', 'zombie'), ('boar', 'boar'), ('wolf', 'wolf'),
             ('bear', 'brown-bear'), ('warden', 'scout'), ('scout', 'scout'), ('raider', 'warrior-infantry'),
             ('soldier', 'warrior-infantry'), ('guard', 'guard'), ('press-gang', 'tough'), ('thug', 'tough'),
             ('bandit', 'bandit'), ('thief', 'bandit'), ('cultist', 'cultist'))
# Else by the Prospero spec's Vitality: (most, monster).
BY_VITALITY = ((8, 'commoner'), (11, 'bandit'), (13, 'tough'), (99, 'bandit-captain'))
# What the Kingswood pack's weapons are in 5E.
WEAPONS = {'sword': 'longsword', 'felling-axe': 'battleaxe', 'hatchet': 'handaxe', 'knife': 'dagger',
           'cudgel': 'club', 'crowbar': 'club', 'bow': 'shortbow'}
# An attack with the body: an unarmed strike, whatever is carried.
BARE = re.compile(r'\b(punch|kick|headbutt|head-butt|elbow|knee|fist|slap|shove|tackle|wrestle|grapple|throttle|'
                  r'strangle|bite|bare hands?|stamp)\w*', re.I)
# What hit points read as, by the wound level they map to (level_for): never Prospero's wounds.
WORDS = ('unhurt', 'lightly hurt', 'bloodied', 'badly hurt', 'barely standing', 'at 0 hit points')
MORALE_DC = 10
DEATH_SAVE = 10
DICE = re.compile(r'(\d+)d(\d+)\s*([+-]\s*\d+)?')


@cache
def monsters() -> dict[str, dict]:
    return {monster['id']: monster for monster in srd52.pack('monsters')}


@cache
def weapons() -> dict[str, dict]:
    return {item['id']: item for item in srd52.pack('equipment')['items'] if item.get('category') == 'weapon'}


def roll_dice(formula: str, rng: random.Random, twice: bool = False) -> int:
    """'2d8+2' rolled; `twice` rolls the dice twice over (a critical hit), the modifier once."""
    match = DICE.search(formula or '')
    if not match:
        return int(re.sub(r'\D', '', formula or '') or 0)
    count, sides = int(match.group(1)) * (2 if twice else 1), int(match.group(2))
    extra = int(match.group(3).replace(' ', '')) if match.group(3) else 0
    return sum(rng.randint(1, sides) for _ in range(count)) + extra


# Hit points and the wound words -------------------------------------------------------------------

def level_for(hp: int, most: int) -> int:
    """The wound word (dungeon/combat.py LEVELS) that hit points read as: full is unhurt, 0 is dying."""
    if hp <= 0:
        return 5
    ratio = hp / max(1, most)
    return next(level for level, floor in ((0, 1), (1, 0.75), (2, 0.5), (3, 0.25)) if ratio >= floor) \
        if ratio >= 0.25 else 4


def hp_for(level: int, most: int) -> int:
    """Hit points that read as a wound word, for a wound dealt outside a fight (a Life Card, a fall)."""
    return {0: most, 1: math.ceil(0.8 * most), 2: math.ceil(0.6 * most), 3: math.ceil(0.35 * most),
            4: max(1, math.ceil(0.15 * most))}.get(level, 0)


def hit_points(connection) -> tuple[int, int] | None:
    found = sheet.native(connection) if sheet.ruleset(connection) == srd52.ID else None
    return (found['hp'], found['max_hp']) if found else None


def set_hp(connection, hp: int, now: str = '') -> int:
    """The character's hit points, and the wound word they read as; returns that level."""
    found = sheet.native(connection)
    found['hp'] = max(0, min(found['max_hp'], hp))
    sheet.set_native(connection, found, now)
    return level_for(found['hp'], found['max_hp'])


def follow_level(connection, level: int):
    """A wound word set outside a fight moves the hit points with it (only when they read differently)."""
    found = sheet.native(connection) if sheet.ruleset(connection) == srd52.ID else None
    if found and level_for(found['hp'], found['max_hp']) != level:
        found['hp'] = hp_for(level, found['max_hp'])
        sheet.set_native(connection, found, '')


# Foes ---------------------------------------------------------------------------------------------

def monster_for(spec: dict) -> dict:
    if spec.get('srd52') in monsters():
        return monsters()[spec['srd52']]
    name = spec['name'].lower()
    found = next((monster for word, monster in FOE_WORDS if word in name), None)
    if found is None:
        found = next(monster for most, monster in BY_VITALITY if spec.get('vitality', 10) <= most)
    return monsters()[found]


def first_attack(monster: dict) -> dict:
    attack = next((action['attack'] for action in monster['actions']
                   if isinstance(action.get('attack'), dict) and action['attack'].get('bonus') is not None), None)
    if attack is None:
        return {'bonus': 2, 'dice': '1d4', 'type': 'bludgeoning'}
    damage = (attack.get('damage') or [{'dice': '1', 'type': 'bludgeoning'}])[0]
    return {'bonus': attack['bonus'], 'dice': damage['dice'], 'type': damage['type']}


def foes_from(spec: dict, zone: str, rng: random.Random) -> list[dict]:
    monster = monster_for(spec)
    count = spec.get('count', 1)
    result = []
    for number in range(count):
        hp = max(1, roll_dice(monster['hp']['formula'], rng))
        result.append({'id': f"{spec['name']}-{number}", 'name': spec['name'] if count == 1 else
                       f"{spec['name']} {number + 1}", 'monster': monster['id'], 'ac': monster['ac'], 'hp': hp,
                       'max_hp': hp, 'attack': first_attack(monster), 'wis_save': monster['abilities']['wis']['save'],
                       'wound': 0, 'zone': zone, 'broken': False} | ({'horror': True} if spec.get('horror') else {}))
    return result


def hurt(foe: dict, damage: int):
    foe['hp'] = max(0, foe['hp'] - damage)
    foe['wound'] = level_for(foe['hp'], foe['max_hp'])


# The player's attack ------------------------------------------------------------------------------

def weapon_of(items: list[dict], action: str = '') -> dict | None:
    """The weapon an attack uses, as its SRD weapon: none for a punch or a kick, the one the action names, else the
    best carried."""
    if BARE.search(action):
        return None
    held = [weapons()[WEAPONS[row['item_id']]] for row in items if WEAPONS.get(row['item_id']) in weapons()]
    named = [weapon for weapon in held if any(word in action.lower() for word in weapon_words(weapon))]
    return max(named or held, key=lambda weapon: roll_average(weapon['damage']['dice']), default=None)


def weapon_words(weapon: dict) -> list[str]:
    """How a line names a carried weapon: its SRD name and the Kingswood item it is ("axe", "knife")."""
    own = [item.replace('-', ' ') for item, srd in WEAPONS.items() if srd == weapon['id']]
    return [weapon['name'].lower(), *own, *(word.split()[-1] for word in own)]


def roll_average(formula: str) -> float:
    match = DICE.search(formula)
    return int(match.group(1)) * (int(match.group(2)) + 1) / 2 if match else 1


def attack_bonus(found: dict, weapon: dict | None) -> tuple[int, str, str, int]:
    """(to hit, damage dice, what it is, damage modifier) for the character's attack with `weapon`."""
    scores = found['abilities']
    if weapon is None:
        modifier = srd52.modifier(scores['str'])
        return modifier + srd52.proficiency(found['level']), '1', 'Unarmed strike', modifier
    finesse = weapon['weapon_type'] == 'ranged' or 'Finesse' in weapon.get('property_names', [])
    ability = 'dex' if finesse and scores['dex'] >= scores['str'] else 'str'
    modifier = srd52.modifier(scores[ability])
    training = srd52.by_id('classes')[found['class']]['weapon_proficiencies'] or ''
    proficient = 'Martial' in training or weapon['weapon_category'] == 'simple'
    return (modifier + (srd52.proficiency(found['level']) if proficient else 0), weapon['damage']['dice'],
            weapon['name'], modifier)


def strike(connection, roll: dict, target: dict, items: list[dict], rng, lines: list[str]):
    """The character's attack on `target` with the turn's own d20; its roll card is rewritten as the attack."""
    found = sheet.native(connection)
    bonus, dice, what, modifier = attack_bonus(found, weapon_of(items, roll['action']))
    natural = roll['natural']
    total = natural + bonus
    # A Champion crits on 19 or 18; a hit on a paralyzed or unconscious foe is a critical hit.
    critical = natural >= srd52.critical_from(found)
    hit = natural != 1 and (critical or total >= target['ac'])
    critical = hit and (critical or (target.get('held') or {}).get('condition') in HELPLESS)
    band = 'critical_success' if critical else 'success' if hit else 'critical_failure' if natural == 1 else 'failure'
    record_roll(connection, roll, f'Attack ({what})', bonus, total, target['ac'], band)
    target['zone'] = 'engaged'
    if not hit:
        lines.append(f"The player's character's attack on {target['name']} misses.")
        return
    damage = max(1, roll_dice(dice, rng, critical) + modifier)
    hurt(target, damage)
    word = 'down, dead' if target['hp'] <= 0 else describe(target)
    lines.append(f"The player's character {'lands a critical hit on' if critical else 'hits'} {target['name']} for "
                 f"{damage} damage: now {word}.")


def spell_in(connection, roll: dict) -> dict | None:
    """The known spell a roll's action casts (dungeon/sheet.py cast already spent its slot), if any."""
    found = sheet.native(connection)
    return srd52.known_spell(found, roll['action']) if found and found.get('spell_ability') else None


def cast(connection, roll: dict, spell: dict, targets: list[dict], rng, lines: list[str]):
    """A spell in a fight: healing already healed; no slot left fizzles; a damaging spell hits a foe, one that lays a
    condition on a failed save lays it, Magic Missile's darts always hit."""
    if 'no spell slot' in (roll.get('skill') or ''):
        lines.append(f"The player's character reaches for {spell['name']}, but has no spell slot left.")
        return
    if srd52.healing_of(spell):
        lines.append(f"The player's character casts {spell['name']}: {roll['skill'].split('(')[-1].rstrip(')')}.")
        return
    slot = srd52.slot_of(roll.get('skill')) or spell['level']
    damage, condition = srd52.damage_of(spell), condition_of(spell)
    if not targets or (damage is None and spell['id'] not in DARTS and not condition):
        lines.append(f"The player's character casts {spell['name']}.")
        return
    target = next((foe for foe in targets if foe['name'].lower() in roll['action'].lower()), targets[0])
    found = sheet.native(connection)
    if spell['id'] in DARTS:
        darts(spell, slot, target, rng, lines)
        return
    if damage is None:
        lay(connection, roll, spell, condition, target, found, rng, lines)
        return
    dice = srd52.cantrip_dice(damage[0], found['level']) if spell['level'] == 0 else \
        srd52.scaled(damage[0], spell, slot)
    if spell.get('attack'):
        natural, bonus = roll['natural'], srd52.spell_bonus(found)
        critical, hit = natural == 20, natural != 1 and (natural == 20 or natural + bonus >= target['ac'])
        band = 'critical_success' if critical else 'success' if hit else 'critical_failure' if natural == 1 else 'failure'
        record_roll(connection, roll, f"{spell['name']} (spell attack)", bonus, natural + bonus, target['ac'], band)
        dealt = max(1, roll_dice(dice, rng, critical)) if hit else 0
    else:
        ability = spell['saving_throws'][0]
        save = monsters()[target['monster']]['abilities'][ability]['save']
        natural, dc = rng.randint(1, 20), srd52.spell_dc(found)
        failed = natural + save < dc
        # The card shows the foe's save: their d20 and bonus against the spell's DC; a failed save is the spell's
        # success.
        record_roll(connection, roll, f"{spell['name']} ({target['name']}'s {srd52.ABILITY_NAMES[ability]} save, DC "
                    f"{dc})", save, natural + save, dc, 'success' if failed else 'failure', natural)
        rolled = max(1, roll_dice(dice, rng))
        # An Evoker's Potent Cantrip deals half on a save, as a levelled spell does.
        halved = spell['level'] > 0 or srd52.has(found, 'Potent Cantrip')
        dealt = rolled if failed else rolled // 2 if halved else 0
    target['zone'] = 'engaged' if not spell.get('attack') or 'melee' in spell['attack'] else target['zone']
    if not dealt:
        lines.append(f"The player's character casts {spell['name']} at {target['name']}, and it does no harm.")
        return
    hurt(target, dealt)
    word = 'down, dead' if target['hp'] <= 0 else describe(target)
    lines.append(f"The player's character casts {spell['name']} at {target['name']}: {dealt} {damage[1]} damage, "
                 f"now {word}.")


# Conditions a failed save lays on a foe, the gravest first: the helpless can't act and may save again each round;
# the charmed stop fighting and the frightened flee; the restrained and blinded attack with disadvantage.
CONDITIONS = ('Paralyzed', 'Unconscious', 'Incapacitated', 'Charmed', 'Frightened', 'Restrained', 'Blinded')
HELPLESS = ('Paralyzed', 'Unconscious', 'Incapacitated')
HAMPERED = ('Restrained', 'Blinded')
# Spells whose darts always hit: how many at the spell's own level (one more a slot level above).
DARTS = {'magic-missile': 3}


def condition_of(spell: dict) -> str | None:
    if not spell.get('saving_throws'):
        return None
    return next((name for name in CONDITIONS if f'{name} condition' in spell['description']), None)


def darts(spell: dict, slot: int, target: dict, rng, lines: list[str]):
    count = DARTS[spell['id']] + slot - spell['level']
    dealt = sum(rng.randint(1, 4) + 1 for _ in range(count))
    hurt(target, dealt)
    word = 'down, dead' if target['hp'] <= 0 else describe(target)
    lines.append(f"The player's character casts {spell['name']}: {count} darts strike {target['name']} for {dealt} "
                 f"force damage, now {word}.")


def lay(connection, roll: dict, spell: dict, condition: str, target: dict, found: dict, rng, lines: list[str]):
    """A spell that lays a condition: the foe's save against the spell save DC; a failure takes it."""
    ability = spell['saving_throws'][0]
    save = monsters()[target['monster']]['abilities'][ability]['save']
    natural, dc = rng.randint(1, 20), srd52.spell_dc(found)
    failed = natural + save < dc
    record_roll(connection, roll, f"{spell['name']} ({target['name']}'s {srd52.ABILITY_NAMES[ability]} save, DC "
                f"{dc})", save, natural + save, dc, 'success' if failed else 'failure', natural)
    if not failed:
        lines.append(f"The player's character casts {spell['name']} at {target['name']}, who resists it.")
        return
    said = condition.lower()
    if condition in HELPLESS:
        target['held'] = {'condition': condition, 'save': ability, 'dc': dc,
                          'repeat': 'repeat' in spell['description']}
        lines.append(f"The player's character casts {spell['name']} at {target['name']}: {said}, they can't act.")
    elif condition in HAMPERED:
        target['hampered'] = condition
        lines.append(f"The player's character casts {spell['name']} at {target['name']}: {said}, their attacks "
                     'falter.')
    else:
        target['broken'] = True
        what = 'they stop fighting' if condition == 'Charmed' else 'they flee'
        lines.append(f"The player's character casts {spell['name']} at {target['name']}: {said}, {what}.")


def held(foe: dict, rng, lines: list[str]) -> bool:
    """A helpless foe loses its turn; one whose spell allows it saves again at the end of it."""
    spell = foe.get('held')
    if not spell:
        return False
    lines.append(f"{foe['name'].capitalize()} is {spell['condition'].lower()} and can't act.")
    if spell['repeat'] and rng.randint(1, 20) + monsters()[foe['monster']]['abilities'][spell['save']]['save'] \
            >= spell['dc']:
        foe.pop('held')
        lines.append(f"{foe['name'].capitalize()} shakes it off.")
    return True


def record_roll(connection, roll: dict, skill: str, bonus: int, total: int, target: int, band: str,
                natural: int | None = None):
    """Rewrites the roll's card as what it became in the fight (an attack on AC, a foe's save)."""
    natural = roll['natural'] if natural is None else natural
    connection.execute('UPDATE story_rolls SET skill=?, natural=?, bonus=?, total=?, target=?, band=? WHERE id=?',
                       (skill, natural, bonus, total, target, band, roll['id']))
    roll.update(skill=skill, natural=natural, bonus=bonus, total=total, target=target, band=band)


# Experience ---------------------------------------------------------------------------------------

def fight_xp(state: dict) -> int:
    return sum(monsters()[foe['monster']]['xp'] for foe in state['foes']
               if 'monster' in foe and (foe['hp'] <= 0 or foe['broken']))


def gain(connection, xp: int, why: str, now: str = '') -> list[str]:
    """XP for the character, and the levels it reaches, at once."""
    found = sheet.native(connection) if sheet.ruleset(connection) == srd52.ID else None
    if not found or xp <= 0:
        return []
    found['xp'] = found.get('xp', 0) + xp
    lines = [f"The character gains {xp} XP ({why}): {found['xp']} in all."]
    while found['level'] < srd52.MAX_LEVEL and found['xp'] >= srd52.xp_for(found['level'] + 1):
        found, gained = srd52.advance(found)
        lines.append(f"The character reaches level {found['level']}: {', '.join(gained)}.")
    sheet.set_native(connection, found, now)
    return lines


def milestone_xp(connection) -> int:
    found = sheet.native(connection)
    budget = next(row for row in srd52.pack('rules')['xp_budget_per_character'] if row['level'] == found['level'])
    return budget['high']


def describe(foe: dict) -> str:
    return 'broken, fleeing or giving up' if foe['broken'] else WORDS[foe['wound']]


# The round ----------------------------------------------------------------------------------------

def morale(state: dict, standing, rng, lines: list[str]):
    if not any(foe['wound'] >= 3 for foe in state['foes']):
        return
    for foe in standing(state):
        if rng.randint(1, 20) + foe['wis_save'] < MORALE_DC:
            foe['broken'] = True
            lines.append(f"{foe['name'].capitalize()} breaks: they flee or give up.")


def foes_attack(connection, state: dict, standing, guarded: bool, rng, lines: list[str]) -> int:
    """Each foe still standing closes in or attacks the character's AC; returns the character's wound level."""
    found = sheet.native(connection)
    hp = found['hp']
    for foe in standing(state):
        if held(foe, rng, lines) or ranges.close(foe, lines):
            continue
        natural, _ = srd52.d20(rng, 'disadvantage' if guarded or foe.get('hampered') else '')
        if natural == 1 or (natural != 20 and natural + foe['attack']['bonus'] < found['ac']):
            lines.append(f"{foe['name'].capitalize()} attacks and misses.")
            continue
        damage = max(1, roll_dice(foe['attack']['dice'], rng, natural == 20))
        before, hp = hp, max(0, hp - damage)
        # A critical hit, or a blow that drops the character to 0, can leave a lasting injury (dungeon/injuries.py),
        # as the lingering injuries rule has it.
        if natural == 20 or before > 0 >= hp:
            state['hurt_by'] = foe['name']
        lines.append(f"{foe['name'].capitalize()} {'lands a critical hit on' if natural == 20 else 'hits'} the "
                     f"player's character for {damage} damage: {hp} of {found['max_hp']} hit points left.")
        if hp <= 0:
            break
    return set_hp(connection, hp)


def death_saves(rng) -> tuple[bool, bool, list[int]]:
    """(alive, back on their feet with 1 hit point, the rolls): three successes or three failures decide."""
    successes = failures = 0
    rolls = []
    while successes < 3 and failures < 3:
        natural = rng.randint(1, 20)
        rolls.append(natural)
        if natural == 20:
            return True, True, rolls
        if natural == 1:
            failures += 2
        elif natural >= DEATH_SAVE:
            successes += 1
        else:
            failures += 1
    return successes >= 3, False, rolls


def long_rest(connection, nights: int) -> list[str]:
    """A night's sleep restores every hit point and spell slot (as written)."""
    found = sheet.native(connection)
    spent = any((found.get('spells') or {}).get('used') or [])
    if nights <= 0 or (found['hp'] >= found['max_hp'] and not spent):
        return []
    lines = [f"A long rest restores the character's hit points: {found['max_hp']} of {found['max_hp']}."] \
        if found['hp'] < found['max_hp'] else []
    found['hp'] = found['max_hp']
    if spent:
        found['spells']['used'] = [0] * 9
        lines.append("A long rest gives the character back their spell slots.")
    sheet.set_native(connection, found, '')
    return lines


def foe_line(foe: dict) -> str:
    return f"{foe['name']}: {'down' if foe['hp'] <= 0 else describe(foe)}"


def encode_foes(foes: list[dict]) -> str:
    return json.dumps(foes)
