"""Life Cards: the Life deck and random tables, the game's small random events (from Companion, Hit List #33 and #35).

A day, a road or a rest can pick up a surprise: a changed habit, an old joke coming back, a favor for a neighbour, a
late bus. The seeded dice (dungeon/life/chance.py, from Prospero's Study) decide whether something happens and, if
so, which card it is. The cards come from two places that share one picker: the Life deck
(world/data/life_deck.json), and Study's d100 random tables (world/data/random_tables.json), whose rows join the deck
as extra cards weighted by their dice ranges.

The drama level sets how often a card turns up and which cards can: quiet keeps to the gentle ones. A card whose
`needs` aren't met is left out, and a card drawn lately steps aside so the weeks don't repeat. No model decides
anything. Companion drew one card a day for the companion; Dungeon draws them for road encounters, rest
interruptions and the drama level (docs/requirements.md), wired up from Milestone 2.
"""
import json
from functools import cache

from dungeon.life import chance
from dungeon.world import catalog


@cache
def deck() -> dict:
    return json.loads((catalog.DATA / 'life_deck.json').read_text(encoding='utf-8'))


@cache
def tables() -> dict:
    return json.loads((catalog.DATA / 'random_tables.json').read_text(encoding='utf-8'))


def table_cards() -> list[dict]:
    """The random tables' rows as cards: each weighted by its share of the top table's roll and of its own table's,
    so the two together take `tables_weight` next to the deck."""
    found, data = [], tables()
    top = data['tables'][data['start']]['rows']
    top_width = sum(row['high'] - row['low'] + 1 for row in top)
    for parent in top:
        if parent['kind'] != 'event' or not parent.get('child'):
            continue
        child = data['tables'][parent['child']]
        rows = [row for row in child['rows'] if row['kind'] == 'event']
        width = sum(row['high'] - row['low'] + 1 for row in child['rows'])
        for row in rows:
            share = (parent['high'] - parent['low'] + 1) / top_width * (row['high'] - row['low'] + 1) / width
            found.append({'id': row['id'], 'source': child['name'], 'title': row['title'], 'tone': row['tone'],
                          'needs': row.get('needs', []), 'drama': row.get('drama', 0), 'text': row['text'],
                          'told': row['told'], 'share': row.get('share'), 'on': True,
                          'weight': max(1, round(deck()['tables_weight'] * share))})
    return found


@cache
def cards() -> tuple[dict, ...]:
    return tuple([{**card, 'source': 'Life deck'} for card in deck()['cards']] + table_cards())


def card(card_id: str | None) -> dict | None:
    return next((item for item in cards() if item['id'] == card_id), None)


# Drawing -------------------------------------------------------------------------------------------------

def eligible(level: int, has: set[str], recent: set[str]) -> list[dict]:
    return [item for item in cards() if item['on'] and item['drama'] <= level and set(item['needs']) <= has
            and item['id'] not in recent]


def pick(pool: list[dict], draws: chance.Draws) -> dict:
    point = draws.die(sum(item['weight'] for item in pool), 'deck', 'card')
    for item in pool:
        if point <= item['weight']:
            return item
        point -= item['weight']
    raise AssertionError('The deck has no card')


def draw(seed: str, level: int, has: set[str], recent: set[str], forced: bool = False) -> tuple[dict | None, float]:
    """(card or None, its odds) for one day. `forced` skips the roll for whether anything happens (the user asked
    for another card)."""
    draws, chances = chance.Draws(seed), deck()['chance']
    happens = chances[min(level, len(chances) - 1)]
    if not forced and draws.die(100, 'deck', 'moment') > happens:
        return None, round(1 - happens / 100, 3)
    pool = eligible(level, has, recent)
    if not pool:
        return None, 1.0
    found = pick(pool, draws)
    share = found['weight'] / sum(item['weight'] for item in pool)
    return found, round(share if forced else happens / 100 * share, 3)
