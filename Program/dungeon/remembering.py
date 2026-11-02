"""What the narrator is reminded of, and what the characters still remember (requirements "Memory and context";
docs/story.md "Layered recall and forgetting").

- **Layered recall.** Each turn the narrator reads the recent turns word for word (dungeon/story.py), the story so
  far as a summary (dungeon/record.py), and facts from the record chosen by relevance: every death and promise,
  then the facts about who is present, where the scene is and anything just mentioned (names, places, items), then
  the newest of the rest.
- **Forgetting, but grudges stick.** The record keeps every fact. What the character is treated as remembering
  fades by its weight and its age in turns: small things soon, notable ones later, big ones (a death, a promise or
  debt, a betrayal) never. A fact about someone the character feels strongly about (any feeling at SHARP or more,
  dungeon/feelings.py) stays sharp whatever its age, and mentioning a fact again refreshes it. Hidden truth never
  fades, since the character never knew it.
- **A roll can recall a faded detail.** "I try to remember the ferryman" adds a Mind roll to the turn when a faded
  fact matches; a success brings what the character knew back to mind.
- **Context fits the model, with a player cap.** The workspace setting `context_cap` caps the tokens a turn may
  send; the record's facts give way before the recent turns do, and the summary goes first.
"""
import re

from dungeon import timeline
from dungeon.database import many, one, settings
from dungeon.rules import ladder

WEIGHTS = {'death': 3, 'promise': 3, 'secret': 2, 'wound': 2, 'relationship': 2, 'item': 1, 'location': 1, 'fact': 1}
BIG = re.compile(r'\b(betray\w*|murder\w*|kill\w*|debt|owe[sd]?|sworn|swore|oath|vow\w*|revenge)\b', re.I)
# Turns before a fact of each weight fades from the character's mind; the heaviest never do.
FADE = {1: 25, 2: 100, 3: None}
SHARP = 3
CAPS = (0, 4000, 8000, 16000, 32000, 64000)
RECALL = 'Recall what they knew of '
REMEMBER = re.compile(r'\b(remember|recall|think back|try to place|search my memory)\b', re.I)
WORD = re.compile(r"[a-z][a-z'-]{2,}", re.I)
SMALL = {'the', 'and', 'her', 'his', 'their', 'with', 'from', 'that', 'this', 'you', 'your', 'character', 'player'}


def weight(kind: str, text: str) -> int:
    return 3 if BIG.search(text) else WEIGHTS.get(kind, 1)


def turn_now(connection) -> int:
    """The turns played on this branch: the age of a fact is counted in them."""
    where, values = timeline.visible(connection)
    return one(connection, f"SELECT COUNT(*) AS n FROM story_messages WHERE role='user' AND {where}", values)['n']


def stamp(connection, entry_id: str, kind: str, text: str):
    """A new fact's weight and the turn it was learned in."""
    connection.execute('UPDATE record_entries SET weight=?, turn=? WHERE id=?',
                       (weight(kind, text), turn_now(connection), entry_id))


def words(text: str) -> set[str]:
    return {word.lower() for word in WORD.findall(text or '')} - SMALL


def about(entry: dict, mentioned: set[str]) -> bool:
    """Whether a fact's subject is among the words mentioned: any of its words of three letters or more."""
    return bool(words(entry['subject']) & mentioned)


def strong(connection) -> set[str]:
    """The words of the names of people the character feels strongly about."""
    from dungeon import feelings  # feelings reads the record, which stamps its facts here.
    names = set()
    for row in many(connection, 'SELECT * FROM story_people'):
        if any(abs(value) >= SHARP for value in feelings.of(row).values()):
            names |= words(row['name'])
    return names


def faded(entry: dict, now: int, sharp: set[str]) -> bool:
    """Whether the character remembers this fact only vaguely now."""
    limit = FADE.get(entry.get('weight') or 1)
    if limit is None or entry['truth'] == 'world' or about(entry, sharp):
        return False
    return now - (entry.get('turn') or 0) > limit


def refresh(connection, text: str):
    """Facts mentioned again (in the player's line or the narration) are fresh in mind once more."""
    mentioned = words(text)
    if not mentioned:
        return
    now = turn_now(connection)
    for row in many(connection, "SELECT id, subject FROM record_entries WHERE removed=0 AND truth != 'world'"):
        if about(row, mentioned):
            connection.execute('UPDATE record_entries SET turn=? WHERE id=?', (now, row['id']))


def chosen(connection, focus: str, limit: int) -> list[dict]:
    """The facts the narrator is given: every death and promise, then those the scene is about, then the newest."""
    rows = many(connection, 'SELECT * FROM record_entries WHERE removed=0 ORDER BY created_at DESC, rowid DESC')
    mentioned = words(focus)
    first = [row for row in rows if row['kind'] in ('death', 'promise')]
    relevant = [row for row in rows if row not in first and about(row, mentioned)]
    rest = [row for row in rows if row not in first and row not in relevant]
    return (first + relevant + rest)[:limit]


# How a legacy character's old deeds open in the record (dungeon/legacy.py): the narrator retells them as history.
HISTORY = 'Old accounts of what they did, long past:'


def prompt_text(connection, focus: str = '', limit: int = 40) -> str:
    """The record for the narrator: what is true, including what the player's character does not know, and what they
    now remember only vaguely."""
    rows = chosen(connection, focus, limit)
    if not rows:
        return ''
    now, sharp = turn_now(connection), strong(connection)
    lines = []
    for row in rows:
        note = {'world': " (hidden: the player's character does not know)",
                'belief': " (the player's character believes this; it may be wrong)", 'both': ''}[row['truth']]
        if HISTORY in row['text']:
            note += ' (history: retell it in the past tense, never word for word)'
        if faded(row, now, sharp):
            note += ' (faded: the character remembers this only vaguely, and the people in it may have forgotten)'
        lines.append(f"- {row['kind']}, {row['subject']}: {row['text']}{note}")
    return '## The record (kept by the game; never contradict it)\n' + '\n'.join(lines)


def faded_ids(connection) -> set[str]:
    now, sharp = turn_now(connection), strong(connection)
    return {row['id'] for row in many(connection, "SELECT * FROM record_entries WHERE removed=0 AND truth != 'world'")
            if faded(row, now, sharp)}


# Recalling a faded detail ------------------------------------------------------------------------

def recall_action(connection, text: str) -> dict | None:
    """A Mind roll when the line tries to remember something the character has let fade."""
    if not REMEMBER.search(text):
        return None
    now, sharp, mentioned = turn_now(connection), strong(connection), words(text)
    for row in many(connection, "SELECT * FROM record_entries WHERE removed=0 AND truth != 'world' "
                                'ORDER BY created_at DESC, rowid DESC'):
        if about(row, mentioned) and faded(row, now, sharp):
            return {'action': RECALL + row['subject'], 'stat': 'Mind', 'difficulty': 'normal'}
    return None


def recalled(connection, rolls: list[dict]) -> list[str]:
    """A recall roll that succeeded brings the faded facts about its subject back to mind."""
    lines = []
    for roll in rolls:
        if roll['action'].startswith(RECALL) and ladder.succeeded(roll['band']):
            subject = roll['action'].removeprefix(RECALL)
            connection.execute("UPDATE record_entries SET turn=? WHERE removed=0 AND truth != 'world' AND subject=?",
                               (turn_now(connection), subject))
            lines.append(f'The character remembers what they knew of {subject} clearly again.')
        elif roll['action'].startswith(RECALL):
            lines.append(f'What the character knew of {roll["action"].removeprefix(RECALL)} will not come back to '
                         'them now.')
    return lines


# Fitting the context -----------------------------------------------------------------------------

def room(connection, config: dict) -> int:
    """The tokens a turn may send: the model's window, under the player's cap when they set one."""
    cap = settings(connection)['context_cap']
    return min(config['context_tokens'], cap) if cap else config['context_tokens']
