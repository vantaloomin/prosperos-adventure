"""What the character carries and what the town sells, v0 (requirements "Inventory and equipment", "Shops and
economy"; docs/story.md "Gear and the shop").

Code owns every item and every coin: the narrator is told what the character carries, what is in their purse and,
in a shop, its stock and prices, and it never adds, removes or prices anything. A town's item file
(world/data/items/<city>.json) lists its items with base prices in the city's currency, its shops with their
starting stock, and the kit each premade starts with.

- Money is kept in hundredths of the currency, so sums never drift.
- Carrying is counted in slots: a knife takes a quarter, a sword one. The character carries 5 plus half their
  Vitality, unless the Table's `carry_limit` is 'off'.
- A shop is open while one of its staff is at work (the townsfolk rules). Its stock is finite: what the player
  buys is gone. It buys what it deals in at its sell rate (half the base price).
- Buying and selling happen on the shop window or in the story ("I buy two loaves"); each trade is logged and
  adds a line to the story.
- Shops restock on the story clock: every `restock_days` (RESTOCK_DAYS by default) what was sold comes back up to the
  file's stock, and what the player sold them stays to be sold again.
- Shopkeepers have finite cash (the Table's `shop_cash`, 'finite' by default): a shop's `cash` (else half its starting
  stock's worth) grows with what it sells and shrinks with what it buys, and is topped up as it restocks. A village
  shop can't buy a dragon hoard; 'unlimited' turns this off.
- Stolen goods are tracked (story_inventory.stolen: what was taken from someone's things, dungeon/finds.py). An honest
  shop won't buy them, nor anything illegal; a fence (a shop with `fence`) buys both, at its own low rate.
- Services are sold the same way (category 'service': lodging by comfort tier, meals, drink, baths, stabling, a guide),
  from finite stock that comes back each day (an inn's `restock_days` of 1: so many rooms a night). A service is not
  carried: it is kept as paid for that story day (story_services) and the narrator is told, so it quotes the tier's
  real price and plays the room the character paid for.
- Gear wears (story_inventory.condition): sound, damaged, broken. An attack that fails critically damages the weapon
  swung (dungeon/combat.py): a damaged weapon hits a step softer, a broken one is no weapon at all. Damaged goods sell
  for half, broken ones for a fifth (CONDITION_VALUE). A smith's repair (a service of kind 'repair') mends the worst
  thing carried one step, broken to damaged, damaged to sound.
- Life Cards move markets (dungeon/happenings.py): a shortage or a glut changes a kind of goods' prices in a town for
  some days (story_markets), both what the shops charge and what they pay.
- Haggling is a roll: an Allure action aimed at a better price, in an open shop, moves the shop's prices for the
  rest of the story day by how it landed (a critical a quarter off, a success 15%, a success at a cost 10% and the
  keeper remembers, a critical failure 20% on). One haggle a shop a day.

All of it is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import re
from datetime import date
from pathlib import Path

from dungeon import table, world_data
from dungeon.database import identifier, many, optional
from dungeon.errors import DomainError, require
from dungeon.rules import ladder, marvel
from dungeon.sheet import stats as sheet_stats

ITEMS = Path(__file__).parent / 'world' / 'data' / 'items'
BASE_SLOTS = 5
HAGGLE = re.compile(r'\b(haggl\w*|barter\w*|bargain\w*|discount|cheaper|better (price|deal)|lower (the )?price|'
                    r'knock\w* (it |that |something |a bit )?(down|off))', re.I)
BUY = re.compile(r"\b(buy|buys|buying|purchase|pay for|i'?ll take|i'?ll have|rent\w*|hire|order\w*|book\w*|"
                 r"take an? (\w+ )?(room|bed|bunk|bath|pallet|meal))\b", re.I)
SERVICE = 'service'
STEAL = re.compile(r'\b(pocket\w*|palm\w*|pinch\w*|swip\w*|nick\w*|pilfer\w*|shoplift\w*|steal\w*|stole|'
                   r'slip\w* (\w+ ){0,3}(into|up) my|tuck\w* (\w+ ){0,3}(into|under|in) my)\b', re.I)
CAUGHT = ('critical_failure', 'failure', 'failure_upside')
REPAIR = re.compile(r'\b(repair\w*|mend\w*|fix\w*)\b', re.I)
CONDITIONS = ('sound', 'damaged', 'broken')
# What a shop pays for a thing in this condition, in percent of its offer.
CONDITION_VALUE = {'sound': 100, 'damaged': 50, 'broken': 20}
SELL = re.compile(r'\b(sell|sells|selling|pawn\w*|fence|offload\w*|trade in|get rid of)\b', re.I)
RESTOCK_DAYS = 7
# A shop's cash when its file names none: this share of what its starting stock is worth.
CASH_SHARE = 0.5
# The Life Cards' kinds of goods (dungeon/life/cards.py GOODS) and the item categories they move; drink is food named
# as drink.
GOODS = {'food': ('food',), 'medicine': ('remedy',), 'arms': ('weapon',), 'cloth': ('clothing',), 'ley': ('curio',)}
DRINK = re.compile(r'\b(ale|beer|wine|spirits?|mead|brandy|whiske?y|rum|gin|vodka|liquor|cider)\b', re.I)
# How a haggle moves the shop's prices for the day, in percent, by how the Allure roll landed.
HAGGLED = {'critical_success': -25, 'success': -15, 'success_cost': -10, 'failure_upside': -5, 'failure': 0,
           'critical_failure': 20}
NUMBERS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
           'nine': 9, 'ten': 10, 'a couple of': 2, 'a pair of': 2}


def catalog(city_id: str) -> dict:
    return world_data.read('items', city_id) or {'items': [], 'shops': [], 'kits': {}}


def item(city_id: str, item_id: str) -> dict | None:
    return next((entry for entry in catalog(city_id)['items'] if entry['id'] == item_id), None)


def cents(amount: float) -> int:
    return round(amount * 100)


def money_text(hundredths: int, currency: dict) -> str:
    """'3.40 cr.', or the currency's name when it has no symbol."""
    amount = f'{hundredths / 100:.2f}'
    return f"{amount} {currency.get('symbol') or currency.get('name') or ''}".strip()


# The purse and the pack --------------------------------------------------------------------------

def purse(connection) -> int:
    row = optional(connection, 'SELECT coins FROM story_purse WHERE id=1')
    return row['coins'] if row else 0


def set_purse(connection, coins: int):
    connection.execute('INSERT INTO story_purse (id, coins) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET '
                       'coins=excluded.coins', (coins,))


def carried(connection, city_id: str) -> list[dict]:
    rows = many(connection, 'SELECT * FROM story_inventory WHERE qty > 0 ORDER BY rowid')
    result = []
    for row in rows:
        entry = item(row['city_id'], row['item_id']) or item(city_id, row['item_id'])
        if entry:
            result.append(row | {'name': entry['name'], 'category': entry['category'], 'slots': entry['slots'],
                                 'price': entry['price'], 'legal': entry.get('legal', True)})
    return result


# What "no limit" carries when the Table turns carrying limits off.
UNLIMITED = 9999


def capacity(connection) -> float:
    """Carry slots: 5 plus half the Vitality, unless the Table turns carrying limits off."""
    if table.rule(connection, 'carry_limit') == 'off':
        return UNLIMITED
    return BASE_SLOTS + sheet_stats(connection).get('Vitality', 10) / 2


def used(rows: list[dict]) -> float:
    return sum(row['slots'] * row['qty'] for row in rows)


def add_item(connection, city_id: str, item_id: str, qty: int = 1, stolen: bool = False, condition: str = 'sound'):
    """Into the pack; stolen goods, and worn ones, are kept apart from the same thing come by honestly and sound."""
    row = optional(connection, 'SELECT id FROM story_inventory WHERE item_id=? AND city_id=? AND stolen=? AND '
                   'condition=?', (item_id, city_id, int(stolen), condition))
    if row:
        connection.execute('UPDATE story_inventory SET qty=qty+? WHERE id=?', (qty, row['id']))
    else:
        connection.execute('INSERT INTO story_inventory (id, city_id, item_id, qty, stolen, condition) '
                           'VALUES (?, ?, ?, ?, ?, ?)', (identifier(), city_id, item_id, qty, int(stolen), condition))


def wear(connection, inventory_id: str, steps: int = 1) -> str | None:
    """One of a carried thing worn this many steps worse (or better, when negative): it leaves its stack for the stack
    of its new condition. Returns the new condition, or None when it can go no further."""
    row = optional(connection, 'SELECT * FROM story_inventory WHERE id=? AND qty > 0', (inventory_id,))
    if row is None:
        return None
    after = max(0, min(len(CONDITIONS) - 1, CONDITIONS.index(row['condition']) + steps))
    if CONDITIONS[after] == row['condition']:
        return None
    connection.execute('UPDATE story_inventory SET qty=qty-1 WHERE id=?', (inventory_id,))
    add_item(connection, row['city_id'], row['item_id'], 1, bool(row['stolen']), CONDITIONS[after])
    return CONDITIONS[after]


def worst(connection, city_id: str) -> dict | None:
    """The carried thing most in need of repair: broken before damaged, the dearest first."""
    rows = [row for row in carried(connection, city_id) if row['condition'] != 'sound']
    return max(rows, key=lambda row: (CONDITIONS.index(row['condition']), row['price']), default=None)


def repair(connection, city_id: str, qty: int) -> list[str]:
    """A smith's repairs: the worst thing carried one step better, once for each repair paid for."""
    mended = []
    for _ in range(qty):
        if (row := worst(connection, city_id)) is None:
            break
        mended.append(f"{row['name']} ({wear(connection, row['id'], -1)} now)")
    return mended


def give_kit(connection, city_id: str, premade_id: str | None):
    """The starting purse and pack: the premade's own kit, or the town's default one."""
    kits = catalog(city_id)['kits']
    kit = kits.get(premade_id or '') or kits.get('default')
    connection.execute('DELETE FROM story_inventory')
    set_purse(connection, cents(kit['coins']) if kit else 0)
    for item_id, qty in (kit or {}).get('items', {}).items():
        add_item(connection, city_id, item_id, qty)


def prompt_text(connection, city_id: str, currency: dict, day: str = '') -> str:
    """What the character carries and has in their purse, and what they paid for today, for the narrator."""
    rows = carried(connection, city_id)
    paid = services_text(connection, day)
    if not rows and not purse(connection):
        return paid
    things = ', '.join(f"{row['name']}" + (f" (x{row['qty']})" if row['qty'] > 1 else '') +
                       (' (stolen)' if row['stolen'] else '') +
                       (f" ({row['condition']})" if row['condition'] != 'sound' else '') for row in rows)
    return (f"Carrying (kept by the game; nothing else, and nothing appears or goes without the game): "
            f"{things or 'nothing'}. Purse: {money_text(purse(connection), currency)}. {money_words(currency)}".rstrip()
            + (f'\n{paid}' if paid else ''))


def services_text(connection, day: str) -> str:
    """What the character paid for this story day: a bed tonight, a meal, a bath, a guide."""
    if not day:
        return ''
    rows = many(connection, 'SELECT city_id, place_id, item_id, qty FROM story_services WHERE day=? ORDER BY rowid',
                (day,))
    paid = [f"{entry['name']}" + (f" (x{row['qty']})" if row['qty'] > 1 else '') +
            f" at {place_name(row['city_id'], row['place_id'])}"
            for row in rows if (entry := item(row['city_id'], row['item_id']))]
    return f"Paid for today (kept by the game): {'; '.join(paid)}." if paid else ''


def place_name(city_id: str, place_id: str) -> str:
    city = world_data.read('cities', city_id) or {}
    return next((place['name'] for place in city.get('places', []) if place['id'] == place_id), place_id)


def bed(connection, city_id: str, place_id: str, day: str) -> dict | None:
    """The lodging the character paid for at this place for the night of this story day, if any."""
    for row in many(connection, 'SELECT item_id FROM story_services WHERE city_id=? AND place_id=? AND day=?',
                    (city_id, place_id, day)):
        entry = item(city_id, row['item_id'])
        if entry and entry.get('service') == 'lodging':
            return entry
    return None


def money_words(currency: dict) -> str:
    """How money is said: the symbol alone reads as 'credits' to a model ("three-quarters of a credit")."""
    if not currency.get('symbol') or not currency.get('name'):
        return ''
    return (f"Money here is {currency['name']} ({currency['symbol']} is only how the game writes it); in the "
            'story say amounts in words, as people here would.')


# The shop ----------------------------------------------------------------------------------------

def shop_at(city_id: str, place_id: str) -> dict | None:
    return next((shop for shop in catalog(city_id)['shops'] if shop['place'] == place_id), None)


def stock(connection, city_id: str, shop: dict, day: str = '') -> dict[str, int]:
    """The shop's stock, seeded from its file the first time anyone looks, and restocked on the story clock."""
    rows = many(connection, 'SELECT item_id, qty FROM story_stock WHERE city_id=? AND place_id=?',
                (city_id, shop['place']))
    if not rows:
        for item_id, qty in shop['stock'].items():
            connection.execute('INSERT INTO story_stock (city_id, place_id, item_id, qty) VALUES (?, ?, ?, ?)',
                               (city_id, shop['place'], item_id, qty))
        till(connection, city_id, shop, day)
        return dict(shop['stock'])
    if day and restock(connection, city_id, shop, day):
        rows = many(connection, 'SELECT item_id, qty FROM story_stock WHERE city_id=? AND place_id=?',
                    (city_id, shop['place']))
    return {row['item_id']: row['qty'] for row in rows}


def start_cash(city_id: str, shop: dict) -> int:
    """The shop's cash when it opens and after each restock: its file's, else a share of its stock's worth."""
    if 'cash' in shop:
        return cents(shop['cash'])
    worth = sum((item(city_id, item_id) or {'price': 0})['price'] * qty for item_id, qty in shop['stock'].items())
    return cents(worth * CASH_SHARE)


def till(connection, city_id: str, shop: dict, day: str = '') -> dict:
    """The shop's cash and when it last restocked (story_shops), set up the first time anyone deals with it."""
    row = optional(connection, 'SELECT cash, restocked FROM story_shops WHERE city_id=? AND place_id=?',
                   (city_id, shop['place']))
    if row is None:
        row = {'cash': start_cash(city_id, shop), 'restocked': day}
        connection.execute('INSERT INTO story_shops (city_id, place_id, cash, restocked) VALUES (?, ?, ?, ?)',
                           (city_id, shop['place'], row['cash'], day))
    return row


def pay(connection, city_id: str, shop: dict, amount: int):
    """Money into the shop's till (out of it when negative)."""
    till(connection, city_id, shop)
    connection.execute('UPDATE story_shops SET cash=MAX(0, cash+?) WHERE city_id=? AND place_id=?',
                       (amount, city_id, shop['place']))


def restock(connection, city_id: str, shop: dict, day: str) -> bool:
    """Every restock_days of story time, what was sold comes back up to the file's stock and the till is topped up;
    what the player sold the shop stays on its shelves. Whether it restocked."""
    found = till(connection, city_id, shop, day)
    if not found['restocked']:
        connection.execute('UPDATE story_shops SET restocked=? WHERE city_id=? AND place_id=?',
                           (day, city_id, shop['place']))
        return False
    if (date.fromisoformat(day) - date.fromisoformat(found['restocked'])).days < shop.get('restock_days',
                                                                                          RESTOCK_DAYS):
        return False
    for item_id, qty in shop['stock'].items():
        connection.execute('INSERT INTO story_stock (city_id, place_id, item_id, qty) VALUES (?, ?, ?, ?) '
                           'ON CONFLICT(city_id, place_id, item_id) DO UPDATE SET qty=MAX(qty, excluded.qty)',
                           (city_id, shop['place'], item_id, qty))
    connection.execute('UPDATE story_shops SET restocked=?, cash=MAX(cash, ?) WHERE city_id=? AND place_id=?',
                       (day, start_cash(city_id, shop), city_id, shop['place']))
    return True


def cash(connection, city_id: str, shop: dict) -> int | None:
    """What the shop has to buy with, in hundredths; None when the Table gives shopkeepers unlimited cash."""
    if table.rule(connection, 'shop_cash') == 'unlimited':
        return None
    return till(connection, city_id, shop)['cash']


def offer(shop: dict, entry: dict, percent: int = 0) -> int | None:
    """What the shop pays for one of an item, in hundredths, with the market's move in percent; None if it does not
    deal in it. Only a fence buys stolen goods or anything illegal."""
    crooked = entry.get('stolen') or not entry.get('legal', True)
    if crooked and not shop.get('fence'):
        return None
    if entry['category'] not in shop['buys'] and not shop.get('fence'):
        return None
    paid = (cents(entry['price'] * shop['sell_rate']) * (100 + percent) + 50) // 100
    return max(1, paid * CONDITION_VALUE[entry.get('condition', 'sound')] // 100)


def refusal(shop: dict, entry: dict) -> str:
    """Why the shop won't buy something."""
    if entry.get('stolen') and not shop.get('fence'):
        return "The keeper won't touch stolen goods."
    if not entry.get('legal', True) and not shop.get('fence'):
        return "The keeper won't be seen buying that."
    return "This shop doesn't buy that."


# Markets ----------------------------------------------------------------------------------------

def move_market(connection, city_id: str, goods: str, shift: int, until: str):
    """A Life Card moves a kind of goods' prices in a town until a day (story_markets)."""
    connection.execute('INSERT INTO story_markets (id, city_id, goods, shift, until) VALUES (?, ?, ?, ?, ?)',
                       (identifier(), city_id, goods, shift, until))


def market(connection, city_id: str, entry: dict, day: str) -> int:
    """How far the market has moved an item's price today, in percent (the moves add up)."""
    if not day:
        return 0
    rows = many(connection, 'SELECT goods, shift FROM story_markets WHERE city_id=? AND until>=?', (city_id, day))
    return sum(row['shift'] for row in rows if moves(row['goods'], entry))


def moves(goods: str, entry: dict) -> bool:
    if goods == 'any':
        return True
    if goods == 'drink':
        return entry['category'] == 'food' and bool(DRINK.search(entry['name']))
    return entry['category'] in GOODS.get(goods, ())


def market_text(connection, city_id: str, day: str) -> str:
    rows = many(connection, 'SELECT goods, SUM(shift) AS shift FROM story_markets WHERE city_id=? AND until>=? '
                'GROUP BY goods', (city_id, day)) if day else []
    moved = [f"{row['goods']} {row['shift']:+d}%" for row in rows if row['shift']]
    return f"Prices moved by what is going on: {', '.join(moved)}." if moved else ''


# Haggling ---------------------------------------------------------------------------------------

def haggled(connection, city_id: str, shop: dict, day: str) -> int:
    """The shop's prices today, in percent off (negative) or on, after a haggle; 0 when there was none today."""
    row = optional(connection, 'SELECT percent FROM story_haggles WHERE city_id=? AND place_id=? AND day=?',
                   (city_id, shop['place'], day))
    return row['percent'] if row else 0


# The keeper's Resolve when the shop's file names none (requirements "Persuasion vs Resolve").
KEEPER_RESOLVE = 10


def opposed(shop: dict, band: str, rng=None) -> tuple[str, str]:
    """A haggle is a contest: the keeper rolls Resolve (the shop's `resolve`, else KEEPER_RESOLVE), and when they do
    better than the character, the character's result lands a step worse. Returns the band and the keeper's."""
    keeper = marvel.roll(shop.get('resolve', KEEPER_RESOLVE), 'normal', rng)['band']
    rank = ladder.BANDS.index
    return (ladder.BANDS[max(0, rank(band) - 1)] if rank(keeper) > rank(band) else band), keeper


def haggled_today(connection, city_id: str, shop: dict, day: str) -> bool:
    return bool(optional(connection, 'SELECT 1 FROM story_haggles WHERE city_id=? AND place_id=? AND day=?',
                         (city_id, shop['place'], day)))


def haggle(connection, city_id: str, shop: dict, band: str, day: str) -> int | None:
    """Settle a haggle by how the roll landed; None when the shop was already haggled with today."""
    if haggled_today(connection, city_id, shop, day):
        return None
    connection.execute('INSERT INTO story_haggles (city_id, place_id, day, percent) VALUES (?, ?, ?, ?) '
                       'ON CONFLICT(city_id, place_id) DO UPDATE SET day=excluded.day, percent=excluded.percent',
                       (city_id, shop['place'], day, HAGGLED[band]))
    return HAGGLED[band]


def priced(entry: dict, percent: int) -> int:
    """An item's price today in hundredths, rounding half a hundredth up."""
    return max(1, (cents(entry['price']) * (100 + percent) + 50) // 100)


def haggle_text(percent: int) -> str:
    return f'{-percent}% off today' if percent < 0 else f'{percent}% dearer today' if percent else ''


# Buying in the story -----------------------------------------------------------------------------

def nouns(entry: dict) -> set[str]:
    """What a player might call an item: its name before any comma, and that name's last word ("rope", "sword"), also
    in the singular."""
    name = entry['name'].split(',')[0].strip().lower()
    last = name.split(' ')[-1]
    # "Tallow candles": "a candle" names them too.
    single = {last[:-1]} if last.endswith('s') and not last.endswith('ss') and len(last) > 3 else set()
    return {name, last} | single


def wanted(text: str, stock_rows: list[dict]) -> list[tuple[str, int]]:
    """The stock a player's line buys ("I buy two loaves and a candle"): (item id, quantity), or nothing."""
    # At a smith's, "I have her mend my sword" pays for a repair; it does not buy a sword.
    repairs = [row for row in stock_rows if 'repair' in nouns(row)]
    if repairs and REPAIR.search(text):
        return [(repairs[0]['item_id'], 1)]
    return named(text, stock_rows) if BUY.search(text) else []


def named(text: str, stock_rows: list[dict]) -> list[tuple[str, int]]:
    """The stock a line names, with how many: (item id, quantity)."""
    found = []
    for row in stock_rows:
        for noun in sorted(nouns(row), key=len, reverse=True):
            match = re.search(rf"(?:\b(\d+|{'|'.join(NUMBERS)})\s+(?:\w+\s+){{0,2}})?\b{re.escape(noun)}(e?s)?\b",
                              text, re.I)
            if match:
                count = match.group(1)
                found.append((row['item_id'], int(count) if count and count.isdigit() else NUMBERS.get(
                    (count or 'one').lower(), 1)))
                break
    return found


def lift(connection, city_id: str, shop: dict, text: str, rolls: list[dict], stock_rows: list[dict]) -> list[str]:
    """Shoplifting: what a line pockets from the shop's stock, by its roll. Got away with, it is in the pack, stolen,
    and gone from the stock; caught, nothing is taken and the keeper saw it."""
    roll = next((roll for roll in rolls if STEAL.search(roll['action'])), None)
    taken = named(text, stock_rows) if STEAL.search(text) and roll else []
    if not taken:
        return []
    names = ', '.join(item(city_id, item_id)['name'] for item_id, _ in taken)
    if roll['band'] in CAUGHT:
        return [f"The keeper sees the player's character try to pocket {names}: caught in the act, and nothing is "
                'taken.']
    have = {row['item_id']: row['qty'] for row in stock_rows}
    room = capacity(connection) - used(carried(connection, city_id))
    lines = []
    for item_id, qty in taken:
        entry, qty = item(city_id, item_id), min(qty, have.get(item_id, 0))
        if not qty or entry['slots'] * qty > room:
            continue
        room -= entry['slots'] * qty
        connection.execute('UPDATE story_stock SET qty=qty-? WHERE city_id=? AND place_id=? AND item_id=?',
                           (qty, city_id, shop['place'], item_id))
        add_item(connection, city_id, item_id, qty, stolen=True)
        what = entry['name'] if qty == 1 else f"{qty} × {entry['name']}"
        lines.append(f"The player's character pockets {what} unseen; it is in their pack, stolen, and nothing is "
                     f"paid{'' if roll['band'] != 'success_cost' else ' (though the keeper may have noticed something)'}.")
    return lines


def buy_in_story(connection, city_id: str, shop: dict, text: str, stock_rows: list[dict], day: str, now: str,
                 currency: dict) -> list[str]:
    """Buy what the player's line asks for, at today's price; a refusal is a line too, so the narrator plays it."""
    lines = []
    for item_id, qty in wanted(text, stock_rows):
        try:
            done = buy(connection, city_id, shop, item_id, qty, now, day)
        except DomainError as refused:
            lines.append(f"No sale of {item(city_id, item_id)['name']}: {refused.message}")
            continue
        what = done['name'] if done['qty'] == 1 else f"{done['qty']} × {done['name']}"
        kept = ('it is theirs today' if item(city_id, item_id)['category'] == SERVICE else 'it is in their pack')
        if done.get('mended'):
            kept = f"the smith mends {'; '.join(done['mended'])}"
        lines.append(f"The player's character buys {what} for {money_text(done['amount'], currency)}; "
                     f'{kept} and the money is paid.')
    return lines


def sell_in_story(connection, city_id: str, shop: dict, text: str, day: str, now: str, currency: dict) -> list[str]:
    """Sell what the player's line offers the shop ("I sell the knife"), at what it pays today; a refusal is a line."""
    if not SELL.search(text):
        return []
    lines = []
    found = offered(text, carried(connection, city_id))
    if not found:
        return ["No sale: the player's character carries no such thing, so nothing is sold and no money changes "
                'hands.']
    for row, qty in found:
        try:
            done = sell(connection, city_id, shop, row['id'], qty, now, day)
        except DomainError as refused:
            lines.append(f"No sale of {row['name']}: {refused.message}")
            continue
        what = done['name'] if done['qty'] == 1 else f"{done['qty']} × {done['name']}"
        lines.append(f"The player's character sells {what} for {money_text(done['amount'], currency)}; it is out of "
                     'their pack and the money is in their purse.')
    return lines


# "Sell her everything I can spare": what the character can do without. "Everything": all but the clothes on them.
SPARE = re.compile(r"\b((can|could) spare|to spare|don'?t need|do without|can live without)\b", re.I)
EVERYTHING = re.compile(r"\b(everything|all (of )?my (stuff|things|gear|goods|loot)|the lot)\b", re.I)
KEPT = ('clothing',)
# Spared, the character keeps their food and one of each other thing; stolen goods and curios all go.
NEEDED = ('clothing', 'food')


def spared(text: str, pack: list[dict]) -> list[tuple[dict, int]]:
    """What "everything I can spare" or "everything" offers, stolen goods first."""
    rows = sorted(pack, key=lambda row: not row['stolen'])
    if SPARE.search(text):
        spare = [(row, row['qty'] if row['stolen'] or row['category'] == 'curio' else
                  0 if row['category'] in NEEDED else row['qty'] - 1) for row in rows]
        return [(row, qty) for row, qty in spare if qty > 0]
    if EVERYTHING.search(text):
        return [(row, row['qty']) for row in rows if row['category'] not in KEPT]
    return []


def offered(text: str, pack: list[dict]) -> list[tuple[dict, int]]:
    """The pack's things a selling line names, with how many (all of them for "all my ..."), stolen ones first; or
    everything it can spare."""
    found, named = [], set()
    for row in sorted(pack, key=lambda row: not row['stolen']):
        if row['item_id'] in named:
            continue
        for noun in sorted(nouns(row), key=len, reverse=True):
            match = re.search(rf"(?:\b(\d+|all|{'|'.join(NUMBERS)})\s+(?:\w+\s+){{0,2}})?\b{re.escape(noun)}(e?s)?\b",
                              text, re.I)
            if match:
                count = (match.group(1) or 'one').lower()
                qty = row['qty'] if count == 'all' else int(count) if count.isdigit() else NUMBERS.get(count, 1)
                found.append((row, min(qty, row['qty'])))
                named.add(row['item_id'])
                break
    return found or spared(text, pack)


# The shop window ---------------------------------------------------------------------------------

def window(connection, city_id: str, shop: dict, open_now: bool, keeper: str, day: str = '') -> dict:
    found = stock(connection, city_id, shop, day)
    percent = haggled(connection, city_id, shop, day)
    order = [entry['id'] for entry in catalog(city_id)['items']]
    items = [(item(city_id, item_id), found[item_id])
             for item_id in sorted(found, key=lambda key: order.index(key) if key in order else len(order))]
    pack = carried(connection, city_id)
    return {'place_id': shop['place'], 'open': open_now, 'keeper': keeper, 'haggled': percent,
            'fence': bool(shop.get('fence')), 'cash': cash(connection, city_id, shop),
            'market': market_text(connection, city_id, day),
            'stock': [{'item_id': entry['id'], 'name': entry['name'], 'category': entry['category'],
                       'price': priced(entry, percent + market(connection, city_id, entry, day)), 'qty': qty,
                       'slots': entry['slots']}
                      for entry, qty in items if entry and qty > 0],
            'offers': {row['id']: price for row in pack
                       if (price := offer(shop, row, market(connection, city_id, row, day))) is not None}}


def shop_prompt(view: dict, currency: dict) -> str:
    if not view['open']:
        return '## The shop here\nIt is closed now; nobody is behind the counter.'
    lines = [f"- {row['name']}: {money_text(row['price'], currency)} ({row['qty']} left)" for row in view['stock']]
    haggled = f"\nToday's prices after haggling: {haggle_text(view['haggled'])}." if view.get('haggled') else ''
    haggled += f"\n{view['market']}" if view.get('market') else ''
    if view.get('fence'):
        haggled += '\nThe keeper fences stolen goods on the quiet, and pays little for them.'
    if view.get('cash') is not None:
        haggled += f"\nThe keeper has {money_text(view['cash'], currency)} to buy with, and no more."
    return ('## The shop here (stock and prices kept by the game; quote them exactly, invent nothing)\n'
            f"{view['keeper'] or 'The shopkeeper'} sells:\n" + '\n'.join(lines) + haggled +
            f'\n{money_words(currency)}'.rstrip() + '\nThe shopkeeper can name what is there and its price, but nothing changes hands until the game says '
            'so.')


def log(connection, now: str, kind: str, city_id: str, item_id: str, qty: int, amount: int):
    connection.execute('INSERT INTO story_trades (id, kind, city_id, item_id, qty, amount, created_at) '
                       'VALUES (?, ?, ?, ?, ?, ?, ?)', (identifier(), kind, city_id, item_id, qty, amount, now))


def buy(connection, city_id: str, shop: dict, item_id: str, qty: int, now: str, day: str = '') -> dict:
    entry = item(city_id, item_id)
    have = stock(connection, city_id, shop, day).get(item_id, 0)
    require(entry is not None and have > 0, 'The shop has none of that.', 404)
    require(qty <= have, f'The shop has only {have}.', 409)
    cost = priced(entry, haggled(connection, city_id, shop, day) + market(connection, city_id, entry, day)) * qty
    require(cost <= purse(connection), "You can't afford that.", 409)
    pack = carried(connection, city_id)
    service = entry['category'] == SERVICE
    require(entry.get('service') != 'repair' or worst(connection, city_id), 'Nothing you carry needs repair.', 409)
    require(service or used(pack) + entry['slots'] * qty <= capacity(connection), "You can't carry that much more.",
            409)
    connection.execute('UPDATE story_stock SET qty=qty-? WHERE city_id=? AND place_id=? AND item_id=?',
                       (qty, city_id, shop['place'], item_id))
    set_purse(connection, purse(connection) - cost)
    pay(connection, city_id, shop, cost)
    mended = repair(connection, city_id, qty) if entry.get('service') == 'repair' else []
    if service:
        connection.execute('INSERT INTO story_services (id, city_id, place_id, item_id, qty, day, created_at) '
                           'VALUES (?, ?, ?, ?, ?, ?, ?)', (identifier(), city_id, shop['place'], item_id, qty, day, now))
    else:
        add_item(connection, city_id, item_id, qty)
    log(connection, now, 'buy', city_id, item_id, qty, cost)
    return {'name': entry['name'], 'qty': qty, 'amount': cost} | ({'mended': mended} if mended else {})


def sell(connection, city_id: str, shop: dict, inventory_id: str, qty: int, now: str, day: str = '') -> dict:
    row = optional(connection, 'SELECT * FROM story_inventory WHERE id=? AND qty > 0', (inventory_id,))
    require(row is not None, "You don't have that.", 404)
    require(qty <= row['qty'], f"You have only {row['qty']}.", 409)
    entry = item(row['city_id'], row['item_id'])
    entry = entry and entry | {'stolen': bool(row['stolen']), 'condition': row['condition']}
    price = offer(shop, entry, market(connection, city_id, entry, day)) if entry else None
    require(price is not None, refusal(shop, entry or {}), 409)
    stock(connection, city_id, shop, day)
    has = cash(connection, city_id, shop)
    if has is not None and price * qty > has:
        raise DomainError("The keeper hasn't the money for that." if has < price else
                          f'The keeper can only afford {has // price} of those.', 409)
    connection.execute('UPDATE story_inventory SET qty=qty-? WHERE id=?', (qty, inventory_id))
    connection.execute('INSERT INTO story_stock (city_id, place_id, item_id, qty) VALUES (?, ?, ?, ?) '
                       'ON CONFLICT(city_id, place_id, item_id) DO UPDATE SET qty=qty+excluded.qty',
                       (city_id, shop['place'], row['item_id'], qty))
    set_purse(connection, purse(connection) + price * qty)
    pay(connection, city_id, shop, -price * qty)
    log(connection, now, 'sell', city_id, row['item_id'], qty, price * qty)
    return {'name': entry['name'], 'qty': qty, 'amount': price * qty}

