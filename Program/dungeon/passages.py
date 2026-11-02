"""Flagged passages and Rewrite (requirements "Flagged passages and Rewrite"; docs/story.md "Rewrite").

What a turn's checks find and do not fix is kept with the narration as flags, one per paragraph, each with why: a
strong prose tell the rewrite pass left (or never ran on, over budget), someone the record says is dead when the
contradiction check gave way for time, or, in a world set in a past year, something from a later one (Instagram in
2009, dungeon/world/decades.py). The player can rewrite a flagged paragraph, or any passage they select, with
an optional note. A rewrite changes the wording only: the dice, the bands and the record's facts stay, so nothing is
rolled again. The wording before the last rewrite is kept, so the player can switch back.

The reason never gives away hidden truth: a clash with a death the character does not know of says only that the
passage conflicts with the story so far.
"""
import re

from dungeon import pace
from dungeon.database import many
from dungeon.narration import prose
from dungeon.world import decades

HIDDEN = 'It conflicts with the story so far.'
MOST_NOTE = 300

SYSTEM = """You are rewriting one passage of a roleplaying game's narration in new words. Keep every event, \
outcome, name and fact in it exactly as it is: nothing new happens, and nothing that happened is undone or softened. \
Never contradict the game's record below. Keep the point of view, tense, paragraphing and roughly the length. Never \
use em dashes or double hyphens. Reply with the rewritten passage only, with no comments before or after it."""


def paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r'\n{2,}', text) if part.strip()]


def span(text: str, passage: str) -> tuple[int, int] | None:
    """Where a passage the player selected sits in the narration; the browser's line breaks may differ."""
    words = passage.split()
    if not words:
        return None
    match = re.search(r'\s+'.join(re.escape(word) for word in words), text)
    return match.span() if match else None


def dead_reasons(connection, names: list[str]) -> dict[str, str]:
    """Why each of the dead the narration names is a problem, said only as far as the character knows it."""
    rows = {row['subject'].lower(): row for row in many(
        connection, "SELECT subject, truth FROM record_entries WHERE kind='death' AND removed=0")}
    return {name: f"The record says {rows[name]['subject']} is dead." if name in rows and rows[name]['truth'] != 'world'
            else HIDDEN for name in names}


def later_reasons(text: str, year: int | None) -> dict[str, str]:
    """Each thing from after the story's past year the text names, with why it is a problem."""
    return {finding['text']: decades.why(finding, year) for finding in decades.anachronisms(text, year)}


def flags(text: str, dead: dict[str, str], unchecked: set[str] | None = None,
          later: dict[str, str] | None = None) -> list[dict]:
    """The paragraphs with a problem left in them, each with why. `dead` is the dead no check has cleared, and
    `unchecked` the paragraphs they may still be in (all of them unless given); `later` the things named from after
    a past-year story's year (later_reasons)."""
    parts = paragraphs(text)
    why: dict[str, list[str]] = {part: [] for part in parts}
    names: dict[str, dict[str, str]] = {part: {} for part in parts}
    for finding in prose.check(text):
        part = next((part for part in parts if finding.text in part), None)
        if finding.severity in (prose.HARD, prose.STRONG) and part:
            why[part].append(f'"{finding.text}": {finding.hint}')
    for named, reason in (later or {}).items():
        for part in parts:
            if named in part:
                why[part].append(reason)
    for name, reason in dead.items():
        for part in parts:
            if (unchecked is None or part in unchecked) and pace.named_dead({name}, part):
                why[part].append(reason)
                names[part][name] = reason
    return [{'passage': part, 'why': list(dict.fromkeys(reasons)), 'dead': names[part]}
            for part, reasons in why.items() if reasons]


def still_dead(flagged: list[dict], text: str) -> tuple[dict[str, str], set[str]]:
    """The unchecked dead of the paragraphs a rewrite left as they were, and those paragraphs."""
    kept = {flag['passage'] for flag in flagged} & set(paragraphs(text))
    return {name: why for flag in flagged if flag['passage'] in kept for name, why in flag['dead'].items()}, kept


def shown(flagged: list[dict]) -> list[dict]:
    """The flags as the player sees them: the passage and why, never whom the record holds dead in secret."""
    return [{'passage': flag['passage'], 'why': flag['why']} for flag in flagged]


def request(text: str, passage: str, flagged: list[dict], note: str) -> list[dict]:
    notes = [reason for flag in flagged if flag['passage'] in passage or passage in flag['passage']
             for reason in flag['why']]
    if note.strip():
        notes.append(f'The player asks: {note.strip()[:MOST_NOTE]}')
    asked = '\n'.join(f'- {line}' for line in dict.fromkeys(notes)) or '- Say it better, in new words.'
    return [{'role': 'user', 'content': f'The whole part, for context:\n\n{text}\n\nRewrite only this passage of it:\n\n'
                                        f'{passage}\n\nNotes:\n{asked}'}]
