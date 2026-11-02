"""The record and the story so far (docs/story.md "The record"; requirements "Memory and context").

The record is the source of truth: facts as structured entries (deaths, items, wounds, promises, locations,
secrets, relationships, other facts), each marked as world truth, the character's belief, or both. Code records
the facts it decides; after each narration the Continuity model, when one is chosen for that job, lists the new
facts the narrator brought in, and code keeps those that do not contradict the record. The narrator is given the
record every turn and never contradicts it.

Extraction is schema-first: the model fills a JSON Schema of record entries (plus the other systems' questions,
each with its own part of the schema), which the backend enforces where it can (dungeon/providers/requests.py
`structured`). A model that cannot fill it is asked again without it, and a weak one that still gives nothing
readable is asked one field at a time.

The player sees and corrects what their character knows (truth 'belief' or 'both'); every correction is logged.
Hidden truth ('world') stays out of their view, except in the GM view (the Table's `gm_view`, dungeon/table.py), which shows
and edits everything and can ask again for, or clear, a single fact the model extracted.

The story so far: the narrator reads the most recent messages word for word and, before them, one rolling summary.
When enough older messages pile up, they are folded into the summary by the Continuity model (or the Default one).

Both are game state, kept per branch (dungeon/timeline.py SAVED).
"""
import asyncio
import json
import re

from dungeon import remembering, table
from dungeon.database import identifier, many, one, optional
from dungeon.errors import DomainError, require
from dungeon.providers.scheduling import CONVERSATION
from dungeon.text_models import config_for, key_for, routes

JOB = 'continuity'
KINDS = ('death', 'item', 'wound', 'promise', 'location', 'secret', 'relationship', 'fact')
TRUTHS = ('world', 'belief', 'both')
MOST_FACTS = 6
# Entries the narrator is given each turn (dungeon/remembering.py chooses them).
IN_PROMPT = 40
# Messages the narrator reads word for word; older ones are folded into the summary FOLD at a time.
RECENT = 30
FOLD = 20
SUMMARY_WORDS = 400

EXTRACT = f"""You keep the continuity of a tabletop roleplaying game. You never write story. Read the latest turn \
and list the new, lasting facts it established. Leave out moods, weather and anything that will not matter later, \
and anything already in the record (listed below, when there is one). Only what the turn says plainly: never guess a \
name, a place or what something is called. At most {MOST_FACTS}.

For each fact give its kind, its subject (the person, item or place it is about, in a few words), the fact in one \
short sentence, and its truth. The kinds:
- death: someone died in this turn, or their death was confirmed. Not graves, old bones, the long dead or threats.
- wound: someone was hurt.
- item: an item was gained, lost or given, by anyone. The game keeps the character's own pack: list what the \
character got only when the turn shows them being given it or buying it.
- promise: a promise or debt was made.
- location: a place was learned of.
- secret: something hidden came out. Not ordinary facts the character heard.
- relationship: how two people stand toward each other changed. Not what the character noticed about someone.
- fact: anything else worth remembering, such as a name, a scar, a rumour or something the character heard.

Truth is "both" when the player's character saw or knows it, "world" when it is true but hidden from them, \
"belief" when the character believes it but it may not be true (what someone told them is often a belief).

Answer with JSON only, in this shape:
{{"facts": [{{"kind": "wound", "subject": "the bouncer", "text": "The bouncer's nose is broken.", "truth": "both"}}]}}
Answer {{"facts": []}} when nothing lasting happened."""
# A new fact this close in words to one the record has about the same subject is a repeat.
SAME = 0.6
GAINED = re.compile(r'\b(you|the character|they)\b.*\b(take|takes|took|pick|picks|picked|pocket|pockets|pocketed|'
                    r'gain|gains|gained|find|finds|found|grab|grabs|grabbed|keep|keeps|kept)\b', re.I)
SELF = re.compile(r'^(you|yourself|the character|the player\'s character|me|i)$', re.I)

# One fact at a time, for weak models that answer no JSON at all: the facts as lines, then each field for all of them.
LINES = f"""You keep the continuity of a tabletop roleplaying game. You never write story. Read the latest turn and \
list the new, lasting facts it established (a death, a wound, an item gained or lost, a promise, a place, a secret, a \
relationship, a name or rumour worth remembering), one short sentence per line, at most {MOST_FACTS}. Leave out moods \
and weather. Answer "none" when nothing lasting happened."""
FIELDS = {
    'kind': f'For each numbered fact, give its kind, one word of: {", ".join(KINDS)}.',
    'subject': 'For each numbered fact, give who or what it is about, in a few words.',
    'truth': 'For each numbered fact, answer "both" if the player\'s character saw or knows it, "world" if it is true '
             'but hidden from them, or "belief" if they believe it but it may be wrong.',
}
FIELD_SHAPE = ' Answer one line per fact, as "1. answer", and nothing else.'

REGENERATE = f"""You keep the continuity of a tabletop roleplaying game. You never write story. A fact was pulled \
from the turn below, and the game master wants it again: read the turn and restate that one fact as the turn \
established it. Give its kind ({', '.join(KINDS)}), its subject in a few words, the fact in one short sentence, and \
its truth ("both", "world" or "belief"). Answer with JSON only, in this shape:
{{"kind": "wound", "subject": "the bouncer", "text": "The bouncer's nose is broken.", "truth": "both"}}"""

SUMMARIZE = f"""You keep the story so far of a tabletop roleplaying game. Rewrite the summary to take in the new \
turns: what happened, in order, who the player's character met and what they did, what is unresolved. Past tense, \
plain prose, at most {SUMMARY_WORDS} words. Keep everything that still matters; drop what no longer does. Answer \
with the summary only."""


# The schema the extraction fills ------------------------------------------------------------------

def strict(properties: dict) -> dict:
    """An object with exactly these properties, all required: the shape strict structured output accepts."""
    return {'type': 'object', 'additionalProperties': False, 'required': list(properties), 'properties': properties}


FACT = strict({'kind': {'type': 'string', 'enum': list(KINDS)}, 'subject': {'type': 'string'},
               'text': {'type': 'string'}, 'truth': {'type': 'string', 'enum': list(TRUTHS)}})


def schema(extra: dict | None = None) -> dict:
    """The turn's facts, plus what the other systems ask (each a list, empty when nothing applies)."""
    return strict({'facts': {'type': 'array', 'items': FACT}, **(extra or {})})


# The record --------------------------------------------------------------------------------------

def dead(connection) -> set[str]:
    return {row['subject'].lower() for row in many(connection, "SELECT subject FROM record_entries WHERE kind='death' "
                                                                'AND removed=0')}


def add(connection, kind: str, subject: str, text: str, now: str, source: str = 'code', truth: str = 'both',
           message_id: str | None = None) -> dict | None:
    """A new entry, or None when the narrator's fact contradicts the record (the dead do nothing more)."""
    require(kind in KINDS, f'{kind} is not a kind of fact.', 422)
    require(truth in TRUTHS, f'{truth} is not a kind of truth.', 422)
    subject, text = subject.strip()[:120], text.strip()[:500]
    require(bool(subject and text), 'A fact needs a subject and its text.', 422)
    if source == 'narrator' and kind != 'death' and subject.lower() in dead(connection):
        return None
    entry_id = identifier()
    connection.execute('INSERT INTO record_entries (id, kind, subject, text, truth, source, message_id, created_at) '
                       'VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (entry_id, kind, subject, text, truth, source, message_id, now))
    remembering.stamp(connection, entry_id, kind, text)
    return one(connection, 'SELECT * FROM record_entries WHERE id=?', (entry_id,))


def entries(connection, known_only: bool = True) -> list[dict]:
    """The record, newest first; only what the character knows unless asked for everything."""
    hidden = "AND truth != 'world'" if known_only else ''
    rows = many(connection, f'SELECT id, kind, subject, text, truth, source, message_id IS NOT NULL AS pulled, '
                            f'created_at FROM record_entries WHERE removed=0 {hidden} ORDER BY created_at DESC, rowid DESC')
    fading = remembering.faded_ids(connection)
    return [row | {'pulled': row['source'] == 'narrator' and bool(row['pulled']), 'faded': row['id'] in fading}
            for row in rows]


def gm_view(connection) -> bool:
    return bool(table.rule(connection, 'gm_view'))


def entry(connection, entry_id: str) -> dict:
    """An entry the player may change: what their character knows, or anything in the GM view."""
    hidden = '' if gm_view(connection) else "AND truth != 'world'"
    row = optional(connection, f'SELECT * FROM record_entries WHERE id=? AND removed=0 {hidden}', (entry_id,))
    require(row is not None, 'That fact is not in your journal.', 404)
    return row


def correct(connection, entry_id: str, now: str, text: str | None = None) -> None:
    """The player changes (text) or removes (None) what their character knows; the change is logged."""
    row = entry(connection, entry_id)
    if text is None:
        connection.execute('UPDATE record_entries SET removed=1 WHERE id=?', (entry_id,))
    else:
        require(bool(text.strip()), 'Write the fact, or remove it.', 422)
        connection.execute("UPDATE record_entries SET text=?, source='player' WHERE id=?", (text.strip()[:500], entry_id))
    connection.execute('INSERT INTO record_corrections (id, entry_id, before, after, created_at) VALUES (?, ?, ?, ?, ?)',
                       (identifier(), entry_id, row['text'], text, now))


def prompt_text(connection, focus: str = '', limit: int = IN_PROMPT) -> str:
    """The record for the narrator: what is true, including what the player's character does not know, chosen by
    relevance to `focus` (dungeon/remembering.py)."""
    return remembering.prompt_text(connection, focus, limit)


def words_of(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z][a-z'-]{2,}", text.lower())}


def repeat(connection, fact: dict) -> bool:
    """A fact the record already has: the same subject, and nearly the same words."""
    subject, said = fact['subject'].strip().lower(), words_of(fact['text'])
    for row in many(connection, 'SELECT subject, text FROM record_entries WHERE removed=0 AND lower(subject)=?',
                    (subject,)):
        held = words_of(row['text'])
        if said and held and len(said & held) / len(said | held) >= SAME:
            return True
    return False


def unearned(connection, fact: dict) -> bool:
    """An item the narration says the character took that the game never put in their pack (dungeon/inventory.py
    decides what they carry)."""
    if fact['kind'] != 'item' or not (SELF.match(fact['subject'].strip()) or GAINED.search(fact['text'])):
        return False
    from dungeon import inventory  # the pack's items, read only for this check.
    names = set()
    for row in inventory.carried(connection, ''):
        names |= words_of(row['name'])
    return not (words_of(fact['text']) - {'you', 'the', 'and', 'character', 'took', 'take', 'takes', 'found'}) & names


def well_formed(item) -> dict | None:
    if not (isinstance(item, dict) and item.get('kind') in KINDS and str(item.get('subject') or '').strip()
            and str(item.get('text') or '').strip()):
        return None
    return {'kind': item['kind'], 'subject': str(item['subject']), 'text': str(item['text']),
            'truth': item.get('truth') if item.get('truth') in TRUTHS else 'both'}


def read_json(answer: str):
    match = re.search(r'\{.*\}', answer, re.S)
    try:
        return json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None


def checked(answer: str) -> list[dict] | None:
    """The model's facts, keeping only well-formed ones; None when nothing in the answer can be read."""
    data = read_json(answer)
    items = data.get('facts') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    return [fact for fact in map(well_formed, items[:MOST_FACTS]) if fact]


async def asked(state, config: dict, system: str, text: str, shape: dict | None = None) -> str:
    """The model's whole answer; with a `shape` (a JSON Schema) the backend is asked to keep to it."""
    if shape is not None:
        config = {**config, 'json_schema': shape}
    async with state.scheduler.reserve(config, CONVERSATION):
        return ''.join([chunk.text async for chunk in state.provider.stream(
            config, key_for(state.vault, config), system, [{'role': 'user', 'content': text}])])


async def schema_first(state, config: dict, system: str, text: str, shape: dict, readable=None) -> str:
    """Asked with the schema; asked again without it when the backend refuses it or the answer cannot be read (by
    `readable`, the facts by default)."""
    readable = readable or (lambda answer: checked(answer) is not None)
    try:
        answer = await asked(state, config, system, text, shape)
        if readable(answer):
            return answer
    except DomainError:
        pass
    return await asked(state, config, system, text)


def numbered(answer: str, count: int) -> list[str]:
    """Answers given one line per numbered fact; '' for a fact not answered."""
    found = {}
    for line in answer.splitlines():
        match = re.match(r'\s*(\d+)[.):]\s*(.+)', line)
        if match:
            found.setdefault(int(match.group(1)), match.group(2).strip().strip('"'))
    return [found.get(number, '') for number in range(1, count + 1)]


async def field_by_field(state, config: dict, text: str) -> list[dict]:
    """A weak model's facts, one question at a time: the facts as lines, then each field for all of them."""
    lines = [re.sub(r'^\s*(\d+[.):]|[-*])\s*', '', line).strip()
             for line in (await asked(state, config, LINES, text)).splitlines()]
    lines = [line for line in lines if line and line.lower().strip('.') != 'none'][:MOST_FACTS]
    if not lines:
        return []
    listed = '\n'.join(f'{number}. {line}' for number, line in enumerate(lines, 1))
    # The fields are asked together, not one after another: the slow path stays one question's wait longer.
    answers = await asyncio.gather(*(asked(state, config, question + FIELD_SHAPE, f'{text}\n\nThe facts:\n{listed}')
                                     for question in FIELDS.values()))
    fields = {field: numbered(answer, len(lines)) for field, answer in zip(FIELDS, answers)}
    facts = []
    for number, line in enumerate(lines):
        kind = fields['kind'][number].lower().strip('. ')
        truth = fields['truth'][number].lower().strip('. ')
        fact = well_formed({'kind': kind if kind in KINDS else 'fact', 'subject': fields['subject'][number][:120],
                            'text': line, 'truth': truth})
        if fact:
            facts.append(fact)
    return facts


def turn_text(user_text: str, reply_text: str) -> str:
    return f'The player: {user_text}\n\nThe narrator: {reply_text}'


async def extract(state, user_text: str, reply: dict, ask: str = '', extra: dict | None = None) -> str:
    """The new facts of a turn, from the Continuity model only when the player chose one for it; `ask` adds a
    question of another system's (dungeon/quests.py), `extra` the part of the schema that answers it, and the model's
    whole answer is returned for it."""
    database = state.database
    with database.connect() as connection:
        config = config_for(connection, JOB) if routes(connection).get(JOB) else None
    if config is None:
        return ''
    text = turn_text(user_text, reply['text'])
    with database.connect() as connection:
        held = many(connection, 'SELECT kind, subject, text FROM record_entries WHERE removed=0 ORDER BY created_at '
                                'DESC, rowid DESC LIMIT 20')
    if held:
        text += '\n\nAlready in the record:\n' + '\n'.join(f"- {row['kind']}, {row['subject']}: {row['text']}"
                                                         for row in held)
    try:
        answer = await schema_first(state, config, EXTRACT + ask, text, schema(extra))
        facts = checked(answer)
        if facts is None:
            facts = await field_by_field(state, config, text)
    except Exception:  # noqa: BLE001 - a fact missed is better than a turn lost.
        return ''
    with database.connect(write=True) as connection:
        for fact in facts:
            if not repeat(connection, fact) and not unearned(connection, fact):
                add(connection, fact['kind'], fact['subject'], fact['text'], database.now(), 'narrator',
                    fact['truth'], reply['id'])
    return answer


def turn_of(connection, message_id: str) -> tuple[str, str] | None:
    """The player's line and the narration a fact was pulled from."""
    reply = optional(connection, 'SELECT seq, text FROM story_messages WHERE id=?', (message_id,))
    if reply is None:
        return None
    user = optional(connection, "SELECT text FROM story_messages WHERE role='user' AND seq < ? ORDER BY seq DESC "
                                'LIMIT 1', (reply['seq'],))
    return (user['text'] if user else ''), reply['text']


async def regenerate(state, entry_id: str) -> None:
    """The GM view asks the Continuity model again for one extracted fact; the change is logged like a correction."""
    database = state.database
    with database.connect() as connection:
        require(gm_view(connection), 'Turn on the GM view to ask for a fact again.', 409)
        row = entry(connection, entry_id)
        require(row['source'] == 'narrator' and bool(row['message_id']), 'Only a fact the model pulled from the story '
                'can be asked for again.', 409)
        turn = turn_of(connection, row['message_id'])
        require(turn is not None, 'The turn this fact came from is no longer in the story.', 409)
        config = config_for(connection, JOB)
    require(config is not None, 'Choose a model for Continuity in Settings > Models first.', 409)
    asking = f"{turn_text(*turn)}\n\nThe fact as it was pulled: {row['kind']}, {row['subject']}: {row['text']}"
    try:
        answer = await asked(state, config, REGENERATE, asking, FACT)
    except DomainError:
        answer = await asked(state, config, REGENERATE, asking)
    fact = well_formed(read_json(answer))
    require(fact is not None, 'The model did not give the fact back in a form the game can read. Try again.', 502)
    with database.connect(write=True) as connection:
        if fact['kind'] != 'death' and fact['subject'].lower() in dead(connection):
            raise DomainError('The model gave back a fact that contradicts the record. Try again, or correct it '
                              'yourself.', 409)
        connection.execute("UPDATE record_entries SET kind=?, subject=?, text=?, truth=? WHERE id=?",
                           (fact['kind'], fact['subject'][:120], fact['text'][:500], fact['truth'], entry_id))
        connection.execute('INSERT INTO record_corrections (id, entry_id, before, after, created_at) VALUES (?, ?, ?, '
                           '?, ?)', (identifier(), entry_id, row['text'], fact['text'][:500], database.now()))


# The story so far --------------------------------------------------------------------------------

def summary(connection) -> dict:
    row = optional(connection, 'SELECT text, through_seq FROM story_summary WHERE id=1')
    return row or {'text': '', 'through_seq': 0}


def summary_text(connection) -> str:
    text = summary(connection)['text']
    return f'## The story so far (older turns, summarized)\n{text}' if text else ''


def to_fold(rows: list[dict], through_seq: int) -> list[dict]:
    """The oldest messages past the summary, once RECENT + FOLD of them wait; else nothing."""
    waiting = [row for row in rows if row['seq'] > through_seq]
    return waiting[:FOLD] if len(waiting) >= RECENT + FOLD else []


def transcript(rows: list[dict]) -> str:
    names = {'user': 'The player', 'narrator': 'The narrator', 'scene': 'Scene'}
    return '\n\n'.join(f"{names[row['role']]}: {row['text']}" for row in rows
                       if row['role'] != 'narrator' or row['status'] == 'complete')


async def fold(state, rows: list[dict]):
    """Fold the oldest waiting messages into the summary, when enough have piled up."""
    database = state.database
    with database.connect() as connection:
        before = summary(connection)
        config = config_for(connection, JOB)
        found = optional(connection, 'SELECT name FROM persona WHERE id=1')
    chunk = to_fold(rows, before['through_seq'])
    # The character by name: the summary never calls them "the player" or "the party".
    named = (f"\n\nThe player's character is {found['name']}, one person: call them {found['name']}, never \"the "
             'player" or "the party".') if found and found['name'] else ''
    if not chunk or config is None:
        return
    try:
        text = (await asked(state, config, SUMMARIZE + named, f"The summary so far:\n{before['text'] or '(none yet)'}\n\n"
                                                    f'The new turns:\n{transcript(chunk)}')).strip()
    except Exception:  # noqa: BLE001 - the turns stay word for word until the next try.
        return
    if text:
        with database.connect(write=True) as connection:
            connection.execute('INSERT INTO story_summary (id, text, through_seq, updated_at) VALUES (1, ?, ?, ?) '
                               'ON CONFLICT(id) DO UPDATE SET text=excluded.text, through_seq=excluded.through_seq, '
                               'updated_at=excluded.updated_at', (text, chunk[-1]['seq'], database.now()))
