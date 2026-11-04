"""The core prompts a power user may reword in Settings > Developer (docs/prompts.md): the Story's narrator and round
Writer, and the Characters' minds (adventure/rounds/agents.py).

Each prompt's default lives where it is used, a module constant written for `str.format`. Here they are shown and
stored in one form,
with `{{placeholder}}` marks the app fills in. A user's wording is stored in `prompt_overrides`
with the default it replaced, so an update that changes the default can say so without touching
their text. Wording is checked before it is saved: every placeholder the default uses must stay,
and no unknown one may be added, so a typo cannot break replies.

A layout (`Prompt.layout`) is checked differently: it places slots (adventure/prompt_layout.py), any of which may be
left out, and is refused when it puts a slot ahead of one that changes more slowly, so every layout stays
cache-friendly.

Only the wording is editable. The in-character filter, OOC handling, the NSFW check and every
reply's validation are code (adventure/in_character.py and the callers) and run whatever it says.
"""
import re
from dataclasses import dataclass, field
from importlib import import_module

from adventure import prompt_layout
from adventure.database import optional
from adventure.errors import DomainError

PLACEHOLDER = re.compile(r'\{\{(\w+)\}\}')
# `{name}` with single braces: almost certainly a placeholder typed the wrong way.
SINGLE = re.compile(r'(?<!\{)\{(\w+)\}(?!\})')
FORMAT_TOKEN = re.compile(r'\{\{|\}\}|\{(\w+)\}')


def from_format(text: str) -> str:
    """A `str.format` template in the `{{placeholder}}` form: `{name}` → `{{name}}`, `{{` → `{`."""
    return FORMAT_TOKEN.sub(lambda match: '{{' + match[1] + '}}' if match[1] else match[0][0], text)


def constant(module: str, name: str, key: str | None = None):
    """A module constant read when needed, so an update to the code is the new default at once; `key` picks one entry
    of a dict constant."""
    def read() -> str:
        value = getattr(import_module(module), name)
        return from_format(value[key] if key is not None else value)
    return read


def literal(module: str, name: str):
    """A module constant written in the `{{slot}}` form already (a layout), read when needed."""
    return lambda: getattr(import_module(module), name)


@dataclass(frozen=True)
class Prompt:
    name: str
    group: str
    label: str
    description: str
    default: object  # () -> str
    placeholders: dict[str, str] = field(default_factory=dict)
    # Placeholders an older default had, with why they went: still filled in a user's older wording, refused on save.
    retired: dict[str, str] = field(default_factory=dict)
    # For a layout: () -> {name: prompt_layout.Slot}, the slots its reader's context builder fills.
    layout: object = None
    reader: str = ''


def agent_slots() -> dict:
    return import_module('adventure.rounds.agents').SLOTS


CHAT, CHARACTERS, GENRES = 'Story', 'Characters', 'Genres'
AGENTS = 'adventure.rounds.agents'
PROMPTS = {prompt.name: prompt for prompt in (
    Prompt('story-narrator', CHAT, 'The Story narrator',
           'Opens every reply in the story: who the narrator is and its contract with the game (what wins when '
           "instructions disagree, the facts are fixed, the player's words are expanded, everyone else lives their "
           'own life, the content rules). The scene, the narration format and the intensity follow it, and the app '
           'decides them. OOC answers are also enforced by the app.',
           constant('adventure.narration.prompt', 'CORE')),
    Prompt('narrator-craft', CHAT, "The narrator's writing rules",
           'Follows the Story narrator and the round Writer: the hard rules (em dashes and the dialogue rules), then '
           'how to write. Models with a small context window get a short version instead. Em dashes, stock phrases '
           'and the strongest tells are checked by the app after every reply, and rewritten before you see them, so '
           'they are not listed here.',
           constant('adventure.narration.prompt', 'CRAFT')),
    Prompt('round-writer', CHAT, 'The round Writer',
           'Opens every round the Writer tells when other characters think for themselves (a party in Play, Author '
           'and Watch), in place of the Story narrator: its contract with the game, what wins when instructions '
           'disagree, the brief and the content rules. The writing rules, the house rules, the point of view, the '
           'intensity and what the Writer may know follow it, and the app decides them.',
           constant('adventure.rounds.writer', 'ROUND')),
    Prompt('authors-note', CHAT, "Author's note",
           "Goes right before your author's note, the last thing the model reads before your message while "
           'the note is switched on. Your note follows this line.',
           constant('adventure.authors_note', 'HEADER')),
    Prompt('character-mind', CHARACTERS, "A character's mind",
           'Opens every call to a character who thinks for themselves, spoken to them as themselves ("You are..."): '
           'that their sheet is who they are, that they want what they want rather than helping, that they know only '
           'what they know, how they speak, and the content rules. What the '
           "character may know, the shape of their answer, the intensity and the scheming dial are added by the app, "
           "so no wording here can show a character someone else's secrets.",
           constant(AGENTS, 'MIND'),
           retired={'character': "The character's name now comes with their sheet, further down the prompt, so every "
                                 'character in a story can share the cached start. Take {{character}} out; to place '
                                 "the name, edit the layout's {{CHARACTER}}."}),
    Prompt('character-declare', CHARACTERS, 'Deciding a move',
           'Follows the character\'s mind when everyone decides at once at the start of a round.',
           constant(AGENTS, 'PURPOSES', 'declare')),
    Prompt('character-react', CHARACTERS, 'Reacting to the others',
           'Follows the character\'s mind once everyone has declared, when a character may change their move once. '
           'How they say whether it changed is added by the app.',
           constant(AGENTS, 'PURPOSES', 'react')),
    Prompt('character-ask', CHARACTERS, 'Speaking up',
           'Follows the character\'s mind in the talk inside a round, when a character is chosen to say something to '
           'someone. The app names whom.',
           constant(AGENTS, 'PURPOSES', 'ask')),
    Prompt('character-answer', CHARACTERS, 'Answering',
           'Follows the character\'s mind in the talk inside a round, when someone has just spoken to a character. '
           'The app adds the line they answer.',
           constant(AGENTS, 'PURPOSES', 'answer')),
    Prompt('character-offpage', CHARACTERS, 'Off the page',
           'Follows the character\'s mind when something happened away from the main scene and the character says a '
           'few lines in it. The app adds what happened and who was there.',
           constant(AGENTS, 'PURPOSES', 'offpage')),
    Prompt('character-invite', CHARACTERS, 'Being asked along',
           'Follows the character\'s mind when the player asks them to come along and their feelings leave it to them '
           '(a wary character refuses before anyone asks). The app adds the line that asked and how they say yes or '
           'no, and their answer decides whether they join.',
           constant(AGENTS, 'PURPOSES', 'invite')),
    Prompt('character-turning', CHARACTERS, 'Turning on someone',
           'What a character may do once they turn against someone, and what turns them. How they stand with each '
           'person present follows it, worked out by the app from their feelings.',
           constant(AGENTS, 'TURNING')),
    Prompt('character-genre-dark-romantasy', CHARACTERS, 'Dark romantasy, for characters',
           "Follows the intensity in every character's prompt when the Table's Genre is Dark romantasy: what wanting "
           "someone does to what a character risks, hides and betrays. The narration's own module is under Genres.",
           constant(AGENTS, 'GENRES', 'dark-romantasy')),
    Prompt('character-genre-adventure', CHARACTERS, 'Adventure, for characters',
           "Follows the intensity in every character's prompt when the Table's Genre is Adventure: their own reason "
           "for being here, and a view on whose fault it is. The narration's own module is under Genres.",
           constant(AGENTS, 'GENRES', 'adventure')),
    Prompt('character-genre-graphic-violence', CHARACTERS, 'Graphic violence, for characters',
           "Follows the intensity in every character's prompt when the Table's Genre is Graphic violence: what a "
           "character will and won't do to someone, and what it costs them. The narration's own module is under "
           'Genres.',
           constant(AGENTS, 'GENRES', 'graphic-violence')),
    Prompt('character-layout', CHARACTERS, "A character's prompt, laid out",
           'Where each part of a character call goes. Slots are filled by the app from what that character may know, '
           "and fenced, so moving one never shows a character anything new. Parts that change least come first so "
           "the model service can cache them: a slot can't come before one that changes more slowly. A slot you "
           'leave out goes back at the end of its group; a paragraph whose slots are all empty is left out, so keep '
           'a heading in the same paragraph as its slot.',
           literal(AGENTS, 'LAYOUT'), layout=agent_slots, reader='a character'),
    Prompt('genre-dark-romantasy', GENRES, 'Dark romantasy',
           'Follows the intensity in the narrator\'s and the round Writer\'s prompt when the Table\'s Genre is Dark '
           'romantasy. How explicit the page gets stays with the intensity.',
           constant('adventure.narration.prompt', 'GENRES', 'dark-romantasy')),
    Prompt('genre-adventure', GENRES, 'Adventure',
           'Follows the intensity in the narrator\'s and the round Writer\'s prompt when the Table\'s Genre is '
           'Adventure.',
           constant('adventure.narration.prompt', 'GENRES', 'adventure')),
    Prompt('genre-graphic-violence', GENRES, 'Graphic violence',
           'Follows the intensity in the narrator\'s and the round Writer\'s prompt when the Table\'s Genre is '
           'Graphic violence. How violent the page gets stays with the intensity.',
           constant('adventure.narration.prompt', 'GENRES', 'graphic-violence')),
)}


def placeholders(text: str) -> list[str]:
    return sorted(set(PLACEHOLDER.findall(text)))


def fill(text: str, /, **values: str) -> str:
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    return text


def require(name: str) -> Prompt:
    if name not in PROMPTS:
        raise DomainError(f'No editable prompt named {name!r}.', 404, 'unknown_prompt')
    return PROMPTS[name]


def override(connection, name: str) -> dict | None:
    return optional(connection, 'SELECT text, default_text FROM prompt_overrides WHERE name=?', (name,))


def text(connection, name: str, /, **values: str) -> str:
    """The wording in use, the user's when they reworded it, with `values` filled in."""
    row = override(connection, name) if connection is not None else None
    return fill(row['text'] if row else PROMPTS[name].default(), **values)


def view(connection, name: str) -> dict:
    prompt = PROMPTS[name]
    default, row = prompt.default(), override(connection, name)
    keys = [] if prompt.layout else placeholders(default)
    return {'name': name, 'group': prompt.group, 'label': prompt.label, 'description': prompt.description,
            'text': row['text'] if row else default, 'default': default, 'customized': row is not None,
            # Saved against an older default: the user's wording stays, with a note that a newer one exists.
            'outdated': bool(row and row['default_text'] is not None and row['default_text'] != default),
            'placeholders': keys,
            'placeholder_help': {key: prompt.placeholders.get(key, '') for key in keys},
            'slots': prompt_layout.described(prompt.layout()) if prompt.layout else []}


def views(database) -> list[dict]:
    with database.connect() as connection:
        return [view(connection, name) for name in PROMPTS]


def problems(default: str, wording: str, retired: dict[str, str] | None = None) -> str | None:
    """Why the wording would break the prompt, in words the user can act on, or None."""
    gone = [key for key in placeholders(wording) if key in (retired or {})]
    if gone:
        return (retired or {})[gone[0]]
    allowed = set(placeholders(default))
    missing = [key for key in sorted(allowed) if '{{' + key + '}}' not in wording]
    unknown = [key for key in placeholders(wording) if key not in allowed]
    single = [key for key in sorted(set(SINGLE.findall(wording))) if key in allowed]
    marks = lambda keys: ', '.join('{{' + key + '}}' for key in keys)  # noqa: E731
    if single:
        return f'Use double braces for the parts the app fills in: write {marks(single)}.'
    if missing:
        return f'Keep these placeholders in the prompt: {marks(missing)}.'
    if unknown:
        known = f' It can fill in {marks(sorted(allowed))}.' if allowed else ' This prompt has none.'
        return f'The app does not fill in {marks(unknown)}, so it would be sent as written.{known}'
    return None


def save(database, name: str, wording: str) -> dict:
    require(name)
    prompt = PROMPTS[name]
    default = prompt.default()
    problem = prompt_layout.problems(wording, prompt.layout(), prompt.reader) if prompt.layout else \
        problems(default, wording, prompt.retired)
    if problem:
        raise DomainError(problem, 422, 'prompt_layout' if prompt.layout else 'prompt_placeholders')
    with database.connect(write=True) as connection:
        if wording == default:
            connection.execute('DELETE FROM prompt_overrides WHERE name=?', (name,))
        else:
            connection.execute(
                'INSERT INTO prompt_overrides (name, text, default_text, updated_at) VALUES (?, ?, ?, ?) '
                'ON CONFLICT(name) DO UPDATE SET text=excluded.text, default_text=excluded.default_text, '
                'updated_at=excluded.updated_at', (name, wording, default, database.now()))
        return view(connection, name)


def reset(database, name: str) -> dict:
    require(name)
    with database.connect(write=True) as connection:
        connection.execute('DELETE FROM prompt_overrides WHERE name=?', (name,))
        return view(connection, name)
