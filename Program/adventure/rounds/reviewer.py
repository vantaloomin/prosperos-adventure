"""The Reviewer (docs/spec.md "The draft scan and the Reviewer"): a second reader that hasn't seen the Writer's
working checks the draft before it is scanned and committed.

It is a separate model call. It reads only the house rules (adventure/rounds/house_rules.py text, with the content
scope), the turn's brief (the beats the user set, each outcome code decided, the math and the stop point), the
story's last few posts for continuity and voice, and the draft. Never the Writer's prompt, its notes, or anything
the post's reader may not know, so a fix it suggests can't put a secret on the page.

It returns a prioritised list of notes, each a quote from the draft, the problem and a concrete fix. Code keeps a
note only when its quote is really in the draft, at most MOST_NOTES of them. The Writer then applies each note or
declines it with a reason, in one rewrite; a note whose quote is still on the page counts as declined. The result
goes on to the scan (adventure/rounds/scan.py settle), which always runs.

On by default in the "Rich" preset, a toggle in the others (`enabled`). A Reviewer that fails, times out
or answers with something code can't read leaves the draft as it was: it never loses a turn.
"""
import json
import logging
import re

from adventure.narration import prose
from adventure.rounds import house_rules
from adventure.rounds.contract import Brief
from adventure.rounds.house_rules import Rulebook

log = logging.getLogger(__name__)

MOST_NOTES = 8

SYSTEM = """You review one turn of a roleplaying game's story before it is published. You did not write it. Check it \
against the house rules, the turn's brief and the story so far, and list what to fix, most important first.

Check: the hard dialogue rules (no echoed phrases, no summarised or reported speech, verbal tics rationed, at least \
one question asked aloud in a scene with dialogue); formatting (thoughts, System panes); counting and pane \
arithmetic; continuity with the story so far; each character's voice; every beat the user set is rendered in full; \
no outcome is better or worse than the brief says; nothing happens past the stop point.

Reply with JSON only: {"notes": [{"quote": "...", "problem": "...", "fix": "..."}]}. Each quote is copied exactly \
from the draft, a few words to one sentence. Each fix says concretely what to write instead. If nothing needs \
fixing, reply {"notes": []}."""

APPLY = """You are revising one turn of a roleplaying game's story after a review. Keep every event, outcome, name \
and fact exactly as it is. For each note, apply the fix, or decline it if it is wrong. Never use em dashes or \
double hyphens.

Reply with JSON only: {"text": "the whole revised turn", "declined": [{"quote": "...", "reason": "..."}]}."""


def enabled(settings: dict) -> bool:
    """Whether the Reviewer runs: the user's own choice, else what the agents' preset says (adventure/rounds/agents.py
    PRESETS: on only in "Rich")."""
    from adventure.rounds import agents
    chosen = settings.get('reviewer')
    if chosen is not None:
        return bool(chosen)
    return bool(agents.PRESETS.get(settings.get('preset') or '', {}).get('reviewer'))


def brief_text(brief: Brief | None) -> str:
    if brief is None:
        return ''
    parts = [('When', [brief.when]), ('Where', [brief.where]), ('Beats the user set (render each in full)',
                                                                  brief.beats),
             ('Outcomes (decided by the game)', brief.outcomes), ('Math', brief.math),
             ('Stop point (end before it)', [brief.stop_point])]
    lines = ['## The turn brief']
    for title, items in parts:
        items = [item for item in items if item]
        if items:
            lines += [f'{title}:', *(f'- {item}' for item in items)]
    return '\n'.join(lines) if len(lines) > 1 else ''


def request(book: Rulebook, brief: Brief | None, draft: str, before: list[str]) -> tuple[str, list[dict]]:
    """The Reviewer's system prompt and message: the rules, the brief, the story so far, the draft."""
    system = '\n\n'.join(part for part in (SYSTEM, house_rules.text(book), brief_text(brief)) if part)
    story = '\n\n---\n\n'.join(before[-3:])
    content = (f'The story so far (the last posts):\n\n{story}\n\n' if story else '') + f'The draft:\n\n{draft}'
    return system, [{'role': 'user', 'content': content}]


def parsed(reply: str) -> dict:
    """The JSON object in a model's reply, fenced or bare; {} when there is none."""
    found = re.search(r'\{.*\}', reply or '', re.DOTALL)
    if not found:
        return {}
    try:
        value = json.loads(found[0])
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def present(quote: str, draft: str) -> bool:
    return bool(quote) and ' '.join(quote.split()).casefold() in ' '.join(draft.split()).casefold()


def notes_from(reply: str, draft: str) -> list[dict]:
    """The notes code keeps: each with a quote that is really in the draft, a problem and a fix, in the order given."""
    kept = []
    for note in parsed(reply).get('notes') or []:
        if not isinstance(note, dict):
            continue
        item = {key: ' '.join(str(note.get(key) or '').split())[:400] for key in ('quote', 'problem', 'fix')}
        if item['problem'] and item['fix'] and present(item['quote'], draft):
            kept.append(item)
    return kept[:MOST_NOTES]


async def review(complete, book: Rulebook, brief: Brief | None, draft: str, before: list[str]) -> list[dict]:
    """The Reviewer's notes on a draft; none when it fails. `complete(system, messages)` is one model reply."""
    system, messages = request(book, brief, draft, before)
    try:
        return notes_from(await complete(system, messages), draft)
    except Exception as error:  # noqa: BLE001 - no review this turn; the scan still runs
        log.warning('The Reviewer failed: %s', error)
        return []


def apply_request(book: Rulebook, draft: str, notes: list[dict]) -> tuple[str, list[dict]]:
    listed = '\n'.join(f'{index}. "{note["quote"]}": {note["problem"]} Fix: {note["fix"]}'
                       for index, note in enumerate(notes, 1))
    return (f'{APPLY}\n\n{house_rules.text(book, scope=False)}',
            [{'role': 'user', 'content': f'The turn:\n\n{draft}\n\nThe review:\n{listed}'}])


async def apply(complete, book: Rulebook, draft: str, notes: list[dict]) -> tuple[str, list[dict]]:
    """The draft with the Writer's answer to the review, and each note as applied or declined (with why).

    A revision is used only when it is about as long as the draft (prose.acceptable). A note whose quote is still on
    the page is declined, with the Writer's reason when it gave one."""
    if not notes:
        return draft, []
    system, messages = apply_request(book, draft, notes)
    try:
        answer = parsed(await complete(system, messages))
    except Exception as error:  # noqa: BLE001 - the draft stands; every note counts as not applied
        log.warning("The Writer's answer to the review failed: %s", error)
        answer = {}
    revised = str(answer.get('text') or '').strip()
    text = revised if prose.acceptable(draft, revised) else draft
    reasons = {' '.join(str(item.get('quote') or '').split()).casefold(): str(item.get('reason') or '')[:300]
               for item in answer.get('declined') or [] if isinstance(item, dict)}
    outcome = []
    for note in notes:
        kept = present(note['quote'], text)
        reason = reasons.get(note['quote'].casefold(), '') if kept else ''
        outcome.append(note | {'applied': not kept, 'reason': reason or ('Kept as written.' if kept else '')})
    return text, outcome
