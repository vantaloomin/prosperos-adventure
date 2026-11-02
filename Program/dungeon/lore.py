"""Lore from imported lorebooks (dungeon/imports/lore_routes.py): what the world knows as fact.

A book belongs to the world (a lorebook file imported on its own), or to a city (a world map's notes). Each entry is
plain text with keywords: always-on, or matched only while one of its keywords is in the last few messages, as a
whole word in any letter case, like Prospero's Study's literal keyword matching (server/lore/matching.py at
bbcbde4), or while the scene fits its "when" (dungeon/lore_moments.py: rain, night, a holiday, a place...). No
pattern runs and no model picks entries. The story narrator reads it in every turn (`prompt_text`).

**Timing** (requirements "Lore timers", from SillyTavern's World Info), counted in story lines (a player line and
its narration), for keyword and "when" entries; always-on ones ignore it. Every setting's default leaves an entry
as it always was.
- **Lingers** (`sticky`): once fired, it stays in for that many more lines, keyword or not, with no new chance roll.
- **Rests** (`cooldown`): after it lingers, it cannot fire again for that many lines.
- **Waits** (`delay`): it cannot fire before that line of the campaign.
- **Chance** (`chance`): the percent it fires on when it matches, on the campaign's dice: the same line on the same
  branch gives the same result, and going back gives new dice.
- **Group** (`lore_group`, `group_weight`): of the entries in one group that would fire on a line, one goes in,
  picked by weight on the same dice; while one lingers, the rest of its group stays out.
Timers are game state (`lore_timers`, in dungeon/timeline.py SAVED), so going back rewinds them. Lingering entries
come before newly fired ones and count toward MAX_TRIGGERED.
"""
import random
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from dungeon import lore_moments as moments
from dungeon.database import decode, encode, identifier, many, one
from dungeon.errors import require
from dungeon.imports import formats

# The messages a keyword is looked for in, counting the one being answered.
SCAN_MESSAGES = 4
# At most this many keyword entries join one reply, first by book then by their order in it.
MAX_TRIGGERED = 8
MACROS = ('{{char}}', '<BOT>', '{{user}}', '<USER>')
# A lore entry's timing columns, their defaults and the ranges the editor allows.
TIMING = {'sticky': (0, 0, 500), 'cooldown': (0, 0, 500), 'delay': (0, 0, 5000), 'chance': (100, 0, 100),
          'group_weight': (100, 1, 1000)}
MAX_GROUP = 80
# A Marinara world map's lorebook (dungeon/world/marinara.py) and the source title its city carries.
MAP_FORMAT = 'Marinara world map'
MAP_TITLE = 'Marinara world map: '


def books(connection) -> list[dict]:
    return many(connection, 'SELECT * FROM lore_books ORDER BY created_at')


def when_of(row: dict, holidays: list[str]) -> tuple[list[str], bool]:
    """(the entry's "when", whether the app read it from its keywords). Always-on entries have none."""
    if row['always']:
        return [], False
    if row.get('moment') is not None:
        return decode(row['moment']), False
    found = moments.guessed(decode(row['keywords']), holidays)
    return found, bool(found)


def entry_view(row: dict, scene: dict) -> dict:
    when, guessed = when_of(row, scene['holidays'])
    return {'id': row['id'], 'title': row['title'], 'text': row['text'], 'keywords': decode(row['keywords']),
            'always': bool(row['always']), 'pattern': bool(row['pattern']), 'enabled': bool(row['enabled']),
            'when': [{'key': key, 'label': moments.label(key, scene['city'])} for key in when],
            'when_guessed': guessed, 'fits_now': bool(row['enabled']) and moments.matches(when, scene['now']),
            'timing': timing_of(row)}


def timing_of(row: dict) -> dict:
    """An entry's timing as the editor shows it: the defaults for a row from before timing existed."""
    return {key: row.get(key, default) for key, (default, _low, _high) in TIMING.items()} | {
        'group': row.get('lore_group') or ''}


def story_scene(connection, now: datetime) -> dict:
    """The story's town, its holidays and what holds in the scene right now, for listing entries."""
    from dungeon import story
    where = story.scene_row(connection)
    city = story.city_data(connection, where['city_id'])
    keys = moments.now_keys(city, where['place_id'], story.local_moment(city, now))
    return {'city': city, 'holidays': moments.holiday_names(city), 'now': keys}


def listing(database) -> dict:
    """The world's books, with their entries, and what the "when" pickers offer in the story's town."""
    with database.connect() as connection:
        from dungeon import story_clock
        scene = story_scene(connection, story_clock.now(connection, database.clock))
        # Where each timed entry stands for the story's next line.
        timers = timers_view(connection, next_line(connection))
        found = []
        for book in books(connection):
            entries = many(connection, 'SELECT * FROM lore_entries WHERE book_id=? ORDER BY position', (book['id'],))
            found.append({'id': book['id'], 'name': book['name'], 'description': book['description'],
                          'source_format': book['source_format'], 'source_file': book['source_file'],
                          'city_id': book['city_id'], 'enabled': bool(book['enabled']),
                          'created_at': book['created_at'], 'entries': [entry_view(row, scene) | {'timer': timers.get(row['id'])}
                                                                 for row in entries]})
        return {'books': found, 'choices': moments.choices(scene['city'])}


def next_line(connection) -> int:
    """The number the story's next player line on this branch will have."""
    from dungeon import timeline
    where, values = timeline.visible(connection)
    return one(connection, f"SELECT COUNT(*) AS n FROM story_messages WHERE {where} AND role='user'", values)['n'] + 1


def visible_book(connection, book_id: str) -> dict:
    return one(connection, 'SELECT * FROM lore_books WHERE id=?', (book_id,))


def set_book(database, book_id: str, enabled: bool) -> dict:
    with database.connect(write=True) as connection:
        visible_book(connection, book_id)
        connection.execute('UPDATE lore_books SET enabled=? WHERE id=?', (int(enabled), book_id))
    return listing(database)


def set_entry(database, entry_id: str, enabled: bool) -> dict:
    with database.connect(write=True) as connection:
        entry = one(connection, 'SELECT * FROM lore_entries WHERE id=?', (entry_id,))
        visible_book(connection, entry['book_id'])
        require(not (enabled and entry['pattern']), 'This entry finds its moment with a search pattern, which the '
                'Dungeon cannot match, so it stays off. Copy what matters into an entry of your own.', 422)
        connection.execute('UPDATE lore_entries SET enabled=? WHERE id=?', (int(enabled), entry_id))
    return listing(database)


def set_when(database, entry_id: str, when: list[str]) -> dict:
    """The player's own "when" for an entry: it replaces the one the app read from its keywords. An empty list
    clears it, so the entry comes only by its keywords."""
    with database.connect(write=True) as connection:
        entry = one(connection, 'SELECT * FROM lore_entries WHERE id=?', (entry_id,))
        visible_book(connection, entry['book_id'])
        require(not entry['always'], 'An always-on entry is part of every turn, so it has no "when".', 422)
        connection.execute('UPDATE lore_entries SET moment=? WHERE id=?', (encode(moments.tidy(when)), entry_id))
    return listing(database)


def set_timing(database, entry_id: str, timing: dict) -> dict:
    """An entry's timing (TIMING): each count within its range, the group's name trimmed."""
    with database.connect(write=True) as connection:
        entry = one(connection, 'SELECT * FROM lore_entries WHERE id=?', (entry_id,))
        visible_book(connection, entry['book_id'])
        require(not entry['always'], 'An always-on entry is part of every turn, so it has no timing.', 422)
        values = {key: timing.get(key, entry[key]) for key in TIMING}
        for key, (_default, low, high) in TIMING.items():
            require(isinstance(values[key], int) and low <= values[key] <= high,
                    f'{key} runs from {low} to {high}.', 422)
        group = str(timing.get('group', entry['lore_group']) or '').strip()[:MAX_GROUP]
        connection.execute('UPDATE lore_entries SET sticky=?, cooldown=?, delay=?, chance=?, group_weight=?, '
                           'lore_group=? WHERE id=?', (*values.values(), group, entry_id))
    return listing(database)


def remove_book(database, book_id: str) -> dict:
    with database.connect(write=True) as connection:
        visible_book(connection, book_id)
        connection.execute('DELETE FROM lore_books WHERE id=?', (book_id,))
    return listing(database)


def add_book(connection, timestamp: str, book: dict, filename: str, city_id: str | None = None) -> dict:
    """A lorebook read by dungeon/imports/formats.py, saved with its entries."""
    book_id = identifier()
    connection.execute('INSERT INTO lore_books (id, name, description, source_format, source_file, created_at, '
                       'city_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (book_id, book['name'], book['description'], book['format'], filename[:260], timestamp, city_id))
    for position, entry in enumerate(book['entries']):
        timing = clamped(entry.get('timing') or {})
        connection.execute('INSERT INTO lore_entries (id, book_id, position, title, text, keywords, always, pattern, '
                           'enabled, sticky, cooldown, delay, chance, group_weight, lore_group) '
                           'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (identifier(), book_id, position, entry['title'], entry['text'], encode(entry['keywords']),
                            int(entry['always']), int(entry['pattern']), int(entry['enabled']),
                            *(timing[key] for key in TIMING), timing['group']))
    return {'id': book_id, 'name': book['name'], 'entries': len(book['entries']),
            'off': sum(not entry['enabled'] for entry in book['entries'])}


def bring(database, filename: str, encoded: str) -> dict:
    """Import one lorebook file straight away. Character cards wait for the game's own characters."""
    found = formats.read(filename, encoded)
    require(found['character'] is None and found['book'] is not None,
            'Only lorebooks can be imported for now. Character cards come back when the game has characters of its '
            'own.', 422)
    with database.connect(write=True) as connection:
        book = add_book(connection, database.now(), found['book'], filename)
    return {'format': found['format'], 'book': book}


# Lore that belongs to a city ------------------------------------------------------------------------------
# A world map's notes describe its city's places, so they follow the city: a new world in that city gets them too
# (dungeon/worlds.py), and deleting the city deletes them.

def city_book_ids(connection, city: dict, schema: str = 'main') -> list[str]:
    rows = connection.execute(f'SELECT id FROM {schema}.lore_books WHERE city_id=? ORDER BY created_at',
                              (city['id'],)).fetchall()
    return [row[0] for row in rows]


def forget_city(connection, city: dict) -> None:
    for book_id in city_book_ids(connection, city):
        connection.execute('DELETE FROM lore_books WHERE id=?', (book_id,))


def clamped(timing: dict) -> dict:
    """Timing read from a file (an imported lorebook, a world package): each count kept within its range, anything
    unreadable left at its default."""
    found = {}
    for key, (default, low, high) in TIMING.items():
        value = timing.get(key, default)
        found[key] = min(high, max(low, int(value))) if isinstance(value, (int, float)) and \
            not isinstance(value, bool) else default
    group = timing.get('group')
    return found | {'group': group.strip()[:MAX_GROUP] if isinstance(group, str) else ''}


def carry_city_lore(target: Path, source: Path, city: dict) -> None:
    """A new world in `city` gets the city's lore from the world it was made from."""
    connection = sqlite3.connect(target, isolation_level=None)
    try:
        connection.execute('ATTACH DATABASE ? AS kept', (str(Path(source).resolve()),))
        connection.execute('BEGIN IMMEDIATE')
        for book_id in [] if city_book_ids(connection, city) else city_book_ids(connection, city, 'kept'):
            new_id = identifier()
            connection.execute(
                'INSERT INTO main.lore_books (id, name, description, source_format, source_file, '
                'enabled, created_at, city_id) SELECT ?, name, description, source_format, source_file, enabled, '
                'created_at, ? FROM kept.lore_books WHERE id=?', (new_id, city['id'], book_id))
            connection.execute(
                'INSERT INTO main.lore_entries (id, book_id, position, title, text, keywords, always, pattern, enabled, '
                'moment, sticky, cooldown, delay, chance, lore_group, group_weight) '
                'SELECT lower(hex(randomblob(16))), ?, position, title, text, keywords, always, pattern, enabled, '
                'moment, sticky, cooldown, delay, chance, lore_group, group_weight '
                'FROM kept.lore_entries WHERE book_id=?', (new_id, book_id))
        connection.execute('COMMIT')
    except BaseException:
        if connection.in_transaction:
            connection.execute('ROLLBACK')
        raise
    finally:
        connection.close()


def drop_orphaned(connection) -> None:
    """City lore whose city is gone (deleted in another world, `world_cities` follows the user)."""
    connection.execute('DELETE FROM lore_entries WHERE book_id IN (SELECT id FROM lore_books WHERE city_id IS NOT NULL '
                       'AND city_id NOT IN (SELECT id FROM world_cities))')
    connection.execute('DELETE FROM lore_books WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM '
                       'world_cities)')


# For the narrator ---------------------------------------------------------------------------------------------

HEADING = '## Lore (true in this world; use what bears on the scene, in your own words)'


def spelled(text: str, user: str) -> str:
    """A card's {{user}} becomes the player character's name, and {{char}} (the card's own character) "the
    narrator"."""
    for macro in MACROS:
        text = text.replace(macro, user if macro in ('{{user}}', '<USER>') else 'the narrator')
    return text


def mentioned(keyword: str, text: str) -> bool:
    """A keyword as a whole word, in any letter case."""
    keyword = keyword.strip()
    return bool(keyword) and re.search(r'(?<!\w)' + re.escape(keyword.casefold()) + r'(?!\w)', text) is not None


def prompt_text(connection, city: dict, place_id: str, local: datetime, recent: list[str], user: str = '',
                line: int = 0, branch: str = '') -> str:
    """The lore for this turn: always-on entries, then lingering ones, then entries whose keywords are in the last
    few messages, then those whose "when" fits the scene, at most MAX_TRIGGERED besides the always-on. '' with no
    lore switched on. `line` is the story line being told (0 leaves timing out) and `branch` the branch it is on."""
    return chosen(connection, city, place_id, local, recent, user, line, branch)[0]


def dice(branch: str, line: int, what: str) -> random.Random:
    """The campaign's dice for one entry or group on one line of one branch."""
    return random.Random(f'lore:{branch}:{line}:{what}')


def chosen(connection, city: dict, place_id: str, local: datetime, recent: list[str], user: str = '',
           line: int = 0, branch: str = '') -> tuple[str, list[dict]]:
    """prompt_text, and the entries that fired anew on this line with a timer to start (for `remember`)."""
    entries = many(connection, 'SELECT e.* FROM lore_entries e JOIN lore_books b ON b.id=e.book_id WHERE e.enabled=1 '
                   'AND b.enabled=1 AND (b.city_id IS NULL OR b.city_id=?) ORDER BY b.created_at, e.position',
                   (city['id'],))
    if not entries:
        return '', []
    timers = {row['entry_id']: row for row in many(connection, 'SELECT * FROM lore_timers')} if line else {}
    scanned = '\n'.join(recent[-SCAN_MESSAGES:]).casefold()
    holidays, keys = moments.holiday_names(city), None
    always, lingering, firing = [], [], []
    for entry in entries:
        if entry['always']:
            always.append(entry)
            continue
        timer = timers.get(entry['id'])
        if timer and line <= timer['active_until']:
            lingering.append(entry)
            continue
        if (timer and line <= timer['rest_until']) or (line and line < entry.get('delay', 0)):
            continue
        when = when_of(entry, holidays)[0]
        if any(mentioned(word, scanned) for word in decode(entry['keywords'])):
            kind = 0
        elif when:
            keys = moments.now_keys(city, place_id, local) if keys is None else keys
            if not moments.matches(when, keys):
                continue
            kind = 1
        else:
            continue
        chance = entry.get('chance', 100)
        if chance < 100 and dice(branch, line, entry['id']).randrange(100) >= chance:
            continue
        firing.append((kind, entry))
    firing = [entry for _kind, entry in sorted(firing, key=lambda item: item[0])]
    firing = one_a_group(firing, {entry.get('lore_group') for entry in lingering if entry.get('lore_group')},
                         branch, line)
    picked = [*lingering, *firing][:MAX_TRIGGERED]
    lines = [spelled(f"- {entry['title']}: {entry['text']}" if entry['title'] else f"- {entry['text']}",
                     user or 'the player character') for entry in [*always, *picked]]
    started = [entry for entry in picked if entry in firing and (entry.get('sticky') or entry.get('cooldown'))]
    return (f'{HEADING}\n' + '\n'.join(lines) if lines else ''), started


def one_a_group(firing: list[dict], taken: set[str], branch: str, line: int) -> list[dict]:
    """At most one entry of each group, picked by weight; none of a group one of whose entries lingers."""
    groups: dict[str, list[dict]] = {}
    for entry in firing:
        if entry.get('lore_group'):
            groups.setdefault(entry['lore_group'], []).append(entry)
    keep = {name: dice(branch, line, f'group:{name}').choices(members, [item['group_weight'] for item in members])[0]
            for name, members in groups.items() if name not in taken}
    return [entry for entry in firing if not entry.get('lore_group') or keep.get(entry['lore_group']) is entry]


def remember(connection, started: list[dict], line: int) -> None:
    """The timers of the entries that fired anew on `line`: in through line + sticky, resting cooldown lines after."""
    for entry in started:
        until = line + entry['sticky']
        connection.execute('INSERT INTO lore_timers (entry_id, active_until, rest_until) VALUES (?, ?, ?) '
                           'ON CONFLICT(entry_id) DO UPDATE SET active_until=excluded.active_until, '
                           'rest_until=excluded.rest_until', (entry['id'], until, until + entry['cooldown']))


def timers_view(connection, line: int) -> dict:
    """Each timed entry's state at `line`, for the GM view: lingering, resting, waiting or ready."""
    timers = {row['entry_id']: row for row in many(connection, 'SELECT * FROM lore_timers')}
    states = {}
    for entry in many(connection, 'SELECT id, sticky, cooldown, delay FROM lore_entries WHERE always=0 AND '
                      '(sticky>0 OR cooldown>0 OR delay>0)'):
        timer = timers.get(entry['id'])
        if timer and line <= timer['active_until']:
            states[entry['id']] = {'state': 'lingering', 'lines': timer['active_until'] - line + 1}
        elif timer and line <= timer['rest_until']:
            states[entry['id']] = {'state': 'resting', 'lines': timer['rest_until'] - line + 1}
        elif line < entry['delay']:
            states[entry['id']] = {'state': 'waiting', 'lines': entry['delay'] - line}
        else:
            states[entry['id']] = {'state': 'ready', 'lines': 0}
    return states
