"""Lorebooks from other apps read into plain keyword lore (dungeon/lore.py).

Adapted from prosperos-study at bbcbde4: the format signatures in server/library_formats/json_formats.py, the
entry layouts in native_lorebooks.py and card_lore.py, and the conservative keyword rules in
server/lore/import_rules.py. Changes: entries become rows the companion uses straight away instead of review
proposals. Only plain primary keywords and always-on flags carry over; an entry whose keywords are search
patterns (regex, or NovelAI's `&`) keeps its text but stays off, since the Dungeon matches literal words only.
A SillyTavern entry's timing carries over (dungeon/lore.py TIMING): sticky, cooldown, delay, its probability
when `useProbability` is on, and its inclusion group and weight. Secondary keys, order, depth, other apps' timing
and scripts are not translated, and macros stay text.
"""
import re

from dungeon.imports.cards import problem

MAX_ENTRIES = 5000
MAX_TEXT = 20000
MAX_KEYWORDS = 64
# Which apps' lorebook files these are, by what only that app writes (json_formats.FORMATS).
BOOKS = (
    ('novelai', 'NovelAI lorebook', lambda value: 'lorebookVersion' in value),
    ('agnai', 'Agnai memory book', lambda value: value.get('kind') == 'memory'),
    ('risu', 'RisuAI lorebook', lambda value: value.get('type') == 'risu'),
    ('sillytavern', 'SillyTavern world info', lambda value: isinstance(value.get('entries'), dict)),
)
TEXT_FIELDS = {'novelai': 'text', 'agnai': 'entry'}
KEY_FIELDS = {'sillytavern': 'key', 'agnai': 'keywords', 'risu': 'key'}
ALWAYS_FIELDS = {'novelai': 'forceActivation', 'risu': 'alwaysActive'}
TITLE_FIELDS = ('name', 'comment', 'displayName', 'title')
PATTERN = re.compile(r'/.*?/[a-z]*')


def portable(value) -> bool:
    """A character card's book saved on its own: an entries list of {keys, content}."""
    entries = value.get('entries')
    return isinstance(entries, list) and bool(entries) and all(
        isinstance(entry, dict) and 'content' in entry and 'keys' in entry for entry in entries)


def kind_of(value) -> tuple[str, str] | None:
    """The lorebook format a JSON object is in, or None when it is not a lorebook."""
    if not isinstance(value, dict):
        return None
    found = [(key, label) for key, label, matches in BOOKS if matches(value)]
    if len(found) > 1:
        raise problem(f"This file looks like more than one kind of lorebook ({', '.join(label for _, label in found)}). "
                      'Export it again from the app that made it.')
    if found:
        return found[0]
    return ('portable', 'Character lorebook') if portable(value) else None


def rows(value, kind: str) -> list:
    if kind == 'risu':
        if value.get('ver') != 1:
            raise problem('Only version 1 RisuAI lorebook exports can be read.')
        entries = value.get('data')
    else:
        entries = value.get('entries')
    if kind == 'novelai' and value.get('lorebookVersion') not in {3, 4, 5, 6}:
        raise problem('Only NovelAI lorebook versions 3 to 6 can be read.')
    if isinstance(entries, dict) and kind == 'sillytavern':
        entries = list(entries.values())
    if not isinstance(entries, list):
        raise problem('This lorebook has no list of entries.')
    if len(entries) > MAX_ENTRIES:
        raise problem(f'A lorebook can have at most {MAX_ENTRIES:,} entries.')
    return entries


def keywords(entry: dict, kind: str) -> tuple[list[str], bool]:
    """The entry's plain keywords, and whether it used search patterns the Dungeon cannot match."""
    keys = entry.get(KEY_FIELDS.get(kind, 'keys'), [])
    if isinstance(keys, str):
        keys = keys.split(',')
    if not isinstance(keys, list):
        return [], False
    words = [key.strip()[:200] for key in keys if isinstance(key, str) and key.strip()]
    pattern = entry.get('use_regex', entry.get('useRegex')) in (True, 'true')
    pattern = pattern or any(PATTERN.fullmatch(word) for word in words)
    pattern = pattern or (kind == 'novelai' and any('&' in word for word in words))
    return ([] if pattern else words[:MAX_KEYWORDS]), pattern


def enabled(entry: dict) -> bool:
    if entry.get('disable') in (True, 'true'):
        return False
    return entry.get('enabled', True) not in (False, 'false')


def title(entry: dict, number: int, words: list[str] | None = None, text: str = '') -> str:
    """The entry's own name; else its first keywords ("Kingswood, the reeve"); else the start of its text."""
    found = next((entry[key] for key in TITLE_FIELDS if isinstance(entry.get(key), str) and entry[key].strip()), '')
    if found.strip():
        return found.strip()[:160]
    if words:
        named = ', '.join(words[:2])
        return named[:1].upper() + named[1:160]
    said = text.split()
    start = ' '.join(said[:6]) + ('…' if len(said) > 6 else '')
    return start[:160] or f'Entry {number}'


def entry(item, kind: str, number: int) -> dict | None:
    """One entry as the Dungeon keeps it, or None for a folder or an entry with no text."""
    if not isinstance(item, dict) or (kind == 'risu' and item.get('mode') == 'folder'):
        return None
    text = item.get(TEXT_FIELDS.get(kind, 'content'))
    if not isinstance(text, str) or not text.strip():
        return None
    words, pattern = keywords(item, kind)
    always = item.get(ALWAYS_FIELDS.get(kind, 'constant')) in (True, 'true')
    usable = always or bool(words)
    return {'title': title(item, number, words, text), 'text': text.strip()[:MAX_TEXT], 'keywords': words, 'always': always,
            'enabled': enabled(item) and usable, 'pattern': pattern and not always,
            'timing': timing(item) if kind == 'sillytavern' else {}}


def timing(item: dict) -> dict:
    """A SillyTavern entry's timing, as dungeon/lore.py clamped reads it."""
    found = {key: item[field] for key, field in (('sticky', 'sticky'), ('cooldown', 'cooldown'), ('delay', 'delay'),
                                                  ('group_weight', 'groupWeight'), ('group', 'group'))
             if item.get(field) not in (None, '')}
    if item.get('useProbability') in (True, 'true') and item.get('probability') is not None:
        found['chance'] = item['probability']
    return found


def book(value: dict, kind: str, label: str, fallback: str) -> dict:
    """A lorebook file (or a card's own book) as {name, description, format, entries}."""
    entries = [found for number, item in enumerate(rows(value, kind), 1) if (found := entry(item, kind, number))]
    name = value.get('name') if isinstance(value.get('name'), str) else ''
    description = value.get('description') if isinstance(value.get('description'), str) else ''
    return {'name': name.strip()[:120] or fallback, 'description': description.strip()[:MAX_TEXT],
            'format': label, 'entries': entries}
