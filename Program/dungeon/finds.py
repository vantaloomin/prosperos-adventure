"""Decide before describing (requirements "Decide before describing"; docs/story.md "What is inside").

When the player looks into something the story hasn't settled (a chest, a drawer, a crate, a body, a stranger's
purse, a room), code rolls what is there from the town's tables (world/data/finds/<city>.json) and stores it before
the narrator writes a word: in story_finds, and in the record as a fact. The narrator is told what is there and
describes only that. The same thing looked into again holds the same contents, so a trap or a coin was there
before anyone looked.

- A failed search roll (Mind) misses what is there: the contents stay as rolled, unseen, for a better look later.
- Taking what was found ("I take the coins", "I pocket the knife") moves it into the pack and purse, within carry
  slots; what does not fit stays. What is taken from someone's things is stolen (story_inventory.stolen): a purse or
  a pocket always, anything else at a place someone owns. Only a body, or a place out in the open (UNOWNED), gives
  what it holds freely. Honest shops won't buy stolen goods; a fence will (dungeon/inventory.py).

- A fight won leaves the fallen where they fell (spoils): their bodies hold what they carried, decided as they fall
  and unseen until searched: a person's coins (more on a robber), and their weapon when the town sells its like; a
  beast, the dead or a fiend, nothing. Every town knows a body, with or without a finds table, and there is no body
  to search where nobody has fallen.

All of it is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import random
import re
from pathlib import Path

from dungeon import inventory, record, world_data
from dungeon.database import decode, encode, many, optional

FINDS = Path(__file__).parent / 'world' / 'data' / 'finds'
LOOK = re.compile(r'\b(search\w*|open\w*|look(s|ing)? (in|into|inside|through|under|behind)|check\w*|rummag\w*|'
                  r'go(es)? through|empt(y|ies)|loot\w*|frisk\w*|pat\w* (him|her|them|it) down|go(es)? over|'
                  r'peer\w* (in|into|inside|behind)|pick\w* (his|her|their|its) pockets?|turn\w* out)\b', re.I)
TAKE = re.compile(r'\b(take|takes|grab\w*|pocket\w*|pick\w* up|help (myself|yourself)|keep|scoop\w* up|stuff\w*)\b',
                  re.I)
MISSED = ('failure', 'failure_upside', 'critical_failure')
# Places nobody owns, where what is found is free to take.
UNOWNED = ('trail', 'garden', 'park')
ALWAYS_STOLEN, NEVER_STOLEN = 'purse', 'body'
# A body where the town's finds table names none: nothing on it but what a fight left (spoils).
BODY = {'words': ['body', 'bodies', 'corpse', 'corpses', 'dead man', 'dead woman', 'the dead'], 'draws': 0, 'table': []}
BEASTLY = re.compile(r'\b(wol(f|ves)|bears?|boars?|hounds?|beasts?|spiders?|rats?|dead|fiends?|ghouls?|wights?|'
                     r'skeletons?|zombies?|crawlers?|serpents?|snakes?)\b', re.I)
# A fallen foe's purse, in the currency, by what they were after; their weapon by how hard it hit (dungeon/combat.py).
PURSES = {'rob': (0.5, 3.0), 'capture': (0.2, 1.5)}
PURSE = (0.1, 1.0)
ARMS = {1: ('sword', 'felling-axe', 'hatchet'), 0: ('knife', 'cudgel', 'hatchet')}
MONEY = re.compile(r'\b(coins?|money|crowns?|silver|everything|all of it|the lot|what\w*|it|them)\b', re.I)


def tables(city_id: str) -> dict:
    found = world_data.read('finds', city_id)
    containers = found['containers'] if found else {}
    return containers if NEVER_STOLEN in containers else {**containers, NEVER_STOLEN: BODY}


def container(city_id: str, text: str) -> tuple[str, str] | None:
    """The kind and the word for what a line looks into ("I search the chest" -> ('chest', 'chest')), if any."""
    if not LOOK.search(text):
        return None
    found = [(match.start(), kind, word) for kind, spec in tables(city_id).items() for word in spec['words']
             if (match := re.search(rf'(?<![\w-]){re.escape(word)}(?![\w-])', text, re.I))]
    return (found and min(found)[1:]) or None


def pick(table: list[dict], rng) -> dict:
    total = sum(entry['weight'] for entry in table)
    roll, at = rng.randint(1, total), 0
    for entry in table:
        at += entry['weight']
        if roll <= at:
            return entry
    return table[-1]


def roll(city_id: str, spec: dict, rng) -> list[dict]:
    """What is inside: items with counts, coins in hundredths, and notes; an empty list when there is nothing."""
    contents: list[dict] = []
    for _ in range(spec['draws']):
        entry = pick(spec['table'], rng)
        if entry.get('item') and inventory.item(city_id, entry['item']):
            same = next((thing for thing in contents if thing.get('item_id') == entry['item']), None)
            if same:
                same['qty'] += 1
            else:
                contents.append({'item_id': entry['item'], 'qty': 1})
        elif entry.get('coins'):
            low, high = (inventory.cents(amount) for amount in entry['coins'])
            contents.append({'coins': rng.randint(low, high)})
        elif entry.get('note') and not any(thing.get('note') == entry['note'] for thing in contents):
            contents.append({'note': entry['note'], 'trap': bool(entry.get('trap'))})
    return contents


def described(city_id: str, contents: list[dict], currency: dict) -> str:
    parts = []
    for thing in contents:
        if 'item_id' in thing:
            name = inventory.item(city_id, thing['item_id'])['name']
            parts.append(name if thing['qty'] == 1 else f"{thing['qty']} × {name}")
        elif 'coins' in thing:
            parts.append(inventory.money_text(thing['coins'], currency))
        else:
            parts.append(thing['note'] + (' (a trap)' if thing.get('trap') else ''))
    return '; '.join(parts) or 'nothing of use'


def stored(connection, key: str) -> dict | None:
    row = optional(connection, 'SELECT * FROM story_finds WHERE key=?', (key,))
    return row and row | {'contents': decode(row['contents'])}


def look(connection, city: dict, place: dict, text: str, rolls: list[dict], rng, now: str) -> list[str]:
    """What a line looks into, decided (rolled once, then kept) before the narrator describes it."""
    found = container(city['id'], text)
    if found is None:
        return []
    kind, word = found
    # One body (or heap of them) a place: "the corpse" is the body the fight left.
    word = NEVER_STOLEN if kind == NEVER_STOLEN else word
    key = f"{city['id']}:{place['id']}:{word.lower()}"
    where = f"the {word.lower()} at {place['name']}"
    row = stored(connection, key)
    if row is None and kind == NEVER_STOLEN:
        # A body is only where someone fell: a fight won leaves one (spoils); nothing else does.
        return [f"There is no body at {place['name']}: nobody has fallen here. Describe no corpse."]
    if row is None:
        contents = roll(city['id'], tables(city['id'])[kind], rng or random.SystemRandom())
        connection.execute('INSERT INTO story_finds (key, city_id, place_id, word, contents, seen, created_at) '
                           'VALUES (?, ?, ?, ?, ?, 0, ?)', (key, city['id'], place['id'], word.lower(),
                                                             encode(contents), now))
        row = stored(connection, key)
    what = described(city['id'], row['contents'], city['currency'])
    searched = next((one for one in rolls if one['stat'] == 'Mind' and LOOK.search(one['action'])), None)
    if searched and searched['band'] in MISSED and not row['seen']:
        return [f"Inside {where} is {what}, but the player's character misses it this time: they find nothing."]
    if not row['seen']:
        connection.execute('UPDATE story_finds SET seen=1 WHERE key=?', (key,))
        record.add(connection, 'fact', where, f'Inside: {what}.', now)
    return [f'Inside {where}: {what}. Describe only this; there is nothing else in it.']


def take(connection, city: dict, place: dict, text: str, now: str) -> list[str]:
    """Taking what was found here: items into the pack while they fit, coins into the purse."""
    if not TAKE.search(text):
        return []
    lines = []
    for found in many(connection, 'SELECT * FROM story_finds WHERE city_id=? AND place_id=? AND seen=1',
                      (city['id'], place['id'])):
        row = found | {'contents': decode(found['contents'])}
        if not mentioned(city['id'], row, text):
            continue
        kept, moved = [], []
        stolen = stolen_from(city['id'], place, row['word'])
        for thing in row['contents']:
            if not moved_thing(connection, city, thing, moved, stolen):
                kept.append(thing)
        if moved:
            connection.execute('UPDATE story_finds SET contents=? WHERE key=?', (encode(kept), row['key']))
            lines.append(f"The player's character takes {'; '.join(moved)} from the {row['word']}; it is in their "
                         'pack or purse now.')
            record.add(connection, 'item', "the player's character", f"{'Stole' if stolen else 'Took'} "
                       f"{'; '.join(moved)} from the {row['word']} at {place['name']}.", now)
    return lines


def spoils(connection, city: dict, place: dict, foes: list[dict], wants: str, rng, now: str) -> list[str]:
    """The bodies a fight won leaves here, with what the fallen carried, unseen until searched."""
    if not foes:
        return []
    rng = rng or random.SystemRandom()
    carried = [thing for foe in foes if not foe.get('beast') and not BEASTLY.search(foe['name'])
               for thing in on_body(city['id'], foe, wants, rng)]
    key = f"{city['id']}:{place['id']}:{NEVER_STOLEN}"
    row = stored(connection, key)
    contents = (row['contents'] if row else []) + carried
    connection.execute('INSERT INTO story_finds (key, city_id, place_id, word, contents, seen, created_at) '
                       'VALUES (?, ?, ?, ?, ?, 0, ?) ON CONFLICT(key) DO UPDATE SET contents=excluded.contents, '
                       'seen=0', (key, city['id'], place['id'], NEVER_STOLEN, encode(contents), now))
    names = ', '.join(foe['name'] for foe in foes)
    return [f"The fallen lie where they fell ({names}). What they carried is on them, for the player's character to "
            'search; nothing is found until they look.']


def on_body(city_id: str, foe: dict, wants: str, rng) -> list[dict]:
    """What one fallen foe carried: what their spec names, else a purse by what they were after and their weapon."""
    if 'carries' in foe:
        return [{'item_id': item_id, 'qty': 1} for item_id in foe['carries'] if inventory.item(city_id, item_id)]
    low, high = (inventory.cents(amount) for amount in PURSES.get(wants, PURSE))
    things: list[dict] = [{'coins': rng.randint(low, high)}]
    arms = [item_id for item_id in ARMS.get(min(1, max(0, foe.get('weapon', 0))), ())
            if inventory.item(city_id, item_id)]
    if arms:
        things.append({'item_id': rng.choice(arms), 'qty': 1})
    return things


def mentioned(city_id: str, row: dict, text: str) -> bool:
    """Whether a line that takes something names this find: its container, its money, or one of its items.
    "I take a seat" takes nothing."""
    nouns = {row['word']} | {noun for thing in row['contents'] if 'item_id' in thing
                             for noun in inventory.nouns(inventory.item(city_id, thing['item_id']))}
    return bool(MONEY.search(text)) or any(re.search(rf'\b{re.escape(noun)}(e?s)?\b', text, re.I) for noun in nouns)


def stolen_from(city_id: str, place: dict, word: str) -> bool:
    """Whether what is taken from this container here is stolen: a purse always, a body never, anything else unless the
    place is one nobody owns."""
    kind = next((kind for kind, spec in tables(city_id).items() if word in spec['words']), '')
    if kind in (ALWAYS_STOLEN, NEVER_STOLEN):
        return kind == ALWAYS_STOLEN
    return place.get('kind') not in UNOWNED


def moved_thing(connection, city: dict, thing: dict, moved: list[str], stolen: bool = False) -> bool:
    """Move one found thing to the character if it can be carried; notes stay where they are."""
    if 'coins' in thing:
        inventory.set_purse(connection, inventory.purse(connection) + thing['coins'])
        moved.append(inventory.money_text(thing['coins'], city['currency']))
        return True
    if 'item_id' not in thing:
        return False
    entry = inventory.item(city['id'], thing['item_id'])
    room = inventory.capacity(connection) - inventory.used(inventory.carried(connection, city['id']))
    if entry['slots'] * thing['qty'] > room:
        return False
    inventory.add_item(connection, city['id'], thing['item_id'], thing['qty'], stolen)
    moved.append(entry['name'] if thing['qty'] == 1 else f"{thing['qty']} × {entry['name']}")
    return True


def prompt_text(lines: list[str]) -> str:
    return '## What is there (decided by the game; describe only this)\n' + '\n'.join(
        f'- {line}' for line in lines) if lines else ''
