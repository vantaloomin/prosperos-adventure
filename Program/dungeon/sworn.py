"""Ironsworn's tracks outside a fight (dungeon/rules/ironsworn.py; docs/story.md "Supply, spirit and vows").

- **Supply.** A day on the road spends a point of supply in place of a food from the pack (dungeon/travel.py), and
  a Life Card's food comes as supply. Resupply, read from the action's words, brings it back.
- **Spirit** follows the stress track (dungeon/stress.py): 5 while steady, down to 0 at the top.
- **Vows** are progress tracks. A line that pursues an open vow by name and lands a roll reaches a milestone, once a
  story day per vow: ticks by the vow's rank (dungeon/rules/ironsworn.py MILESTONE). A quest or an oath done is
  Fulfill Your Vow, the deed that ends it a last milestone: a progress roll of the filled boxes against two challenge
  dice. A strong hit gives experience by its rank, a weak hit one less, a miss none (the story already says it
  ended; the vow is not what was sworn). Experience is spent by code.
- **Bonds** is a progress track too: each bond forged (dungeon/bonds.py) marks a tick.
"""
import math
import re

from dungeon import sheet
from dungeon.rules import ironsworn

LANDED = ('success_cost', 'success', 'critical_success')
# "I swear an iron vow to find whoever is breaking the saws": the line swears it, with no model needed.
IRON_VOW = re.compile(r"\b(?:swear\w*|swore|sworn|make|made)\s+(?:an?\s+)?iron\s+vow\b[^.!?]*?\b(?:to|that)\s+"
                      r"(?:I\s+will\s+|I'll\s+)?([^.!?,;\n]+)", re.I)
# "The vow is done", "I fulfil my vow": Fulfill Your Vow, which the player calls when they judge it kept.
DONE = re.compile(r"\b(?:the|my|this|that)\s+vow\s+is\s+(?:done|fulfill?ed|kept|complete|met)\b|"
                  r"\bI\s+(?:have\s+)?(?:fulfill?|fulfill?ed|kept|keep)\s+(?:my|the|this)\s+(?:iron\s+)?vow\b", re.I)
MOST_TITLE = 60


def played(connection) -> dict | None:
    """The character's Ironsworn sheet, when the campaign plays Ironsworn."""
    return sheet.native(connection) if sheet.ruleset(connection) == ironsworn.ID else None


def spend_supply(connection, days: int) -> tuple[int, int] | None:
    """(spent, left) for `days` on the road; None when the campaign keeps food in the pack."""
    found = played(connection)
    if found is None:
        return None
    spent = max(0, min(days, found['supply']))
    found['supply'] -= spent
    sheet.set_native(connection, found, '')
    return spent, found['supply']


def restock(connection, amount: int) -> int | None:
    """Supply gained (up to 5), or None when the campaign keeps food in the pack."""
    found = played(connection)
    if found is None:
        return None
    before = found['supply']
    found['supply'] = min(5, before + amount)
    sheet.set_native(connection, found, '')
    return found['supply'] - before


def resupplied(connection, roll: dict) -> str:
    """What a Resupply roll brought back."""
    gained = restock(connection, ironsworn.RESUPPLY.get(roll['band'], 0)) if roll.get('move') == 'resupply' else None
    return f"Resupply: +{gained} supply, now {played(connection)['supply']} of 5." if gained else ''


def follow_stress(connection, points: int, top: int):
    found = played(connection)
    spirit = 5 - math.ceil(points * 5 / top)
    if found and found['spirit'] != spirit:
        found['spirit'] = spirit
        sheet.set_native(connection, found, '')


def rank(quest: dict) -> str:
    return 'dangerous' if quest.get('kind') == 'oath' else ironsworn.rank_of(quest.get('tier'))


def swore(connection, quest: dict):
    """Swear an Iron Vow: the vow's progress track, empty, on the sheet from the start."""
    found = played(connection)
    if found is not None and quest['id'] not in found.setdefault('vows', {}):
        found['vows'][quest['id']] = {'title': quest['title'], 'rank': rank(quest), 'ticks': 0, 'day': ''}
        sheet.set_native(connection, found, '')


def iron_vow(text: str) -> dict | None:
    """The vow a line swears in so many words, as an oath to no one but the character (dungeon/quests.py vow)."""
    found = IRON_VOW.search(text)
    if not found:
        return None
    sworn = found.group(1).strip().rstrip(',;:')
    title = sworn if len(sworn) <= MOST_TITLE else sworn[:MOST_TITLE].rsplit(' ', 1)[0] + '…'
    return {'to': '', 'text': sworn[0].upper() + sworn[1:], 'days': None, 'title': f'Vow: {title}'}


def milestone(connection, quest: dict, day: str) -> str:
    """Reach a Milestone on a vow, once a story day: its progress ticks by its rank."""
    found = played(connection)
    if found is None:
        return ''
    vows = found.setdefault('vows', {})
    track = vows.setdefault(quest['id'], {'title': quest['title'], 'rank': rank(quest), 'ticks': 0, 'day': ''})
    if track['day'] == day:
        return ''
    track['ticks'], track['day'] = ironsworn.mark(track['ticks'], track['rank']), day
    sheet.set_native(connection, found, '')
    return (f"Reach a Milestone on the vow {quest['title']}: progress {track['ticks'] // ironsworn.TICKS_PER_BOX} of "
            f"{ironsworn.BOXES}.")


def fulfil(connection, quest: dict, rng=None) -> str:
    """Fulfill Your Vow: a progress roll on the vow's track; experience by its rank and the hit, spent on the
    character's assets."""
    found = played(connection)
    if found is None:
        return ''
    track = found.get('vows', {}).pop(quest['id'], None) or {'ticks': 0}
    ranked = rank(quest)
    # The deed that ends it is a milestone of its own.
    rolled = ironsworn.progress_roll(ironsworn.mark(track['ticks'], ranked), rng)
    weak, miss = rolled['band'] == 'success_cost', rolled['band'] in ('failure', 'critical_failure')
    gained = 0 if miss else ironsworn.vow_xp(ranked, weak)
    found['xp'] = found.get('xp', 0) + gained
    grown = ironsworn.spend(found)
    sheet.set_native(connection, found, '')
    hit = 'a miss: the vow is not what was sworn' if miss else 'a weak hit: more remains to be done' if weak \
        else 'a strong hit'
    first, second = rolled['challenge']
    return (f"Fulfill Your Vow, {ranked} ({quest['title']}), progress {rolled['score']} vs {first} and {second}, "
            f"{hit}: {gained} experience" + (f"; {'; '.join(grown)}." if grown else f", {found['xp']} unspent."))


def forge_bond(connection, name: str):
    """Forge a Bond marks a tick on the bonds track."""
    found = played(connection)
    if found is not None:
        found['bonds'] = min(ironsworn.BOXES * ironsworn.TICKS_PER_BOX, found.get('bonds', 0) + 1)
        sheet.set_native(connection, found, '')


def bonds_line(connection) -> str:
    found = played(connection)
    if not found or not found.get('bonds'):
        return ''
    plural = 's' if found['bonds'] != 1 else ''
    return f"Forge a Bond: the bonds track has {found['bonds']} tick{plural}."


def sworn_to(connection, text: str, only: bool = False) -> dict | None:
    """The open quest a line names (dungeon/quests.py named), else the one sworn vow that a word of its title names
    ("the saws"), else, when `only`, the one sworn vow there is."""
    from dungeon import quests
    if quest := quests.named(connection, text):
        return quest
    tracked = (played(connection) or {}).get('vows') or {}
    open_vows = [quest for quest in quests.rows(connection, 'open') if quest['id'] in tracked]
    hinted = [quest for quest in open_vows if quests.says(text, quests.stems(quest['title']))]
    if len(hinted) == 1:
        return hinted[0]
    return open_vows[0] if only and len(open_vows) == 1 else None


def declared(connection, city_id: str, text: str, rolls: list[dict], day: str, now) -> list[str]:
    """A line's own vow moves under Ironsworn: fulfilling a vow the player calls kept, a milestone on one it pursues,
    then swearing a new one it names."""
    from dungeon import quests
    if played(connection) is None:
        return []
    lines = []
    if DONE.search(text) and (quest := sworn_to(connection, text, only=True)):
        lines += [line for line in quests.end(connection, quest['id'], 'done', text, now.isoformat())
                  if line.startswith('Fulfill Your Vow')]
    else:
        lines += pursued(connection, text, rolls, day)
    if oath := iron_vow(text):
        quest_id = quests.vow(connection, city_id, text, oath, now)
        title = next((quest['title'] for quest in quests.rows(connection, 'open') if quest['id'] == quest_id), '')
        lines.append(f'Swear an Iron Vow: {title}.')
    return lines


def pursued(connection, text: str, rolls: list[dict], day: str) -> list[str]:
    """A line that pursues an open vow by name and lands a roll reaches a milestone on it."""
    if played(connection) is None or not any(roll.get('band') in LANDED for roll in rolls):
        return []
    quest = sworn_to(connection, text)
    line = milestone(connection, quest, day) if quest else ''
    return [line] if line else []


def prompt_text(lines: list[str]) -> str:
    return '## Vows (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''
