"""Progression (requirements "Progression"; docs/story.md "Progression").

Prospero characters grow by use, plus milestones, and dark tracks bite.

- **Use.** A roll of the character's that mattered (one that succeeded, or one with a danger riding on it) marks its
  stat. After a night's rest, code rolls for each marked stat, Basic Roleplaying style: over GROW times the stat on
  a d100, the stat rises a point, so a high stat grows slowly. The marks clear either way.
- **Milestones.** A town's own quest done, or a rise in tier (dungeon/tiers.py), gives MILESTONE points to the stat
  the character has used most since the last one.
- **Dark tracks** (rules/dark.json: corruption, addiction, infamy). Code raises them: Life Cards' `corruption`
  effects, and what the Continuity model saw the character do each turn (a pact, a drug, a public atrocity). Each
  threshold grants power (a stat boost) and rolls a lasting change to body, mind or how people treat them, among
  those the intensity settings allow; the top of a track costs the player the character.

Marks, uses and dark tracks are game state, branched with the story (dungeon/timeline.py SAVED).
"""
import functools
import json
import random
import re
from pathlib import Path

from dungeon import bonds, record, sheet
from dungeon.database import decode, encode, many, optional
from dungeon.life import cards
from dungeon.rules import brp, fate, ironsworn, ladder, marvel, narrative

DARK = Path(__file__).parent / 'rules' / 'dark.json'
GROW = 3
MILESTONE = 2


@functools.cache
def tracks() -> dict[str, dict]:
    return json.loads(DARK.read_text(encoding='utf-8'))['tracks']


def raise_stat(connection, stat: str, amount: int, now: str) -> tuple[int, int]:
    before = sheet.stats(connection)[stat]
    after = min(marvel.STAT_RANGE[1], before + amount)
    if after != before:
        sheet.set_stats(connection, {stat: after}, now)
    return before, after


# Growth by use -----------------------------------------------------------------------------------

def mattered(roll: dict) -> bool:
    return roll.get('actor') == sheet.PERSONA and (ladder.succeeded(roll['band']) or bool(roll.get('threat')))


def mark(connection, rolls: list[dict], message_id: str):
    """The stats the line's rolls that mattered used, once for the line however often it is told."""
    for roll in filter(mattered, rolls):
        connection.execute('INSERT INTO story_marks (stat, marked, uses, last_message) VALUES (?, 1, 1, ?) ON '
                           'CONFLICT(stat) DO UPDATE SET marked=1, uses=uses + (last_message IS NOT ?), '
                           'last_message=?', (roll['stat'], message_id, message_id, message_id))


def marked(connection) -> list[str]:
    return [row['stat'] for row in many(connection, 'SELECT stat FROM story_marks WHERE marked=1 ORDER BY stat')]


def grow(connection, now: str, rng=None) -> list[str]:
    """After a night's rest: each marked stat may rise a point."""
    rng = rng or random.SystemRandom()
    lines = []
    # Growth by use is Prospero's; another ruleset grows its own way (5E: experience and levels). BRP's experience
    # checks are rolled now, as written.
    if sheet.ruleset(connection) == brp.ID:
        found = sheet.native(connection)
        lines = brp.improve(found, rng)
        sheet.set_native(connection, found, now)
        return lines
    if sheet.ruleset(connection) != marvel.ID:
        connection.execute('UPDATE story_marks SET marked=0')
        return lines
    for stat in marked(connection):
        value = sheet.stats(connection)[stat]
        if rng.randint(1, 100) > GROW * value:
            before, after = raise_stat(connection, stat, 1, now)
            if after > before:
                lines.append(f"What the character has been through has taught them: {stat} grows from {before} to "
                             f'{after}.')
    connection.execute('UPDATE story_marks SET marked=0')
    return lines


def milestone(connection, why: str, now: str) -> str:
    """A milestone's bigger boost, to the stat used most since the last one."""
    if sheet.ruleset(connection) in (ironsworn.ID, brp.ID, narrative.ID):
        # Ironsworn grows by its vows' experience (dungeon/sworn.py fulfil), BRP by its experience checks, Narrative
        # Only by what the character is known for (the record), which the judge reads.
        return ''
    if sheet.ruleset(connection) == fate.ID:
        # Fate's significant milestone: one approach a step better (dungeon/rules/fate.py grow).
        found = sheet.native(connection)
        line = fate.grow(found)
        sheet.set_native(connection, found, now)
        return line
    if sheet.ruleset(connection) != marvel.ID:
        # 5E grows by XP: a milestone is worth the level's high encounter budget (dungeon/combat5e.py).
        from dungeon import combat5e
        return ' '.join(combat5e.gain(connection, combat5e.milestone_xp(connection), f'a milestone: {why}', now))
    row = optional(connection, 'SELECT stat FROM story_marks WHERE uses > 0 ORDER BY uses DESC, stat LIMIT 1')
    if row is None:
        return ''
    connection.execute('UPDATE story_marks SET uses=0')
    before, after = raise_stat(connection, row['stat'], MILESTONE, now)
    return f"A milestone ({why}): the character's {row['stat']} grows from {before} to {after}." if after > before \
        else ''


# Dark tracks -------------------------------------------------------------------------------------

def dark(connection) -> dict[str, dict]:
    return {row['track']: row | {'changes': decode(row['changes'])}
            for row in many(connection, 'SELECT * FROM story_dark')}


def word(track: dict, points: int) -> str:
    if points >= track['top']:
        return track['words'][-1]
    return track['words'][sum(points >= threshold for threshold in track['thresholds'])]


def darken(connection, track_id: str, shift: int, levels: dict | None, now: str, rng=None) -> list[str]:
    """A dark track moves: power and a lasting change at each threshold it crosses going up, the end at its top."""
    track = tracks().get(track_id)
    if track is None or not shift:
        return []
    rng = rng or random.SystemRandom()
    row = dark(connection).get(track_id) or {'points': 0, 'changes': [], 'lost': 0}
    before = row['points']
    after = max(0, min(track['top'], before + shift))
    changes, lines = list(row['changes']), []
    for threshold in track['thresholds']:
        if before < threshold <= after:
            stat, boost = track['power']['stat'], track['power']['shift']
            old, new = raise_stat(connection, stat, boost, now)
            lines.append(f"{track['name']} gives as it takes: the character's {stat} grows from {old} to {new}.")
            allowed = [item for item in track['changes'] if item['text'] not in changes
                       and cards.allowed(item, levels or {})]
            if allowed:
                change = rng.choice(allowed)
                changes.append(change['text'])
                lines.append(f"A lasting change ({track['name'].lower()}): {change['text']}")
    lost = after >= track['top']
    if lost and not row['lost']:
        lines.append(track['lost'])
    connection.execute('INSERT INTO story_dark (track, points, changes, lost) VALUES (?, ?, ?, ?) ON CONFLICT(track) '
                       'DO UPDATE SET points=excluded.points, changes=excluded.changes, lost=excluded.lost',
                       (track_id, after, encode(changes), int(lost)))
    for line in lines:
        record.add(connection, 'fact', 'The character', line, now)
    if word(track, after) != word(track, before) and not lost:
        lines.append(f"The character's {track['name'].lower()}: now {word(track, after)}.")
    return lines


def lost(connection) -> str | None:
    """The dark track that has cost the player the character, if one has."""
    return next((tracks()[key]['name'] for key, row in dark(connection).items() if row['lost'] and key in tracks()),
                None)


def dark_ask() -> str:
    """Added to the Continuity model's question every turn: what the character did that feeds a dark track."""
    listed = '; '.join(f"{key}: {track['ask']}" for key, track in tracks().items())
    return ('\n\nOnly if the player\'s character this turn did something that feeds one of these, add "dark": '
            f'["one of: {", ".join(tracks())}"] to your answer ({listed}).')


def dark_schema() -> dict:
    """The part of the extraction schema (dungeon/record.py) that answers dark_ask."""
    return {'dark': {'type': 'array', 'items': {'type': 'string', 'enum': list(tracks())}}}


def darkened(answer: str) -> list[str]:
    match = re.search(r'\{.*\}', answer, re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        return []
    items = data.get('dark') if isinstance(data, dict) else None
    return sorted({item for item in items or [] if isinstance(item, str) and item in tracks()})


# For the narrator and the screen -----------------------------------------------------------------

def prompt_text(connection) -> str:
    lines = []
    for key, row in dark(connection).items():
        track = tracks().get(key)
        if track and row['points']:
            lasting = f" Lasting: {' '.join(row['changes'])}" if row['changes'] else ''
            lines.append(f"- {track['name']}: {word(track, row['points'])}.{lasting}")
    return ('## What the character is becoming (kept by the game; show it, never name the track)\n'
            + '\n'.join(lines)) if lines else ''


def view(connection, shown: bool) -> dict:
    tracked = []
    for key, row in dark(connection).items():
        track = tracks().get(key)
        if track and row['points']:
            tracked.append({'id': key, 'name': track['name'], 'word': word(track, row['points']),
                            'changes': row['changes']} | ({'points': row['points'], 'top': track['top']}
                                                          if shown else {}))
    return {'marked': marked(connection), 'dark': tracked, 'bonds': bonds.track(connection, shown)}
