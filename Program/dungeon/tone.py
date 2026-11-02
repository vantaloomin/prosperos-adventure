"""Intensity and tone for the campaign being played (requirements "Intensity and tone"; docs/story.md "Tone").

- **Per category.** Violence, sex, horror, cruelty and drugs each sit at a level from 0 (off the page) to 3
  (unflinching). A preset (restrained, mature, unflinching) sets them all; the player's own `levels` at the Table
  move single categories from there. Picking a preset again clears them (dungeon/table.py change).
- **Veils** name topics (dungeon/life/cards.py TOPICS) that may still happen but fade to black on the page: a card
  with a veiled topic is still drawn, and the narrator is told to keep it off the page.
- **Lower levels change what can happen.** Cards (`cards.allowed`), corruption, and the lasting-injury table
  (`injuries.roll`, entries with an `intensity`) leave out what the levels do not allow.
- **Voice** is how the narrator writes: the world's own, or one the player picks (VOICES). Drama is its own dial
  (dungeon/happenings.py). Neither changes the dice.
- **Worlds set the default** (a city's `intensity`: `preset`, optional `levels` and `veils`, `voice`, `drama`); the
  player can change any of it at any time, and the next line follows it.
"""
from dungeon import happenings, table
from dungeon.life import cards
from dungeon.narration import prompt as narration_prompt
from dungeon.sheet import ruleset as ruleset_of

CATEGORIES = cards.CATEGORIES
TOPICS = cards.TOPICS
VOICES = {
    'grim': 'grim and unsentimental: hard choices, real costs, little comfort',
    'wry': 'wry and dry: a sharp eye for the absurd, even when it hurts',
    'romantic': 'romantic and warm: longing, closeness and what people mean to each other',
    'hopeful': 'hopeful: darkness is real, but so is decency, and it is worth the fight',
    'lyrical': 'lyrical: rich, sensory prose with an eye for beauty in hard places',
    'plain': 'plain and direct: clear, quick prose that keeps out of the way',
}


def levels_for(preset: str, *overrides: dict) -> dict[str, int]:
    """Every category at the preset's level, then each override's categories on top (unknown ones ignored)."""
    found = dict.fromkeys(CATEGORIES, narration_prompt.PRESETS[preset])
    for override in overrides:
        found |= {key: max(0, min(3, int(value))) for key, value in (override or {}).items() if key in CATEGORIES}
    return found


def of(connection, data: dict) -> dict:
    """How far the story goes on the page, and how it sounds: the player's choices over the world's."""
    world = data.get('intensity') or {}
    rules = table.rules(connection)
    chosen = rules['intensity']
    world_preset = world.get('preset') or narration_prompt.DEFAULT_PRESET
    preset = world_preset if chosen == 'world' else chosen
    world_levels = world.get('levels') if chosen == 'world' else None
    levels = levels_for(preset, world_levels, rules['levels'])
    veils = [topic for topic in (rules['veils'] if rules['veils'] is not None else world.get('veils') or [])
             if topic in TOPICS]
    world_voice = world.get('voice') or ''
    voice = world_voice if rules['voice'] == 'world' else VOICES.get(rules['voice'], world_voice)
    drama, world_drama = rules['drama'], world.get('drama') or happenings.DEFAULT_DRAMA
    return {'preset': preset, 'chosen': chosen, 'world': world_preset, 'levels': levels,
            'custom': bool(rules['levels']), 'veils': veils, 'voice': voice, 'voice_chosen': rules['voice'],
            'voice_world': world_voice, 'drama': world_drama if drama == 'world' else drama, 'drama_chosen': drama,
            'drama_world': world_drama, 'cutaways': rules['cutaways'], 'defeat': rules['defeat'],
            'ruleset': ruleset_of(connection)}


def now(connection) -> dict:
    """The levels in play where the story is now; every category unflinching when there is no scene yet."""
    from dungeon import story
    row = story.scene_row(connection)
    try:
        return of(connection, story.city_data(connection, row['city_id']))
    except Exception:  # noqa: BLE001 - no city to read: the default, every category at the top.
        return {'levels': levels_for(narration_prompt.DEFAULT_PRESET), 'veils': []}


def narration(found: dict) -> narration_prompt.Intensity:
    """What the narrator is told (dungeon/narration/prompt.py Intensity)."""
    return narration_prompt.Intensity(levels=found['levels'], veils=tuple(found['veils']), voice=found['voice'])
