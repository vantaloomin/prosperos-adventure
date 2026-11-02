"""Prospero, the house ruleset (Mabry Curve's dice): d100 plus a stat die, less a difficulty shift, onto six bands.

Read from Mabry Curve's roll log (rng/roll.py itself was not in the archive):
- A natural 1 to 10 is a critical failure, whatever the bonus.
- Otherwise the natural roll plus the stat die, less the difficulty shift, picks the band: 30 or less is a failure
  (however low the shift takes it), 31 to 50 a failure with an upside, 51 to 70 a success at a cost, 71 to 89 a
  success, and 90 or more a critical success.
- The stat die grows with the stat (STAT_DICE). An actor with no stats rolls with no die.
"""
import random

ID = 'marvel'
NAME = 'Prospero'
STATS = ('Mind', 'Allure', 'Resolve', 'Vitality', 'Essence', 'Luck')
# What each stat covers, for the Referee, the narrator and the sheet.
MEANINGS = {'Mind': 'reason, perception, knowledge, skill with the hands',
            'Allure': 'charm, persuasion, deception, performance',
            'Resolve': 'will, nerve, intimidation, resisting pain or influence',
            'Vitality': 'strength, speed, fighting, endurance',
            'Essence': 'magic, faith, the uncanny',
            'Luck': 'chance, stealth, timing'}
STAT_RANGE = (1, 30)
DEFAULT_STAT = 10
# The shift is taken off the total, so a harder task needs a higher roll.
DIFFICULTIES = {'easy': -10, 'normal': 0, 'hard': 10, 'very_hard': 20, 'extreme': 30}
# (lowest stat, die sides), highest first: the die a stat rolls.
STAT_DICE = ((14, 12), (12, 10), (10, 8), (8, 6), (1, 4))
CRITICAL_NATURAL = 10
# The highest total of each band below critical success, worst first.
CEILINGS = ((30, 'failure'), (50, 'failure_upside'), (70, 'success_cost'),
            (89, 'success'))


def die_for(value: int | None) -> int | None:
    """The sides of the stat die; None for an actor with no stats."""
    if value is None:
        return None
    return next(sides for lowest, sides in STAT_DICE if value >= lowest)


def band(natural: int, total: int) -> str:
    if natural <= CRITICAL_NATURAL:
        return 'critical_failure'
    return next((name for ceiling, name in CEILINGS if total <= ceiling), 'critical_success')


def roll(stat_value: int | None, difficulty: str = 'normal', rng: random.Random | None = None) -> dict:
    """One check: the natural d100, the stat die and its roll, the shift, the total and the band."""
    rng = rng or random.SystemRandom()
    sides = die_for(stat_value)
    natural = rng.randint(1, 100)
    bonus = rng.randint(1, sides) if sides else 0
    shift = DIFFICULTIES[difficulty]
    total = natural + bonus - shift
    return {'natural': natural, 'die': sides, 'bonus': bonus, 'shift': shift, 'total': total,
            'band': band(natural, total)}
