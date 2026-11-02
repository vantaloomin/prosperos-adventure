-- Prospero Dungeon workspace schema. One database is one world: its persona, its story and the settings that
-- follow the user from world to world (dungeon/worlds.py). Nothing here is migrated: a schema change makes the app
-- upgrade a copy of the workspace (dungeon/upgrade.py), and CREATE TABLE IF NOT EXISTS keeps existing tables.

CREATE TABLE IF NOT EXISTS app_identity (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  user_timezone TEXT NOT NULL DEFAULT 'UTC',
  -- 'default' until set: 'pc' follows this PC's timezone, 'chosen' was picked in Settings and is kept.
  user_timezone_source TEXT NOT NULL DEFAULT 'default' CHECK (user_timezone_source IN ('default', 'pc', 'chosen')),
  -- Start the local programs in use when the Dungeon starts (dungeon/launcher.py); off until turned on.
  auto_launch INTEGER NOT NULL DEFAULT 0 CHECK (auto_launch IN (0, 1)),
  -- The app's colors, Prospero's Study's palettes. custom_palette is JSON hex colors.
  color_scheme TEXT NOT NULL DEFAULT 'ink' CHECK (color_scheme IN ('ink', 'slate', 'umber', 'moss', 'wine', 'ash', 'custom')),
  custom_palette TEXT NOT NULL DEFAULT '',
  -- Light or dark: 'system' matches the computer (Paper or Ink), 'paper' is the light profile, 'scheme' uses color_scheme.
  theme TEXT NOT NULL DEFAULT 'scheme' CHECK (theme IN ('system', 'scheme', 'paper')),
  -- "Why it went this way": the odds behind how a turning went (dungeon/consequences.py).
  show_odds INTEGER NOT NULL DEFAULT 0 CHECK (show_odds IN (0, 1)),
  -- The adult side of life (dungeon/world/intimacy.py): off until the user turns it on; showing what townsfolk
  -- are like that way is a hidden value.
  adult_side INTEGER NOT NULL DEFAULT 0 CHECK (adult_side IN (0, 1)),
  show_adult_side INTEGER NOT NULL DEFAULT 0 CHECK (show_adult_side IN (0, 1)),
  -- Settings > Developer: write every model request and response in full to logs/model-calls (dungeon/model_calls.py).
  record_model_calls INTEGER NOT NULL DEFAULT 0 CHECK (record_model_calls IN (0, 1)),
  -- Automatic backups of every world (dungeon/auto_backup.py).
  auto_backups TEXT NOT NULL DEFAULT 'daily' CHECK (auto_backups IN ('off', 'daily', 'weekly')),
  -- How far the story goes on the page (dungeon/story.py intensity): the world's own preset, or one the player chose.
  intensity TEXT NOT NULL DEFAULT 'world' CHECK (intensity IN ('world', 'restrained', 'mature', 'unflinching')),
  -- Seconds a story turn may take before its optional steps give way (dungeon/pace.py); 0 is automatic.
  turn_budget INTEGER NOT NULL DEFAULT 0 CHECK (turn_budget IN (0, 15, 30, 60, 90, 120, 180)),
  -- How eventful the story is (dungeon/happenings.py): the world's own level, or one the player chose.
  drama TEXT NOT NULL DEFAULT 'world' CHECK (drama IN ('world', 'quiet', 'uneasy', 'eventful', 'merciless')),
  cutaways INTEGER NOT NULL DEFAULT 0,
  -- Pictures made on their own from what happens in the story, a few each session (dungeon/art.py passive).
  passive_art INTEGER NOT NULL DEFAULT 0,
  -- A defeat under 5E: death saves as written, or what the foes were after (dungeon/combat.py fall).
  defeat TEXT NOT NULL DEFAULT 'as_written' CHECK (defeat IN ('as_written', 'by_aim')),
  -- Dice that tumble on screen and land on each roll the code made; only while the dice are shown.
  roll_dice INTEGER NOT NULL DEFAULT 0,
  -- The GM view (dungeon/record.py): the whole record, hidden truth included, to see and edit.
  gm_view INTEGER NOT NULL DEFAULT 0,
  -- Whether a narration that clashes with the record is rewritten before the player sees it (dungeon/story.py told).
  contradiction_check INTEGER NOT NULL DEFAULT 1,
  -- Tokens a turn may send at most (dungeon/remembering.py); 0 is the model's whole window.
  context_cap INTEGER NOT NULL DEFAULT 0 CHECK (context_cap IN (0, 4000, 8000, 16000, 32000, 64000)),
  -- Injury persistence (dungeon/injuries.py): lasting injuries stay, fade, or never happen.
  injury_persistence TEXT NOT NULL DEFAULT 'permanent' CHECK (injury_persistence IN ('permanent', 'temporary', 'none')),
  -- The first-run notice: the story is AI written, and the user is 18 or older.
  ai_notice_at TEXT,
  updated_at TEXT NOT NULL
);

-- Settings > Models: one provider, model and saved key each (config is JSON; the key lives in the
-- OS credential vault under credential_ref).
CREATE TABLE IF NOT EXISTS model_profiles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  config TEXT NOT NULL,
  credential_ref TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Which profile does each job; a job without a row uses the 'chat' job's profile.
CREATE TABLE IF NOT EXISTS model_routes (
  job TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
  updated_at TEXT NOT NULL
);

-- Built-in recall (Settings > Models, dungeon/providers/builtin_recall.py): a llama.cpp server the
-- Dungeon starts on this PC with an embedding model file the user downloaded. While enabled it does
-- semantic recall instead of a profile.
CREATE TABLE IF NOT EXISTS builtin_recall (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
  model_path TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

-- The user's own wording for an editable prompt (dungeon/prompt_library.py); without a row the default is used.
-- default_text is the default it replaced, so a newer default can be pointed out.
CREATE TABLE IF NOT EXISTS prompt_overrides (
  name TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  default_text TEXT,
  updated_at TEXT NOT NULL
);

-- Local programs the Dungeon starts (dungeon/launcher.py): where each is installed, found or typed by the
-- user (`chosen`), and KoboldCpp's model file. Whether they all start with the Dungeon is
-- workspace_settings.auto_launch.
CREATE TABLE IF NOT EXISTS local_programs (
  program TEXT PRIMARY KEY CHECK (program IN ('lmstudio', 'ollama', 'kobold', 'comfyui')),
  path TEXT NOT NULL DEFAULT '',
  chosen INTEGER NOT NULL DEFAULT 0 CHECK (chosen IN (0, 1)),
  model_path TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

-- An image backend (Settings > Images). Secrets live in the OS vault under `credential_ref`, never here.
CREATE TABLE IF NOT EXISTS image_backends (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('comfyui', 'codex', 'hosted')),
  provider TEXT NOT NULL,
  label TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  position INTEGER NOT NULL,
  config TEXT NOT NULL DEFAULT '{}',
  credential_ref TEXT,
  -- The user marked a non-loopback ComfyUI address as a machine they control.
  controlled_machine INTEGER NOT NULL DEFAULT 0 CHECK (controlled_machine IN (0, 1)),
  concurrency INTEGER NOT NULL DEFAULT 1,
  -- Set when the backend must not run until the user acts, such as signing in to Codex again.
  blocked_reason TEXT,
  disclosure_accepted_at TEXT,
  allows_nsfw INTEGER NOT NULL DEFAULT 0 CHECK (allows_nsfw IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Debug time (Settings > Developer, dungeon/debug_time.py). While the row exists the app clock reads
-- app_anchor + (real time since real_anchor) * speed. `snapshot` is the database copy taken first, which
-- returning to real time restores unless the user keeps what happened; `backup` is the verified archive.
CREATE TABLE IF NOT EXISTS debug_time (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  app_anchor TEXT NOT NULL,
  real_anchor TEXT NOT NULL,
  speed REAL NOT NULL DEFAULT 1 CHECK (speed >= 1),
  started_at TEXT NOT NULL,
  app_started_at TEXT NOT NULL,
  snapshot TEXT NOT NULL,
  backup TEXT NOT NULL
);

-- Who the user is in this world (dungeon/worlds.py): the persona the world belongs to, copied from worlds.json
-- in the data folder whenever the world opens or the persona changes. The narrator's prompt reads it here.
-- `town_seed` is the world's own, set once when the world is made ('' in the first world); `townsfolk_key` names a
-- townsperson the user plays. The home is the world's (dungeon/world/where.py).
CREATE TABLE IF NOT EXISTS persona (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  persona_id TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  gender TEXT NOT NULL DEFAULT '',
  age INTEGER,
  about TEXT NOT NULL DEFAULT '',
  birthday TEXT NOT NULL DEFAULT '',
  townsfolk_key TEXT NOT NULL DEFAULT '',
  town_seed TEXT NOT NULL DEFAULT '',
  home_city_id TEXT NOT NULL DEFAULT '',
  home_neighbourhood TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT '',
  lifespan INTEGER,
  updated_at TEXT NOT NULL
);

-- Cities the user wrote or copied. Built-in cities ship as files and are never stored here.
CREATE TABLE IF NOT EXISTS world_cities (
  id TEXT PRIMARY KEY,
  definition TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Changes to a city the workspace keeps (dungeon/world/changes.py): the user's own (`origin` 'real' and
-- `observation_id` are left from real-world lookups and stay unused). Seeded changes are computed from the city and
-- month, not stored; one the user dismisses is listed in world_change_dismissals and never happens.
CREATE TABLE IF NOT EXISTS world_changes (
  id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('opening', 'closing', 'renovation', 'roadworks', 'news')),
  origin TEXT NOT NULL CHECK (origin IN ('user', 'real')),
  place_id TEXT,
  neighborhood_id TEXT,
  name TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  details TEXT,
  announced_on TEXT NOT NULL,
  starts_on TEXT NOT NULL,
  ends_on TEXT,
  observation_id TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS world_changes_city ON world_changes(city_id, starts_on);

CREATE TABLE IF NOT EXISTS world_change_dismissals (
  change_id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  dismissed_at TEXT NOT NULL
);

-- Lore from imported lorebooks (dungeon/lore.py): a book belongs to one city, or to the whole world when city_id
-- is NULL. An entry joins the prompt when one of its keywords is in the story, or always when `always` is set;
-- `pattern` marks entries whose search patterns the app cannot match, which stay off.
CREATE TABLE IF NOT EXISTS lore_books (
  id TEXT PRIMARY KEY,
  city_id TEXT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  source_format TEXT NOT NULL DEFAULT '',
  source_file TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lore_entries (
  id TEXT PRIMARY KEY,
  book_id TEXT NOT NULL REFERENCES lore_books(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL,
  keywords TEXT NOT NULL DEFAULT '[]',
  always INTEGER NOT NULL DEFAULT 0 CHECK (always IN (0, 1)),
  pattern INTEGER NOT NULL DEFAULT 0 CHECK (pattern IN (0, 1)),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  -- When it applies besides its keywords (dungeon/lore_moments.py): a JSON list such as ["weather:rain"], or NULL
  -- while the app reads one from its keywords.
  moment TEXT,
  -- Timing (dungeon/lore.py TIMING), counted in story lines: it lingers `sticky` lines after it fires, then rests
  -- `cooldown` lines, can fire only from line `delay`, fires on `chance` percent, and of one `lore_group` only one
  -- goes in a line, by `group_weight`. The defaults leave an entry as it always was.
  sticky INTEGER NOT NULL DEFAULT 0,
  cooldown INTEGER NOT NULL DEFAULT 0,
  delay INTEGER NOT NULL DEFAULT 0,
  chance INTEGER NOT NULL DEFAULT 100,
  lore_group TEXT NOT NULL DEFAULT '',
  group_weight INTEGER NOT NULL DEFAULT 100
);

CREATE INDEX IF NOT EXISTS lore_entries_book ON lore_entries(book_id, position);

-- Lore entries fired with a timer (dungeon/lore.py): in the narrator's lore through line `active_until`, then not
-- again before line `rest_until`. Game state (dungeon/timeline.py SAVED), so going back rewinds the timers.
CREATE TABLE IF NOT EXISTS lore_timers (
  entry_id TEXT PRIMARY KEY,
  active_until INTEGER NOT NULL,
  rest_until INTEGER NOT NULL
);

-- A reference library (dungeon/library.py): long texts the player adds to the world (a world bible, a novel, a
-- script, a wiki export), split into passages; the few that fit the story join the narrator's prompt.
CREATE TABLE IF NOT EXISTS library_books (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  source_format TEXT NOT NULL DEFAULT '',
  source_file TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_passages (
  id TEXT PRIMARY KEY,
  book_id TEXT NOT NULL REFERENCES library_books(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS library_passages_book ON library_passages(book_id, position);

-- The story message (seq of the player's line) each passage was last given with, so the next few turns skip it.
CREATE TABLE IF NOT EXISTS library_given (
  passage_id TEXT PRIMARY KEY REFERENCES library_passages(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL
);

-- The story (dungeon/story.py): one scene (where the user is) and its history.
CREATE TABLE IF NOT EXISTS story_scene (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_messages (
  id TEXT PRIMARY KEY,
  seq INTEGER NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('user', 'narrator', 'scene')),
  text TEXT NOT NULL,
  client_id TEXT UNIQUE,
  reply_to TEXT,
  status TEXT NOT NULL DEFAULT 'complete' CHECK (status IN ('complete', 'failed')),
  error TEXT,
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  -- The branch the message was written in (dungeon/timeline.py); 'first' is the story's first.
  branch_id TEXT NOT NULL DEFAULT 'first',
  -- A narration's paragraphs with a problem the checks left in them, and its wording before the player's last
  -- rewrite as {text, flags} (dungeon/passages.py).
  flags TEXT NOT NULL DEFAULT '[]',
  previous TEXT
);

-- Branches of the story (dungeon/timeline.py). A branch shows its parent's messages before `fork_seq`, then its
-- own. `tip` is the game state where the player left it, kept while another branch is played.
CREATE TABLE IF NOT EXISTS story_branches (
  id TEXT PRIMARY KEY,
  parent_id TEXT,
  fork_seq INTEGER,
  tip TEXT,
  created_at TEXT NOT NULL,
  -- How it ended, when the character died ('death') or was lost ('lost') there (dungeon/chapters.py tree).
  ending TEXT NOT NULL DEFAULT ''
);

-- Which branch is being played.
CREATE TABLE IF NOT EXISTS story_timeline (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  branch_id TEXT NOT NULL DEFAULT 'first'
);

-- The game state at the start of each of the player's turns: going back to a turn puts it back.
CREATE TABLE IF NOT EXISTS story_saves (
  message_id TEXT PRIMARY KEY REFERENCES story_messages(id) ON DELETE CASCADE,
  state TEXT NOT NULL
);

-- The record (dungeon/record.py): facts the game holds true, each world truth, the character's belief, or
-- both. Branched with the story (dungeon/timeline.py SAVED), so `message_id` is not a foreign key.
CREATE TABLE IF NOT EXISTS record_entries (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('death', 'item', 'wound', 'promise', 'location', 'secret', 'relationship',
                                     'fact')),
  subject TEXT NOT NULL,
  text TEXT NOT NULL,
  truth TEXT NOT NULL DEFAULT 'both' CHECK (truth IN ('world', 'belief', 'both')),
  source TEXT NOT NULL CHECK (source IN ('code', 'narrator', 'player')),
  message_id TEXT,
  removed INTEGER NOT NULL DEFAULT 0 CHECK (removed IN (0, 1)),
  created_at TEXT NOT NULL,
  -- How much it matters (1 to 3) and the turn the character last had it in mind (dungeon/remembering.py).
  weight INTEGER NOT NULL DEFAULT 1,
  turn INTEGER NOT NULL DEFAULT 0
);

-- Every change the player made to their journal; `after` is NULL for a fact removed.
CREATE TABLE IF NOT EXISTS record_corrections (
  id TEXT PRIMARY KEY,
  entry_id TEXT NOT NULL,
  before TEXT NOT NULL,
  after TEXT,
  created_at TEXT NOT NULL
);

-- The story so far, before the messages the narrator reads word for word (dungeon/record.py fold).
CREATE TABLE IF NOT EXISTS story_summary (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  text TEXT NOT NULL,
  through_seq INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

-- The story's quests (dungeon/quests.py): their text is in the town's adventure file; the deadline is story time.
CREATE TABLE IF NOT EXISTS story_quests (
  id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'done', 'failed', 'missed')),
  known INTEGER NOT NULL DEFAULT 0 CHECK (known IN (0, 1)),
  due_at TEXT,
  outcome TEXT NOT NULL DEFAULT '',
  -- Where it came from: a town's adventure file, a faction's job (dungeon/jobs.py), or an oath the player swore.
  kind TEXT NOT NULL DEFAULT 'authored' CHECK (kind IN ('authored', 'job', 'oath')),
  -- A job's or an oath's own text (an authored quest's is in its adventure file).
  title TEXT,
  hook TEXT,
  truth TEXT,
  missed TEXT,
  -- Who asked, for whom, what it pays (hundredths) and the standing it earns.
  faction_id TEXT,
  giver TEXT,
  reward INTEGER NOT NULL DEFAULT 0,
  standing INTEGER NOT NULL DEFAULT 0,
  -- For the story director: the arc it feeds, its thread, and the loose ends it leaves ([{kind, ref}]).
  arc_id TEXT,
  thread_id TEXT,
  ties TEXT NOT NULL DEFAULT '[]',
  -- Its tier on the shared ladder (dungeon/tiers.py).
  tier INTEGER NOT NULL DEFAULT 1,
  -- An institution's demand (dungeon/institutions.py): whose, which and when (`id@when`, so it opens once), and its
  -- weight in the term's grades.
  institution TEXT,
  demand TEXT,
  weight INTEGER NOT NULL DEFAULT 1
);

-- What the character carries and the shops' stock (dungeon/inventory.py); money in hundredths of the currency.
CREATE TABLE IF NOT EXISTS story_inventory (
  id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL CHECK (qty >= 0),
  stolen INTEGER NOT NULL DEFAULT 0 CHECK (stolen IN (0, 1)),
  condition TEXT NOT NULL DEFAULT 'sound' CHECK (condition IN ('sound', 'damaged', 'broken'))
);

CREATE TABLE IF NOT EXISTS story_purse (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  coins INTEGER NOT NULL CHECK (coins >= 0)
);

CREATE TABLE IF NOT EXISTS story_stock (
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL CHECK (qty >= 0),
  PRIMARY KEY (city_id, place_id, item_id)
);

-- Each shop's till and when it last restocked (dungeon/inventory.py), set up the first time anyone deals with it.
CREATE TABLE IF NOT EXISTS story_shops (
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  cash INTEGER NOT NULL,
  restocked TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (city_id, place_id)
);

-- How the character looks right now (dungeon/appearance.py): cleanliness 0 to 3 and its marks (JSON), the clothes'
-- condition, the state of dress per layer (JSON), and the paid baths, laundry and mending already used (JSON).
CREATE TABLE IF NOT EXISTS story_appearance (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  grime INTEGER NOT NULL DEFAULT 0 CHECK (grime BETWEEN 0 AND 3),
  marks TEXT NOT NULL DEFAULT '[]',
  clothes TEXT NOT NULL DEFAULT 'intact' CHECK (clothes IN ('intact', 'rumpled', 'torn', 'ruined')),
  dress TEXT NOT NULL DEFAULT '{}',
  used TEXT
);

-- Each line's change to the character's look, decided once (dungeon/appearance.py).
CREATE TABLE IF NOT EXISTS story_appearance_turns (
  message_id TEXT PRIMARY KEY,
  lines TEXT NOT NULL
);

-- Services paid for (dungeon/inventory.py): lodging, a meal, a bath, a guide, kept for the story day they were bought.
CREATE TABLE IF NOT EXISTS story_services (
  id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  day TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Markets moved by Life Cards (dungeon/inventory.py move_market): a kind of goods' prices in a town, until a day.
CREATE TABLE IF NOT EXISTS story_markets (
  id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  goods TEXT NOT NULL,
  shift INTEGER NOT NULL,
  until TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_trades (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('buy', 'sell')),
  city_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

-- The character's wounds and the fight under way (dungeon/combat.py); each round is kept with the player's line.
CREATE TABLE IF NOT EXISTS story_wounds (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 5),
  dead INTEGER NOT NULL DEFAULT 0 CHECK (dead IN (0, 1)),
  rested INTEGER NOT NULL DEFAULT 0,
  treated INTEGER NOT NULL DEFAULT 0,
  captors TEXT
);

-- Life Cards drawn into the story (dungeon/happenings.py): each line's draw for a scene (town, road, rest), with
-- the card (none when nothing happened) and what the narrator was told.
CREATE TABLE IF NOT EXISTS story_cards (
  message_id TEXT NOT NULL,
  scene TEXT NOT NULL,
  day TEXT NOT NULL,
  card_id TEXT,
  lines TEXT NOT NULL,
  PRIMARY KEY (message_id, scene)
);

-- The character's tier track (dungeon/tiers.py): the arc and pace the campaign started with, and the track's points.
CREATE TABLE IF NOT EXISTS story_tier (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  arc TEXT NOT NULL,
  pace TEXT NOT NULL,
  points INTEGER NOT NULL DEFAULT 0
);

-- Progression (dungeon/growth.py): the stats marked by use since the last rest and how often each was used since the
-- last milestone; the dark tracks, their lasting changes and whether one has cost the player the character.
CREATE TABLE IF NOT EXISTS story_marks (
  stat TEXT PRIMARY KEY,
  marked INTEGER NOT NULL DEFAULT 0,
  uses INTEGER NOT NULL DEFAULT 0,
  last_message TEXT
);

CREATE TABLE IF NOT EXISTS story_dark (
  track TEXT PRIMARY KEY,
  points INTEGER NOT NULL DEFAULT 0,
  changes TEXT NOT NULL DEFAULT '[]',
  lost INTEGER NOT NULL DEFAULT 0
);

-- The director (dungeon/director.py): the campaign's hand and spine, the lines played and their kinds (the tension
-- curve), the seeds planted; each arc's stage and how hard play has bitten on it; the threads (the GM's notebook);
-- and the nemeses.
CREATE TABLE IF NOT EXISTS story_director (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  world TEXT,
  hand TEXT NOT NULL DEFAULT 'guiding' CHECK (hand IN ('soft', 'guiding', 'firm')),
  spine_id TEXT,
  lines INTEGER NOT NULL DEFAULT 0,
  recent TEXT NOT NULL DEFAULT '[]',
  planted TEXT NOT NULL DEFAULT '[]',
  last_message TEXT
);

CREATE TABLE IF NOT EXISTS story_arcs (
  arc_id TEXT PRIMARY KEY,
  stage INTEGER NOT NULL DEFAULT 0,
  bite INTEGER NOT NULL DEFAULT 0,
  moved_at TEXT,
  told INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS story_threads (
  id TEXT PRIMARY KEY,
  arc_id TEXT,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  seen TEXT NOT NULL DEFAULT '',
  truth TEXT NOT NULL DEFAULT '',
  words TEXT NOT NULL DEFAULT '[]',
  heat REAL NOT NULL DEFAULT 0,
  bite INTEGER NOT NULL DEFAULT 0,
  known INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',
  quest_id TEXT,
  opened_at TEXT,
  touched_at TEXT
);

CREATE TABLE IF NOT EXISTS story_nemeses (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  grudge TEXT NOT NULL,
  remembers TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'alive',
  since TEXT NOT NULL,
  thread_id TEXT
);

-- Off-page beats (dungeon/beats.py): what has become of the people the character is connected to, each beat that
-- happened, the word of it still travelling to the character, and when the off-page clock last looked.
CREATE TABLE IF NOT EXISTS story_fates (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  state TEXT NOT NULL,
  since TEXT NOT NULL
);

-- Bonds (dungeon/bonds.py): the people the character is bound to, earned by warm feelings or sworn.
CREATE TABLE IF NOT EXISTS story_bonds (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  how TEXT NOT NULL CHECK (how IN ('earned', 'sworn')),
  since TEXT NOT NULL
);

-- The party (dungeon/party.py): who travels with the character, with their townsfolk sheet from home.
CREATE TABLE IF NOT EXISTS story_party (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  city_id TEXT NOT NULL,
  sheet TEXT NOT NULL,
  joined TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_beats (
  message_id TEXT NOT NULL,
  key TEXT NOT NULL,
  card_id TEXT NOT NULL,
  at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_word (
  about TEXT NOT NULL,
  text TEXT NOT NULL,
  truth TEXT NOT NULL,
  heard_at TEXT NOT NULL,
  told INTEGER NOT NULL DEFAULT 0,
  message_id TEXT
);

CREATE TABLE IF NOT EXISTS story_offpage (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  checked_at TEXT,
  quiet INTEGER NOT NULL DEFAULT 0
);

-- The factions' progress clocks (dungeon/factions.py): how far each has run, when it filled, and whether the news
-- has reached the character.
CREATE TABLE IF NOT EXISTS story_clocks (
  faction_id TEXT NOT NULL,
  clock_id TEXT NOT NULL,
  filled INTEGER NOT NULL DEFAULT 0,
  done_at TEXT,
  told INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (faction_id, clock_id)
);

-- The character's standing with each faction (dungeon/factions.py), -5 to 5.
CREATE TABLE IF NOT EXISTS story_reputation (
  faction_id TEXT PRIMARY KEY,
  value INTEGER NOT NULL DEFAULT 0 CHECK (value BETWEEN -5 AND 5)
);

-- The character's stress track (dungeon/stress.py), and how many they have killed.
CREATE TABLE IF NOT EXISTS story_stress (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  points INTEGER NOT NULL DEFAULT 0 CHECK (points BETWEEN 0 AND 12),
  kills INTEGER NOT NULL DEFAULT 0
);

-- The character's lasting injuries (dungeon/injuries.py), each from the table, since a story time.
CREATE TABLE IF NOT EXISTS story_injuries (
  injury_id TEXT PRIMARY KEY,
  since TEXT NOT NULL
);

-- Each line's treatment (dungeon/injuries.py), decided once.
CREATE TABLE IF NOT EXISTS story_treatments (
  message_id TEXT PRIMARY KEY,
  lines TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_fight (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  round INTEGER NOT NULL,
  wants TEXT NOT NULL,
  foes TEXT NOT NULL,
  initiative TEXT,
  -- A fight begun bare-handed stays so until a line names a weapon (dungeon/combat.py hands).
  bare INTEGER NOT NULL DEFAULT 0,
  -- The named area the character fights from ("the stairs", dungeon/ranges.py).
  area TEXT
);

-- A haggle at a shop holds for the rest of that story day (dungeon/inventory.py): percent off (negative) or on.
CREATE TABLE IF NOT EXISTS story_haggles (
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  day TEXT NOT NULL,
  percent INTEGER NOT NULL,
  PRIMARY KEY (city_id, place_id)
);

-- What happened at the counter on a player's line (haggling, buying in the story), decided once and retold the same.
CREATE TABLE IF NOT EXISTS story_counter (
  message_id TEXT PRIMARY KEY REFERENCES story_messages(id) ON DELETE CASCADE,
  lines TEXT NOT NULL
);

-- How long each step of a turn took and what was skipped for time (dungeon/pace.py), kept with the player's line.
CREATE TABLE IF NOT EXISTS story_turn_steps (
  message_id TEXT PRIMARY KEY REFERENCES story_messages(id) ON DELETE CASCADE,
  steps TEXT NOT NULL
);

-- What is inside things the player looked into, rolled the first time (dungeon/finds.py); contents is JSON.
CREATE TABLE IF NOT EXISTS story_finds (
  key TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  word TEXT NOT NULL,
  contents TEXT NOT NULL,
  seen INTEGER NOT NULL DEFAULT 0 CHECK (seen IN (0, 1)),
  created_at TEXT NOT NULL
);

-- What a player's line looked into and took (dungeon/finds.py), decided once and retold the same.
CREATE TABLE IF NOT EXISTS story_looks (
  message_id TEXT PRIMARY KEY REFERENCES story_messages(id) ON DELETE CASCADE,
  lines TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_rounds (
  message_id TEXT PRIMARY KEY REFERENCES story_messages(id) ON DELETE CASCADE,
  lines TEXT NOT NULL
);

-- The story's own time once a campaign starts (dungeon/story_clock.py); without it the story runs on the app clock.
CREATE TABLE IF NOT EXISTS story_clock (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  at TEXT NOT NULL
);

-- The app clock when the story last caught up with real time (dungeon/story_clock.py caught_up). Not branched: a
-- rewound line does not bring back the hours since.
CREATE TABLE IF NOT EXISTS story_real (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  at TEXT NOT NULL
);

-- Prospero stats per actor (dungeon/sheet.py); 'persona' is the player's character.
CREATE TABLE IF NOT EXISTS character_stats (
  actor TEXT NOT NULL,
  stat TEXT NOT NULL CHECK (stat IN ('Mind', 'Allure', 'Resolve', 'Vitality', 'Essence', 'Luck')),
  value INTEGER NOT NULL CHECK (value BETWEEN 1 AND 30),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (actor, stat)
);

-- Every roll of a turn (dungeon/turn.py), made once per player message before the narrator writes; retelling
-- keeps the dice. Shown to the player only while "Show the dice" (Story > Tone and rules) is on.
CREATE TABLE IF NOT EXISTS story_rolls (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL REFERENCES story_messages(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  said INTEGER NOT NULL DEFAULT 0 CHECK (said IN (0, 1)),
  stat TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  die INTEGER,
  natural INTEGER NOT NULL,
  bonus INTEGER NOT NULL,
  shift INTEGER NOT NULL,
  total INTEGER NOT NULL,
  threat TEXT,
  ruleset TEXT NOT NULL DEFAULT 'marvel',
  target INTEGER,
  skill TEXT,
  band TEXT NOT NULL CHECK (band IN ('critical_failure', 'failure', 'failure_upside', 'success_cost', 'success',
                                     'critical_success')),
  created_at TEXT NOT NULL,
  UNIQUE (message_id, position)
);

-- People the user has met in their story (dungeon/story_people.py): one meeting a local day, a few notes.
CREATE TABLE IF NOT EXISTS story_people (
  key TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  name TEXT NOT NULL,
  first_met_at TEXT NOT NULL,
  last_met_at TEXT NOT NULL,
  last_day TEXT NOT NULL,
  meetings INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT '[]',
  -- Their feelings toward the player's character and their impressions of them (dungeon/feelings.py).
  trust INTEGER NOT NULL DEFAULT 0,
  affection INTEGER NOT NULL DEFAULT 0,
  respect INTEGER NOT NULL DEFAULT 0,
  fear INTEGER NOT NULL DEFAULT 0,
  desire INTEGER NOT NULL DEFAULT 0,
  impressions TEXT NOT NULL DEFAULT '[]',
  -- Lines they said in the story, newest last (dungeon/story_people.py): [{text, day}].
  voice TEXT NOT NULL DEFAULT '[]'
);

-- Author's note (dungeon/authors_note.py): the user's note for the story, sent with every turn while it is on.
-- `chat` is 'story'. Never a message: not in the transcript or the narrator's history.
CREATE TABLE IF NOT EXISTS authors_notes (
  chat TEXT PRIMARY KEY,
  text TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  updated_at TEXT NOT NULL
);

-- The town's mix (dungeon/world/mix.py, Worlds > Townsfolk mix): the shares townsfolk rolls use for looks and who people
-- are drawn to. No row is the built-in mix. Each world keeps its own; a new world starts from the one it was made from.
CREATE TABLE IF NOT EXISTS townsfolk_mix (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  mix TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Personality sliders the user changed on a townsperson's profile (dungeon/world/personality.py), by town (the
-- world's town seed) and townsperson key. The rest stays rolled.
CREATE TABLE IF NOT EXISTS townsfolk_personality (
  town TEXT NOT NULL,
  key TEXT NOT NULL,
  sliders TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (town, key)
);

-- Everyone gets older (dungeon/life/ages.py). The row with kind 'town' and an empty key holds the day the town's
-- people started getting older; a townsperson's age moves on from their seeded age on that day.
CREATE TABLE IF NOT EXISTS birth_dates (
  kind TEXT NOT NULL CHECK (kind IN ('town')),
  person_key TEXT NOT NULL,
  born_on TEXT NOT NULL,
  birthday TEXT NOT NULL,
  from_age INTEGER NOT NULL,
  anchored_on TEXT NOT NULL,
  held_age INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (kind, person_key)
);

-- The town changes hands (dungeon/world/turnover.py): the levels the town's pace, passing away and growing
-- families held before a change, until the week they stopped holding, so a change only moves the town on from
-- then. `loss` is 0 when nobody passes away, else the loss level plus one.
CREATE TABLE IF NOT EXISTS town_levels (
  until_week INTEGER PRIMARY KEY,
  pace INTEGER NOT NULL,
  loss INTEGER NOT NULL,
  families INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

-- The travel map as far as the character knows it (dungeon/travel.py): each place heard of, and whether they have
-- been there. Branched with the story (dungeon/timeline.py SAVED).
CREATE TABLE IF NOT EXISTS story_map (
  node_id TEXT PRIMARY KEY,
  visited INTEGER NOT NULL DEFAULT 0 CHECK (visited IN (0, 1))
);

-- The hexes the character has seen on a hex-crawl travel map (dungeon/hexes.py), and whether they have walked them.
-- Branched with the story (dungeon/timeline.py SAVED); what is in a hex comes from the map and the campaign's seed.
CREATE TABLE IF NOT EXISTS story_hexes (
  map TEXT NOT NULL,
  q INTEGER NOT NULL,
  r INTEGER NOT NULL,
  visited INTEGER NOT NULL DEFAULT 0 CHECK (visited IN (0, 1)),
  PRIMARY KEY (map, q, r)
);

-- The sites the character has found on a hex crawl (dungeon/hexes.py): ruins, lairs, shrines and the like, seen from
-- afar, walked into or searched out. What a site is comes from the map, the seed and the intensity levels, and is
-- kept as found (`site`, JSON). Branched with the story.
CREATE TABLE IF NOT EXISTS story_sites (
  map TEXT NOT NULL,
  q INTEGER NOT NULL,
  r INTEGER NOT NULL,
  site TEXT,
  PRIMARY KEY (map, q, r)
);

-- The lots of a town map the character has looked at (dungeon/townmap.py), and what stands there (`found`, JSON),
-- kept as found whatever the intensity levels are later. Branched with the story; the map itself comes from the
-- town's data and the campaign's seed.
CREATE TABLE IF NOT EXISTS story_lots (
  town TEXT NOT NULL,
  lot TEXT NOT NULL,
  found TEXT NOT NULL,
  PRIMARY KEY (town, lot)
);

-- The town's own places the character knows of (dungeon/townmap.py known): visited, passed on the street, looked at
-- on the map, or named to them in the story. Landmarks, and a home town's places, are known without a row.
-- Branched with the story (dungeon/timeline.py SAVED).
CREATE TABLE IF NOT EXISTS story_places (
  town TEXT NOT NULL,
  place TEXT NOT NULL,
  how TEXT NOT NULL,
  PRIMARY KEY (town, place)
);

-- Where the character is when a hex crawl leaves them out in the wild, between places (dungeon/hexes.py): the hex,
-- and the hex they believe they are in when they have lost their way. Branched with the story.
CREATE TABLE IF NOT EXISTS story_position (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  map TEXT NOT NULL,
  q INTEGER NOT NULL,
  r INTEGER NOT NULL,
  believed_q INTEGER NOT NULL,
  believed_r INTEGER NOT NULL
);

-- Where the character is inside an interior (dungeon/delving.py): the interior, the room and the one before, moves
-- since a wandering encounter, the room a fight began in, and for a rolled site the site it is laid out from (JSON).
-- Branched with the story (dungeon/timeline.py SAVED).
CREATE TABLE IF NOT EXISTS story_interior (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  interior TEXT NOT NULL,
  room TEXT NOT NULL,
  previous TEXT,
  moves INTEGER NOT NULL DEFAULT 0,
  fighting TEXT,
  site TEXT
);

-- The rooms of interiors the character has been in, and what they did there. Branched with the story.
CREATE TABLE IF NOT EXISTS story_interior_rooms (
  interior TEXT NOT NULL,
  room TEXT NOT NULL,
  visited INTEGER NOT NULL DEFAULT 0,
  searched INTEGER NOT NULL DEFAULT 0,
  looted INTEGER NOT NULL DEFAULT 0,
  cleared INTEGER NOT NULL DEFAULT 0,
  hazard_met INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (interior, room)
);

-- The passages of interiors the character knows (`a` and `b` the rooms, sorted): found, opened, its trap sprung,
-- walked through. Branched with the story.
CREATE TABLE IF NOT EXISTS story_interior_ways (
  interior TEXT NOT NULL,
  a TEXT NOT NULL,
  b TEXT NOT NULL,
  found INTEGER NOT NULL DEFAULT 0,
  opened INTEGER NOT NULL DEFAULT 0,
  sprung INTEGER NOT NULL DEFAULT 0,
  passed INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (interior, a, b)
);

-- Each line's move inside an interior, planned once, and what came of it (dungeon/delving.py).
CREATE TABLE IF NOT EXISTS story_delves (
  message_id TEXT PRIMARY KEY,
  plan TEXT NOT NULL,
  lines TEXT
);

-- Each line's journey, planned once with its encounter, and what happened on it once walked (dungeon/travel.py).
CREATE TABLE IF NOT EXISTS story_journeys (
  message_id TEXT PRIMARY KEY,
  plan TEXT NOT NULL,
  lines TEXT
);

-- Each line's rest (dungeon/rest.py): the nights and what one of them turned up, decided once; and what came of it.
CREATE TABLE IF NOT EXISTS story_rests (
  message_id TEXT PRIMARY KEY,
  plan TEXT NOT NULL,
  lines TEXT
);

-- Chapters (dungeon/chapters.py): each starts at one of the player's lines; its end is kept on the branch where it
-- ended, so both are read through the branches like the messages.
CREATE TABLE IF NOT EXISTS story_chapters (
  id TEXT PRIMARY KEY,
  branch_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_chapter_ends (
  chapter_id TEXT NOT NULL,
  branch_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  reason TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  -- The question still open at its end (dungeon/chapters.py), for the next chapter's "previously".
  hook TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (chapter_id, branch_id)
);

-- A scene break waiting for the player's next line, which opens the next chapter; game state, so it is branched.
CREATE TABLE IF NOT EXISTS story_chapter_break (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  reason TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  -- The ending chapter summarized as the break is made: its summary, the model's name for it and its hook.
  summary TEXT NOT NULL DEFAULT '',
  named TEXT NOT NULL DEFAULT '',
  hook TEXT NOT NULL DEFAULT ''
);

-- Named moments to find again; across every branch.
CREATE TABLE IF NOT EXISTS story_bookmarks (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- The player's own notebook: across every branch, and never read by a model.
CREATE TABLE IF NOT EXISTS story_notebook (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- The campaign's choices made at its start that hold across every branch: Ironman turns off going back.
CREATE TABLE IF NOT EXISTS story_campaign (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  ironman INTEGER NOT NULL DEFAULT 0,
  ruleset TEXT NOT NULL DEFAULT 'marvel',
  -- The Table (dungeon/table.py): this campaign's rules. NULL until set, then the campaign's own.
  intensity TEXT CHECK (intensity IN ('world', 'restrained', 'mature', 'unflinching')),
  drama TEXT CHECK (drama IN ('world', 'quiet', 'uneasy', 'eventful', 'merciless')),
  injury_persistence TEXT CHECK (injury_persistence IN ('permanent', 'temporary', 'none')),
  show_odds INTEGER,
  roll_dice INTEGER,
  show_adult_side INTEGER,
  gm_view INTEGER,
  cutaways INTEGER,
  defeat TEXT CHECK (defeat IN ('as_written', 'by_aim')),
  -- dungeon/tone.py: categories moved off the preset and veiled topics (JSON), and the narrator's voice.
  levels TEXT,
  veils TEXT,
  voice TEXT,
  -- The narration format (dungeon/narration/prompt.py Format): point of view, tense and length.
  pov TEXT CHECK (pov IN ('first', 'second', 'third')),
  tense TEXT CHECK (tense IN ('past', 'present')),
  length TEXT CHECK (length IN ('short', 'medium', 'long')),
  -- Whether shopkeepers have finite cash to buy with (dungeon/inventory.py).
  shop_cash TEXT CHECK (shop_cash IN ('finite', 'unlimited')),
  -- Whether carrying is limited by slots (dungeon/inventory.py capacity).
  carry_limit TEXT CHECK (carry_limit IN ('slots', 'off')),
  -- Story time, or real time while the app is closed too ('world': the world's own; dungeon/story_clock.py).
  clock TEXT CHECK (clock IN ('world', 'story', 'real_time')),
  -- Whether the narrator gets the rule text that fits the turn (dungeon/rules/passages.py).
  rule_text TEXT CHECK (rule_text IN ('on', 'off')),
  -- Who can stop the character leaving a scene: anyone with a reason, only a fight, nobody (dungeon/leaving.py).
  leaving TEXT CHECK (leaving IN ('anyone', 'fights', 'nobody')),
  -- The world seed the land past a hex map's authored edge is generated from (dungeon/hexes.py).
  seed TEXT
);

-- The persona's sheet under a ruleset other than Prospero (dungeon/sheet.py), as that ruleset keeps it.
CREATE TABLE IF NOT EXISTS story_sheet (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  ruleset TEXT NOT NULL,
  data TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- The director's Chekhov list (dungeon/plotting.py): each seed planted, the truth it points to, its payoff window in
-- lines, and whether it reached the page, was asked to come back, paid off or was retired.
CREATE TABLE IF NOT EXISTS story_seeds (
  id TEXT PRIMARY KEY,
  arc_id TEXT,
  thread_id TEXT,
  text TEXT NOT NULL,
  truth TEXT NOT NULL DEFAULT '',
  words TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'planted' CHECK (status IN ('planted', 'reached', 'asked', 'paid', 'retired')),
  planted_line INTEGER NOT NULL DEFAULT 0,
  until_line INTEGER NOT NULL DEFAULT 0,
  message_id TEXT NOT NULL DEFAULT ''
);

-- Each arc stage's planned beats (dungeon/plotting.py): drafted by the director model or the world's own, in order;
-- the GM view can cut and reorder them.
CREATE TABLE IF NOT EXISTS story_arc_beats (
  id TEXT PRIMARY KEY,
  arc_id TEXT NOT NULL,
  stage INTEGER NOT NULL,
  text TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  cut INTEGER NOT NULL DEFAULT 0,
  used INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'world'
);

-- The institutions the character belongs to and the classes they take (dungeon/institutions.py).
CREATE TABLE IF NOT EXISTS story_enrollment (
  institution_id TEXT PRIMARY KEY,
  world TEXT NOT NULL,
  classes TEXT NOT NULL DEFAULT '[]',
  enrolled_at TEXT NOT NULL
);

-- Classes attended and missed, each term.
CREATE TABLE IF NOT EXISTS story_attendance (
  institution_id TEXT NOT NULL,
  term TEXT NOT NULL,
  attended INTEGER NOT NULL DEFAULT 0,
  missed INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (institution_id, term)
);

-- Each demand's mark (0 to 100) and weight, each term.
CREATE TABLE IF NOT EXISTS story_grades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institution_id TEXT NOT NULL,
  term TEXT NOT NULL,
  title TEXT NOT NULL,
  weight INTEGER NOT NULL DEFAULT 1,
  mark INTEGER NOT NULL CHECK (mark BETWEEN 0 AND 100)
);

-- Pictures asked for in the story (dungeon/art.py): what each shows and where it is. Not game state: going back keeps
-- them. `state` fingerprints what it was built from, to tell when it is out of date; `reference` marks someone's
-- first portrait, sent with every later picture of them.
CREATE TABLE IF NOT EXISTS story_art (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('portrait', 'place', 'scene', 'passage')),
  subject TEXT NOT NULL,
  chapter_id TEXT,
  prompt TEXT NOT NULL,
  style TEXT,
  state TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed', 'refused')),
  file TEXT,
  width INTEGER,
  height INTEGER,
  backend_id TEXT,
  reference INTEGER NOT NULL DEFAULT 0 CHECK (reference IN (0, 1)),
  error TEXT,
  created_at TEXT NOT NULL,
  done_at TEXT
);

-- The narrator's Mix (dungeon/text_models.py reply_config): profiles that take turns telling the story, in turn or at
-- random, each with its own model and settings. Off, or with fewer than two finished profiles, the job's own profile
-- answers.
CREATE TABLE IF NOT EXISTS model_mix (
  job TEXT NOT NULL,
  profile_id TEXT NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  PRIMARY KEY (job, profile_id)
);
CREATE TABLE IF NOT EXISTS model_mix_state (
  job TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0,
  mode TEXT NOT NULL DEFAULT 'random' CHECK (mode IN ('random', 'in_turn')),
  turn INTEGER NOT NULL DEFAULT 0
);

-- Local politics (dungeon/world/politics.py, dungeon/politics.py): the player's own changes to a city's issues
-- and factions. Seeded issues and factions are rebuilt from the city and the date; a row here is an issue or faction
-- the player added (origin 'user') or their changes to a seeded one (origin 'edit'), or one they put away (dismissed).
CREATE TABLE IF NOT EXISTS politics_issues (
  city_id TEXT NOT NULL,
  issue_id TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('user', 'edit')),
  data TEXT NOT NULL DEFAULT '{}',
  dismissed INTEGER NOT NULL DEFAULT 0 CHECK (dismissed IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (city_id, issue_id)
);

CREATE TABLE IF NOT EXISTS politics_factions (
  city_id TEXT NOT NULL,
  faction_id TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('user', 'edit')),
  data TEXT NOT NULL DEFAULT '{}',
  dismissed INTEGER NOT NULL DEFAULT 0 CHECK (dismissed IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (city_id, faction_id)
);

-- Someone's view on an issue as the player set it: -2 strongly the second side ... 2 strongly the first.
CREATE TABLE IF NOT EXISTS politics_views (
  city_id TEXT NOT NULL,
  issue_id TEXT NOT NULL,
  person TEXT NOT NULL,
  view INTEGER NOT NULL CHECK (view BETWEEN -2 AND 2),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (city_id, issue_id, person)
);

-- How two factions stand as the player set it (first < second): -2 at open odds ... 2 allies.
CREATE TABLE IF NOT EXISTS politics_relations (
  city_id TEXT NOT NULL,
  first TEXT NOT NULL,
  second TEXT NOT NULL,
  stance INTEGER NOT NULL CHECK (stance BETWEEN -2 AND 2),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (city_id, first, second)
);
