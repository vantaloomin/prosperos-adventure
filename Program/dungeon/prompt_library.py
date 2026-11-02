"""The core prompts a power user may reword in Settings > Developer (docs/prompts.md).

Each prompt's default lives where it is used, a module constant written for `str.format`. Here they are shown and
stored in one form,
with `{{placeholder}}` marks the app fills in. A user's wording is stored in `prompt_overrides`
with the default it replaced, so an update that changes the default can say so without touching
their text. Wording is checked before it is saved: every placeholder the default uses must stay,
and no unknown one may be added, so a typo cannot break replies.

Only the wording is editable. The in-character filter, OOC handling, the NSFW check and every
reply's validation are code (dungeon/in_character.py and the callers) and run whatever it says.
"""
import re
from dataclasses import dataclass, field
from importlib import import_module

from dungeon.database import optional
from dungeon.errors import DomainError

PLACEHOLDER = re.compile(r'\{\{(\w+)\}\}')
# `{name}` with single braces: almost certainly a placeholder typed the wrong way.
SINGLE = re.compile(r'(?<!\{)\{(\w+)\}(?!\})')
FORMAT_TOKEN = re.compile(r'\{\{|\}\}|\{(\w+)\}')


def from_format(text: str) -> str:
    """A `str.format` template in the `{{placeholder}}` form: `{name}` → `{{name}}`, `{{` → `{`."""
    return FORMAT_TOKEN.sub(lambda match: '{{' + match[1] + '}}' if match[1] else match[0][0], text)


def constant(module: str, name: str):
    """A module constant read when needed, so an update to the code is the new default at once."""
    return lambda: from_format(getattr(import_module(module), name))


@dataclass(frozen=True)
class Prompt:
    name: str
    group: str
    label: str
    description: str
    default: object  # () -> str
    placeholders: dict[str, str] = field(default_factory=dict)


CHAT = 'Story'
PROMPTS = {prompt.name: prompt for prompt in (
    Prompt('story-narrator', CHAT, 'The Story narrator',
           'Opens every reply in the story: who the narrator is and its contract with the game (the facts are '
           "fixed, the player's words are expanded, everyone else lives their own life). The scene, the "
           'narration format and the intensity follow it, and the app decides them. OOC answers are also '
           'enforced by the app.',
           constant('dungeon.narration.prompt', 'CORE')),
    Prompt('narrator-craft', CHAT, "The narrator's writing rules",
           'Follows the Story narrator: how to write, the dialogue rules and the phrases never to use. Models '
           'with a small context window get a short version instead. Em dashes and the strongest tells are '
           'also checked by the app after every reply, and rewritten before you see them.',
           constant('dungeon.narration.prompt', 'CRAFT')),
    Prompt('authors-note', CHAT, "Author's note",
           "Goes right before your author's note, the last thing the model reads before your message while "
           'the note is switched on. Your note follows this line.',
           constant('dungeon.authors_note', 'HEADER')),
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
    keys = placeholders(default)
    return {'name': name, 'group': prompt.group, 'label': prompt.label, 'description': prompt.description,
            'text': row['text'] if row else default, 'default': default, 'customized': row is not None,
            # Saved against an older default: the user's wording stays, with a note that a newer one exists.
            'outdated': bool(row and row['default_text'] is not None and row['default_text'] != default),
            'placeholders': keys,
            'placeholder_help': {key: prompt.placeholders.get(key, '') for key in keys}}


def views(database) -> list[dict]:
    with database.connect() as connection:
        return [view(connection, name) for name in PROMPTS]


def problems(default: str, wording: str) -> str | None:
    """Why the wording would break the prompt, in words the user can act on, or None."""
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
    default = PROMPTS[name].default()
    if problem := problems(default, wording):
        raise DomainError(problem, 422, 'prompt_placeholders')
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
