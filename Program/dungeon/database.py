"""SQLite access adapted from prosperos-study server/database.py at bbcbde4.

Opening a database checks the Dungeon identity marker first: a Study database or any
other non-empty SQLite file is refused rather than silently gaining Dungeon tables.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

from dungeon.clock import AppClock, Clock, stamp
from dungeon.errors import DomainError, require
from dungeon.identity import APP_ID, SCHEMA_VERSION, VERSION, database_path

SCHEMA = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
# The world a piece of work belongs to (dungeon/worlds.py). A request, a background tick and every task they
# start read and write the world they began in, even when the user switches worlds while they wait on a model.
PINNED: ContextVar[tuple[int, Path] | None] = ContextVar('dungeon_world', default=None)


def identifier() -> str:
    return uuid4().hex


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def decode(value: str | None):
    return None if value is None else json.loads(value)


class Database:
    def __init__(self, path: str | Path | None = None, clock: Clock | None = None):
        self.active = Path(path or database_path())
        # The folder of the first world: what every world shares (downloaded models, worlds.json) lives there.
        # Another world's database is in its own folder below it (dungeon/worlds.py), and `use` switches to it.
        self.root = self.active.parent
        self.home = self.active
        self.world: str | None = None  # The open world's id, set by dungeon/worlds.py.
        # Tests hand in a FixedClock; debug time (dungeon/debug_time.py) shifts the app clock wrapped around it.
        self.clock = clock if isinstance(clock, AppClock) else AppClock(clock)
        self.open()

    @property
    def path(self) -> Path:
        """The open world's database, or the one the work under way was pinned to."""
        pinned = PINNED.get()
        return pinned[1] if pinned and pinned[0] == id(self) else self.active

    @contextmanager
    def pin(self):
        """Keep this work (and every task it starts) in the world open now, whatever is opened meanwhile."""
        token = PINNED.set((id(self), self.path))
        try:
            yield
        finally:
            PINNED.reset(token)

    def use(self, path: str | Path):
        """Every part of the app reads and writes through this object, so pointing it at another world's
        database moves all of them there; each connection opens the file anew. Work already pinned to the
        world being left stays there; the work doing the switch follows it."""
        previous, pinned = self.active, PINNED.get()
        self.active = Path(path)
        if pinned and pinned[0] == id(self):
            PINNED.set((id(self), self.active))
        try:
            self.open()
        except BaseException:
            self.active = previous
            if pinned and pinned[0] == id(self):
                PINNED.set(pinned)
            raise

    def open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        inspect_existing(self.path)
        if upgrade_needed(self.path):
            from dungeon import upgrade
            upgrade.run(self.path, self.now())
        with self.connect(write=True) as connection:
            initialize(connection, self.now())
        from dungeon import debug_time
        from dungeon.world import turnover
        debug_time.load(self)
        turnover.load(self)

    def now(self) -> str:
        return stamp(self.clock.now())

    @contextmanager
    def connect(self, write: bool = False):
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
        try:
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def schema_digest() -> str:
    """Changes whenever schema.sql does, so an upgrade is noticed without a version bump."""
    return hashlib.sha256(SCHEMA.encode('utf-8')).hexdigest()


# One-row settings tables, created with their defaults.
SINGLETONS = ('workspace_settings', 'builtin_recall')
# Columns added to a table after it shipped: (table, column, definition). CREATE TABLE IF NOT EXISTS leaves an
# existing table as it was, so an upgraded workspace gains them here. schema.sql lists them too, for new workspaces.
ADDED_COLUMNS = (('story_messages', 'branch_id', "TEXT NOT NULL DEFAULT 'first'"),
                 # When a lore entry applies besides its keywords (dungeon/lore_moments.py), as a JSON list of
                 # conditions; NULL until the player sets one, while the app reads one from its keywords.
                 ('lore_entries', 'moment', 'TEXT'),
                 # A lore entry's timing (dungeon/lore.py TIMING).
                 ('lore_entries', 'sticky', 'INTEGER NOT NULL DEFAULT 0'),
                 ('lore_entries', 'cooldown', 'INTEGER NOT NULL DEFAULT 0'),
                 ('lore_entries', 'delay', 'INTEGER NOT NULL DEFAULT 0'),
                 ('lore_entries', 'chance', 'INTEGER NOT NULL DEFAULT 100'),
                 ('lore_entries', 'lore_group', "TEXT NOT NULL DEFAULT ''"),
                 ('lore_entries', 'group_weight', 'INTEGER NOT NULL DEFAULT 100'),
                 ('story_messages', 'flags', "TEXT NOT NULL DEFAULT '[]'"), ('story_messages', 'previous', 'TEXT'),
                 ('story_rolls', 'threat', 'TEXT'), ('story_wounds', 'rested', 'INTEGER NOT NULL DEFAULT 0'),
                 ('story_wounds', 'treated', 'INTEGER NOT NULL DEFAULT 0'),
                 ('story_wounds', 'captors', 'TEXT'),
                 ('story_fight', 'initiative', 'TEXT'),
                 ('story_fight', 'bare', 'INTEGER NOT NULL DEFAULT 0'),
                 ('story_fight', 'area', 'TEXT'),
                 ('story_quests', 'kind', "TEXT NOT NULL DEFAULT 'authored' CHECK (kind IN ('authored', 'job', "
                                          "'oath'))"),
                 *(('story_quests', column, 'TEXT') for column in ('title', 'hook', 'truth', 'missed', 'faction_id',
                                                                   'giver', 'arc_id', 'thread_id')),
                 ('story_quests', 'reward', 'INTEGER NOT NULL DEFAULT 0'),
                 ('story_quests', 'standing', 'INTEGER NOT NULL DEFAULT 0'),
                 ('story_quests', 'ties', "TEXT NOT NULL DEFAULT '[]'"),
                 ('story_quests', 'tier', 'INTEGER NOT NULL DEFAULT 1'),
                 ('story_quests', 'institution', 'TEXT'), ('story_quests', 'demand', 'TEXT'),
                 ('story_quests', 'weight', 'INTEGER NOT NULL DEFAULT 1'),
                 *(('story_people', axis, 'INTEGER NOT NULL DEFAULT 0')
                   for axis in ('trust', 'affection', 'respect', 'fear', 'desire')),
                 ('story_people', 'impressions', "TEXT NOT NULL DEFAULT '[]'"),
                 # Lines they said in the story, for their voice (dungeon/story_people.py): [{text, day}].
                 ('story_people', 'voice', "TEXT NOT NULL DEFAULT '[]'"),
                 ('workspace_settings', 'intensity', "TEXT NOT NULL DEFAULT 'world' CHECK (intensity IN "
                                                     "('world', 'restrained', 'mature', 'unflinching'))"),
                 ('workspace_settings', 'turn_budget', 'INTEGER NOT NULL DEFAULT 0 CHECK (turn_budget IN '
                                                       '(0, 15, 30, 60, 90, 120, 180))'),
                 ('workspace_settings', 'drama', "TEXT NOT NULL DEFAULT 'world' CHECK (drama IN ('world', 'quiet', "
                                                 "'uneasy', 'eventful', 'merciless'))"),
                 ('workspace_settings', 'cutaways', 'INTEGER NOT NULL DEFAULT 0'),
                 ('workspace_settings', 'passive_art', 'INTEGER NOT NULL DEFAULT 0'),
                 ('workspace_settings', 'defeat', "TEXT NOT NULL DEFAULT 'as_written' CHECK (defeat IN "
                                                  "('as_written', 'by_aim'))"),
                 ('workspace_settings', 'roll_dice', 'INTEGER NOT NULL DEFAULT 0'),
                 ('workspace_settings', 'injury_persistence', "TEXT NOT NULL DEFAULT 'permanent' CHECK "
                                                              "(injury_persistence IN ('permanent', 'temporary', 'none'))"),
                 ('workspace_settings', 'gm_view', 'INTEGER NOT NULL DEFAULT 0'),
                 ('workspace_settings', 'contradiction_check', 'INTEGER NOT NULL DEFAULT 1'),
                 ('workspace_settings', 'context_cap', 'INTEGER NOT NULL DEFAULT 0 CHECK (context_cap IN (0, 4000, '
                                                       '8000, 16000, 32000, 64000))'),
                 ('record_entries', 'weight', 'INTEGER NOT NULL DEFAULT 1'),
                 ('record_entries', 'turn', 'INTEGER NOT NULL DEFAULT 0'),
                 ('story_branches', 'ending', "TEXT NOT NULL DEFAULT ''"),
                 ('story_chapter_ends', 'hook', "TEXT NOT NULL DEFAULT ''"),
                 ('story_chapter_break', 'summary', "TEXT NOT NULL DEFAULT ''"),
                 ('story_chapter_break', 'named', "TEXT NOT NULL DEFAULT ''"),
                 ('story_chapter_break', 'hook', "TEXT NOT NULL DEFAULT ''"),
                 ('story_campaign', 'ruleset', "TEXT NOT NULL DEFAULT 'marvel'"),
                 ('story_campaign', 'intensity', "TEXT CHECK (intensity IN ('world', 'restrained', 'mature', "
                                                 "'unflinching'))"),
                 ('story_campaign', 'drama', "TEXT CHECK (drama IN ('world', 'quiet', 'uneasy', 'eventful', "
                                             "'merciless'))"),
                 ('story_campaign', 'injury_persistence', "TEXT CHECK (injury_persistence IN ('permanent', "
                                                          "'temporary', 'none'))"),
                 ('story_campaign', 'show_odds', 'INTEGER'), ('story_campaign', 'roll_dice', 'INTEGER'),
                 ('story_campaign', 'show_adult_side', 'INTEGER'), ('story_campaign', 'gm_view', 'INTEGER'),
                 ('story_campaign', 'cutaways', 'INTEGER'),
                 ('story_campaign', 'defeat', "TEXT CHECK (defeat IN ('as_written', 'by_aim'))"),
                 ('story_campaign', 'levels', 'TEXT'), ('story_campaign', 'veils', 'TEXT'),
                 ('story_campaign', 'voice', 'TEXT'), ('story_campaign', 'seed', 'TEXT'), ('story_sites', 'site', 'TEXT'),
                 ('story_rolls', 'ruleset', "TEXT NOT NULL DEFAULT 'marvel'"), ('story_rolls', 'target', 'INTEGER'),
                 ('story_rolls', 'skill', 'TEXT'),
                 ('story_campaign', 'pov', "TEXT CHECK (pov IN ('first', 'second', 'third'))"),
                 ('story_campaign', 'tense', "TEXT CHECK (tense IN ('past', 'present'))"),
                 ('story_campaign', 'length', "TEXT CHECK (length IN ('short', 'medium', 'long'))"),
                 ('story_campaign', 'shop_cash', "TEXT CHECK (shop_cash IN ('finite', 'unlimited'))"),
                 ('story_campaign', 'carry_limit', "TEXT CHECK (carry_limit IN ('slots', 'off'))"),
                 ('story_campaign', 'clock', "TEXT CHECK (clock IN ('world', 'story', 'real_time'))"),
                 ('story_campaign', 'rule_text', "TEXT CHECK (rule_text IN ('on', 'off'))"),
                 ('story_campaign', 'leaving', "TEXT CHECK (leaving IN ('anyone', 'fights', 'nobody'))"),
                 ('story_campaign', 'politics', "TEXT CHECK (politics IN ('off', 'quiet', 'true_to_life', 'lively'))"),
                 ('story_inventory', 'stolen', 'INTEGER NOT NULL DEFAULT 0 CHECK (stolen IN (0, 1))'),
                 ('story_inventory', 'condition',
                  "TEXT NOT NULL DEFAULT 'sound' CHECK (condition IN ('sound', 'damaged', 'broken'))"))


# Tables renamed since they were made: (old, new). Renamed before the schema runs, so their rows carry over.
RENAMED_TABLES = (('ledger_entries', 'record_entries'), ('ledger_corrections', 'record_corrections'))


def rename_tables(connection):
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for old, new in RENAMED_TABLES:
        if old in tables and new not in tables:
            connection.execute(f'ALTER TABLE {old} RENAME TO {new}')


def add_columns(connection):
    for table, column, definition in ADDED_COLUMNS:
        columns = {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}
        if columns and column not in columns:
            connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def initialize(connection, timestamp: str):
    claim_identity(connection)
    rename_tables(connection)
    connection.executescript(SCHEMA)
    add_columns(connection)
    for table in SINGLETONS:
        connection.execute(f'INSERT OR IGNORE INTO {table} (id, updated_at) VALUES (1, ?)', (timestamp,))
    from dungeon import table
    table.adopt(connection)
    from dungeon.life import ages
    ages.start_town(connection, timestamp)
    from dungeon.world import retired
    retired.keep(connection, timestamp)
    connection.executemany('INSERT OR REPLACE INTO app_identity (key, value) VALUES (?, ?)',
                           (('schema_version', str(SCHEMA_VERSION)), ('schema_digest', schema_digest()),
                            ('app_version', VERSION)))


def stored_identity(path: Path) -> dict:
    connection = sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)
    try:
        return dict(connection.execute('SELECT key, value FROM app_identity').fetchall())
    finally:
        connection.close()


def upgrade_needed(path: Path) -> bool:
    """An existing workspace whose schema differs from this version's goes through the safe upgrade."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        return stored_identity(path).get('schema_digest') != schema_digest()
    except sqlite3.DatabaseError:
        return False  # An empty database without an identity yet.


FOREIGN = 'This database belongs to another application. Choose a Dungeon workspace.'


def inspect_existing(path: Path):
    """Read-only check, so a foreign file is refused before any pragma can change it."""
    if not path.exists() or path.stat().st_size == 0:
        return
    try:
        connection = sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)
        try:
            validate_identity(connection)
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise DomainError(FOREIGN, 409) from error


def validate_identity(connection):
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'app_identity' not in tables:
        require(not tables, FOREIGN, 409)
        return
    marker = dict(connection.execute('SELECT key, value FROM app_identity').fetchall())
    require(marker.get('app_id') == APP_ID, FOREIGN, 409)
    require(int(marker.get('schema_version', 0)) <= SCHEMA_VERSION,
            'This workspace was created by a newer Dungeon version.', 409)


def claim_identity(connection):
    validate_identity(connection)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'app_identity' not in tables:
        connection.execute('CREATE TABLE app_identity (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        connection.executemany('INSERT INTO app_identity (key, value) VALUES (?, ?)',
                               (('app_id', APP_ID), ('schema_version', str(SCHEMA_VERSION))))


def one(connection, sql: str, values=()) -> dict:
    row = connection.execute(sql, values).fetchone()
    require(row is not None, 'This item could not be found.', 404)
    return dict(row)


def optional(connection, sql: str, values=()) -> dict | None:
    row = connection.execute(sql, values).fetchone()
    return None if row is None else dict(row)


def many(connection, sql: str, values=()) -> list[dict]:
    return [dict(row) for row in connection.execute(sql, values).fetchall()]


def settings(connection) -> dict:
    return one(connection, 'SELECT * FROM workspace_settings WHERE id=1')
