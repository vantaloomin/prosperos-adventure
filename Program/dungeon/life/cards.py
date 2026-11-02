"""World Life Cards: each world's own deck and d100 tables, drawn into town days, roads, rests and off-page beats.

The Companion Life deck (deck.py, world/data/life_deck.json) drew small everyday moments for one companion. Dungeon
worlds keep the same idea and the same seeded dice (chance.py), with what the requirements add on top
(docs/requirements.md: "Intensity and tone", "Off-page beats", "NPC minds", "Time and travel"); the schema is
written up in docs/life-cards.md.

- A card belongs to one or more **scenes**: a day in town, a stretch of road, a rest outside safety, or an
  off-page beat for an absent character ({them}).
- The **drama** level (0 quiet to 3 merciless) sets how often a scene draws anything and which cards can turn up,
  as the Life deck's drama level did. It never touches roll odds.
- **Intensity** filters what can happen: a card that needs violence at Mature is left out below Mature. Topics on
  the player's **veil** list stay in play; the draw says so, and the narrator fades them to black.
- A card keeps the hidden **truth** apart from what the character **sees**, and says how accurate that is, so the
  journal records belief and the record records fact.
- **Effects** are what code applies (prices, feelings, fates, rumors, fights). Nothing here applies them yet: the
  Milestone 2 systems read them.

No model decides anything here. Decks live in life/decks/<world>.json until world packages (Milestone 5) carry them.
"""
import json
import re
from functools import cache
from pathlib import Path

from dungeon.life import chance

DECKS = Path(__file__).parent / 'decks'

SCENES = ('town', 'road', 'rest', 'beat')
TONES = ('good', 'bad', 'grey')
DRAMA = ('quiet', 'uneasy', 'eventful', 'merciless')
# Intensity levels per category, as the presets name them. 0 is Off: nothing that needs the category is drawn.
LEVELS = ('off', 'restrained', 'mature', 'unflinching')
CATEGORIES = ('violence', 'sex', 'horror', 'cruelty', 'drugs')
PRESETS = {name: dict.fromkeys(CATEGORIES, level) for level, name in enumerate(LEVELS) if level}
TOPICS = ('execution', 'slavery', 'mutilation', 'disease', 'self-harm', 'addiction', 'torture', 'sexual-violence',
          'sacrifice', 'child-harm')
NEEDS = ('bond', 'party', 'debt', 'wanted', 'injured', 'caster', 'captive')
ACCURACY = ('true', 'partial', 'false')
REGIONS = ('cyrel', 'badlands', 'asania', 'trein', 'gulf', 'dwarfholds', 'brynwyr', 'kujuur', 'fjallagracht',
           'etryona', 'wrenspire')
PLACEHOLDERS = ('pc', 'npc', 'bond', 'them', 'faction', 'town')
WHO = ('npc', 'bond', 'them')
GOODS = ('food', 'drink', 'medicine', 'ley', 'arms', 'cloth', 'lodging', 'any')
AXES = ('trust', 'affection', 'respect', 'fear', 'desire')
FATES = ('wounded', 'sick', 'captured', 'dead', 'turned', 'missing', 'indebted', 'wanted', 'freed', 'addicted',
         'conscripted')
FOES = ('bandits', 'deserters', 'gnolls', 'orcs', 'beasts', 'undead', 'corsairs', 'hunters', 'fiend', 'cultists',
        'watch', 'fey')
WOUNDS = ('Grazed', 'Hurt', 'Wounded', 'Maimed', 'Dying')
# Each effect kind and the type or vocabulary of each of its fields.
EFFECTS = {
    'market': {'goods': GOODS, 'shift': int, 'days': int},  # price change in percent, for so many days
    'stress': {'amount': int},
    'wound': {'level': WOUNDS},  # to the player character
    'feeling': {'who': WHO, 'axis': AXES, 'shift': int},  # that character's feeling toward the player character
    'fate': {'who': WHO, 'state': FATES},
    'coin': {'wages': int},  # gained or lost, in an unskilled worker's daily wages in the local currency
    'supply': {'shift': int},
    'rumor': {'about': ('pc', 'npc', 'bond', 'them', 'faction', 'place'), 'true': bool},
    'clock': {'shift': int},  # the {faction}'s clock
    'reputation': {'shift': int},  # with the {faction}
    'quest': {'from': ('npc', 'bond', 'them', 'faction'), 'days': int},  # a deadline on the story clock
    'fight': {'foes': FOES},  # starts the Combat rules, foes at the region's tier
    'pursuer': {'days': int},  # someone is this many days behind the player character
    'corruption': {'shift': int},
    'time': {'hours': int},
}
TEXT = ('truth', 'seen', 'pressure')


@cache
def deck(world: str) -> dict:
    return json.loads((DECKS / f'{world}.json').read_text(encoding='utf-8'))


def worlds() -> list[str]:
    return sorted(path.stem for path in DECKS.glob('*.json'))


# What a card may leave out, and what it means then.
DEFAULTS = {'accuracy': 'true', 'pressure': None, 'drama': 0, 'needs': [], 'where': [], 'intensity': {}, 'topics': [],
            'effects': [], 'on': True}


def _as_card(row: dict, table: dict, weight: int) -> dict:
    keys = ('id', 'title', 'tone', 'truth', 'seen', *DEFAULTS)
    return {key: row.get(key, DEFAULTS.get(key)) for key in keys} | {
        'source': table['name'], 'scenes': [table['scene']], 'weight': weight}


def table_cards(world: str) -> list[dict]:
    """Each scene's d100 table rows as cards, weighted by their share of the roll (through a child table when the
    top row names one), so a scene's table takes `tables_weight` next to its deck cards."""
    data, found = deck(world), []
    for table in data['tables'].values():
        if not table.get('scene'):
            continue
        top_width = sum(row['high'] - row['low'] + 1 for row in table['rows'])
        for parent in table['rows']:
            share = (parent['high'] - parent['low'] + 1) / top_width
            if not parent.get('child'):
                found.append(_as_card(parent, table, max(1, round(data['tables_weight'] * share))))
                continue
            child = data['tables'][parent['child']]
            width = sum(row['high'] - row['low'] + 1 for row in child['rows'])
            for row in child['rows']:
                part = share * (row['high'] - row['low'] + 1) / width
                found.append(_as_card(row, child | {'scene': table['scene']},
                                      max(1, round(data['tables_weight'] * part))))
    return found


@cache
def cards(world: str) -> tuple[dict, ...]:
    return tuple([DEFAULTS | card | {'source': 'deck'} for card in deck(world)['cards']] + table_cards(world))


def card(world: str, card_id: str | None) -> dict | None:
    return next((item for item in cards(world) if item['id'] == card_id), None)


# Filtering and drawing -----------------------------------------------------------------------------------

def allowed(item: dict, intensity: dict[str, int]) -> bool:
    """Whether the intensity settings let this card happen at all. A category left out counts as its top level."""
    return all(intensity.get(category, len(LEVELS) - 1) >= level for category, level in item['intensity'].items())


def veiled(item: dict, veils: set[str]) -> bool:
    return bool(veils & set(item['topics']))


def eligible(world: str, scene: str, level: int, intensity: dict[str, int], has: set[str], recent: set[str],
             region: str | None = None) -> list[dict]:
    return [item for item in cards(world) if item['on'] and scene in item['scenes'] and item['drama'] <= level
            and set(item['needs']) <= has and item['id'] not in recent and allowed(item, intensity)
            and (not item['where'] or region in item['where'])]


def pick(pool: list[dict], draws: chance.Draws) -> dict:
    point = draws.die(sum(item['weight'] for item in pool), 'cards', 'card')
    for item in pool:
        if point <= item['weight']:
            return item
        point -= item['weight']
    raise AssertionError('The deck has no card')


def draw(world: str, scene: str, seed: str, level: int, intensity: dict[str, int], has: set[str], recent: set[str],
         region: str | None = None, veils: frozenset[str] = frozenset(), forced: bool = False) -> dict:
    """One draw for a scene: {'card', 'odds', 'veiled'}, with card None when nothing happens. `forced` skips the
    roll for whether anything happens."""
    draws, chances = chance.Draws(seed), deck(world)['chance'][scene]
    happens = chances[min(level, len(chances) - 1)]
    if not forced and draws.die(100, 'cards', 'moment') > happens:
        return {'card': None, 'odds': round(1 - happens / 100, 3), 'veiled': False}
    pool = eligible(world, scene, level, intensity, has, recent, region)
    if not pool:
        return {'card': None, 'odds': 1.0, 'veiled': False}
    found = pick(pool, draws)
    share = found['weight'] / sum(item['weight'] for item in pool)
    return {'card': found, 'odds': round(share if forced else happens / 100 * share, 3),
            'veiled': veiled(found, set(veils))}


# Checking a deck -----------------------------------------------------------------------------------------

def _effect_problems(effect: dict) -> list[str]:
    fields = EFFECTS.get(effect.get('kind'))
    if fields is None:
        return [f'unknown effect {effect.get("kind")!r}']
    found = [f'{effect["kind"]} effect has unknown field {key!r}' for key in effect if key != 'kind' and
             key not in fields]
    for key, kind in fields.items():
        value = effect.get(key)
        ok = isinstance(value, kind) and not (kind is int and isinstance(value, bool)) if isinstance(kind, type) \
            else value in kind
        if not ok:
            found.append(f'{effect["kind"]} effect has a bad {key}: {value!r}')
    return found


def _card_problems(item: dict, scenes: list[str]) -> list[str]:
    found = []
    checks = [
        (isinstance(item.get('title'), str) and item['title'], 'no title'),
        (item.get('tone') in TONES, f'tone {item.get("tone")!r}'),
        (item.get('drama', 0) in range(len(DRAMA)), f'drama {item.get("drama")!r}'),
        (item.get('accuracy', 'true') in ACCURACY, f'accuracy {item.get("accuracy")!r}'),
        (set(item.get('needs', [])) <= set(NEEDS), f'needs {item.get("needs")}'),
        (set(item.get('where', [])) <= set(REGIONS), f'where {item.get("where")}'),
        (set(item.get('topics', [])) <= set(TOPICS), f'topics {item.get("topics")}'),
        (all(key in CATEGORIES and value in range(1, len(LEVELS)) for key, value in
             item.get('intensity', {}).items()), f'intensity {item.get("intensity")}'),
        (isinstance(item.get('truth'), str) and isinstance(item.get('seen'), str), 'no truth or seen'),
    ]
    found += [message for ok, message in checks if not ok]
    for effect in item.get('effects', []):
        found += _effect_problems(effect)
    text = ' '.join(item.get(key) or '' for key in TEXT)
    names = set(re.findall(r'\{(\w+)\}', text))
    found += [f'unknown placeholder {{{name}}}' for name in sorted(names - set(PLACEHOLDERS))]
    if 'bond' in names and 'bond' not in item.get('needs', []):
        found.append('{bond} without needing a bond')
    if 'them' in names and scenes != ['beat']:
        found.append('{them} outside a beat-only card')
    if scenes == ['beat'] and 'them' not in names:
        found.append('a beat card that never names {them}')
    return [f'{item.get("id")}: {message}' for message in found]


def _table_problems(name: str, table: dict, tables: dict) -> list[str]:
    found, rows = [], sorted(table.get('rows', []), key=lambda row: row['low'])
    edge = 1
    for row in rows:
        if row['low'] != edge or row['high'] < row['low']:
            found.append(f'table {name}: rows leave a gap or overlap at {edge}')
        edge = row['high'] + 1
    if rows and edge - 1 != table.get('die'):
        found.append(f'table {name}: rows end at {edge - 1}, not at its die {table.get("die")}')
    if table.get('scene') is not None and table['scene'] not in SCENES:
        found.append(f'table {name}: scene {table["scene"]!r}')
    for row in rows:
        if row.get('child') and row['child'] not in tables:
            found.append(f'table {name}: {row["id"]} names a missing table {row["child"]!r}')
    return found


def _rows_problems(tables: dict) -> list[str]:
    """Each table's own problems, and each event row checked as a card of the scene its top table belongs to."""
    found, parents = [], {}
    for name, table in tables.items():
        found += _table_problems(name, table, tables)
        parents |= {row['child']: table.get('scene') for row in table.get('rows', []) if row.get('child')}
    for name, table in tables.items():
        scene = table.get('scene') or parents.get(name)
        for row in table.get('rows', []):
            if not row.get('child'):
                found += _card_problems(row, [scene] if scene else [])
    return found


def problems(data: dict) -> list[str]:
    """Everything wrong with a deck file, as messages; an empty list means it loads and draws as intended."""
    found = []
    for scene in SCENES:
        odds = data.get('chance', {}).get(scene)
        if not (isinstance(odds, list) and len(odds) == len(DRAMA) and odds == sorted(odds)
                and all(0 < value <= 100 for value in odds)):
            found.append(f'chance for {scene} must rise over the {len(DRAMA)} drama levels, 1 to 100')
    for item in data.get('cards', []):
        scenes = item.get('scenes', [])
        if not scenes or not set(scenes) <= set(SCENES):
            found.append(f'{item.get("id")}: scenes {scenes}')
        if not isinstance(item.get('weight'), int) or item['weight'] < 1:
            found.append(f'{item.get("id")}: weight {item.get("weight")!r}')
        found += _card_problems(item, scenes)
    tables = data.get('tables', {})
    found += _rows_problems(tables)
    ids = [item.get('id') for item in data.get('cards', [])] + \
        [row.get('id') for table in tables.values() for row in table.get('rows', [])]
    found += [f'{name}: the id is used twice' for name in sorted({name for name in ids if ids.count(name) > 1})]
    return found
