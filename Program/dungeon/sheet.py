"""Character sheets: Prospero stats per actor (dungeon/rules/marvel.py). The player's character is 'persona'; an actor
with no stats rolls with no die.

The campaign's ruleset is chosen at its start and then locked (story_campaign.ruleset; docs/requirements.md
"Rulesets"). Under Prospero the persona's sheet is its six stats. Under another ruleset the persona has that ruleset's
own sheet (story_sheet, branched with the story), and `check` rolls the persona's checks its way: the Referee's
approach (a Prospero stat) and the action's words decide what the ruleset tests. Everyone else keeps Prospero stats.
"""
import random
import re

from dungeon.database import decode, encode, many, optional
from dungeon.errors import require
from dungeon.rules import brp, fate, ironsworn, marvel, narrative, srd52

CASTING = re.compile(r'\b(cast\w*|spell)\b', re.I)
RULESETS = {marvel.ID: marvel.NAME, srd52.ID: srd52.NAME, ironsworn.ID: ironsworn.NAME, brp.ID: brp.NAME,
            narrative.ID: narrative.NAME, fate.ID: fate.NAME}
WORLD_RULESETS: dict[str, str] = {}

PERSONA = 'persona'


def stats(connection, actor: str = PERSONA) -> dict[str, int]:
    """Every stat of an actor; the persona's unset ones are the default, anyone else's are left out."""
    rows = {row['stat']: row['value'] for row in many(connection, 'SELECT stat, value FROM character_stats '
                                                                  'WHERE actor=?', (actor,))}
    if actor == PERSONA:
        return {stat: rows.get(stat, marvel.DEFAULT_STAT) for stat in marvel.STATS}
    return rows


def set_stats(connection, values: dict[str, int], now: str, actor: str = PERSONA) -> dict[str, int]:
    low, high = marvel.STAT_RANGE
    for stat, value in values.items():
        require(stat in marvel.STATS, f'{stat} is not a Prospero stat.', 422)
        require(isinstance(value, int) and low <= value <= high, f'{stat} must be from {low} to {high}.', 422)
    connection.executemany(
        'INSERT INTO character_stats (actor, stat, value, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(actor, stat) '
        'DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
        [(actor, stat, value, now) for stat, value in values.items()])
    return stats(connection, actor)


def view(connection) -> dict:
    return {'stats': stats(connection), 'stat_names': list(marvel.STATS), 'range': list(marvel.STAT_RANGE),
            'dice': {stat: marvel.die_for(value) for stat, value in stats(connection).items()}}


# The campaign's ruleset ---------------------------------------------------------------------------

def ruleset(connection) -> str:
    row = optional(connection, 'SELECT ruleset FROM story_campaign WHERE id=1')
    return (row and row['ruleset']) or marvel.ID


def default_for(world: str | None) -> str:
    """The ruleset a world names for its campaigns (every built-in world plays Prospero for now)."""
    return WORLD_RULESETS.get(world or '', marvel.ID)


def set_ruleset(connection, ruleset_id: str):
    require(ruleset_id in RULESETS, 'That ruleset is not built in.', 422)
    connection.execute('INSERT INTO story_campaign (id, ruleset) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET '
                       'ruleset=excluded.ruleset', (ruleset_id,))


def native(connection) -> dict | None:
    """The persona's sheet under a ruleset other than Prospero."""
    row = optional(connection, 'SELECT data FROM story_sheet WHERE id=1')
    return decode(row['data']) if row else None


def set_native(connection, data: dict, now: str):
    connection.execute('INSERT INTO story_sheet (id, ruleset, data, updated_at) VALUES (1, ?, ?, ?) ON CONFLICT(id) '
                       'DO UPDATE SET ruleset=excluded.ruleset, data=excluded.data, updated_at=excluded.updated_at',
                       (ruleset(connection), encode(data), now))


def check(connection, approach: str, difficulty: str = 'normal', text: str = '', rng: random.Random | None = None,
          save: bool = False, judged: dict | None = None) -> dict:
    """One of the persona's checks in the campaign's ruleset, on the shared ladder. `approach` is a Prospero stat;
    `save` asks for a saving throw where the ruleset has them (resisting fear, pain, poison). Under Narrative Only
    nothing is rolled: the judge's verdict (`judged`, dungeon/judge.py) stands, else the difficulty decides."""
    played = ruleset(connection)
    if played == narrative.ID:
        return narrative.result((judged or {}).get('verdict'), (judged or {}).get('reason', ''), difficulty)
    found = native(connection) if played != marvel.ID else None
    if found and played == srd52.ID:
        result = srd52.check(found, approach, difficulty, text, rng, save) | {'ruleset': srd52.ID}
        return cast(connection, found, result, rng, text) if result.get('spell') else result
    if found and played == brp.ID:
        # A skill that succeeds gets its experience check; First Aid on the character's own wound heals.
        from dungeon import combat_brp
        result = brp.check(found, approach, difficulty, text, rng, save) | {'ruleset': brp.ID}
        result = combat_brp.first_aid(connection, found, result, rng)
        # A Heal spell heals the character at once (dungeon/combat_brp.py healed).
        result = combat_brp.healed(found, result, rng)
        if (not save and brp.check_skill(found, result)) or result.get('healed') or result.get('brp_spell'):
            set_native(connection, found, '')
        if result.get('healed'):
            from dungeon import combat, combat5e
            combat.set_condition(connection, combat5e.level_for(found['hp'], found['max_hp']))
        return result
    if found and played == fate.ID:
        # A Fate point spent on an invoke, or gained from a compel (dungeon/rules/fate.py roll).
        result = fate.roll(found, approach, difficulty, text, rng) | {'ruleset': fate.ID}
        if result['fate_points'] != found['fate_points']:
            set_native(connection, found | {'fate_points': result['fate_points']}, '')
        return result
    if found and played == ironsworn.ID:
        # Resisting is a suffer move: Endure Harm on iron for the body, Endure Stress on heart for the mind.
        move, stat = (('endure_harm', 'iron') if approach == 'Vitality' else ('endure_stress', 'heart')) if save \
            else (None, None)
        result = ironsworn.roll(found, approach, difficulty, text, rng, stat, move) | {'ruleset': ironsworn.ID}
        # Resupply brings supply back (dungeon/sworn.py).
        restocked = min(5 - found['supply'], ironsworn.RESUPPLY.get(result['band'], 0)) \
            if result['move'] == 'resupply' else 0
        if result['momentum'] != found['momentum'] or restocked:
            set_native(connection, found | {'momentum': result['momentum'], 'supply': found['supply'] + restocked}, '')
        return result | ({'skill': f"{result['skill']} (+{restocked} supply)"} if restocked else {})
    return marvel.roll(stats(connection).get(approach), difficulty, rng) | {'ruleset': marvel.ID, 'target': None,
                                                                            'skill': None}


def cast(connection, found: dict, result: dict, rng, text: str = '') -> dict:
    """A 5E spell cast by the turn's check: it spends a slot, the one the line asks for when it is free ("at 2nd
    level"; none left, it fails); a healing spell always works and heals the character. A slot above the spell's
    level is named on the card ("2nd-level slot") for the fight to scale the spell by."""
    spell = srd52.spells()[result['spell']]
    slot = srd52.spend(found, spell, srd52.upcast(text))
    if slot is None:
        # No dice: the spell just fails (the card shows no roll).
        return result | {'band': 'failure', 'natural': 0, 'total': 0, 'rolls': [],
                         'skill': f"{spell['name']} (no spell slot left)", 'spell': None}
    upcast = f" ({srd52.ordinal(slot)}-level slot)" if slot > spell['level'] else ''
    if dice := srd52.healing_of(spell):
        from dungeon import combat, combat5e
        # The Life Domain's Disciple of Life adds 2 + the slot's level to a levelled healing spell.
        blessed = 2 + slot if slot and srd52.has(found, 'Disciple of Life') else 0
        healed = max(1, combat5e.roll_dice(srd52.scaled(dice, spell, slot), rng or random.SystemRandom())
                     + srd52.modifier(found['abilities'][found['spell_ability']]) + blessed)
        found['hp'] = min(found['max_hp'], found['hp'] + healed)
        set_native(connection, found, '')
        combat.set_condition(connection, combat5e.level_for(found['hp'], found['max_hp']))
        return result | {'band': 'success', 'skill': f"{spell['name']}{upcast} (heals {healed})"}
    set_native(connection, found, '')
    return result | ({'skill': f"{result['skill']}{upcast}"} if upcast else {})


def caster(connection) -> dict | None:
    """The persona's 5E sheet, when the campaign plays 5E."""
    return native(connection) if ruleset(connection) == srd52.ID else None


def spell_actions(connection, text: str, actions: list[dict]) -> list[dict]:
    """Under 5E, the turn's actions as the spell a line casts by name needs them: a spell the character has not
    prepared is not cast, so nothing about it is rolled; a known spell is cast though the Referee saw nothing uncertain
    in it ("I cast Cure Wounds on myself") or split the line into the other thing it does ("I cast Healing Word on
    myself and hit the thug with my mace"); a slot the line asks for anywhere in it ("I cast Burning
    Hands at the nearer one at 2nd level") goes with the action that casts it (dungeon/turn.py store)."""
    found, spell = caster(connection), srd52.cast_named(text)
    if not found or not spell:
        return actions
    names = lambda action: re.search(rf"\b{re.escape(spell['name'].lower())}\b", action['action'].lower())  # noqa: E731
    if not srd52.knows(found, spell):
        return [action for action in actions if not names(action) and not CASTING.search(action['action'])]
    if not any(names(action) for action in actions):
        actions = [*actions, {'action': f"cast {spell['name']}", 'stat': 'Essence', 'difficulty': 'normal'}]
    slot = srd52.upcast(text)
    return [action | {'slot': slot} if slot and names(action) else action for action in actions]


def unprepared(connection, text: str) -> list[str]:
    """What the narrator is told of a 5E spell the line casts that the character has not got ready."""
    found, spell = caster(connection), srd52.cast_named(text)
    if not found or not spell or srd52.knows(found, spell):
        return []
    had = 'know' if spell['level'] == 0 else 'have prepared'
    return [f"The character does not {had} {spell['name']}: it is not cast, and nothing is rolled for it."]


def full_view(connection) -> dict:
    """The sheet the screen shows, in the campaign's ruleset."""
    played = ruleset(connection)
    found = native(connection) if played != marvel.ID else None
    if found:
        return srd52.view(found) if played == srd52.ID else brp.view(found) if played == brp.ID else \
            narrative.view(found) if played == narrative.ID else fate.view(found) if played == fate.ID else \
            ironsworn.view(found)
    return view(connection) | {'ruleset': marvel.ID, 'ruleset_name': marvel.NAME}


def refresh_fate(connection, nights: int) -> list[str]:
    """Under Fate, a night's sleep brings Fate points back up to the refresh and clears stress. Silent: the sheet
    shows it, and the narrator never writes the bookkeeping."""
    found = native(connection) if nights > 0 and ruleset(connection) == fate.ID else None
    if found:
        set_native(connection, fate.refreshed(found), '')
    return []


def compel_line(connection, text: str, rolls: list[dict]):
    """Under Fate, the player's line acting on the trouble is a compel even when no roll was (one a turn: a roll that
    already compelled pays it)."""
    found = native(connection) if ruleset(connection) == fate.ID else None
    if found and not any('compelled' in (row.get('skill') or '') for row in rolls) and fate.compelled(found, text):
        set_native(connection, found | {'fate_points': found['fate_points'] + 1}, '')
