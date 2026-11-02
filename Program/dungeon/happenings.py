"""Life Cards in play (requirements "Intensity and tone": drama; "Time and travel"; docs/life-cards.md;
docs/story.md "Life Cards").

The world's deck (dungeon/life/cards.py) is drawn into the story by code, with the same seeded dice:
- **A day in town** draws once, on the first line of each story day spent in a town on the travel map.
- **A journey** draws once, for the road it ends on, unless a road encounter already stopped it.
- **A rest out in the open** draws once; a card that brings foes ends the rest like a bad night.

How often a scene draws anything, and which cards can turn up, follow the **drama** level (the world's own, or the
player's: quiet, uneasy, eventful, merciless); the intensity levels leave out cards it does not allow. Drama never
touches roll odds.

A drawn card's hidden truth goes in the record as the world's (and what the character sees, as their belief when
it is not the whole truth); the narrator gets what the character sees and any choice it puts to them. Code applies
the effects the game can keep so far: stress, a wound, coin in an unskilled day's wages, food gained or lost, time,
someone's feelings, a fight, and markets (dungeon/inventory.py). Rumor, quest, faction, fate and pursuer effects wait
for their systems (factions, off-page beats, word gets around); their truth is kept in the record meanwhile.

Draws are game state (story_cards), branched with the story; each line's draw is kept with it, so telling the turn
again draws nothing new.
"""
import re
from datetime import date, timedelta

from dungeon import (
    bonds,
    combat,
    director,
    factions,
    feelings,
    growth,
    injuries,
    inventory,
    quests,
    record,
    stress,
    sworn,
    table,
    tiers,
    travel,
    world_data,
)
from dungeon.database import encode, many
from dungeon.errors import require
from dungeon.life import cards

DEFAULT_DRAMA = 'uneasy'
# Off only for tests that are about something else (tests/conftest.py).
ACTIVE = True
# Cards that need someone the game cannot name here: a bond, until the character has one (dungeon/bonds.py), a beat's
# absent character; and a faction, where no faction has a hand.
UNNAMED = re.compile(r'\{(bond|them)\}')
BOND = re.compile(r'\{bond\}')
THEM = re.compile(r'\{them\}')
FACTION = re.compile(r'\{faction\}')
# The scenes whose draw the story shows as a card under the player's line, and how a title's placeholders read there.
SHOWN = ('town', 'road', 'rest')
PLAIN = {'bond': 'your companion', 'them': 'someone you know', 'npc': 'someone', 'faction': 'the powers here',
         'town': 'town', 'pc': 'you'}
WAGE_ID = 'day-wage'
DEFAULT_WAGE = 100
# Who a card's fight brings, at the first tier (dungeon/tiers.py scales them to the region's): the name of one, of them all, how many,
# Vitality, Resolve, weapon and what they want; the dreadful ones are horror (dungeon/stress.py).
FOE_FIELDS = ('name', 'group', 'count', 'vitality', 'resolve', 'weapon', 'wants')
HORRORS = ('undead', 'fiend', 'fey')
# Foes whose bodies carry nothing worth taking (dungeon/finds.py spoils).
BEASTS = ('beasts', 'undead', 'fiend')
FOES = {kind: dict(zip(FOE_FIELDS, row)) | ({'horror': True} if kind in HORRORS else {}) |
        ({'beast': True} if kind in BEASTS else {}) for kind, row in {
    'bandits': ('bandit', 'bandits', 2, 10, 8, 0, 'rob'),
    'deserters': ('deserter', 'deserters', 2, 11, 7, 1, 'rob'),
    'gnolls': ('gnoll', 'gnolls', 2, 12, 10, 1, 'kill'),
    'orcs': ('orc raider', 'orc raiders', 2, 13, 12, 1, 'kill'),
    'beasts': ('starving wolf', 'starving wolves', 2, 11, 8, 0, 'kill'),
    'undead': ('restless dead', 'one of the restless dead', 1, 14, 20, 1, 'kill'),
    'corsairs': ('corsair', 'corsairs', 2, 11, 10, 1, 'capture'),
    'hunters': ('bounty hunter', 'bounty hunters', 2, 12, 12, 1, 'capture'),
    'fiend': ('fiend', 'a fiend', 1, 16, 20, 1, 'kill'),
    'cultists': ('cultist', 'cultists', 3, 9, 14, 0, 'capture'),
    'watch': ('watchman', 'the watch', 2, 11, 10, 0, 'capture'),
    'fey': ('fey hunter', 'a fey hunter', 1, 13, 16, 1, 'capture'),
}.items()}


# What to draw from --------------------------------------------------------------------------------

def where(city_id: str, place_id: str) -> dict | None:
    """The deck and region a place draws from, and whether it is a town, from the travel map."""
    found = travel.node_at(city_id, place_id)
    if found is None or not found[0].get('world'):
        return None
    travel_map, node = found
    region = travel_map['regions'][node['region']]
    return {'world': travel_map['world'], 'region': region.get('cards'), 'tier': region.get('tier', 1),
            'area': node['region'], 'town': node['safe'] and node['city'] != 'vallarith-road', 'map': travel_map, 'node': node['id']}


def drama(connection, data: dict) -> str:
    chosen = table.rule(connection, 'drama')
    return (data.get('intensity') or {}).get('drama') or DEFAULT_DRAMA if chosen == 'world' else chosen


def unnamed(world: str, faction: bool = False, them: bool = False, bonded: bool = False) -> set[str]:
    """The cards that name someone the game cannot fill in here: {them} only an off-page beat can (dungeon/beats.py),
    {bond} only a scene while the character has a bond."""
    who = BOND if them else THEM if bonded else UNNAMED
    return {item['id'] for item in cards.cards(world) if any(
        who.search(item.get(field) or '') or (not faction and FACTION.search(item.get(field) or ''))
        for field in ('title', *cards.TEXT)) or (not faction and any(
            effect['kind'] in ('clock', 'reputation') for effect in item['effects']))}


def recent(connection, world: str, day: date) -> set[str]:
    since = (day - timedelta(days=cards.deck(world).get('repeat_days', 0))).isoformat()
    return {row['card_id'] for row in many(connection, 'SELECT card_id FROM story_cards WHERE day >= ? AND card_id '
                                                       'IS NOT NULL', (since,))}


def draw(connection, scene: str, seed: str, city_id: str, place_id: str, data: dict, level: dict,
         day: date, has: set[str] | None = None, skip: set[str] | None = None, forced: bool = False) -> dict | None:
    """One draw for a scene at a place: {'card', 'veiled', 'map'}, or None when nothing happens. A beat names
    `has` (its character's needs, such as captive) and `skip` (the cards drawn lately); `forced` skips the roll for
    whether anything happens."""
    found = where(city_id, place_id)
    if found is None or not ACTIVE:
        return None
    world = found['world']
    beat = scene == 'beat'
    bound = [] if beat else bonds.whole(connection)
    has = has if beat else ({'injured'} if combat.condition(connection)['level'] else set()) | \
        ({'bond'} if bound else set())
    powers = factions.local(world, found['node'])
    skipped = (skip or set()) if beat else recent(connection, world, day)
    drawn = cards.draw(world, scene, seed, cards.DRAMA.index(drama(connection, data)), level['levels'],
                       has or set(), skipped | unnamed(world, bool(powers), beat, bool(bound)), found['region'],
                       veils=frozenset(level['veils']), forced=forced)
    if not drawn['card']:
        return None
    faction = powers[sum(map(ord, seed)) % len(powers)] if powers else None
    bond = bound[sum(map(ord, seed)) % len(bound)] if bound else None
    return drawn | {'map': found['map'], 'world': world, 'faction': faction, 'found': found, 'bond': bond}


def keep(connection, message_id: str, scene: str, day: date, card_id: str | None, lines: list[str]):
    connection.execute('INSERT OR REPLACE INTO story_cards (message_id, scene, day, card_id, lines) VALUES '
                       '(?, ?, ?, ?, ?)', (message_id, scene, day.isoformat(), card_id, encode(lines)))


def drawn_today(connection, scene: str, day: date) -> bool:
    return bool(many(connection, 'SELECT 1 FROM story_cards WHERE scene=? AND day=?', (scene, day.isoformat())))


# Showing a drawn card ---------------------------------------------------------------------------------

def with_cards(connection, rows: list[dict], veils: set[str]) -> list[dict]:
    """The Life Cards drawn on each of the player's lines, to show under it: title, tone and picture, never the
    truth. A card on a veiled topic shows only the world's card back."""
    drawn: dict[str, list[str]] = {}
    for row in many(connection, f"SELECT message_id, card_id FROM story_cards WHERE card_id IS NOT NULL AND scene IN "
                                f"({', '.join('?' * len(SHOWN))}) ORDER BY scene DESC", SHOWN):
        drawn.setdefault(row['message_id'], []).append(row['card_id'])
    found = []
    for row in rows:
        world = drawn.get(row['id']) and row['role'] == 'user' and tiers.world_of(row['city_id'])
        shown = [view for card_id in drawn[row['id']] if (view := card_view(world, card_id, veils))] if world else []
        found.append({**row, 'cards': shown} if shown else row)
    return found


def card_view(world: str, card_id: str, veils: set[str]) -> dict | None:
    card = cards.card(world, card_id)
    if card is None:
        return None
    if cards.veiled(card, veils):
        return {'title': 'Veiled', 'tone': 'grey', 'art': card_art(world, 'back'), 'veiled': True}
    title = re.sub(r'\{(\w+)\}', lambda match: PLAIN.get(match[1], match[0]), card['title'])
    return {'title': title, 'tone': card['tone'], 'art': card_art(world, card_id) or card_art(world, 'back'),
            'veiled': False}


def card_art(world: str, name: str) -> str | None:
    """The picture of a card (scripts/art/cards.py made them), as the story serves it, if the world has one."""
    return f'/api/story/art/card/{world}/{name}.webp' if world_data.asset(world, f'cards/{name}.webp') else None


def card_file(world: str, name: str) -> bytes:
    found = world_data.asset(world, f'cards/{name}') if name.endswith('.webp') and '/' not in name else None
    require(found is not None, 'There is no such card picture.', 404)
    return found


# Playing a card -------------------------------------------------------------------------------------

def fill(text: str, names: dict[str, str]) -> str:
    return re.sub(r'\{(pc|npc|town|faction|them|bond)\}', lambda match: names[match.group(1)], text)


def npc(people: list[dict]) -> dict | None:
    return people[0]['sheet'] if people else None


def wage(data: dict) -> int:
    found = next((price for price in data.get('prices', []) if price['id'] == WAGE_ID), None)
    return inventory.cents((found['low'] + found['high']) / 2) if found else DEFAULT_WAGE


def food_city(travel_map: dict, food: str) -> str | None:
    return next((node['city'] for node in travel_map['nodes'] if inventory.item(node['city'], food)), None)


def coin(connection, effect: dict, context: dict) -> list[str]:
    amount = effect['wages'] * wage(context['data'])
    before = inventory.purse(connection)
    inventory.set_purse(connection, max(0, before + amount))
    moved = inventory.money_text(abs(inventory.purse(connection) - before), context['data']['currency'])
    return [f"The character gains {moved}." if amount > 0 else f"It costs the character {moved}."] if moved else []


def supply(connection, effect: dict, context: dict) -> list[str]:
    travel_map, food = context['map'], context['map']['food']
    if effect['shift'] > 0:
        if gained := sworn.restock(connection, effect['shift']):
            return [f"Supplies: +{gained} supply."]
        if sworn.played(connection) or not food:
            return []
        city = food_city(travel_map, food[0])
        if city is None:
            return []
        inventory.add_item(connection, city, food[0], effect['shift'])
        return [f"Food for the pack: {effect['shift']} more of {inventory.item(city, food[0])['name']}."]
    lost, _ = travel.eat(connection, food, -effect['shift'])
    return [f"Food lost from the pack: {', '.join(lost)}."] if lost else []


def wound(connection, effect: dict, context: dict) -> list[str]:
    level = min(combat.DOWN, cards.WOUNDS.index(effect['level']) + 1)
    if level <= combat.condition(connection)['level']:
        return []
    combat.set_condition(connection, level)
    lines = [f"The character is hurt in it: now {combat.word(connection, level)}."]
    if level >= combat.DOWN and (left := injuries.roll(connection, context['now'], context['title'], context['rng'],
                                                         context['logged'])):
        lines.append(left)
    return lines


def feeling(connection, effect: dict, context: dict) -> list[str]:
    """How the one here (`npc`) or the character's bond (`bond`) comes to feel about the character."""
    person = {'npc': context['npc'], 'bond': context.get('bond')}.get(effect['who'])
    if person is None:
        return []
    feelings.change(connection, person['key'], {effect['axis']: effect['shift']}, context['title'])
    return []


def fight(connection, effect: dict, context: dict) -> list[str]:
    if combat.fight(connection) is not None:
        return []
    # At the region's tier, or sent by an enemy above it (dungeon/tiers.py).
    spec, sent = tiers.foe(connection, context['found'], FOES[effect['foes']], 1) if context.get('found') else \
        (FOES[effect['foes']], '')
    combat.save_fight(connection, {'round': 0, 'wants': spec['wants'], 'foes': combat.foes_from(spec)})
    return [f"It comes to a fight: {spec['group']} {'close' if spec['count'] > 1 else 'closes'} in.", *filter(None, [sent])]


def clocked(connection, effect: dict, context: dict) -> list[str]:
    faction = context['faction']
    clock = faction and factions.first_open(connection, faction)
    if clock:
        factions.tick(connection, context['world'], faction, clock, effect['shift'], context['now'], context['logged'])
    return []


def reputed(connection, effect: dict, context: dict) -> list[str]:
    return [factions.shift(connection, context['faction'], effect['shift'])] if context['faction'] else []


def feared(connection, effect: dict, context: dict) -> list[str]:
    return stress.add(connection, 'card', '', context['now'], context['rng'], context['logged'],
                      amount=effect['amount'], cause='what just happened')


def marketed(connection, effect: dict, context: dict) -> list[str]:
    """A shortage or a glut: a kind of goods' prices in this town move for some days (dungeon/inventory.py)."""
    if not context.get('city') or not effect['shift']:
        return []
    until = (date.fromisoformat(context['day']) + timedelta(days=effect['days'] - 1)).isoformat()
    inventory.move_market(connection, context['city'], effect['goods'], effect['shift'], until)
    goods = 'everything' if effect['goods'] == 'any' else effect['goods']
    return [f"Prices of {goods} here are {abs(effect['shift'])}% {'up' if effect['shift'] > 0 else 'down'} for "
            f"{effect['days']} day{'s' if effect['days'] != 1 else ''}."]


def corrupted(connection, effect: dict, context: dict) -> list[str]:
    return growth.darken(connection, 'corruption', effect['shift'], context.get('levels'),
                         context['logged'], context['rng'])


def fated(connection, effect: dict, context: dict) -> list[str]:
    """What becomes of the person the card names: the one here (`npc`) is marked so (story_fates, as an off-page
    beat marks them, dungeon/beats.py); dead, the record holds them dead. The unnamed ones are only the card's text."""
    person = context['npc']
    if effect['who'] != 'npc' or person is None:
        return []
    name = person.get('full') or person.get('name') or 'someone'
    connection.execute('INSERT INTO story_fates (key, name, state, since) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO '
                       'UPDATE SET state=excluded.state, since=excluded.since', (person['key'], name, effect['state'],
                                                                                 context['logged']))
    if effect['state'] == 'dead':
        record.add(connection, 'death', name, context['truth'], context['logged'], truth='world')
    elif effect['state'] == 'turned':
        feelings.change(connection, person['key'], {'trust': -3, 'affection': -2}, context['title'])
    return [f"From now on {name} is {effect['state']}: play them so."]


def rumored(connection, effect: dict, context: dict) -> list[str]:
    """Word goes round town. About the character, the townsfolk may have heard it and treat them by it; true or not,
    the record keeps what is said as belief, and a false one as the world's lie."""
    said = context['seen']
    if effect['about'] == 'pc':
        record.add(connection, 'fact', "the player's character", f'Word going round town: {said}', context['logged'],
                   truth='world' if not effect['true'] else 'both')
        return ["Word of it is going round town: the people the character meets may have heard it, and treat them "
                'by it.']
    if not effect['true']:
        record.add(connection, 'fact', context['title'], f'A false rumor: {said}', context['logged'], truth='world')
    return ['It is the talk of the town; people repeat it as they heard it.']


def quested(connection, effect: dict, context: dict) -> list[str]:
    """Someone asks something of the character, due on the story clock: a job in the journal, the card's truth its
    hidden side (dungeon/quests.py)."""
    if not context.get('city'):
        return []
    person = {'npc': context['npc'], 'bond': context.get('bond')}.get(effect['from'])
    giver = (person.get('full') or person.get('name')) if person else \
        context['faction']['name'] if effect['from'] == 'faction' and context['faction'] else None
    due = context['now'] + timedelta(days=effect['days'])
    quests.create(connection, 'job', context['city'], context['title'][:1].upper() + context['title'][1:],
                  context['pressure'] or context['seen'], context['truth'], 'Nothing comes of it, for now.',
                  due.isoformat(), giver=giver, faction_id=context['faction']['id'] if effect['from'] == 'faction'
                  and context['faction'] else None)
    who = giver or 'someone'
    return [f"{who[:1].upper() + who[1:]} wants something of the character, within {effect['days']} days: it is in "
            'their journal now.']


def pursued(connection, effect: dict, context: dict) -> list[str]:
    """Someone is on the character's trail, `days` behind: a nemesis who catches up then (dungeon/director.py)."""
    director.pursue(connection, context['truth'], effect['days'], context['now'], context['logged'])
    return [f"Someone is on the character's trail, about {effect['days']} day{'s' if effect['days'] != 1 else ''} "
            'behind. The character does not know who.']


APPLY = {'coin': coin, 'supply': supply, 'wound': wound, 'feeling': feeling, 'fight': fight, 'stress': feared,
         'clock': clocked, 'reputation': reputed, 'corruption': corrupted, 'market': marketed, 'fate': fated,
         'rumor': rumored, 'quest': quested, 'pursuer': pursued}


def play(connection, drawn: dict, context: dict) -> tuple[list[str], int]:
    """A drawn card in play: the record keeps its truth, the narrator gets what the character sees, and code applies
    what it can. Returns the lines for the narrator and the minutes it costs."""
    card = drawn['card']
    person = npc(context['people'])
    names = {'pc': context['name'] or 'the character', 'town': context['data']['name'],
             'faction': drawn['faction']['name'] if drawn.get('faction') else 'the powers here',
             'npc': (person.get('full') or f"the {person.get('occupation') or person['role']}") if person
             else 'a stranger', 'bond': drawn['bond']['name'] if drawn.get('bond') else 'a friend'}
    truth, seen = fill(card['truth'], names), fill(card['seen'], names)
    context = context | {'npc': person, 'title': fill(card['title'], names).lower(), 'faction': drawn.get('faction'),
                         'world': drawn.get('world'), 'found': drawn.get('found'), 'truth': truth, 'seen': seen,
                         'bond': drawn.get('bond'),
                         'pressure': fill(card['pressure'], names) if card.get('pressure') else ''}
    record.add(connection, 'fact', fill(card['title'], names), truth, context['logged'], truth='world')
    if card['accuracy'] != 'true':
        record.add(connection, 'fact', fill(card['title'], names), seen, context['logged'], truth='belief')
    lines = [seen[:1].upper() + seen[1:]]
    if card.get('pressure'):
        lines.append(f"It puts a choice to the player: {fill(card['pressure'], names)}")
    if drawn['veiled']:
        lines.append('Veiled: whatever it holds that the player veiled happens off the page; fade to black.')
    minutes = 0
    for effect in card['effects']:
        if effect['kind'] == 'time':
            minutes += effect['hours'] * 60
        elif effect['kind'] in APPLY:
            lines += APPLY[effect['kind']](connection, effect, context)
    return lines, minutes


def prompt_text(lines: list[str]) -> str:
    return ('## What the world brings (a Life Card, decided by the game; weave it in)\n'
            + '\n'.join(f'- {line}' for line in lines)) if lines else ''
