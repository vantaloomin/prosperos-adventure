"""Narrative Only (docs/requirements.md "Narrative Only"): no stats and no dice.

- **The sheet** is the character's own description (the persona's About), with two short optional lists the player
  may fill in, what they are good at and bad at.
- **A verdict, not a roll.** A judge (dungeon/judge.py) gives each action one of four verdicts with a one-line
  reason, from who the character is, what the player wrote, who they are dealing with and the world. The verdict is
  fixed before the narrator writes, as a roll is. On the shared ladder: No is a failure, No, but a failure with an
  upside, Yes, but a success at a cost, Yes a success.
- **With no judge** (no model, or one that fails), the Referee's difficulty decides it in code, with no dice: easy is
  Yes, normal Yes, but, hard No, but, and very hard or extreme No. The feelings and injuries already move that
  difficulty (dungeon/feelings.py adjust, dungeon/injuries.py adjust).
- **Nothing is shown.** The verdicts reach the narrator only, never a roll card; the GM view shows them.
"""
ID = 'narrative'
NAME = 'Narrative'
HINT = 'No stats or dice: what happens comes from who your character is and what they say.'
VERDICTS = {'no': 'No', 'no_but': 'No, but', 'yes_but': 'Yes, but', 'yes': 'Yes'}
BANDS = {'no': 'failure', 'no_but': 'failure_upside', 'yes_but': 'success_cost', 'yes': 'success'}
BY_DIFFICULTY = {'easy': 'yes', 'normal': 'yes_but', 'hard': 'no_but', 'very_hard': 'no', 'extreme': 'no'}
MOST_LIST = 6
MOST_ITEM = 80


def build(good_at: list[str] | None = None, bad_at: list[str] | None = None) -> dict:
    """The sheet: what the player says the character is good and bad at (both may be empty)."""
    tidy = lambda items: [item.strip()[:MOST_ITEM] for item in (items or []) if item.strip()][:MOST_LIST]  # noqa: E731
    return {'good_at': tidy(good_at), 'bad_at': tidy(bad_at)}


def verdict_for(difficulty: str) -> str:
    return BY_DIFFICULTY.get(difficulty, 'yes_but')


def result(verdict: str | None, reason: str, difficulty: str) -> dict:
    """An action's outcome as a roll row keeps it: the verdict (the judge's, else the difficulty's) and its reason,
    with no die."""
    verdict = verdict if verdict in VERDICTS else verdict_for(difficulty)
    said = VERDICTS[verdict] + (f': {reason.strip()}' if reason and reason.strip() else '')
    return {'natural': 0, 'die': 0, 'bonus': 0, 'shift': 0, 'total': 0, 'target': None, 'rolls': [],
            'band': BANDS[verdict], 'skill': said[:300], 'ruleset': ID, 'verdict': verdict}


def described(sheet: dict) -> str:
    """The character's lists in a line, for the narrator and the judge."""
    parts = [f"good at {', '.join(sheet['good_at'])}" if sheet.get('good_at') else '',
             f"bad at {', '.join(sheet['bad_at'])}" if sheet.get('bad_at') else '']
    return ('By their own account: ' + '; '.join(part for part in parts if part) + '.') if any(parts) else ''


def view(sheet: dict) -> dict:
    return {'ruleset': ID, 'ruleset_name': NAME, 'good_at': sheet.get('good_at', []), 'bad_at': sheet.get('bad_at', [])}
