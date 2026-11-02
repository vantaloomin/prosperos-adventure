"""How the character looks right now (requirements "Inventory and equipment": appearance state and visible gear;
docs/story.md "How you look").

Code keeps the character's look and the narrator describes it the same way every turn:
- **Cleanliness:** clean, worn, grimy or filthy (GRIME), with marks (blood, mud, sweat, other fluids, smoke). A
  journey, a night camped, a fight, a day's hard work or sex raise it; washing lowers it and clears the marks, and a
  paid bath or laundry (dungeon/inventory.py services) clears it all.
- **Clothing condition:** intact, rumpled, torn or ruined (CLOTHES). A wound in a fight tears them, sex rumples them;
  the laundry presses them, mending (a service) fixes a tear, and new clothes bought replace ruined ones.
- **State of dress,** per layer (outer, under, accessories): worn, loosened or off, and where what came off was left.
  A line that undresses, loosens or dresses moves them.
- **On show:** what the character wears and wields that anyone can see: a weapon carried, a wound's bandage.
A world can set its city's `appearance` to 'basic' (cleanliness and condition only, no state of dress). All of it is
game state (story_appearance, dungeon/timeline.py SAVED); each line's change is decided once (story_appearance_turns),
so telling it again changes nothing more.
"""
import re

from dungeon import combat, inventory
from dungeon.database import decode, encode, many, optional

GRIME = ('clean', 'worn', 'grimy', 'filthy')
CLOTHES = ('intact', 'rumpled', 'torn', 'ruined')
LAYERS = ('outer', 'under', 'accessories')
DRESSED = {layer: 'worn' for layer in LAYERS}
LAYER_WORDS = {
    'outer': r'cloak|coat|jacket|armou?r|mail|robe|overcoat|hoodie|cape|doublet|jerkin',
    'under': r'shirt|tunic|dress|blouse|trousers|breeches|pants|skirt|smallclothes|underwear|shift|chemise|jeans',
    'accessories': r'boots|shoes|gloves|hat|belt|scarf|mask|hood|socks|stockings',
}
ALL = re.compile(r'\b(clothes|everything|naked|bare|undress\w*|strip\w*( off)?)\b', re.I)
OFF = re.compile(r'\b(undress\w*|strip\w*|take\w* off|took off|pull\w* off|shed\w*|remov\w*|slip\w* out of|'
                 r'peel\w* off|shrug\w* off)\b', re.I)
ON = re.compile(r'\b(get dressed|gets dressed|dress\w* again|put\w* (on|back on)|pull\w* on|button\w* up|'
                r'lace\w* up|re-?dress\w*)\b', re.I)
# "I put my shirt and coat back on": dresses only the layers it names.
PUT_ON = re.compile(r'\b(put\w*|pull\w*|slip\w*|shrug\w*)\b(\s+[\w,\']+){1,8}?\s+(back\s+)?on\b', re.I)
LOOSEN = re.compile(r'\b(loosen\w*|unbutton\w*|unlace\w*|undo\w*)\b', re.I)
WASH = re.compile(r'\b(wash\w*|bath(e|es|ing)?|scrub\w*|rins\w*|clean (myself|up|off)|swim\w*)\b', re.I)
WORK = re.compile(r'\b(spend\w* the (day|morning|afternoon) (felling|chopping|digging|hauling|working|labou?ring)|'
                  r'fell\w* trees|chop\w* wood|dig\w*|haul\w*|labou?r\w*|muck\w* out|work\w* the (forge|fields?|mill))\b',
                  re.I)
SEX = re.compile(r'\b(have sex|make love|fuck\w*|sleep with|bed (him|her|them)|take (him|her|them) to bed|'
                 r'tumble with)\b', re.I)
WEAPONS = ('weapon',)


def state(connection) -> dict:
    row = optional(connection, 'SELECT grime, marks, clothes, dress FROM story_appearance WHERE id=1')
    if row is None:
        return {'grime': 0, 'marks': [], 'clothes': 'intact', 'dress': dict(DRESSED)}
    return {'grime': row['grime'], 'marks': decode(row['marks']), 'clothes': row['clothes'],
            'dress': decode(row['dress'])}


def save(connection, look: dict):
    connection.execute('INSERT INTO story_appearance (id, grime, marks, clothes, dress) VALUES (1, ?, ?, ?, ?) '
                       'ON CONFLICT(id) DO UPDATE SET grime=excluded.grime, marks=excluded.marks, '
                       'clothes=excluded.clothes, dress=excluded.dress',
                       (look['grime'], encode(look['marks']), look['clothes'], encode(look['dress'])))


def dirtier(look: dict, steps: int = 1, *marks: str) -> dict:
    return look | {'grime': min(len(GRIME) - 1, look['grime'] + steps),
                   'marks': list(dict.fromkeys([*look['marks'], *marks]))}


def worse(look: dict, at_least: str) -> dict:
    """Clothes at least this bad; a new tear in torn clothes ruins them."""
    now, floor = CLOTHES.index(look['clothes']), CLOTHES.index(at_least)
    torn = CLOTHES.index('torn')
    after = min(len(CLOTHES) - 1, now + 1) if floor >= torn and now >= torn else max(now, floor)
    return look | {'clothes': CLOTHES[after]}


def dressing(look: dict, text: str, where: str) -> dict:
    """What a line takes off, loosens or puts on, layer by layer, and where what came off was left."""
    dress = dict(look['dress'])
    named = [layer for layer, words in LAYER_WORDS.items() if re.search(rf'\b({words})\b', text, re.I)]
    if OFF.search(text):
        for layer in (named or (LAYERS if ALL.search(text) else ())):
            if not dress[layer].startswith('off'):
                dress[layer] = f'off ({where})'
    elif LOOSEN.search(text):
        for layer in (named or ('outer', 'under')):
            if dress[layer] == 'worn':
                dress[layer] = 'loosened'
    elif ON.search(text) or (named and PUT_ON.search(text)):
        for layer in (named or LAYERS):
            dress[layer] = 'worn'
    return look | {'dress': dress}


def paid(connection, day: str, kinds: tuple[str, ...]) -> list[str]:
    """Services of these kinds paid for today (dungeon/inventory.py), by their row ids."""
    rows = many(connection, 'SELECT id, city_id, item_id FROM story_services WHERE day=?', (day,)) if day else []
    return [row['id'] for row in rows
            if (entry := inventory.item(row['city_id'], row['item_id'])) and entry.get('service') in kinds]


def changed(connection, message_id: str, text: str, events: dict, where: str, day: str, detail: str = 'full') \
        -> list[str]:
    """The line's change to how the character looks, decided once: what the turn did (events: travelled, camped,
    fought, wounded, bought_clothes) and what the line says (washing, work, sex, undressing)."""
    kept = optional(connection, 'SELECT lines FROM story_appearance_turns WHERE message_id=?', (message_id,))
    if kept:
        return decode(kept['lines'])
    before = state(connection)
    look, used = cleaned(connection, soiled(dict(before), text, events), text, day)
    if detail != 'basic':
        look = dressing(look, text, where)
    save(connection, look)
    connection.execute('UPDATE story_appearance SET used=? WHERE id=1', (encode(sorted(used)),))
    lines = differences(before, look)
    connection.execute('INSERT INTO story_appearance_turns (message_id, lines) VALUES (?, ?)',
                       (message_id, encode(lines)))
    return lines


def soiled(look: dict, text: str, events: dict) -> dict:
    """What the turn and the line did to the character's cleanliness and clothes."""
    if events.get('travelled'):
        look = dirtier(look, 1, 'road dust')
    if events.get('camped'):
        look = dirtier(look, 1, 'smoke')
    if events.get('fought'):
        look = dirtier(look, 1, 'sweat', 'blood')
    if events.get('wounded'):
        look = worse(dirtier(look, 0, 'blood'), 'torn')
    if WORK.search(text):
        look = dirtier(look, 1, 'sweat', 'sawdust' if re.search(r'fell|chop|saw', text, re.I) else 'dirt')
    if SEX.search(text):
        look = worse(dirtier(look, 0, 'sweat', 'other fluids'), 'rumpled')
    if events.get('bought_clothes') and look['clothes'] == 'ruined':
        look = look | {'clothes': 'intact'}
    return look


def cleaned(connection, look: dict, text: str, day: str) -> tuple[dict, set[str]]:
    """Washing, and the baths, laundry and mending paid for today and not yet used; with the services used so far."""
    row = optional(connection, 'SELECT used FROM story_appearance WHERE id=1')
    used = set(decode(row['used'])) if row and row['used'] else set()
    bath, laundry, mending = (set(paid(connection, day, kinds)) - used
                              for kinds in (('bath',), ('laundry',), ('mending',)))
    if bath:
        look = look | {'grime': 0, 'marks': []}
    elif WASH.search(text):
        look = look | {'grime': max(0, look['grime'] - 1), 'marks': []}
    if laundry:
        look = look | {'marks': [], 'clothes': 'intact' if look['clothes'] == 'rumpled' else look['clothes']}
    if mending and look['clothes'] == 'torn':
        look = look | {'clothes': 'intact'}
    return look, used | bath | laundry | mending


def differences(before: dict, after: dict) -> list[str]:
    """What changed, in words for the narrator."""
    lines = []
    if after['grime'] != before['grime'] or after['marks'] != before['marks']:
        lines.append(f"The character is {cleanliness(after)} now.")
    if after['clothes'] != before['clothes']:
        lines.append(f"Their clothes are {after['clothes']} now.")
    for layer in LAYERS:
        if after['dress'][layer] != before['dress'][layer]:
            lines.append(f"Their {layer} clothing: {after['dress'][layer]}.")
    return lines


def cleanliness(look: dict) -> str:
    marks = f" ({', '.join(look['marks'])})" if look['marks'] else ''
    return GRIME[look['grime']] + marks


def on_show(connection, city_id: str) -> list[str]:
    """What anyone can see the character carry: their weapons."""
    return [row['name'] for row in inventory.carried(connection, city_id) if row['category'] in WEAPONS]


def summary(connection, city_id: str, detail: str = 'full') -> dict:
    look = state(connection)
    return {'cleanliness': cleanliness(look), 'grime': GRIME[look['grime']], 'marks': look['marks'],
            'clothes': look['clothes'],
            'dress': {} if detail == 'basic' else {layer: value for layer, value in look['dress'].items()
                                                   if value != 'worn'},
            'on_show': on_show(connection, city_id)}


def prompt_text(connection, city_id: str, detail: str = 'full') -> str:
    """How the character looks right now, for the narrator: describe it consistently, and people react to it."""
    found = summary(connection, city_id, detail)
    parts = [f"{found['cleanliness'][:1].upper()}{found['cleanliness'][1:]}", f"clothes {found['clothes']}"]
    parts += [f'{layer} clothing {value}' for layer, value in found['dress'].items()]
    if found['on_show']:
        parts.append(f"on show: {', '.join(found['on_show'])}")
    if combat.condition(connection)['level'] >= 2:
        parts.append('their wounds show')
    return ('How the character looks right now (kept by the game; describe it consistently, and people notice it): '
            + '; '.join(parts) + '.')


def note_text(lines: list[str]) -> str:
    return '## How the character looks (changed this turn, by the game)\n' + '\n'.join(f'- {line}' for line in lines)
