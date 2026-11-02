"""Campaign start (docs/story.md "Campaign start"): who the player is when a story begins.

A city may ship premade characters (`world/data/premades/<city>.json`), each with a few lines about them and their
Prospero stats. Or the player makes their own: a name, a few lines, and stats bought from a pool of points. Either
way the persona of this world takes them on, the story clock starts (dungeon/story_clock.py), and the story opens
with the player arriving where the scene is.
"""
from pathlib import Path

from dungeon import (
    chapters,
    combat_brp,
    director,
    hexes,
    institutions,
    inventory,
    legacy,
    package_lore,
    quests,
    sheet,
    story,
    story_clock,
    table,
    tiers,
    timeline,
    world_data,
    worlds,
)
from dungeon.database import one
from dungeon.errors import require
from dungeon.models import PersonaInput
from dungeon.rules import brp, fate, ironsworn, marvel, narrative, srd52

PREMADES = Path(__file__).parent / 'world' / 'data' / 'premades'
# Point-buy at the start: the six stats share POINTS, each from START_RANGE, so the default sheet (all 10) fits.
POINTS = 60
START_RANGE = (4, 18)
# A premade with no 5E build of its own takes one from its strongest Prospero stat.
CLASS_BY_STAT = {'Vitality': ('fighter', 'soldier'), 'Mind': ('wizard', 'sage'), 'Allure': ('bard', 'criminal'),
                 'Resolve': ('paladin', 'soldier'), 'Essence': ('cleric', 'acolyte'), 'Luck': ('rogue', 'criminal')}


def premades(city_id: str) -> list[dict]:
    found = world_data.read('premades', city_id)
    return found['premades'] if found else []


def view(database) -> dict:
    with database.connect() as connection:
        city_id = story.scene_row(connection)['city_id']
        rules = table.starting(connection)
    world = tiers.world_of(city_id)
    return {'premades': premades(city_id), 'points': POINTS, 'range': list(START_RANGE),
            'stat_names': list(marvel.STATS), 'meanings': marvel.MEANINGS,
            # The rulesets a campaign can be played in, the world's own first (dungeon/sheet.py).
            'rulesets': [{'id': key, 'name': name} for key, name in sheet.RULESETS.items()],
            'ruleset': sheet.default_for(world), 'srd52': srd52_choices(), 'ironsworn': ironsworn_choices(),
            'brp': brp_choices(), 'narrative': {'hint': narrative.HINT},
            'fate': {'hint': fate.HINT, 'approaches': list(fate.APPROACHES), 'array': list(fate.ARRAY),
                     'most_aspects': fate.MOST_ASPECTS, 'most_stunts': fate.MOST_STUNTS, 'attribution': fate.ATTRIBUTION},
            'arc': world and {'arc': tiers.track(world)['arc'], 'pace': tiers.track(world)['pace'],
                              'hand': director.DEFAULT_HAND},
            # Session zero (dungeon/table.py): the presets, and the rules as a new campaign would start.
            'presets': table.PRESETS, 'table': rules,
            # Other worlds' stories, to bring in as history (dungeon/legacy.py).
            'legacy': legacy.candidates(database)}


def srd52_choices() -> dict:
    """What a 5E character is built from: the pack's classes, species and backgrounds, and the standard array."""
    return {'classes': [{'id': item['id'], 'name': item['name'], 'hit_die': item['hit_die'],
                         'primary': item['primary_ability'], 'skills': item['skill_choices']}
                        for item in srd52.pack('classes')],
            'species': [{'id': item['id'], 'name': item['name']} for item in srd52.pack('species')],
            'backgrounds': [{'id': item['id'], 'name': item['name'], 'skills': item['skill_proficiencies'],
                             'abilities': item['ability_scores']} for item in srd52.pack('backgrounds')],
            'abilities': [{'id': ability, 'name': name} for ability, name in srd52.ABILITY_NAMES.items()],
            'skills': [{'id': skill['id'], 'name': skill['name'], 'ability': skill['ability']}
                       for skill in srd52.pack('rules')['skills']],
            'array': list(srd52.STANDARD_ARRAY), 'attribution': srd52.attribution()}


def ironsworn_choices() -> dict:
    """What an Ironsworn character is built from: the five stats, the array, the pack's assets by category."""
    return {'stats': [{'id': stat, 'name': stat, 'about': ironsworn.pack()['rules']['stats'][stat]['description']}
                      for stat in ironsworn.STATS],
            'array': list(ironsworn.ARRAY), 'count': ironsworn.ASSETS,
            'assets': [{'id': key, 'name': asset['name'], 'category': asset['category'],
                        'about': ironsworn.plain(next((ability['text'] for ability in asset['abilities']
                                                       if ability.get('enabled')), ''))}
                       for key, asset in ironsworn.assets().items()],
            'attribution': ironsworn.attribution()}


def brp_choices() -> dict:
    """What a BRP character is built from: the characteristics and their point-buy, professions, personalities."""
    rules = brp.pack()['creation']
    return {'characteristics': [{'id': item['id'], 'name': item['name'], 'roll': item['roll']}
                                for item in brp.pack()['characteristics']],
            'points': rules['points'], 'start': rules['start'], 'range': [rules['least'], rules['most']],
            'costly': rules['costly'], 'costly_price': rules['costly_price'],
            'professions': [{'id': item['id'], 'name': item['name'],
                             'skills': [brp.skills()[skill]['name'] for skill in item['skills']]}
                            for item in brp.pack()['professions']],
            'personalities': [{'id': item['id'], 'name': item['name'], 'about': item['about']}
                              for item in brp.pack()['personalities']],
            'attribution': brp.attribution()}


def premade_brp(chosen: dict) -> dict:
    top = max(marvel.STATS, key=lambda stat: chosen['stats'].get(stat, 0))
    quick = brp.suggested(top)
    return brp.build(quick['characteristics'], quick['profession'], quick['personality'])


# A premade's Ironsworn stat from its strongest Prospero stat.
IRONSWORN_BY_STAT = {'Vitality': 'iron', 'Mind': 'wits', 'Allure': 'heart', 'Resolve': 'heart', 'Essence': 'wits',
                     'Luck': 'edge'}


def premade_ironsworn(chosen: dict) -> dict:
    top = max(marvel.STATS, key=lambda stat: chosen['stats'].get(stat, 0))
    quick = ironsworn.suggested(IRONSWORN_BY_STAT[top])
    return ironsworn.build(quick['stats'], quick['assets'])


def premade_build(chosen: dict) -> dict:
    """A premade's 5E character: its own class, species and background, with the quick build's scores and skills."""
    own = chosen.get('srd52')
    if not own:
        top = max(marvel.STATS, key=lambda stat: chosen['stats'].get(stat, 0))
        class_id, background = CLASS_BY_STAT[top]
        own = {'class': class_id, 'species': 'human', 'background': background}
    quick = srd52.suggested(own['class'], own['background'])
    return srd52.build(own['class'], own['species'], own['background'], quick['scores'], quick['picks'])


def bought(stats: dict[str, int]) -> dict[str, int]:
    """The stats of a made character: every stat, each in START_RANGE, spending no more than POINTS."""
    low, high = START_RANGE
    require(set(stats) == set(marvel.STATS), f"Give all six stats: {', '.join(marvel.STATS)}.", 422)
    require(all(isinstance(value, int) and low <= value <= high for value in stats.values()),
            f'Each stat starts from {low} to {high}.', 422)
    require(sum(stats.values()) <= POINTS, f'The stats can share {POINTS} points at most.', 422)
    return stats


def begin(database, premade_id: str | None = None, persona: PersonaInput | None = None,
          stats: dict[str, int] | None = None, arc: str | None = None, pace: str | None = None,
          hand: str | None = None, ironman: bool = False, legacy_of: dict | None = None,
          ruleset: str | None = None, build: dict | None = None, iron: dict | None = None,
          rules: dict | None = None, percentile: dict | None = None, narrated: dict | None = None,
          fated: dict | None = None) -> dict:
    """Start the story as a premade character or one the player made; only a story with nothing in it yet. The
    ruleset (the world's own by default) is chosen now and locked; under 5E a made character is `build` (class,
    species, background, the standard array placed, the class's skills). `rules` are session zero's (dungeon/table.py)."""
    with database.connect() as connection:
        where, values = timeline.visible(connection)
        require(one(connection, f'SELECT COUNT(*) AS n FROM story_messages WHERE {where}', values)['n'] == 0,
                'The story has already begun. Start a new story to choose someone else.', 409)
        city_id = story.scene_row(connection)['city_id']
    ruleset = ruleset or sheet.default_for(tiers.world_of(city_id))
    require(ruleset in sheet.RULESETS, 'That ruleset is not built in.', 422)
    native = None
    if premade_id:
        chosen = next((item for item in premades(city_id) if item['id'] == premade_id), None)
        require(chosen is not None, 'That character is not in this town.', 404)
        persona = PersonaInput(name=chosen['name'], gender=chosen['gender'], age=chosen['age'], about=chosen['about'])
        stats = chosen['stats']
        native = premade_build(chosen) if ruleset == srd52.ID else premade_ironsworn(chosen) \
            if ruleset == ironsworn.ID else premade_brp(chosen) if ruleset == brp.ID else \
            narrative.build() if ruleset == narrative.ID else \
            fate.premade(chosen['about'], max(marvel.STATS, key=lambda stat: chosen['stats'].get(stat, 0))) \
            if ruleset == fate.ID else None
    else:
        require(persona is not None and bool((persona.name or '').strip()), 'Give your character a name.', 422)
        if ruleset == srd52.ID:
            require(build is not None, 'Choose a class, species and background, and place the standard array.', 422)
            native = srd52.build(build['class_id'], build['species_id'], build['background_id'], build['scores'],
                                 build['skills'])
            stats = {stat: marvel.DEFAULT_STAT for stat in marvel.STATS}
        elif ruleset == ironsworn.ID:
            require(iron is not None, 'Place 3, 2, 2, 1 and 1 on the five stats and choose three assets.', 422)
            native = ironsworn.build(iron['stats'], iron['assets'])
            stats = {stat: marvel.DEFAULT_STAT for stat in marvel.STATS}
        elif ruleset == brp.ID:
            require(percentile is not None, 'Buy the seven characteristics and choose a profession and a personality.',
                    422)
            native = brp.build(percentile['characteristics'], percentile['profession'], percentile['personality'])
            stats = {stat: marvel.DEFAULT_STAT for stat in marvel.STATS}
        elif ruleset == narrative.ID:
            # No stats: who they are is their own description, and what they say they are good and bad at.
            native = narrative.build(**(narrated or {}))
            stats = {stat: marvel.DEFAULT_STAT for stat in marvel.STATS}
        elif ruleset == fate.ID:
            require(fated is not None, 'Give a high concept and place +3, +2, +2, +1, +1 and +0 on the approaches.',
                    422)
            native = fate.build(**fated)
            stats = {stat: marvel.DEFAULT_STAT for stat in marvel.STATS}
        else:
            stats = bought(stats or {})
    earlier = legacy_of and legacy.chosen(database, legacy_of['world_id'], legacy_of['role'])
    data = worlds.registry(database)
    active = worlds.found(data['worlds'], data['active'], 'world')
    worlds.update_persona(database, active['persona_id'], persona)
    with database.connect(write=True) as connection:
        sheet.set_stats(connection, stats, database.now())
        # The ruleset (dungeon/sheet.py): chosen now, for the whole campaign, with its own sheet.
        sheet.set_ruleset(connection, ruleset)
        # The world seed (dungeon/hexes.py), chosen now so that a read (a town's streets) never has to write it.
        hexes.seed(connection)
        if native:
            sheet.set_native(connection, native, database.now())
        # Ironman (dungeon/chapters.py): chosen now, for the whole campaign.
        chapters.set_ironman(connection, ironman)
        # The Table (dungeon/table.py): session zero's rules, the rest from the world's tone and the player's last taste.
        table.choose(connection, rules or {}, database.now())
        table.begin(connection)
        # The story clock starts at the world's own date when it has one (Havenbrooke's 2009), else today.
        began = tiers.start(tiers.world_of(city_id)) or database.clock.now()
        story_clock.start(connection, began)
        story_clock.caught_up(connection, database.clock.now(), False)
        quests.start(connection, city_id, began)
        inventory.give_kit(connection, city_id, premade_id)
        # A made Percentile character carries their profession's weapons (dungeon/combat_brp.py).
        combat_brp.arm(connection, city_id, None if premade_id or ruleset != brp.ID else native)
        # How far and how fast the character can rise (dungeon/tiers.py).
        if world := tiers.world_of(city_id):
            tiers.begin(connection, world, arc, pace)
            # The director's arcs and threads, and how hard its hand pushes (dungeon/director.py).
            director.begin(connection, world, hand, database.now())
            # The world package's public lore, read by keyword like any lorebook (dungeon/package_lore.py).
            package_lore.bring(connection, database.root, world, database.now())
            # The school or guild the character starts in (dungeon/institutions.py).
            institutions.begin(connection, world, chosen if premade_id else None, began)
        # An earlier campaign's character as this world's history (dungeon/legacy.py).
        if earlier:
            legacy.bring(connection, earlier, legacy_of['role'], began)
        story.arrive(connection, database.now())
    return story.story(database)
