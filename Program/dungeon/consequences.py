"""The consequence engine: how a choice in the world turns out, from what the app knows (from Companion, 2026-10-09).

Some things in the world have more than one way to go: whether two feuding friends make up, whether someone gets
the promotion. The engine reads the facts that bear on it (how close the people are, a character's own description,
the drama level), turns them into odds from a small table per choice (world/data/consequences.json) and rolls seeded
dice against those odds. No model decides anything and the model never sees the odds. Odds come from the tables
alone, so the same world and seed always give the same result.

Companion recorded outcomes and the marks they left per companion timeline; Dungeon keeps only the engine until the
game's own records (the record) use it.
"""
import json
import random
import re
from functools import cache

from dungeon.world import catalog

# Words in a character's own description that the tables' `sheet` rules look for.
WORDS = {
    'driven': r'driven|ambitious|hard[- ]working|workaholic|go-getter|career[- ]focused',
    'unfocused': r'lazy|procrastinat\w*|disorganized|scatterbrained|easily distracted|unmotivated',
    'assertive': r'assertive|blunt|outspoken|direct|confident|no-nonsense|fearless',
    'shy': r'shy|timid|introvert\w*|conflict[- ]avoidant|avoids conflict|quiet',
    'forgiving': r'forgiving|easygoing|easy-going|laid[- ]back|kind-hearted|peacemaker',
    'stubborn': r'stubborn|proud|grudges?|hot[- ]headed|short temper|temper|unforgiving',
    'restless': r'restless|adventurous|wanderlust|spontaneous|free[- ]spirited|thrill[- ]seek\w*',
    'homebody': r'homebody|home-loving|nester|cozy|cosy|settled|creature of habit',
}
SHEET_FIELDS = ('identity', 'personality', 'voice', 'background', 'flaws')
NEGATED = re.compile(r"\b(?:not|never|isn't|hardly|no)\s+(?:\w+\s+)?$", re.IGNORECASE)


@cache
def tables() -> dict:
    return json.loads((catalog.DATA / 'consequences.json').read_text(encoding='utf-8'))['choices']


def has_choice(choice: str) -> bool:
    return choice in tables()


# Reading the state ----------------------------------------------------------------------------------

def sheet_text(definition: dict) -> str:
    parts = []
    for field in SHEET_FIELDS:
        value = definition.get(field) or ''
        parts.append(' '.join(value) if isinstance(value, list) else value)
    return ' '.join(parts)


def sheet_has(definition: dict, group: str) -> bool:
    """Whether a character's own description says this about them, not negated ("not shy")."""
    text = sheet_text(definition)
    for found in re.finditer(rf"\b(?:{WORDS[group]})\b", text, re.IGNORECASE):
        if not NEGATED.search(text[:found.start()]):
            return True
    return False


def matches(rule: dict, facts: dict) -> bool:
    if rule['reader'] == 'sheet':
        return rule['has'] in facts.get('sheet', ())
    value = facts.get(rule['reader'])
    if value is None:
        return False
    if 'is' in rule:
        return value == rule['is']
    return ('at_least' not in rule or value >= rule['at_least']) and ('at_most' not in rule or value <= rule['at_most'])


def move(times: float) -> str:
    """Which way a reason pushed its option ("More likely because…")."""
    return 'out' if times == 0 else 'possible' if times == 1 else 'more' if times > 1 else 'less'


def odds(choice: str, facts: dict, names: dict) -> list[dict]:
    """Each option's odds (0 to 1, summing to 1) with the reasons that moved it and which way each one pushed
    (`moves`, one per reason: more, less, out or possible): [{option, odds, reasons, moves}]."""
    weights, reasons, moves = [], [], []
    for option in tables()[choice]['options']:
        weight, why, ways = option['weight'], [], []
        for rule in option.get('rules', ()):
            if matches(rule, facts):
                weight *= rule['times']
                why.append(rule['why'].format(**names))
                ways.append(move(rule['times']))
        weights.append(weight)
        reasons.append(why)
        moves.append(ways)
    total = sum(weights) or 1
    return [{'option': index, 'odds': round(weight / total, 3), 'reasons': why, 'moves': ways}
            for index, (weight, why, ways) in enumerate(zip(weights, reasons, moves, strict=True))]


def roll(seed: str, found: list[dict]) -> int:
    """The option the seeded dice land on, using the odds as they are."""
    point, running = random.Random(f'consequence:{seed}').random(), 0.0
    for item in found:
        running += item['odds']
        if point < running:
            return item['option']
    return found[-1]['option']
