"""The house rulebook (docs/spec.md "House rules and rulings"): how this campaign's prose is written, kept as data.

A rule the Writer is only asked to keep is folklore; one kept here is checked in code every turn
(adventure/rounds/scan.py) and given to the Writer, the Referee and the Reviewer as the same text. The book is three
layers, each over the one before:

1. DEFAULTS: Vanta's writing rules, the hard dialogue rules and tells adventure/narration/prose.py has always
   checked, and Worldsmith's list of names that read as model-made (adventure/world/naming.py).
2. The world's `house_rules` (adventure/world/schema.py HouseRules): what its package adds to each list, and its own
   thought and System pane formats.
3. The campaign's edits at the Table. An edited list is stored as what the user added and removed, never as a copy,
   so a name added to the shipped list later still reaches a campaign begun before it.

Point of view and tense are the Table's (adventure/table.py) and the content scope is the intensity settings
(adventure/tone.py): the book reads them and keeps no copy, so there is one place to change each.

**Rulings** are the user's standing decisions ("Hesk's limp is permanent"). Each is stored with the turn it was made:
the branch, and the seq of the last line on it. They are read through the branch's ancestry as lines are
(adventure/timeline.py visible), so a ruling applies from its turn forward and going back before it un-makes it on
the new branch. Withdrawing one is a row of its own, read the same way, so a withdrawal also applies only from its
turn forward. Applying a ruling backward is a correction (adventure/rounds/corrections.py), not this.

Neither table is in timeline.SAVED: like the Table, a rule changed stays changed when a line is rewound, and rulings
need no snapshot because they are keyed by turn. A new story (story.clear) starts with the world's book again.
"""
from dataclasses import dataclass, field, fields, replace

from adventure import table, timeline
from adventure.database import decode, encode, identifier, many, one, optional
from adventure.errors import require
from adventure.narration import prompt as narration_prompt
from adventure.world import naming

# How inner thoughts are set on the page: what the Writer is told, and what scan.py checks.
THOUGHTS = {'quoted-italics': "in single-quoted italics, '*like this*'",
            'italics': 'in italics, *like this*',
            'plain': 'as plain narration, with no marks'}
# Punctuation the book can forbid by name; anything else on the list is the mark itself ('!', ';', '…').
NAMED_MARKS = {'em dash': 'em dashes or double hyphens, in any form'}
DIALOGUE = (
    "Nobody repeats another character's phrase back with a twist; answer with new content, a question, an action or "
    'silence. Greetings and ritual lines are fine.',
    'No reported speech: if someone said it, quote the words, unless the point of view character could not hear it.',
    "A character's catchphrase or verbal habit appears once per scene at most, and never in back-to-back lines.",
    # Tendencies, not quotas: a quota is met the same way every time and becomes a tell of its own. The Reviewer
    # treats a scene of dialogue with no question as a place to look (adventure/rounds/reviewer.py).
    'People ask each other questions aloud, and do not always get answers.',
    'After about three untagged lines of back-and-forth, ground the reader with an action beat or a tag.',
    'People do not count or keep score; System panes can count, people cannot.',
)
# The lists a user edits by adding and removing entries.
LISTS = ('dialogue', 'punctuation', 'words', 'phrases', 'names')
# The choices a user sets outright.
CHOICES = ('thoughts', 'pane_title', 'pane_row')
# The Reviewer's toggle as the Table sends it, and as it is kept (None: whatever the preset says).
REVIEWER = {'on': True, 'off': False, 'preset': None}
REVIEWER_CHOSEN = {True: 'on', False: 'off', None: 'preset'}
MOST = {'dialogue': 40, 'punctuation': 20, 'words': 400, 'phrases': 400, 'names': 1000}
LONGEST = {'dialogue': 300, 'punctuation': 8, 'words': 40, 'phrases': 120, 'names': 60, 'pane_title': 60,
           'pane_row': 60}


@dataclass(frozen=True)
class Rulebook:
    """Everything the house rules say, at one turn. Built with no arguments it is the defaults, which tests and the
    scan use without a database."""
    pov: str = 'third'
    tense: str = 'past'
    length: str = 'short'
    levels: dict = field(default_factory=lambda: dict.fromkeys(narration_prompt.CATEGORIES, 3))
    veils: tuple[str, ...] = ()
    thoughts: str = 'quoted-italics'
    # A System pane is a code block: its title line, then one row per value (adventure/rounds/scan.py PANE).
    pane_title: str = '[ {title} ]'
    pane_row: str = '{label}: {value}'
    dialogue: tuple[str, ...] = DIALOGUE
    punctuation: tuple[str, ...] = ('em dash',)
    words: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    names: tuple[str, ...] = field(default_factory=lambda: default_names())
    rulings: tuple[str, ...] = ()


def default_names() -> tuple[str, ...]:
    found = naming.data()['invented']
    return tuple(dict.fromkeys([*found['given'], *found['family']]))


def clean(entries) -> tuple[str, ...]:
    """A list as stored: trimmed, without blanks or repeats (ignoring case), in the order given."""
    seen, kept = set(), []
    for entry in entries or ():
        text = ' '.join(str(entry).split())
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            kept.append(text)
    return tuple(kept)


def edited(base: tuple[str, ...], edits: dict | None) -> tuple[str, ...]:
    """A list with the user's additions after it and their removals taken out."""
    edits = edits or {}
    removed = {entry.casefold() for entry in edits.get('remove') or ()}
    return clean(entry for entry in (*base, *(edits.get('add') or ())) if entry.casefold() not in removed)


def layered(world: dict | None, edits: dict | None) -> Rulebook:
    """The defaults, then what the world adds, then the campaign's edits; the Table's settings are not in it yet."""
    book, world, edits = Rulebook(), world or {}, edits or {}
    lists = {key: clean((*getattr(book, key), *(world.get(key) or ()))) for key in LISTS}
    lists = {key: edited(value, edits.get(key)) for key, value in lists.items()}
    choices = {key: edits.get(key) or world.get(key) or getattr(book, key) for key in CHOICES}
    return replace(book, **lists, **choices)


def stored(connection) -> dict:
    row = optional(connection, 'SELECT edits FROM house_rules WHERE id=1')
    return decode(row['edits']) if row else {}


def of(connection, data: dict) -> Rulebook:
    """The book in force for this city's world: its layers, the Table's format and intensity, and the rulings that
    apply where the story is now."""
    from adventure import tone
    rules, scope = table.rules(connection), tone.of(connection, data)
    book = layered(data.get('house_rules'), stored(connection))
    return replace(book, pov=rules['pov'], tense=rules['tense'], length=rules['length'], levels=scope['levels'],
                   veils=tuple(scope['veils']), rulings=tuple(item['text'] for item in rulings(connection)))


def now(connection) -> Rulebook:
    """The book for where the story is now; the defaults, with the Table's format, when there is no city to read."""
    from adventure import story
    try:
        return of(connection, story.city_data(connection, story.scene_row(connection)['city_id']))
    except Exception:  # noqa: BLE001 - no city yet: the defaults
        rules = table.rules(connection)
        return replace(layered(None, stored(connection)), pov=rules['pov'], tense=rules['tense'],
                       length=rules['length'], rulings=tuple(item['text'] for item in rulings(connection)))


def view(connection) -> dict:
    """The book as the Table shows it, with each ruling in force and the turn it was made at, and whether the
    Reviewer runs (adventure/rounds/reviewer.py): 'on' or 'off' as the user chose, or 'preset' to follow the preset."""
    from adventure.rounds import agents, reviewer
    book, chosen = now(connection), stored(connection).get('reviewer')
    return {item.name: list(value) if isinstance(value := getattr(book, item.name), tuple) else value
            for item in fields(book) if item.name != 'rulings'} | {
        'rulings': rulings(connection), 'thought_styles': list(THOUGHTS),
        'reviewer': {'chosen': REVIEWER_CHOSEN[chosen], 'on': reviewer.enabled(agents.settings(connection)
                                                                              | {'reviewer': chosen})}}


def change(connection, changes: dict, now: str):
    """The user edits the book. A list arrives whole, as the Table shows it, and is kept as what was added to and
    removed from the world's list; a choice set back to the world's own is no longer an edit."""
    from adventure import story
    try:
        world = story.city_data(connection, story.scene_row(connection)['city_id']).get('house_rules')
    except Exception:  # noqa: BLE001 - no city yet: edits are made against the defaults
        world = None
    base, edits = layered(world, None), stored(connection)
    for key in LISTS:
        if key in changes:
            given, before = clean(changes[key]), getattr(base, key)
            check_list(key, given)
            folded, given_folded = {entry.casefold() for entry in before}, {entry.casefold() for entry in given}
            edits[key] = {'add': [entry for entry in given if entry.casefold() not in folded],
                          'remove': [entry for entry in before if entry.casefold() not in given_folded]}
    for key in CHOICES:
        if key in changes:
            value = ' '.join(str(changes[key] or '').split())
            check_choice(key, value)
            edits[key] = None if value == getattr(base, key) else value or None
    if 'reviewer' in changes:
        require(changes['reviewer'] in REVIEWER, 'The Reviewer is on, off, or as the preset has it.')
        edits['reviewer'] = REVIEWER[changes['reviewer']]
    edits = {key: value for key, value in edits.items()
             if value is not None and (key == 'reviewer' or (value and (key in CHOICES or any(value.values()))))}
    connection.execute('INSERT INTO house_rules (id, edits, updated_at) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE '
                       'SET edits=excluded.edits, updated_at=excluded.updated_at', (encode(edits), now))


def check_list(key: str, entries: tuple[str, ...]):
    require(len(entries) <= MOST[key], f'The house rules keep at most {MOST[key]} {key}.')
    require(all(len(entry) <= LONGEST[key] for entry in entries),
            f'Each of the {key} can be at most {LONGEST[key]} characters.')
    if key == 'punctuation':
        require(all(entry in NAMED_MARKS or not any(char.isalnum() for char in entry) for entry in entries),
                'Forbid a punctuation mark itself, or "em dash".')


def check_choice(key: str, value: str):
    if key == 'thoughts':
        require(value in THOUGHTS, 'Pick one of the ways to set thoughts on the page.')
    else:
        require(len(value) <= LONGEST[key], f'The System pane format can be at most {LONGEST[key]} characters.')
        needed = ('{title}',) if key == 'pane_title' else ('{label}', '{value}')
        require(all(part in value for part in needed), f'The format needs {" and ".join(needed)} in it.')


# Rulings -------------------------------------------------------------------------------------------

def turn_now(connection) -> tuple[str, int]:
    """The turn the story is at: the branch being played and the seq of its last line (0 before the first)."""
    where, values = timeline.visible(connection)
    return timeline.active(connection), one(connection, f'SELECT COALESCE(MAX(seq), 0) AS seq FROM story_messages '
                                                        f'WHERE {where}', values)['seq']


def rulings(connection, branch_id: str | None = None) -> list[dict]:
    """The rulings in force on a branch (the one being played by default), oldest first."""
    where, values = timeline.visible(connection, branch_id)
    rows = many(connection, f'SELECT * FROM house_rulings WHERE {where} ORDER BY seq, created_at', values)
    withdrawn = {row['ruling_id'] for row in rows if row['kind'] == 'withdrawal'}
    return [{'id': row['id'], 'text': row['text'], 'branch_id': row['branch_id'], 'seq': row['seq'],
             'created_at': row['created_at']} for row in rows if row['kind'] == 'ruling' and row['id'] not in withdrawn]


def rule(connection, text: str, now: str) -> str:
    """A standing decision, made at the turn the story is at; it applies from here forward."""
    text = ' '.join(text.split())
    require(0 < len(text) <= 500, 'A ruling is one line of at most 500 characters.')
    ruling_id, (branch, seq) = identifier(), turn_now(connection)
    connection.execute("INSERT INTO house_rulings (id, kind, text, branch_id, seq, created_at) VALUES "
                       "(?, 'ruling', ?, ?, ?, ?)", (ruling_id, text, branch, seq, now))
    return ruling_id


def withdraw(connection, ruling_id: str, now: str):
    """A ruling no longer stands, from the turn the story is at forward."""
    require(any(item['id'] == ruling_id for item in rulings(connection)), 'That ruling is not in force here.',
            status=404)
    branch, seq = turn_now(connection)
    connection.execute("INSERT INTO house_rulings (id, kind, ruling_id, branch_id, seq, created_at) VALUES "
                       "(?, 'withdrawal', ?, ?, ?, ?)", (identifier(), ruling_id, branch, seq, now))


def clear(connection):
    """A new story: the campaign's edits and rulings go, and the world's book is in force again."""
    connection.execute('DELETE FROM house_rules')
    connection.execute('DELETE FROM house_rulings')


# The book as text --------------------------------------------------------------------------------

def marks(book: Rulebook) -> list[str]:
    return [NAMED_MARKS.get(entry, f'"{entry}"') for entry in book.punctuation]


def text(book: Rulebook, scope: bool = True) -> str:
    """The house rules as the Writer, the Referee and the Reviewer read them. `scope` adds the content scope, which
    the narrator's prompt already has in its own layer (adventure/narration/prompt.py Intensity)."""
    view_ = narration_prompt.POINTS_OF_VIEW[book.pov]
    lines = ['## House rules', f'- Narration: {view_}, {book.tense} tense.',
             f'- Inner thoughts go {THOUGHTS[book.thoughts]}.',
             f'- Numbers appear only in System panes, which the game adds after your text in the house format (a '
             f'title line like "{filled(book.pane_title, title="Status")}" and one row per value like '
             f'"{filled(book.pane_row, label="Health", value="12 of 20")}"). Never write a pane yourself and never '
             'put a game number in the narration. Narration never mentions dice or rolls.']
    lines += [f'- {rule_}' for rule_ in book.dialogue]
    if book.punctuation:
        lines.append(f"- Never use {', '.join(marks(book))}.")
    if book.words or book.phrases:
        lines.append(f"- Never write these: {', '.join((*book.words, *book.phrases))}.")
    if book.names:
        lines.append(f"- Never give anyone these names, which read as made up: {', '.join(book.names)}. Names the "
                     'world already has are fine.')
    if scope:
        lines.append(narration_prompt.Intensity(levels=book.levels, veils=book.veils).text())
    if book.rulings:
        lines += ['## Rulings (standing decisions; never contradict one)', *(f'- {item}' for item in book.rulings)]
    return '\n'.join(lines)


def filled(format_: str, **parts: str) -> str:
    """A format the user wrote, with its {title}, {label} and {value} filled in; nothing else in it is read."""
    for key, value in parts.items():
        format_ = format_.replace('{' + key + '}', value)
    return format_


def pane(book: Rulebook, title: str, rows: list[tuple[str, str]]) -> str:
    """A System pane in the house format, as code writes it from the record (docs/spec.md "Numbers live in panes")."""
    body = [filled(book.pane_title, title=title), *(filled(book.pane_row, label=label, value=value)
                                                    for label, value in rows)]
    return '```\n' + '\n'.join(body) + '\n```'
