"""Combat v0 (requirements "Combat", "Injuries and recovery"; docs/story.md "Fights").

Code runs the fight; the narrator writes it. One line of the player's is one round:
- A fight starts when the player attacks someone in the scene (by name or by what they do: "the barkeep"), or when
  a dangerous place's threat brings a foe (dungeon/quests.py). An attack on someone the scene does not hold (an extra
  the narrator brought in) fights a stand-in.
- Each round the player's rolled actions land first: an attack that succeeds wounds its target by the band (a cost
  one level, a success two, a critical three) and the weapon carried (a sword or axe one more, bare hands one less).
  A successful dodge, block or parry makes the foes' attacks this round hard. A successful flight ends the fight.
- Foes at a distance close in instead of attacking. Engaged foes roll Vitality to hit back the same way.
- A foe at Maimed is down. When one falls or is badly hurt, the rest roll Resolve, and a failure breaks them: they
  flee or give up. The player wins when no foe is left standing and unbroken.
- Prospero wounds: Grazed, Hurt, Wounded, Maimed, Dying. Wounded makes physical actions a step harder; Maimed makes
  every action a step harder and physical ones two. Prospero heals gritty: a wound drops one level after nights of
  rest set by its severity (dungeon/rest.py), from Maimed down; a new wound starts the count again.
- At Dying the character rolls Vitality to cling on, then the defeat table, weighted by what the foes want: beasts
  kill, wardens capture, robbers rob, a brawl ends with the character thrown out. Death is real; the player can
  always go back to an earlier line. A character taken prisoner stays held (story_wounds.captors): they go nowhere
  until a line that tries to get free (slip the bonds, pick the lock, run) succeeds.

Under 5E the same fight runs on hit points, Armor Class and SRD stat blocks (dungeon/combat5e.py); under Ironsworn
on health, harm, initiative and progress tracks (dungeon/combat_iron.py); under BRP on skills, the Attack and Defense
Matrix, hit points and major wounds (dungeon/combat_brp.py).

Surprise is rolled as a fight begins (requirements "Surprise and ambushes are rolled"): an attack the player's line
makes by stealth ("I creep up behind him") rolls the character's Vitality against the foe's awareness, and a danger's
foe rolls its stealth against the character's Mind. A side taken unawares loses the first round: surprised foes don't
strike back, a surprised character's actions come to nothing while the foes close and strike. Both rolls are roll
cards.

Fight on my plan (requirements "Pacing"): a line that sets a plan ("I hold the door and cut down whoever comes, fight
on until they break") plays its round, then keeps fighting on that plan, a roll a round (each a roll card), until a
turning point: someone falls, a foe breaks, the character is badly hurt, the fight ends, or PLAN_ROUNDS rounds pass.
A plan with no attack or guard in it stops at once.

Foes fight for what they want (requirements "Who decides enemy actions"): robbers who have hurt the character demand
their purse, and a line that hands it over (or yields) ends the fight with the purse gone; captors fight to take the
character whole, so their blows stop at Maimed and a surrender makes the character their prisoner; a brawler lets a
character who backs off or yields go; killers give no quarter.

Gear wears: an attack that fails critically damages the weapon swung (dungeon/inventory.py wear), and a damaged weapon
hits a step softer. A fight won leaves its fallen foes' bodies where it was fought, with what they carried (coins, their
weapon) for the character to search (dungeon/finds.py spoils); a beast carries nothing.

Each round is decided once, kept with the player's line (story_rounds), and retold the same way. The fight and the
character's wounds are game state, branched with the story (dungeon/timeline.py SAVED).
"""
import json
import random
import re

from dungeon import (
    allies,
    battlemap,
    combat5e,
    combat_brp,
    combat_fate,
    combat_iron,
    inventory,
    ranges,
    record,
    referee,
    sheet,
    timeline,
)
from dungeon import table as campaign_table
from dungeon.database import encode, identifier, optional
from dungeon.rules import ladder, marvel, narrative

LEVELS = ('unhurt', 'grazed', 'hurt', 'wounded', 'maimed', 'dying')
DOWN, DYING = 4, 5
# The wound level at which robbers stop to demand the purse (Hurt).
DEMAND = 2
# Nights of rest that mend each level by one: Grazed, Hurt, Wounded, Maimed.
MEND_NIGHTS = {1: 1, 2: 2, 3: 4, 4: 7}
DAMAGE = {'success_cost': 1, 'success': 2, 'critical_success': 3}
WEAPONS = {'sword': 1, 'felling-axe': 1, 'hatchet': 0, 'knife': 0, 'cudgel': 0, 'crowbar': 0}
BARE_HANDS = -1
ATTACK = re.compile(r'\b(attack|hit|punch|strike|fight|swing|stab|slash|shoot|kick|tackle|wrestle|club|cut|kill|hack|'
                    r'lunge|thrust|smash|bash|bite|headbutt|throttle|strangle|charg|rush|ram|barrel|go(?:es)? for|sword|axe|knife|'
                    r'blade)\w*',
                    re.I)
# A line that takes up a weapon (dungeon/combat.py hands).
ARMED = re.compile(r'\b(sword|blade|axe|hatchet|knife|dagger|cudgel|club|crowbar|mace|spear|bow|staff|hammer|sling|'
                   r'weapon|draws?|stab|slash|shoot)\w*', re.I)
# Who an attack is aimed at when it names nobody in the scene: someone the narrator brought in ("punch him", "the big
# logger"). An attack on a thing ("hack at the roots") names neither.
# A friendly contest of strength or speed, not a fight: it never starts one.
CONTEST = re.compile(r"\b(arm[- ]?wrestl\w*|thumb[- ]?wrestl\w*|race|races|racing|footrace|contest|tug[- ]of[- ]war|"
                     r"wager\w*|bet|bets|betting|spar|spars|sparring|for (a|the) (round|drinks?|pints?|bet|prize|coin)|"
                     r"drinking (game|match)|test of strength|out-?(lift|run|drink)\w*)\b", re.I)
SOMEONE = re.compile(r'\b(him|her|them|man|woman|men|women|fellow|lad|boy|girl|stranger|drunk|thug|brute|logger|'
                     r'cutter|guard|bandit|thief|sailor|soldier|bully|foreman|sawyer|teamster|bargeman|smith|keeper|'
                     r'barkeep|clerk|watchman|warden|sergeant|cook|worker|labou?rer|merchant|trader|priest|elf|dwarf|'
                     r'orc|goblin|brigand|cultist|stranger)\b', re.I)
OPPONENT = 'their opponent'
SNEAK = re.compile(r"\b(sneak\w*|snuck|creep\w*|crept|from behind|unseen|unawares|ambush\w*|by surprise|quietly|"
                   r"silently|stealthily|stalk\w*|in (his|her|their) sleep|while (he|she|they)('s|'re| is| are) "
                   r"(asleep|sleeping|unaware|distracted|not looking))\b", re.I)
YIELD = re.compile(r"\b(surrender\w*|yield\w*|give up|gives? in|beg\w* for (mercy|my life)|hands up|"
                   r"drop\w* my (weapon|sword|axe|knife|blade)|back\w* off|walk\w* away|leave (them|him|her) be)\b", re.I)
HAND_OVER = re.compile(r"\b(hand\w* (it |them |him |her )?over|give (it|them|him|her)|throw (it|them|him|her)|toss\w* "
                       r"(it|them|him|her)|pay (them|him|her)( off)?)\b.*\b(purse|money|coins?|silver|crowns?|it|them)\b",
                       re.I)
PLAN = re.compile(r"\b(on my plan|fight it out|fight on|keep fighting|fight until|until (they|he|she|it)('s| is| are)? "
                  r"(down|done|beaten|dead|yields?|gives? up|flees?|runs?|breaks?))\b", re.I)
PLAN_ROUNDS = 5
GUARD = re.compile(r'\b(dodge|block|parry|defend|duck|guard)\w*', re.I)
FREE = re.compile(r'\b(free|untie|slip (?:the|my|out)|loosen|pick the lock|break (?:the|my) (?:bonds|ropes|chains)|'
                  r'cut (?:the|my) (?:bonds|ropes)|bribe|break out)\w*', re.I)
FLEE = re.compile(r'\b(flee|run away|run for|escape|retreat|bolt|get away)\w*', re.I)
SUCCESS = ('success_cost', 'success', 'critical_success')
HARDER = {'easy': 'normal', 'normal': 'hard', 'hard': 'very_hard', 'very_hard': 'extreme', 'extreme': 'extreme'}
PHYSICAL = ('Vitality',)
# What the winners do with a character they beat, by what they want: (outcome, weight).
DEFEAT = {
    'kill': (('death', 7), ('robbed', 1), ('rescued', 2)),
    'capture': (('captured', 7), ('death', 1), ('rescued', 2)),
    'rob': (('robbed', 7), ('death', 2), ('rescued', 1)),
    'drive_off': (('thrown_out', 8), ('rescued', 2)),
}
# The foes whose blows can leave a lasting injury (maimed_by).
MAIMING = ('kill', 'rob')
DEFEAT_TEXT = {
    'death': 'The player\'s character dies here.',
    'robbed': 'They take the character\'s purse and leave them for dead.',
    'captured': 'They take the character prisoner, bound and helpless.',
    'rescued': 'Someone drives the attackers off and drags the character clear, barely alive.',
    'thrown_out': 'They beat the character senseless and throw them out.',
}


# The character's condition -----------------------------------------------------------------------

def condition(connection) -> dict:
    row = optional(connection, 'SELECT level, dead, rested FROM story_wounds WHERE id=1')
    return ({'level': row['level'], 'dead': bool(row['dead']), 'rested': row['rested']} if row
            else {'level': 0, 'dead': False, 'rested': 0})


def set_condition(connection, level: int, dead: bool = False, rested: int = 0):
    """The character's wound level; the nights rested toward mending it start again whenever it changes, and a new
    wound can be treated again (dungeon/injuries.py)."""
    connection.execute('INSERT INTO story_wounds (id, level, dead, rested) VALUES (1, ?, ?, ?) ON CONFLICT(id) DO '
                       'UPDATE SET rested=CASE WHEN level=excluded.level THEN rested ELSE excluded.rested END, '
                       'treated=CASE WHEN excluded.level > level THEN 0 ELSE treated END, '
                       'level=excluded.level, dead=excluded.dead', (max(0, min(DYING, level)), int(dead), rested))
    # Under 5E the hit points follow a wound dealt outside a fight (a Life Card, a fall).
    combat5e.follow_level(connection, max(0, min(DYING, level)))
    combat_iron.follow_level(connection, max(0, min(DYING, level)))
    combat_brp.follow_level(connection, max(0, min(DYING, level)))
    combat_fate.follow_level(connection, max(0, min(DYING, level)))


def word(connection, level: int) -> str:
    """The character's condition in words: Prospero's wound levels, or under 5E what the hit points read as."""
    return (combat5e.WORDS if fifth(connection) or basic(connection) else combat_iron.WORDS if sworn(connection)
            else LEVELS)[level]


def sworn(connection) -> bool:
    """Whether the fight runs on Ironsworn's health and harm (dungeon/combat_iron.py)."""
    return combat_iron.health(connection) is not None


def basic(connection) -> bool:
    """Whether the fight runs on BRP's hit points and skills (dungeon/combat_brp.py)."""
    return combat_brp.hit_points(connection) is not None


def points_of(connection) -> tuple[int, int] | None:
    """The character's hit points, under a ruleset that keeps them."""
    return combat5e.hit_points(connection) or combat_brp.hit_points(connection)


def fated(connection) -> bool:
    """Whether a blow on the character is Fate's stress and consequences (dungeon/combat_fate.py)."""
    return combat_fate.played(connection) is not None


def fifth(connection) -> bool:
    """Whether the fight runs on 5E's hit points (dungeon/combat5e.py)."""
    return combat5e.hit_points(connection) is not None


def mend(connection, nights: int) -> list[str]:
    """Nights of good rest count toward the wound's mending: each level takes its own (MEND_NIGHTS)."""
    now = condition(connection)
    if fifth(connection) and not now['dead'] and now['level'] < DYING:
        # 5E heals as written: a long rest restores every hit point and spell slot.
        lines = combat5e.long_rest(connection, nights)
        if lines and now['level']:
            connection.execute('UPDATE story_wounds SET level=0, rested=0 WHERE id=1')
        return lines
    if basic(connection) and not now['dead'] and now['level'] < DYING:
        # BRP heals slowly, as written (dungeon/combat_brp.py rest).
        lines = combat_brp.rest(connection, nights)
        hp, most = combat_brp.hit_points(connection)
        connection.execute('UPDATE story_wounds SET level=? WHERE id=1', (combat5e.level_for(hp, most),))
        return lines
    if sworn(connection) and not now['dead'] and now['level'] < DYING:
        # Ironsworn: Make Camp, +1 health a night.
        lines = combat_iron.rest(connection, nights)
        connection.execute('UPDATE story_wounds SET level=? WHERE id=1', (combat_iron.level_for(combat_iron.health(connection)),))
        return lines
    if fated(connection) and not now['dead'] and now['level'] < DYING:
        # Fate: a night's sleep refreshes Fate points and clears stress; consequences heal with nights of rest.
        lines = sheet.refresh_fate(connection, nights) + combat_fate.rest(connection, nights)
        connection.execute('UPDATE story_wounds SET level=?, rested=0 WHERE id=1',
                           (combat_fate.level_for(combat_fate.played(connection)),))
        return lines
    return mend_wounds(connection, nights, now)


def mend_wounds(connection, nights: int, now: dict) -> list[str]:
    """The shared wound levels mending with rest (Prospero and Narrative)."""
    if nights <= 0 or now['dead'] or not 0 < now['level'] < DYING:
        return []
    level, rested = now['level'], now['rested'] + nights
    while 0 < level < DYING and rested >= MEND_NIGHTS[level]:
        rested -= MEND_NIGHTS[level]
        level -= 1
    rested = rested if level else 0
    connection.execute('UPDATE story_wounds SET level=?, rested=? WHERE id=1', (level, rested))
    if level < now['level']:
        return [f"Rest mends the character's wounds: from {LEVELS[now['level']]} to {LEVELS[level]}."]
    left = MEND_NIGHTS[level] - rested
    return [f"The character is still {LEVELS[level]}: {left} more night{'s' if left > 1 else ''} of rest to mend."]


def adjust(connection, actions: list[dict]) -> list[dict]:
    """Wounds make actions harder: Wounded slows physical ones, Maimed everything and physical ones twice."""
    level = condition(connection)['level']
    if fifth(connection) or sworn(connection) or basic(connection) or fated(connection):
        # 5E, Ironsworn, BRP and Fate have no wound penalties: hit points, health and consequences are whole (or
        # aspects for the narrator) until they run out.
        return actions
    adjusted = []
    for action in actions:
        steps = (1 if level >= 3 and action['stat'] in PHYSICAL else 0) + (1 if level >= DOWN else 0)
        difficulty = action['difficulty']
        for _ in range(steps):
            difficulty = HARDER[difficulty]
        adjusted.append(action | {'difficulty': difficulty})
    return adjusted


def captors(connection) -> str | None:
    """Who holds the character prisoner, if anyone."""
    row = optional(connection, 'SELECT captors FROM story_wounds WHERE id=1')
    return row['captors'] if row else None


def escape(connection, rolls: list[dict]) -> list[str]:
    """A prisoner's line that tries to get free: free on a success, still held on a failure."""
    held = captors(connection)
    tries = [roll for roll in rolls if FREE.search(roll['action']) or FLEE.search(roll['action'])] if held else []
    if not tries:
        return []
    if any(roll['band'] in SUCCESS for roll in tries):
        connection.execute('UPDATE story_wounds SET captors=NULL WHERE id=1')
        return [f"The player's character gets free of {held}."]
    return [f"The player's character tries to get free of {held} and cannot; they are still held."]


def condition_text(connection) -> str:
    now = condition(connection)
    if now['dead']:
        return "The player's character is dead."
    held = captors(connection)
    prisoner = f"The player's character is a prisoner of {held}, bound and watched; they go nowhere until they get " \
               "free (kept by the game)." if held else ''
    if not now['level']:
        return prisoner
    points = points_of(connection)
    hp = f", {max(0, points[0])} of {points[1]} hit points" if points else ''
    if (left := combat_iron.health(connection)) is not None:
        hp = f', health {left} of 5'
    return (f"The player's character is {word(connection, now['level'])}{hp} (kept by the game; write the wounds as they "
            "are)." + (f' {prisoner}' if prisoner else ''))


# The fight ---------------------------------------------------------------------------------------

def fight(connection) -> dict | None:
    row = optional(connection, 'SELECT * FROM story_fight WHERE id=1')
    return row | {'foes': json.loads(row['foes'])} if row else None


def walk_away(connection, now: str):
    """The character walks out of the fight, as the Table lets them (dungeon/leaving.py 'nobody'): it is over, the
    foes left where they stand."""
    state = fight(connection)
    if state is None:
        return
    allies.aftermath(connection, state, now)
    who = ', '.join(foe['name'] for foe in standing(state)) or 'the fight'
    record.add(connection, 'fact', "the player's character", f'Walked away from a fight with {who}.', now)
    save_fight(connection, None)


def save_fight(connection, state: dict | None):
    if state is None:
        connection.execute('DELETE FROM story_fight')
        return
    # Whether the fight is bare-handed (hands) is kept with it, so "I hit him again" next line stays a punch.
    connection.execute('INSERT INTO story_fight (id, round, wants, foes, initiative, bare, area) '
                       'VALUES (1, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET round=excluded.round, '
                       'wants=excluded.wants, foes=excluded.foes, initiative=excluded.initiative, bare=excluded.bare, '
                       'area=excluded.area',
                       (state['round'], state['wants'], json.dumps(state['foes']), state.get('initiative'),
                        int(bool(state.get('bare'))), state.get('area')))


def foes_from(spec: dict, zone: str = 'near') -> list[dict]:
    count = spec.get('count', 1)
    return [{'id': f"{spec['name']}-{n}", 'name': spec['name'] if count == 1 else f"{spec['name']} {n + 1}",
             'vitality': spec.get('vitality', 10), 'resolve': spec.get('resolve', 10), 'weapon': spec.get('weapon', 0),
             'wound': 0, 'zone': zone, 'broken': False} | ({'horror': True} if spec.get('horror') else {})
            | {key: spec[key] for key in ('beast', 'carries') if key in spec}
            for n in range(count)]


def stand_in(rolls: list[dict]) -> dict | None:
    """A foe for an attack on someone the scene does not hold (the narrator's own extra), named as the action names
    them ("the big logger"), else 'their opponent'."""
    for roll in rolls:
        if roll['stat'] == 'Vitality' and fighting_words(roll['action']) and (who := SOMEONE.search(roll['action'])):
            named = re.search(rf'\b(?:the|that|this)\s+((?:[a-z-]+\s+){{0,2}}?{who.group(1)})\b', roll['action'], re.I)
            return {'name': f'the {named.group(1).lower()}' if named else OPPONENT, 'vitality': 10, 'resolve': 10,
                    'weapon': 0, 'wants': 'drive_off'}
    return None


def person_foe(person: dict) -> dict:
    sheet = person['sheet']
    return {'name': sheet['full'] or f"the {sheet.get('occupation') or sheet['role']}", 'vitality': 10, 'resolve': 10, 'weapon': 0, 'wants': 'drive_off'}


def aimed(person: dict, action: str) -> bool:
    sheet = person['sheet']
    names = {sheet['full'], sheet.get('name') or '', sheet.get('role') or '', sheet.get('occupation') or ''}
    return any(name and len(name) > 2 and re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', action, re.I)
               for name in names)


def fighting_words(action: str) -> bool:
    """Whether an action outside a fight attacks someone: a blow, not a friendly contest (an arm-wrestle, a race)."""
    return bool(ATTACK.search(action)) and not CONTEST.search(action)


def attack_on(people: list[dict], rolls: list[dict]) -> dict | None:
    """The person in the scene the player's attack is aimed at, if any."""
    for roll in rolls:
        if roll['stat'] == 'Vitality' and fighting_words(roll['action']):
            if person := next((person for person in people if aimed(person, roll['action'])), None):
                return person
    return None


def weapon_bonus(items: list[dict]) -> int:
    """The best weapon carried: a damaged one a step softer, a broken one no weapon at all."""
    held = [WEAPONS[row['item_id']] - (row.get('condition') == 'damaged') for row in items
            if row['item_id'] in WEAPONS and row.get('condition') != 'broken']
    return max(held) if held else BARE_HANDS


def swung(items: list[dict], action: str) -> dict | None:
    """The weapon an attack swings: the one the line names, else the best carried."""
    held = [row for row in items if row['item_id'] in WEAPONS and row.get('condition') != 'broken']
    named = [row for row in held if any(re.search(rf'\b{re.escape(noun)}\b', action, re.I)
                                        for noun in inventory.nouns(row))]
    return max(named or held, key=lambda row: (WEAPONS[row['item_id']], row.get('condition') == 'sound'), default=None)


def worn(connection, rolls: list[dict], state: dict, items: list[dict]) -> list[str]:
    """An attack that fails critically damages the weapon swung, one step: sound to damaged, damaged to broken."""
    if state.get('bare'):
        return []
    for roll in rolls:
        if roll['band'] == 'critical_failure' and roll['stat'] == 'Vitality' and attacks(roll['action']) and \
                (row := swung(items, roll['action'])) and (after := inventory.wear(connection, row['id'])):
            return [f"The player's character's {row['name'].lower()} is {after} by the botched blow."]
    return []


def down(foe: dict) -> bool:
    """A Prospero foe is down at Maimed; a 5E foe at 0 hit points."""
    if 'npc' in foe:
        return foe['out']
    return foe['hp'] <= 0 if 'hp' in foe else foe['wound'] >= DOWN


def standing(state: dict) -> list[dict]:
    return [foe for foe in state['foes'] if not down(foe) and not foe['broken']]


def foe_word(foe: dict) -> str:
    if 'hp' in foe:
        return combat5e.describe(foe) if foe['hp'] > 0 else 'down'
    if 'npc' in foe:
        return combat_iron.describe(foe)
    if down(foe):
        return 'down'
    if foe['broken']:
        return 'broken, fleeing or giving up'
    return LEVELS[foe['wound']] if foe['wound'] else 'unhurt'


def player_moves(connection, state: dict, rolls: list[dict], items: list[dict], rng,
                 lines: list[str]) -> tuple[bool, bool]:
    """The player's rolled actions against the foes: (got away, guarded this round). Under 5E a dodge needs no roll
    and an attack is made against the target's AC. A roll that changes nothing in the fight (other than a guard)
    still gets its line."""
    guarded = False
    for roll in rolls:
        before = len(lines)
        escaped, guarding = player_move(connection, state, roll, items, rng, lines)
        if escaped:
            return True, guarded
        guarded = guarded or guarding
        if len(lines) == before and not GUARD.search(roll['action']):
            lines.append(f"The player's character tries this ({roll['action']}): "
                         + ('it works, but strikes no foe.' if roll['band'] in SUCCESS else 'it fails.'))
    return False, guarded


def player_move(connection, state: dict, roll: dict, items: list[dict], rng, lines: list[str]) -> tuple[bool, bool]:
    """One rolled action in the fight: (got away, guards this round)."""
    landed, five, percent = roll['band'] in SUCCESS, fifth(connection), basic(connection)
    if five and (spell := combat5e.spell_in(connection, roll)):
        combat5e.cast(connection, roll, spell, standing(state), rng, lines)
        return False, False
    if percent and (cast := combat_brp.spell_in(connection, roll)):
        combat_brp.cast(connection, state, roll, cast, standing(state), rng, lines)
        return False, False
    if ranges.backing(roll['action']):
        # "I fall back to the stairs": a move within the fight, not an escape (dungeon/ranges.py).
        ranges.break_away(state, roll['action'], landed, lines)
    elif FLEE.search(roll['action']):
        # The Table may let the character walk out of any fight (dungeon/leaving.py).
        if landed or campaign_table.rule(connection, 'leaving') == 'nobody':
            lines.append("The player's character gets away.")
            return True, False
        lines.append("The player's character tries to get away and cannot.")
        return False, False
    # Under 5E a dodge needs no roll; under BRP a line that defends dodges every attack this round.
    guarding = bool(GUARD.search(roll['action'])) and (landed or five or percent)
    # "I dodge his swing and cut at him" defends and attacks.
    if roll['stat'] == 'Vitality' and attacks(roll['action']) and (targets := standing(state)):
        attack(connection, state, roll, targets, hands(state, roll['action'], items), rng, lines)
    return False, guarding and not ranges.backing(roll['action'])


def attacks(action: str) -> bool:
    """Whether a line attacks: a blow in a part of it that is not a defence ("I dodge his swing" only defends)."""
    return any(not GUARD.search(part) and (ATTACK.search(part) or referee.PRESSING.search(part))
               for part in re.split(r',|;|\band\b|\bthen\b', action))


def attack(connection, state: dict, roll: dict, targets: list[dict], items: list[dict], rng, lines: list[str]):
    """The character's attack in the campaign's ruleset, if it reaches (dungeon/ranges.py): a shot leaves its target
    where it stands."""
    target = aimed_at(roll, targets)
    zone = target.get('zone', 'engaged')
    if not ranges.reach(target, roll['action'], lines):
        return
    struck(connection, state, roll, targets, items, rng, lines)
    if ranges.ranged(roll['action']):
        target['zone'] = zone


def struck(connection, state: dict, roll: dict, targets: list[dict], items: list[dict], rng, lines: list[str]):
    if fifth(connection):
        combat5e.strike(connection, roll, aimed_at(roll, targets), items, rng, lines)
    elif basic(connection):
        combat_brp.strike(connection, roll, aimed_at(roll, targets), items, rng, lines, state)
    elif 'npc' in targets[0]:
        combat_iron.strike(connection, state, roll, aimed_at(roll, targets), items, rng, lines)
    else:
        strike(roll, targets, items, lines)


def hands(state: dict, action: str, items: list[dict]) -> list[dict]:
    """What the character fights with: a fight begun bare-handed ("I punch him") stays bare-handed ("I hit him
    again") until a line names a weapon."""
    if combat5e.BARE.search(action):
        state['bare'] = True
    elif ARMED.search(action):
        state['bare'] = False
    return [] if state.get('bare') else items


def fighting_whom(connection) -> str | None:
    """Who the character is fighting, with how each stands, for the Referee ("the thug (badly hurt)"); None when no
    fight is on."""
    state = fight(connection)
    targets = standing(state) if state else []
    return ', '.join(f"{foe['name']} ({foe_word(foe)})" for foe in targets) or None


def aimed_at(roll: dict, targets: list[dict]) -> dict:
    return next((foe for foe in targets if foe['name'].lower() in roll['action'].lower()), targets[0])


def strike(roll: dict, targets: list[dict], items: list[dict], lines: list[str]):
    target = aimed_at(roll, targets)
    target['zone'] = 'engaged'
    if roll['band'] in SUCCESS:
        target['wound'] = min(DYING, target['wound'] + max(1, DAMAGE[roll['band']] + weapon_bonus(items)))
        lines.append(f"The player's character hits {target['name']}: now {foe_word(target)}.")
    else:
        lines.append(f"The player's character's attack on {target['name']} misses.")


def morale(state: dict, rng, lines: list[str]):
    """When a foe is badly hurt or down, the rest roll Resolve; a failure breaks them."""
    if not any(foe['wound'] >= 3 for foe in state['foes']):
        return
    for foe in standing(state):
        if marvel.roll(foe['resolve'], 'normal', rng)['band'] not in SUCCESS:
            foe['broken'] = True
            lines.append(f"{foe['name'].capitalize()} breaks: they flee or give up.")


def blow(band: str, weapon: int) -> int:
    """Wound levels a foe's hit deals: by how well it landed and the weapon, at least one; bare hands or a poor
    weapon (0 or less) at most two, however well it lands."""
    dealt = max(1, DAMAGE[band] + weapon)
    return min(2, dealt) if weapon <= 0 else dealt


def foes_move(connection, state: dict, guarded: bool, rng, lines: list[str], free=None) -> int:
    """Each foe still standing (and not busy with an ally, `free`) closes in or attacks; returns the character's
    wound level after."""
    level = condition(connection)['level']
    # Captors want the character whole: their blows stop at Maimed. Nor does one round take a character on their
    # feet past Maimed: they go down first.
    worst = DOWN if state['wants'] == 'capture' or level < DOWN else DYING
    for foe in (free or standing)(state):
        if ranges.close(foe, lines):
            continue
        # Guarding makes a blow a step harder; so does a shot from far off.
        steps = int(guarded) + int(foe.get('zone') == 'far')
        band = marvel.roll(foe['vitality'], ('normal', 'hard', 'very_hard')[steps], rng)['band']
        if band in SUCCESS:
            before, level = level, min(worst, level + blow(band, foe['weapon']))
            # A maiming, or a critical hit that leaves the character Wounded or worse, can leave a lasting injury
            # (dungeon/injuries.py): a Hurt blow never maims.
            if before < DOWN <= level or (band == 'critical_success' and level >= DOWN - 1):
                state['hurt_by'] = foe['name']
            lines.append(f"{foe['name'].capitalize()} hits the player's character: now {LEVELS[level]}.")
        else:
            lines.append(f"{foe['name'].capitalize()} attacks and misses.")
    set_condition(connection, level)
    return level


def play_round(connection, state: dict, rolls: list[dict], items: list[dict], rng) -> tuple[dict, list[str], str]:
    """One round: the player's actions, then morale, then each foe. Returns the fight after it, what happened, and how
    it ended: '' while it goes on, else 'escaped', 'won' or 'dying'."""
    rng = rng or random.SystemRandom()
    lines, state = [], state | {'round': state['round'] + 1}
    caught = state['round'] == 1 and state.get('surprised')
    if caught == 'player':
        escaped, guarded = False, False
        lines.append("Taken unawares, the player's character can do nothing this round.")
    else:
        escaped, guarded = player_moves(connection, state, rolls, items, rng, lines)
    if escaped:
        return state, lines, 'escaped'
    # The character's companions fight beside them, on their own (dungeon/allies.py).
    allies.join(connection, state)
    if caught != 'player':
        allies.strike(state, standing, down, rng, lines)
    morale_rolls(connection, state, rng, lines)
    if not standing(state):
        lines.append('No foe is left standing: the fight is won.')
        return state, lines, 'won'
    if caught == 'foes':
        lines.append('Taken unawares, the foes do nothing this round.')
        return state, lines, ''
    hurt = condition(connection)['level']
    level = foes_strike(connection, state, guarded, rng, lines)
    if state['wants'] == 'rob' and hurt < DEMAND <= level < DYING:
        lines.append(f"{standing(state)[0]['name'].capitalize()} demands the character's purse: hand it over and the "
                     'robbers go.')
    beaten = level >= DOWN and state['wants'] == 'capture' and not (fifth(connection) or sworn(connection)
                                                                     or basic(connection) or fated(connection))
    return state, lines, 'dying' if level >= DYING or beaten else ''


def morale_rolls(connection, state: dict, rng, lines: list[str]):
    """The foes' morale, by the campaign's ruleset (Ironsworn foes have none)."""
    if fifth(connection):
        combat5e.morale(state, standing, rng, lines)
    elif basic(connection):
        combat_brp.morale(state, standing, rng, lines)
    elif not sworn(connection):
        morale(state, rng, lines)


def foes_strike(connection, state: dict, guarded: bool, rng, lines: list[str]) -> int:
    """The foes' turn: those that turn on an ally fight them (dungeon/allies.py), the rest the character. Returns the
    character's wound level after."""
    busy = allies.draw_fire(state, standing, rng, lines)

    def free(fight_state: dict) -> list[dict]:
        return [foe for foe in standing(fight_state) if foe['id'] not in busy]

    five, iron, percent, fates = fifth(connection), sworn(connection), basic(connection), fated(connection)
    if not (five or iron or percent or fates):
        return foes_move(connection, state, guarded, rng, lines, free)
    module = combat5e if five else combat_brp if percent else combat_iron if iron else combat_fate
    level = module.foes_attack(connection, state, free, guarded, rng, lines)
    set_condition(connection, level)
    return level


def defeat(connection, state: dict, rng, now: str, saved: bool | None = None) -> tuple[str, str]:
    """The character went down: cling on with Vitality, then what the winners do with them. Under 5E the death saves
    already decided (`saved`): three failures is death, stable is the table without it."""
    rng = rng or random.SystemRandom()
    if saved is False:
        outcome = 'death'
    else:
        clung = saved or (deadly(state) and sheet.check(connection, 'Vitality', 'hard', rng=rng, save=True)['band']
                          in SUCCESS)
        table = [(outcome, weight) for outcome, weight in DEFEAT[state['wants']] if not (clung and outcome == 'death')]
        pick = rng.randint(1, sum(weight for _, weight in table))
        outcome = next(name for name, weight in _running(table) if pick <= weight)
    winners = state['foes'][0]['name']
    if outcome == 'death':
        set_condition(connection, DYING, dead=True)
        record.add(connection, 'death', "the player's character", f'Killed by {winners}.', now)
    else:
        set_condition(connection, DOWN)
        if fifth(connection):
            combat5e.set_hp(connection, 1, now)
        if basic(connection):
            combat_brp.set_hp(connection, 1)
        if outcome == 'robbed':
            connection.execute('UPDATE story_purse SET coins=0')
        if outcome == 'captured':
            connection.execute('UPDATE story_wounds SET captors=? WHERE id=1', (winners,))
        record.add(connection, 'fact', "the player's character", f'Beaten by {winners}. {DEFEAT_TEXT[outcome]}', now)
    return outcome, DEFEAT_TEXT[outcome]


def maimed_by(state: dict) -> str | None:
    """Who left the character a lasting injury this round. A brawl to drive them off leaves bruises, not a lost eye,
    and captors want their prisoner whole: only foes who fight to kill or rob can maim."""
    cause = state.pop('hurt_by', None)
    return cause if cause and state['wants'] in MAIMING else None


def deadly(state: dict) -> bool:
    """Whether the foes would kill: a brawl to drive someone off ends in a beating, never a death."""
    return any(outcome == 'death' for outcome, _ in DEFEAT[state['wants']])


def _running(table):
    total = 0
    for name, weight in table:
        total += weight
        yield name, total


# A round, kept with the player's line ------------------------------------------------------------

def saved_round(connection, message_id: str) -> list[str] | None:
    row = optional(connection, 'SELECT lines FROM story_rounds WHERE message_id=?', (message_id,))
    return json.loads(row['lines']) if row else None


def turn(connection, message_id: str, people: list[dict], rolls: list[dict], start: dict | None, items: list[dict],
         rng, now: str, aftermath=None, spoils=None, said: str = '') -> list[str]:
    """The fight's part of a turn, decided once: start a fight if one begins, play the round, and keep the lines.
    `aftermath(events)` deals with what the round did to the character, [(event, who)]: 'horror' when a fight with
    something dreadful starts, 'kill' when the character kills, 'fled' when a foe gets away from a fight the character
    won, 'maimed' when a hit calls for a lasting injury, and
    the defeat table's outcome; it says what that left (dungeon/stress.py). `spoils(foes, wants)` leaves the bodies of a
    fight won, with what they carried (dungeon/finds.py). `said` is the line itself: it can yield or pay the foes off
    (terms), or set a plan that plays on past this round to a turning point."""
    if (kept := saved_round(connection, message_id)) is not None:
        return kept
    rng = rng or random.SystemRandom()
    freed = escape(connection, rolls) if fight(connection) is None else []
    state = fight(connection) or begin(connection, people, rolls, start, rng, message_id)
    if state is None:
        if freed:
            connection.execute('INSERT INTO story_rounds (message_id, lines) VALUES (?, ?)', (message_id, encode(freed)))
        return freed
    before = {foe['id']: foe['wound'] for foe in state['foes']}
    events = [('horror', foe['name']) for foe in state['foes'][:1] if foe.get('horror') and not state['round']]
    settled, over = terms(connection, state, said, now)
    if over:
        return keep(connection, message_id, freed + settled, None)
    freed += settled
    marked = mark(connection, state)
    state, lines, ending = play_round(connection, state, rolls, items, rng)
    lines = freed + lines + worn(connection, rolls, state, items)
    plan = said if PLAN.search(said) else ''
    state, ending = fight_on(connection, message_id, state, plan, items, rng, now, (marked, ending), lines)
    events += [('kill', foe['name']) for foe in state['foes'] if foe['wound'] >= DYING > before[foe['id']]]
    # A foe who broke and got away alive (the story director may make a nemesis of them).
    events += [('fled', foe['name']) for foe in state['foes'] if ending == 'won' and foe['broken'] and not down(foe)]
    ending = settle(connection, message_id, state, ending, lines, events, spoils, rng, now)
    if aftermath and events and not condition(connection)['dead']:
        lines += aftermath(events)
    return keep(connection, message_id, lines, None if ending else state)


def settle(connection, message_id: str, state: dict, ending: str, lines: list[str], events: list, spoils, rng,
           now: str) -> str:
    """How the round ended, dealt with: a fall to the defeat table, a fight won's experience and its fallen, a lasting
    injury, and the fight's own roll cards. Returns the ending after a fall."""
    if ending == 'dying':
        ending = fall(connection, state, rng, now, lines, events)
    if ending == 'won' and fifth(connection):
        lines += combat5e.gain(connection, combat5e.fight_xp(state), 'the fight won', now)
    if ending == 'won' and spoils:
        lines += spoils([foe for foe in state['foes'] if down(foe)], state.get('wants', ''))
    if cause := maimed_by(state):
        events.append(('maimed', cause))
    if ending:
        allies.aftermath(connection, state, now)
    for card in state.pop('cards', []):
        card_for(connection, message_id, card, now)
    return ending


def keep(connection, message_id: str, lines: list[str], state: dict | None) -> list[str]:
    """The fight as the round left it (None when it is over), and the round's lines kept with the player's line."""
    save_fight(connection, state)
    connection.execute('INSERT INTO story_rounds (message_id, lines) VALUES (?, ?)', (message_id, encode(lines)))
    return lines


def terms(connection, state: dict, said: str, now: str) -> tuple[list[str], bool]:
    """A line that yields or pays the foes off, met by what they want: robbers take the purse and go, captors take a
    prisoner, a brawl lets the character go; killers give no quarter. Returns what happened and whether the fight is
    over."""
    wants, paying = state['wants'], bool(HAND_OVER.search(said))
    if not said or not (YIELD.search(said) or paying) or not standing(state):
        return [], False
    who = standing(state)[0]['name']
    if wants == 'rob':
        connection.execute('UPDATE story_purse SET coins=0')
        record.add(connection, 'fact', "the player's character", f'Handed their purse over to {who}.', now)
        return [f"The player's character hands over their purse; {who} takes it, and the robbers go. The fight is "
                'over.'], True
    if wants == 'capture':
        set_condition(connection, condition(connection)['level'])
        connection.execute('UPDATE story_wounds SET captors=? WHERE id=1', (who,))
        record.add(connection, 'fact', "the player's character", f'Surrendered to {who} and was taken prisoner.', now)
        return [f"The player's character surrenders; {who} binds them and takes them prisoner. The fight is over."], True
    if wants == 'drive_off':
        return [f"The player's character backs down; {who} lets them go. The fight is over."], True
    return [f"The player's character tries to give in; {who} gives no quarter."], False


def mark(connection, state: dict) -> tuple[int, int, int]:
    """Where a fight stands, to tell a turning point: foes down, foes broken, and the character's wound level."""
    return (sum(down(foe) for foe in state['foes']), sum(bool(foe['broken']) for foe in state['foes']),
            condition(connection)['level'])


def turning(connection, state: dict, before: tuple[int, int, int], ending: str) -> str:
    """Why a fight on the player's plan stops here, if it does."""
    fallen, broken, level = mark(connection, state)
    reasons = ((ending, 'the fight is over'), (fallen > before[0], 'someone falls'), (broken > before[1], 'a foe breaks'),
               (level > before[2] and level >= DOWN - 1, "the player's character is badly hurt"))
    return next((reason for found, reason in reasons if found), '')


def fight_on(connection, message_id: str, state: dict, plan: str, items: list[dict], rng, now: str,
             after: tuple[tuple, str], lines: list[str]) -> tuple[dict, str]:
    """Fight on the player's plan: more rounds, a roll each, until a turning point (or PLAN_ROUNDS in all)."""
    before, ending = after
    if not plan:
        return state, ending
    why = turning(connection, state, before, ending)
    if not why and not (attacks(plan) or GUARD.search(plan)):
        why = 'the plan no longer makes sense'
    last = state['round'] + PLAN_ROUNDS - 1
    while not why and state['round'] < last:
        before = mark(connection, state)
        roll = planned(connection, message_id, plan, rng, now)
        state, more, ending = play_round(connection, state, [roll], items, rng)
        lines += [f"Round {state['round']}, fighting on the player's plan:", *more]
        why = turning(connection, state, before, ending)
    lines.append(f"The fight on the player's plan stops here: {why or 'enough rounds for one telling'}. The player "
                 'decides what next.')
    return state, ending


def planned(connection, message_id: str, plan: str, rng, now: str) -> dict:
    """A round's roll on the player's plan, as a roll card the fight can rewrite (an attack on AC, a skill)."""
    result = sheet.check(connection, 'Vitality', 'normal', plan, rng)
    roll = {'action': plan, 'stat': 'Vitality'} | {key: result.get(key) for key in (
        'band', 'natural', 'die', 'bonus', 'shift', 'total', 'target', 'skill')}
    roll['id'] = card_for(connection, message_id, {'action': plan, 'stat': 'Vitality', 'result': result}, now)
    return roll


def card_for(connection, message_id: str, card: dict, now: str) -> str | None:
    """A roll the fight itself made (surprise, Ironsworn's Endure Harm and Face Death), as a roll card after the line's
    own; returns its id. Narrative Only rolls nothing, so it shows no card."""
    result = card['result']
    if result.get('ruleset') == narrative.ID:
        return None
    found = identifier()
    position = optional(connection, 'SELECT COUNT(*) AS n FROM story_rolls WHERE message_id=?', (message_id,))['n']
    connection.execute(
        'INSERT INTO story_rolls (id, message_id, position, actor, action, said, stat, difficulty, die, natural, bonus, '
        'shift, total, band, threat, ruleset, target, skill, created_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, '
        '?, NULL, ?, ?, ?, ?)',
        (found, message_id, position, sheet.PERSONA, card['action'], card['stat'], card.get('difficulty', 'normal'),
         result['die'],
         result['natural'], result.get('bonus', 0), result.get('shift', 0), result['total'], result['band'],
         sheet.ruleset(connection), result.get('target'), result.get('skill'), now))
    return found


def just_ended(connection, message_id: str) -> bool:
    """Whether the player's line before this one ended a fight. The stand-in they beat, or who beat them, is gone, so
    "I hit him again" right after starts nothing new against a fresh one."""
    where, values = timeline.visible(connection)
    row = optional(connection, f"SELECT r.lines FROM story_messages m LEFT JOIN story_rounds r ON r.message_id=m.id "
                               f"WHERE {where} AND m.role='user' AND m.id<>? ORDER BY m.seq DESC LIMIT 1",
                   (*values, message_id))
    return bool(row and row['lines']) and fight(connection) is None


def begin(connection, people: list[dict], rolls: list[dict], start: dict | None, rng,
          message_id: str = '') -> dict | None:
    """A fight that starts this turn: on someone in the scene the player attacks, a danger's foe, or a stand-in (not
    on the line straight after a fight ended)."""
    target = attack_on(people, rolls)
    spec = person_foe(target) if target else start or (
        None if message_id and just_ended(connection, message_id) else stand_in(rolls))
    if spec is None:
        return None
    # A danger's foes come from where its spec puts them (archers far off), an attack begins at arm's length.
    zone = spec.get('zone', 'near') if spec is start else 'engaged'
    if fifth(connection):
        foes = combat5e.foes_from(spec, zone, rng)
    elif sworn(connection):
        foes = combat_iron.foes_from(spec, zone)
    elif basic(connection):
        foes = combat_brp.foes_from(spec, zone)
    else:
        foes = foes_from(spec, zone)
    for foe in foes if spec.get('ranged') else []:
        foe['ranged'] = True
    # Ironsworn: whoever starts it has the upper hand.
    state = {'round': 0, 'wants': spec.get('wants', 'kill'), 'foes': foes,
             'initiative': 'foe' if spec is start else 'player'}
    return surprise(connection, state, spec, rolls, spec is start, rng)


def surprise(connection, state: dict, spec: dict, rolls: list[dict], ambushed: bool, rng) -> dict:
    """Stealth against awareness as a fight begins: a danger's foe tries to ambush the character, and the character's
    attack by stealth tries to take the foe unawares. The loser loses the first round; both rolls are roll cards."""
    sneaking = not ambushed and any(SNEAK.search(roll['action']) for roll in rolls if attacks(roll['action']))
    if not (ambushed or sneaking):
        return state
    rank = ladder.BANDS.index
    if ambushed:
        noticed = sheet.check(connection, 'Mind', 'normal', 'notice an ambush', rng)
        hidden = marvel.roll(spec.get('vitality', 10), 'normal', rng)
        card = {'action': 'Spot the ambush', 'stat': 'Mind', 'result': noticed}
        caught = rank(hidden['band']) > rank(noticed['band'])
        if caught:
            for foe in state['foes']:
                foe['zone'] = foe['zone'] if foe.get('ranged') else 'engaged'
        return state | {'surprised': 'player' if caught else None, 'cards': [card]}
    crept = sheet.check(connection, 'Vitality', 'normal', 'sneak up unseen', rng)
    aware = marvel.roll(spec.get('resolve', 10), 'normal', rng)
    card = {'action': 'Sneak up unseen', 'stat': 'Vitality', 'result': crept}
    caught = rank(crept['band']) > rank(aware['band'])
    return state | {'surprised': 'foes' if caught else None, 'cards': [card],
                    'initiative': 'player' if caught else state['initiative']}


def fall(connection, state: dict, rng, now: str, lines: list[str], events: list) -> str:
    """The character dropped: under 5E the death saves first (a natural 20 is back up and fighting), then the defeat
    table. With the Table's defeat 'by_aim', only foes out to kill bring the death saves; for the rest the table decides. Returns how the fight stands: '' when it goes on, else 'dying'."""
    saved = None
    # Captors beat the character down at Maimed; they are not dying.
    fell = 'is beaten down' if condition(connection)['level'] < DYING else 'falls, dying'
    if fifth(connection) and (state['wants'] == 'kill' or campaign_table.rule(connection, 'defeat') == 'as_written'):
        saved, up, saves = combat5e.death_saves(rng)
        rolled = ', '.join(str(natural) for natural in saves)
        if up:
            set_condition(connection, combat5e.set_hp(connection, 1, now))
            lines.append(f"The player's character drops to 0 hit points, then rolls a natural 20 on a death save "
                         f"({rolled}) and is back on their feet with 1 hit point.")
            return ''
        lines.append(f"The player's character drops to 0 hit points. Death saves: {rolled}: "
                     f"{'stable' if saved else 'three failures'}.")
    elif basic(connection):
        # BRP: a collapse from a major wound is not death; a fatal wound leaves it to the defeat table.
        saved = True if state.pop('collapsed', False) and combat_brp.hit_points(connection)[0] > 0 else None
    elif sworn(connection) and deadly(state):
        saved, how = combat_iron.face_death(connection, state, rng)
        lines.append(f"The player's character is brought to the brink of death and faces it: {how or 'it takes them.'}")
    outcome, said = defeat(connection, state, rng, now, saved)
    lines.append(f"The player's character {fell}. {said}")
    events.append((outcome, state['foes'][0]['name']))
    return 'dying'


def prompt_text(lines: list[str], connection) -> str:
    if not lines:
        return ''
    state = fight(connection)
    foes = '; '.join(f"{foe['name']}: {foe_word(foe)}" for foe in state['foes']) if state else ''
    where = ranges.positions(state, standing(state)) if state else ''
    if state and (grid := battlemap.positions(connection, state, standing(state))):
        # Under 5E, the distances on the battle map (dungeon/battlemap.py).
        where = f'{where} {grid}'.strip()
    return ('## The fight (decided by the game; write this round exactly as it went, nothing more)\n'
            + '\n'.join(f'- {line}' for line in lines)
            + (f'\nStill fighting: {foes}.' if foes else '\nThe fight is over.') + (f'\n{where}' if where else ''))


def view(connection, shown: bool) -> dict:
    """The fight and the character's wounds for the screen: levels with the dice shown, words otherwise."""
    state, now = fight(connection), condition(connection)
    points = points_of(connection)
    return {'condition': word(connection, now['level']), 'dead': now['dead'], 'captors': captors(connection),
            'fight': state and {'round': state['round'], 'area': state.get('area'),
                                'foes': [{'name': foe['name'], 'state': foe_word(foe), 'zone': foe.get('zone'),
                                          'wound': foe['wound'] if shown else None}
                                         | ({'hp': foe['hp'], 'max_hp': foe['max_hp']} if shown and 'hp' in foe else {})
                                         for foe in state['foes']], 'allies': allies.view(state),
                                # Under 5E, the fight on a grid of five-foot squares (dungeon/battlemap.py).
                                'grid': battlemap.view(connection, state, standing, allies.view(state))}} \
        | ({'hp': max(0, points[0]), 'max_hp': points[1]} if points else {})
