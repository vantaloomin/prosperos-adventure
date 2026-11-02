"""How fast a story turn goes (requirements "Turn speed"; docs/story.md "Turn speed").

A turn can chain the Referee, the narrator, the prose rewrite, a contradiction rewrite, fact extraction and the
summary, so each turn has a time budget and every step is timed and logged with the player's line
(story_turn_steps):
- Obvious actions (walking, looking, plain talk) skip the Referee's model; the keyword rules settle them.
- The narration streams as it is written (dungeon/story_routes.py), and fact extraction and the summary run after
  the reply is on screen. They finish before the next turn starts.
- The contradiction check runs only when the narration names someone the record says is dead; a clean turn costs
  no extra call.
- Over budget, the optional steps give way: the prose rewrite first, then the contradiction rewrite (logged as
  skipped). Dice and the record are never skipped. The em dash fix always runs; it costs nothing.
"""
import re
import time
from urllib.parse import urlsplit

from dungeon.database import encode, optional, settings
from dungeon.narration import prose
from dungeon.providers.urls import is_loopback
from dungeon.referee import sentences, stat_for

# Seconds a turn may take when the player leaves the budget on automatic: local models are slower.
AUTOMATIC = {'local': 90, 'hosted': 30}
BUDGETS = (0, 15, 30, 60, 90, 120, 180)
LOCAL_PROVIDERS = {'local', 'kobold'}
OBVIOUS = re.compile(r"^(?:i\s+)?(?:go|walk|head|wander|stroll|return|come|enter|leave|step|sit|stand|wait|rest|"
                     r'look|glance|watch|listen|say|says|ask|tell|reply|answer|greet|nod|smile|shrug|wave|talk|chat|'
                     r'order|eat|drink|sleep|thank|pick out|picks out|single out|singles out|point out|point at|'
                     r'points (?:out|at))\b', re.I)
# Telling, asking or ordering someone to do something is persuasion, not plain talk: "I tell the guard to stand aside".
COMMAND = re.compile(r'\b(tell|tells|ask|asks|order|orders|beg|get)\b.*\bto\s+'
                     r'(?!(the|a|an|my|his|her|their|him|them|me|us|you)\b)\w', re.I)

CONTRADICTION = """You check one passage of a story against the game's record. The record says these people are \
dead: {names}. If the passage has any of them acting, speaking, moving or alive, rewrite only the sentences that \
need it so they are dead (a body, a memory, a name spoken by others); change nothing else. If the passage already \
agrees, answer it unchanged. Answer with the passage only."""


def is_local(config: dict) -> bool:
    return config.get('provider') in LOCAL_PROVIDERS or is_loopback(urlsplit(config.get('base_url') or '').hostname)


def budget_for(connection, config: dict) -> int:
    """The turn's budget in seconds: the player's, or automatic by where the narrator's model runs."""
    chosen = settings(connection)['turn_budget']
    return chosen or AUTOMATIC['local' if is_local(config) else 'hosted']


class Steps:
    """A turn's clock: how long each step took, what was skipped for time, and whether time is left."""

    def __init__(self, budget: int, clock=time.monotonic):
        self.budget, self.clock, self.started = budget, clock, clock()
        self.steps: dict[str, float] = {}
        self.skipped: list[str] = []

    def elapsed(self) -> float:
        return self.clock() - self.started

    def has_time(self) -> bool:
        return self.elapsed() < self.budget

    def timed(self, name: str, since: float):
        self.steps[name] = round(self.steps.get(name, 0) + self.clock() - since, 2)

    def skip(self, name: str):
        self.skipped.append(name)

    def view(self) -> dict:
        return {'steps': self.steps, 'skipped': self.skipped, 'budget': self.budget, 'total': round(self.elapsed(), 2)}


def save(connection, message_id: str, steps: Steps):
    connection.execute('INSERT INTO story_turn_steps (message_id, steps) VALUES (?, ?) ON CONFLICT(message_id) '
                       'DO UPDATE SET steps=excluded.steps', (message_id, encode(steps.view())))


def saved(connection, message_id: str) -> str | None:
    row = optional(connection, 'SELECT steps FROM story_turn_steps WHERE message_id=?', (message_id,))
    return row['steps'] if row else None


def obvious(text: str) -> bool:
    """A line with nothing uncertain in it: every sentence is speech or a plain act (walking, looking, talking)."""
    parts = sentences(re.sub(r'"[^"]*"', '"…"', text))
    return bool(parts) and all((part.startswith('"') or OBVIOUS.search(part)) and not stat_for(part)
                               and not COMMAND.search(part) for part in parts)


def named_dead(dead: set[str], text: str) -> list[str]:
    """The dead the narration names, by their full subject or a first name of more than two letters. Only a name
    counts as a first name: "five fresh graves" is not named by "five, maybe six"."""
    found = []
    for subject in sorted(dead):
        first = subject.removeprefix('the ').split(' ')[0]
        names = {subject, first} if first[:1].isupper() else {subject}
        if any(len(name) > 2 and re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', text, re.I) for name in names):
            found.append(subject)
    return found


async def contradiction(text: str, names: list[str], complete) -> str:
    """The narration agreeing with the record of the dead, rewritten only when needed and only if it stays whole."""
    try:
        revised = (await complete(CONTRADICTION.format(names=', '.join(names)),
                                  [{'role': 'user', 'content': text}])).strip()
    except Exception:  # noqa: BLE001 - the draft stands; a failed check never loses a turn
        return text
    return revised if prose.acceptable(text, revised) else text
