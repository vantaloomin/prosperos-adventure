# Worlds and personas

A **persona** is the user as someone in particular: a name, gender, age, birthday and a few lines about them. A
**world** is everything that happened to one persona there: the story, the people met and the town. Each persona
has one or more worlds. Two worlds can share a city: each seeds its own townsfolk (`persona.town_seed`, set once
when the world is made), so the same streets hold different people.

## Where things live

- Each world is its own workspace database in its own folder. The first world keeps the data folder's own
  `dungeon.sqlite3` (`Database.root`, `Database.home`); every other world is `worlds/<id>/dungeon.sqlite3`, with
  its own `backups/` beside it.
- `worlds.json` in the data folder lists personas and worlds and which world is active (`dungeon/worlds.py`). It
  is written whole and swapped in.
- Shared by every world, in the data folder: downloaded models (`voice/`, `embeddings/`), logs, city packs and
  `worlds.json`.
- Each world's `persona` table holds the persona it belongs to, copied from `worlds.json` whenever the world opens
  or the persona changes.

## What a world is made of

The Worlds page ends with "What <world> is made of": its cities, its world packages (docs/packages.md), its lore,
its reference library, the adult side and the townsfolk mix.

- **Lore** (`src/features/worlds/WorldLore.tsx`, `dungeon/lore.py`): import a lorebook (JSON or .lorebook), turn a
  book or any entry on or off, delete a book, and set an entry's "when" (weather, season, time of day, day, holiday,
  place in the story's town) beside its keywords. Each entry says how it comes into the story, and "Fits the scene
  now" when it would join this turn. A book of more than eight entries gets a search.
- **Lore timing** (`dungeon/lore.py` "Timing", `PUT /api/lore/entries/{id}/timing`): an entry that is not always on
  can linger (stay in for some lines after it comes up), rest (stay out for some lines after that), wait (not come up
  before a given line), come up on a chance in a hundred, or belong to a group that only one entry comes up from at
  a time, picked by weight. Lines are the player's lines in the story. The timers (`lore_timers`) are saved with each
  line, so going back or switching branch rewinds them, and the chance is seeded by branch, line and entry, so a
  retry rolls the same. SillyTavern world info brings its own sticky, cooldown, delay, probability and inclusion
  groups; a world package entry can carry the same fields. Each entry's "Timing" fold sets them, and its line says
  where its timer stands ("Resting for 2 more lines").
- **Reference library** (`dungeon/library.py`): add a long text (text, Markdown, HTML, EPUB or a TiddlyWiki file),
  turn it on or off, delete it, and "Look inside" to search its passages the way the narrator would.

## Switching

`POST /api/worlds/{id}/switch` (or `/api/worlds/personas/{id}/switch`, the persona's most recent world) refuses
while debug time is on. It checkpoints the current database, points the app's one `Database` at the other file
(`Database.use`), carries the user's settings across (`worlds.SHARED`: restore's kept settings minus debug time,
plus the user's own cities) and writes the persona. The interface reloads.

Work already under way stays in its own world. Each request and each background task is pinned to the world open
when it began (`Database.pin`, a context variable that every task it starts inherits), so a reply that comes back
from a model after the switch is stored where it was asked for. Pages send the world they show
(`X-Dungeon-World`); a tab still showing the old world gets `409 world_changed` for anything it asks and reloads
into the new one, rather than writing into it.

## Defaults

- A new workspace is the first world, in Kingswood, with a blank persona.
- A new world starts in the current city (or `city_id`, or "Somewhere new", a featured city picked for it) with
  fresh townsfolk.
- The persona is the user's to say (Vanta, 2026-10-09). "New persona" opens the persona form; the name they type
  is required, anything left blank stays blank, and the app makes nothing up. Their world is still decided for
  them, as above.

## Deleting

A world can be deleted unless it is active or the first world (which holds the others). A verified backup goes to
`backups/deleted-worlds/` in the data folder first. A persona goes with all its worlds, unless it is active or owns
the first world.

## Automatic backups

`dungeon/auto_backup.py` backs up every world on its own while the app runs: daily by default
(`workspace_settings.auto_backups`: `daily`, `weekly` or `off`, Settings > Data), first a couple of minutes after
a start, then checked every 15 minutes. A world unchanged since its last automatic backup is skipped. Archives go
to the world's own `backups/` as `auto-YYYYMMDDTHHMMSS.zip`; the newest of each of the last 7 days with one and of
each of the 4 weeks before are kept. It never calls a model.
