"""5E via the SRD 5.2.1 (docs/requirements.md "Rulesets"; content in dungeon/rules/packs/srd52, under CC-BY-4.0).

- **The sheet.** Six ability scores, a class, a species and a background from the pack, a level, proficiency in the
  class's saving throws and in skills (the background's two and the class's own picks), hit points from the class's
  hit die and Constitution, and Armor Class from the armour in the class's starting equipment (option A: a Fighter's
  Chain Mail, a Cleric's Chain Shirt and Shield), else unarmored: 10 + Dexterity (Barbarians add Constitution, Monks
  Wisdom).
  A new character takes the standard array (15, 14, 13, 12, 10, 8) placed where the player likes, then the
  background's +2 and +1.
- **A check** is a d20 plus the ability modifier, plus the proficiency bonus when the character is proficient in the
  skill (or the save), against a DC. The Referee's difficulty is Prospero's, where a hard check passes about half the
  time, so it maps to the DC that does the same for a starting character: 10 easy, 12 normal, 15 hard, 20 very hard,
  25 extreme. Advantage rolls two d20
  and keeps the higher, disadvantage the lower.
- **The outcome ladder: pass or fail as written** (the pack's `resolution.outcome_mapping`). Meeting the DC is a
  success, else a failure. A natural 20 or 1 is a critical only on attack rolls and death saves.
- **Levels** (docs/story.md "5E levels and spells"): XP from the pack's advancement table; each level adds the hit
  die's fixed average plus Constitution to hit points, the class's features, and at Ability Score Improvement +2 to
  the class's primary ability (up to 20, the rest to the next ability).
- **Spells.** A caster knows the class's cantrips and prepares spells up to the class's counts, picked by code (the
  damaging and healing ones first) and kept as they level. An action that names a known spell is cast with the
  spellcasting ability: an attack is d20 + ability + proficiency, a save's DC 8 + ability + proficiency. A
  levelled spell spends a slot of its level or higher; a long rest gives them back.
- **The Referee still speaks in approaches** (Prospero's six stats, which name what an action leans on); code reads
  the skill from the action's words and its ability from the skill, else from the approach (EQUIVALENT).
"""
import json
import random
import re
from functools import cache
from pathlib import Path

ID = 'srd52'
NAME = '5E (SRD 5.2.1)'
PACK = Path(__file__).parent / 'packs' / 'srd52'
ABILITIES = ('str', 'dex', 'con', 'int', 'wis', 'cha')
ABILITY_NAMES = {'str': 'Strength', 'dex': 'Dexterity', 'con': 'Constitution', 'int': 'Intelligence',
                 'wis': 'Wisdom', 'cha': 'Charisma'}
STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)
SCORE_RANGE = (1, 30)
DCS = {'easy': 10, 'normal': 12, 'hard': 15, 'very_hard': 20, 'extreme': 25}
# What each of the Referee's approaches leans on, when the action's words name no skill. Essence is the class's
# spellcasting ability, else Wisdom.
EQUIVALENT = {'Mind': 'int', 'Allure': 'cha', 'Resolve': 'wis', 'Vitality': 'str', 'Essence': None, 'Luck': 'dex'}
# Words that name a skill, the more specific first.
SKILL_WORDS = (
    ('sleight-of-hand', ('pickpocket', 'steal', 'palm', 'pick the lock', 'pick a lock', 'lift his', 'lift her',
                         'sleight')),
    ('stealth', ('sneak', 'hide', 'slip past', 'creep', 'unseen', 'quietly')),
    ('acrobatics', ('dodge', 'tumble', 'balance', 'flip', 'roll away', 'squeeze', 'slip free')),
    ('athletics', ('climb', 'jump', 'leap', 'swim', 'shove', 'wrestle', 'grapple', 'lift', 'force', 'break',
                   'push', 'tackle', 'run')),
    ('deception', ('lie', 'bluff', 'deceive', 'disguise', 'pretend', 'con ')),
    ('intimidation', ('intimidate', 'threaten', 'stare down', 'menace', 'scare')),
    ('persuasion', ('persuade', 'convince', 'charm', 'haggle', 'bargain', 'negotiate', 'beg', 'flatter', 'plead',
                    'talk them', 'talk him', 'talk her', 'talk my way', 'sweet-talk', 'seduce', 'flirt')),
    ('performance', ('perform', 'sing', 'dance', 'play the', 'recite', 'taunt')),
    ('insight', ('read his', 'read her', 'read their', 'tell if', 'sense', 'motive', 'lying to me')),
    ('perception', ('notice', 'spot', 'listen', 'look out', 'keep watch', 'hear')),
    ('investigation', ('search', 'examine', 'investigate', 'deduce', 'figure out', 'study', 'inspect')),
    ('medicine', ('treat', 'patch', 'bandage', 'stitch', 'heal', 'stabilize', 'diagnose')),
    ('survival', ('track', 'forage', 'hunt', 'find the way', 'navigate', 'find our way', 'find my way')),
    ('animal-handling', ('calm the horse', 'calm the dog', 'ride', 'tame', 'soothe the')),
    ('arcana', ('magic', 'spell', 'rune', 'arcane', 'ward', 'enchant')),
    ('religion', ('pray', 'god', 'rite', 'holy', 'shrine')),
    ('history', ('recall', 'remember', 'history', 'legend')),
    ('nature', ('plant', 'herb', 'weather', 'beast')),
)
# The save that resists what an approach stands up to (fear and pain with Resolve, a blow with Vitality).
SAVE_EQUIVALENT = {'Mind': 'int', 'Allure': 'cha', 'Resolve': 'wis', 'Vitality': 'con', 'Essence': None, 'Luck': 'dex'}
UNARMORED = {'barbarian': 'con', 'monk': 'wis'}


@cache
def pack(name: str) -> list | dict:
    return json.loads((PACK / f'{name}.json').read_text(encoding='utf-8'))


def by_id(name: str) -> dict[str, dict]:
    return {item['id']: item for item in pack(name)}


def skills() -> dict[str, dict]:
    return {skill['id']: skill for skill in pack('rules')['skills']}


def skill_id(name: str) -> str:
    return name.strip().lower().replace(' ', '-')


def attribution() -> str:
    return pack('pack')['license']['attribution']


def modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency(level: int) -> int:
    return 2 + (max(1, level) - 1) // 4


def signed(value: int) -> str:
    return f'+{value}' if value >= 0 else str(value)


# The sheet --------------------------------------------------------------------------------------------------

def spell_ability(class_id: str) -> str | None:
    found = by_id('classes').get(class_id, {}).get('spellcasting')
    return found.get('ability') if isinstance(found, dict) else None


def starting_armor(class_id: str) -> list[str]:
    """The armour (and shield) in the class's starting equipment, option A."""
    text = by_id('classes')[class_id]['starting_equipment']
    first = text.split('(B)')[0]
    named = [item for item in pack('equipment')['items'] if item.get('category') == 'armor'
             and re.search(rf"\b{re.escape(item['name'])}\b", first)]
    # "Studded Leather Armor" is not also "Leather Armor".
    return [item['id'] for item in named if not any(item is not other and item['name'] in other['name']
                                                    for other in named)]


def armor_class(class_id: str, scores: dict[str, int], armor: list[str] | None = None) -> int:
    worn = [item for item in pack('equipment')['items'] if item['id'] in (armor or [])]
    body = next((item for item in worn if item.get('armor_type') != 'shield'), None)
    shield = sum(item.get('ac_bonus', 0) for item in worn if item.get('armor_type') == 'shield')
    dex = modifier(scores['dex'])
    if body:
        allowed = min(dex, body['dex_max']) if body.get('dex_max') is not None else dex
        return body['ac_base'] + (allowed if body.get('dex_bonus') else 0) + shield
    extra = UNARMORED.get(class_id)
    return 10 + dex + (modifier(scores[extra]) if extra else 0) + shield


def with_background(scores: dict[str, int], background: dict) -> dict[str, int]:
    """The background's +2 to the best of its three abilities as placed, +1 to the next (2024 rules)."""
    ranked = sorted(background['ability_scores'], key=lambda ability: (-scores[ability], ABILITIES.index(ability)))
    raised = dict(scores)
    raised[ranked[0]] += 2
    raised[ranked[1]] += 1
    return {ability: min(20, value) for ability, value in raised.items()}


def build(class_id: str, species_id: str, background_id: str, scores: dict[str, int], picks: list[str]) -> dict:
    """A level 1 character from the pack. `scores` places the standard array; `picks` are the class's skills."""
    from dungeon.errors import require
    classes, species, backgrounds = by_id('classes'), by_id('species'), by_id('backgrounds')
    require(class_id in classes, 'That class is not in the 5E pack.', 422)
    require(species_id in species, 'That species is not in the 5E pack.', 422)
    require(background_id in backgrounds, 'That background is not in the 5E pack.', 422)
    require(set(scores) == set(ABILITIES) and sorted(scores.values(), reverse=True) == list(STANDARD_ARRAY),
            'Place the standard array (15, 14, 13, 12, 10, 8) on the six abilities, one each.', 422)
    chosen, background = classes[class_id], backgrounds[background_id]
    from_background = [skill_id(name) for name in background['skill_proficiencies']]
    allowed = {skill_id(name) for name in chosen['skill_choices']['from']} - set(from_background)
    picks = list(dict.fromkeys(skill_id(name) for name in picks))
    require(len(picks) == chosen['skill_choices']['count'] and set(picks) <= allowed,
            f"Pick {chosen['skill_choices']['count']} of the {chosen['name']}'s skills the background doesn't give.", 422)
    final = with_background(scores, background)
    hp = chosen['hit_die'] + modifier(final['con'])
    made = {'class': class_id, 'species': species_id, 'background': background_id, 'level': 1, 'xp': 0,
            'abilities': final, 'skills': sorted(set(from_background) | set(picks)), 'saves': chosen['saving_throws'],
            'max_hp': max(1, hp), 'hp': max(1, hp), 'armor': starting_armor(class_id),
            'ac': armor_class(class_id, final, starting_armor(class_id)),
            'speed': species[species_id]['speed'], 'spell_ability': spell_ability(class_id),
            'features': step(class_id, 1)['features']}
    return with_spells(made)


def suggested(class_id: str, background_id: str) -> dict:
    """A quick build: the standard array on the class's primary abilities first, the class's first skills."""
    chosen, background = by_id('classes')[class_id], by_id('backgrounds')[background_id]
    primary = [ability for ability, name in ABILITY_NAMES.items() if name in chosen['primary_ability']]
    order = primary + [ability for ability in ('con', 'dex', 'wis', 'str', 'cha', 'int') if ability not in primary]
    scores = dict(zip(order, STANDARD_ARRAY))
    taken = {skill_id(name) for name in background['skill_proficiencies']}
    picks = [skill_id(name) for name in chosen['skill_choices']['from'] if skill_id(name) not in taken]
    return {'scores': scores, 'picks': picks[:chosen['skill_choices']['count']]}


# Levels -----------------------------------------------------------------------------------------------------

MAX_LEVEL = 20
IMPROVEMENT = 'Ability Score Improvement'


def xp_for(level: int) -> int | None:
    """The XP that reaches `level` (None past 20)."""
    return next((row['xp'] for row in pack('rules')['character_advancement'] if row['level'] == level), None)


def level_for_xp(xp: int) -> int:
    return max(row['level'] for row in pack('rules')['character_advancement'] if row['xp'] <= xp)


def step(class_id: str, level: int) -> dict:
    """The class's progression row for `level`: features, columns, spell slots."""
    return next(row for row in by_id('classes')[class_id]['progression'] if row['level'] == level)


def improve(sheet: dict) -> list[str]:
    """Ability Score Improvement: +2 to the class's primary ability, up to 20; what is left to the next best."""
    chosen = by_id('classes')[sheet['class']]
    primary = [ability for ability, name in ABILITY_NAMES.items() if name in chosen['primary_ability']]
    order = primary + sorted((ability for ability in ABILITIES if ability not in primary),
                             key=lambda ability: (-sheet['abilities'][ability], ABILITIES.index(ability)))
    raised, left = [], 2
    for ability in order:
        room = min(left, 20 - sheet['abilities'][ability])
        if room > 0:
            sheet['abilities'][ability] += room
            raised.append(f'{ABILITY_NAMES[ability]} +{room}')
            left -= room
        if not left:
            break
    return raised


def advance(sheet: dict) -> tuple[dict, list[str]]:
    """One level up, as written (the hit die's fixed average): the new sheet and what it gained."""
    found = json.loads(json.dumps(sheet))
    found['level'] = level = min(MAX_LEVEL, found['level'] + 1)
    row = step(found['class'], level)
    gained = []
    features = [name for name in row['features'] if name != IMPROVEMENT]
    if IMPROVEMENT in row['features'] and (raised := improve(found)):
        gained.append(', '.join(raised))
    before = found['max_hp']
    found['max_hp'] += max(1, by_id('classes')[found['class']]['hit_die'] // 2 + 1 + modifier(found['abilities']['con']))
    found['hp'] += found['max_hp'] - before
    found['ac'] = armor_class(found['class'], found['abilities'], found.get('armor'))
    features = subclassed(found, features)
    found['features'] = list(dict.fromkeys(found.get('features', []) + features))
    gained.insert(0, f"{found['max_hp'] - before} more hit points")
    gained += features
    found = with_spells(found)
    return found, gained


def subclassed(sheet: dict, features: list[str]) -> list[str]:
    """The level's features with the subclass in them: at the class's subclass level the SRD's one subclass is the
    character's (its name in place of "Fighter Subclass"), and from then each level adds its features. Changes
    `sheet`."""
    chosen = by_id('classes')[sheet['class']]['subclass']
    if any(name.endswith(' Subclass') for name in features):
        sheet['subclass'] = chosen['id']
        features = [chosen['name'] if name.endswith(' Subclass') else name for name in features]
    if sheet.get('subclass') != chosen['id']:
        return features
    return features + [feature['name'] for feature in chosen['features'] if feature['level'] == sheet['level']]


def subclass_spells(sheet: dict) -> list[str]:
    """The spells the subclass always has prepared at the character's level (a Circle of the Land druid's first
    land, as code picks it)."""
    chosen = by_id('classes')[sheet['class']]['subclass']
    if sheet.get('subclass') != chosen['id']:
        return []
    named = {spell['name'].lower().replace('’', "'"): spell['id'] for spell in spells().values()}
    found = []
    for feature in chosen['features']:
        if feature['name'].endswith(' Spells') and feature.get('tables'):
            for level, names in feature['tables'][0]['rows']:
                if int(level) <= sheet['level']:
                    found += [named[name] for name in (part.strip().lower().replace('’', "'")
                                                       for part in names.split(',')) if name in named]
    return found


def has(sheet: dict, feature: str) -> bool:
    return feature in sheet.get('features', [])


def critical_from(sheet: dict) -> int:
    """The lowest natural d20 that is a critical hit: 20, or 19 with the Champion's Improved Critical, 18 with
    Superior Critical."""
    return 18 if has(sheet, 'Superior Critical') else 19 if has(sheet, 'Improved Critical') else 20


# Spells -----------------------------------------------------------------------------------------------------

DAMAGE = re.compile(r'(\d+)d(\d+)(?:\s*\+\s*your spellcasting ability modifier)?\s+(\w+) damage')
HEALING = re.compile(r'regains? (?:a number of )?Hit Points equal to (\d+d\d+)')


@cache
def spells() -> dict[str, dict]:
    return {spell['id']: spell for spell in pack('spells')}


def damage_of(spell: dict) -> tuple[str, str] | None:
    """(dice, type) a spell that attacks or forces a save deals, else None (riders like Hex do not count)."""
    match = DAMAGE.search(spell['description'])
    return (f'{match.group(1)}d{match.group(2)}', match.group(3).lower()) \
        if match and (spell.get('attack') or spell.get('saving_throws')) else None


def healing_of(spell: dict) -> str | None:
    match = HEALING.search(spell['description'])
    return match.group(1) if match else None


def slots_for(class_id: str, level: int) -> list[int]:
    row = step(class_id, level)
    if row.get('spell_slots'):
        return list(row['spell_slots']) + [0] * (9 - len(row['spell_slots']))
    columns = row['columns']
    if columns.get('spell_slots'):  # Pact Magic: a few slots, all of one level.
        return [columns['spell_slots'] if number == columns['slot_level'] else 0 for number in range(1, 10)]
    return [0] * 9


def picks_from(class_name: str, levels: range, count: int, kept: list[str]) -> list[str]:
    """`count` spells of `levels` from the class's list: those already kept, then damage, then healing, then the rest."""
    known = [spell for spell in spells().values() if class_name in spell['classes'] and spell['level'] in levels]
    ranked = sorted(known, key=lambda spell: (spell['id'] not in kept, not damage_of(spell), not healing_of(spell),
                                              -spell['level'], spell['name']))
    return [spell['id'] for spell in ranked[:count]]


def with_spells(sheet: dict) -> dict:
    """The sheet with the class's spells for its level: cantrips, prepared spells, slots (used ones stay used)."""
    if not sheet.get('spell_ability'):
        return sheet
    chosen = by_id('classes')[sheet['class']]
    columns, slots = step(sheet['class'], sheet['level'])['columns'], slots_for(sheet['class'], sheet['level'])
    highest = max((number for number, count in enumerate(slots, 1) if count), default=1)
    old = sheet.get('spells') or {}
    used = old.get('used') or [0] * 9
    always = subclass_spells(sheet)
    own = picks_from(chosen['name'], range(1, highest + 1), int(columns.get('prepared_spells') or 0),
                     [spell for spell in old.get('prepared', []) if spell not in always])
    return sheet | {'spells': {
        'cantrips': list(dict.fromkeys(
            picks_from(chosen['name'], range(0, 1), int(columns.get('cantrips') or 0), old.get('cantrips', []))
            + [spell for spell in always if spells()[spell]['level'] == 0])),
        # The subclass's spells are always prepared, on top of the class's count.
        'prepared': list(dict.fromkeys(own + [spell for spell in always if spells()[spell]['level'] > 0])),
        'slots': slots, 'used': [min(count, spent) for count, spent in zip(slots, used)]}}


def known_spell(sheet: dict, text: str) -> dict | None:
    """A cantrip or prepared spell the action names."""
    own = sheet.get('spells') or {}
    lowered = text.lower()
    return next((spells()[spell] for spell in own.get('cantrips', []) + own.get('prepared', [])
                 if re.search(rf"\b{re.escape(spells()[spell]['name'].lower())}\b", lowered)), None)


def cast_named(text: str) -> dict | None:
    """The SRD spell a line casts by name ("I cast Cure Wounds on myself"), known or not; the longest name first, so
    "Mass Cure Wounds" is not read as Cure Wounds. Only a name after "cast": "Light" or "Sleep" alone are words."""
    lowered = text.lower()
    return next((spell for spell in sorted(spells().values(), key=lambda spell: -len(spell['name']))
                 if re.search(rf"\bcast(?:s|ing)?\s+(?:(?:a|an|the|my)\s+)?{re.escape(spell['name'].lower())}\b",
                              lowered)), None)


def knows(sheet: dict, spell: dict) -> bool:
    own = sheet.get('spells') or {}
    return spell['id'] in own.get('cantrips', []) + own.get('prepared', [])


def spell_bonus(sheet: dict) -> int:
    return modifier(sheet['abilities'][sheet['spell_ability']]) + proficiency(sheet['level'])


def spell_dc(sheet: dict) -> int:
    return 8 + spell_bonus(sheet)


def cantrip_dice(dice: str, level: int) -> str:
    count, sides = dice.split('d')
    return f"{int(count) * (1 + (level >= 5) + (level >= 11) + (level >= 17))}d{sides}"


UPCAST = re.compile(r'\b(?:at|as an?|with an?|using an?|in an?|from an?|on an?)\s+(\d)(?:st|nd|rd|th)[- ]level\b|'
                    r'\bupcast\w*\s+(?:to|at)\s+(?:level\s+)?(\d)\b', re.I)
HIGHER = re.compile(r'(damage|healing)[^.]*?increases by (\d+)d(\d+) for each spell slot level above (\d)', re.I)


def ordinal(number: int) -> str:
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number, 'th')}"


SLOT = re.compile(r'\((\d)(?:st|nd|rd|th)-level slot\)')


def slot_of(skill: str | None) -> int | None:
    """The slot a roll's card says a spell was cast with, when above the spell's level."""
    match = SLOT.search(skill or '')
    return int(match.group(1)) if match else None


def upcast(text: str) -> int | None:
    """The slot level a line asks for ("cast Cure Wounds at 2nd level", "with a 3rd-level slot")."""
    match = UPCAST.search(text)
    return int(match.group(1) or match.group(2)) if match else None


def scaled(dice: str, spell: dict, slot: int | None) -> str:
    """A spell's damage or healing dice cast with a higher slot, as its higher_levels text says."""
    match = HIGHER.search(spell.get('higher_levels') or '')
    count, sides = dice.split('d')
    if not match or not slot or slot <= int(match.group(4)) or match.group(3) != sides:
        return dice
    return f"{int(count) + int(match.group(2)) * (slot - int(match.group(4)))}d{sides}"


def spend(sheet: dict, spell: dict, at: int | None = None) -> int | None:
    """Spends a slot for the spell: the level asked for (`at`) when it is free, else the lowest free slot it fits;
    returns the slot's level (0 for a cantrip), None when none is left."""
    if spell['level'] == 0:
        return 0
    own = sheet['spells']
    asked = [at] if at and spell['level'] <= at <= 9 else []
    for number in asked + list(range(spell['level'], 10)):
        if own['used'][number - 1] < own['slots'][number - 1]:
            own['used'][number - 1] += 1
            return number
    return None


def view(sheet: dict) -> dict:
    """The sheet as the screen shows it: names, modifiers, every skill's bonus and the attribution."""
    bonus = proficiency(sheet['level'])
    names = {'class': by_id('classes')[sheet['class']]['name'], 'species': by_id('species')[sheet['species']]['name'],
             'background': by_id('backgrounds')[sheet['background']]['name'],
             'subclass': by_id('classes')[sheet['class']]['subclass']['name'] if sheet.get('subclass') else None}
    return {'ruleset': ID, 'ruleset_name': NAME, **sheet, 'names': names, 'proficiency': bonus,
            'modifiers': {ability: modifier(score) for ability, score in sheet['abilities'].items()},
            'skill_bonuses': {skill['id']: {'name': skill['name'], 'ability': skill['ability'],
                                            'bonus': modifier(sheet['abilities'][skill['ability']])
                                            + (bonus if skill['id'] in sheet['skills'] else 0),
                                            'proficient': skill['id'] in sheet['skills']}
                              for skill in pack('rules')['skills']},
            'attribution': attribution(), 'next_xp': xp_for(sheet['level'] + 1),
            'spell_list': spell_view(sheet)}


def spell_view(sheet: dict) -> dict | None:
    own = sheet.get('spells')
    if not own:
        return None
    name = lambda spell: spells()[spell]['name']  # noqa: E731
    return {'ability': ABILITY_NAMES[sheet['spell_ability']], 'attack': spell_bonus(sheet), 'dc': spell_dc(sheet),
            'cantrips': [name(spell) for spell in own['cantrips']],
            'prepared': [{'name': name(spell), 'level': spells()[spell]['level']} for spell in own['prepared']],
            'slots': [{'level': number, 'left': count - spent, 'of': count}
                      for number, (count, spent) in enumerate(zip(own['slots'], own['used']), 1) if count]}


def described(sheet: dict) -> str:
    """The character in a line, for the narrator."""
    view_names = view(sheet)['names']
    strong = [ABILITY_NAMES[ability] for ability, score in sheet['abilities'].items() if score >= 15]
    weak = [ABILITY_NAMES[ability] for ability, score in sheet['abilities'].items() if score <= 9]
    subclass = f", {view_names['subclass']}" if view_names['subclass'] else ''
    return (f"A level {sheet['level']} {view_names['species']} {view_names['class']}{subclass} "
            f"({view_names['background']})"
            + (f"; strong in {', '.join(strong)}" if strong else '') + (f"; weak in {', '.join(weak)}" if weak else '')
            + '.')


# Checks -----------------------------------------------------------------------------------------------------

def skill_for(text: str) -> str | None:
    lowered = text.lower()
    return next((skill for skill, words in SKILL_WORDS if any(re.search(rf'\b{re.escape(word)}', lowered)
                                                                for word in words)), None)


def read(sheet: dict, approach: str, text: str) -> tuple[str | None, str]:
    """The skill an action uses (None for a plain ability check) and its ability."""
    skill = skill_for(text)
    if skill:
        return skill, skills()[skill]['ability']
    return None, EQUIVALENT.get(approach) or sheet.get('spell_ability') or 'wis'


def d20(rng: random.Random, edge: str = '') -> tuple[int, list[int]]:
    rolls = [rng.randint(1, 20)] + ([rng.randint(1, 20)] if edge in ('advantage', 'disadvantage') else [])
    return (max(rolls) if edge == 'advantage' else min(rolls) if edge == 'disadvantage' else rolls[0]), rolls


def check(sheet: dict, approach: str, difficulty: str, text: str = '', rng: random.Random | None = None,
          save: bool = False, edge: str = '') -> dict:
    """An ability check (or a saving throw) against the DC for the difficulty, pass or fail as written."""
    rng = rng or random.SystemRandom()
    if not save and sheet.get('spell_ability') and (spell := known_spell(sheet, text)):
        return cast_check(sheet, spell, difficulty, rng, edge)
    skill, ability = (None, SAVE_EQUIVALENT.get(approach) or sheet.get('spell_ability') or 'wis') if save else \
        read(sheet, approach, text)
    proficient = (ability in sheet['saves']) if save else (skill in sheet['skills'])
    bonus = modifier(sheet['abilities'][ability]) + (proficiency(sheet['level']) if proficient else 0)
    natural, rolls = d20(rng, edge)
    dc = DCS.get(difficulty, DCS['normal'])
    total = natural + bonus
    label = (skills()[skill]['name'] if skill else ABILITY_NAMES[ability]) + (' save' if save else '')
    return {'natural': natural, 'die': 20, 'bonus': bonus, 'shift': 0, 'total': total, 'target': dc,
            'skill': label, 'ability': ability, 'rolls': rolls,
            'band': 'success' if total >= dc else 'failure'}


def cast_check(sheet: dict, spell: dict, difficulty: str, rng: random.Random, edge: str = '') -> dict:
    """An action that casts a known spell: the spellcasting ability and proficiency against the DC. (In a fight the
    attack or save is made against the foe instead, dungeon/combat5e.py.) `spell` names it for the slot it spends."""
    bonus, natural_rolls = spell_bonus(sheet), d20(rng, edge)
    natural, rolls = natural_rolls
    dc = DCS.get(difficulty, DCS['normal'])
    return {'natural': natural, 'die': 20, 'bonus': bonus, 'shift': 0, 'total': natural + bonus, 'target': dc,
            'skill': f"{spell['name']} (spell)", 'ability': sheet['spell_ability'], 'rolls': rolls,
            'spell': spell['id'], 'band': 'success' if natural + bonus >= dc else 'failure'}
