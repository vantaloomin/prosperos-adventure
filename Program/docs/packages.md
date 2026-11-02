# World packages

Milestone 5 (requirements "World packages"). A world (a setting such as Vallarith, not a save: see
[worlds.md](worlds.md) for those) is one SQLite file: its canon, cast, personas, hidden truths, planned beats,
rules, tables, prices and assets. The same world can be written out as a folder of Markdown and JSON and read back
in. `dungeon/packages.py` does both.

## The folder

`dungeon/world/packages/vallarith/` is the built-in example, and its README describes each file.

| Path | Kept as |
|---|---|
| `world.json` | `meta.world`: the world's id, name and settings |
| `canon/*.md` and any other `.md` | `documents`, word for word |
| `lore.json`, `regions.json`, `settlements.json`, `factions.json`, `deities.json`, `cast.json`, `personas.json`, `hidden-truths.json`, `beats.json` | `entries`: one row per entry, with its section, id, position, name and whether it holds a hidden truth. The rest of the file (schema_version, fields, notes) is kept in `meta.sections` |
| `engine/<kind>/<key>.json` | `engine`: the game's own data (`adventures`, `arcs`, `cities`, `factions`, `finds`, `items`, `premades`, `tiers`, `travel`) |
| `assets/**` | `assets`: bytes and media type |

`world.json` may carry a `theme`: `{"name": "Ember and soot", "palette": {"accent", "background", "surface", "text"}}`,
each a `#rrggbb` color (`dungeon/world_theme.py`). The story screen wears it while the story is in that world, unless
the player turns off Settings > General > Appearance > "Use the world's colors". The rest of the app keeps the
player's scheme. A theme with a color missing, or one whose text or accent would not read (4.5:1 and 3:1, as a
custom palette must), is not used. Vallarith ships "Ember and soot", Havenbrooke "Autumn quad" (light) and BABEL
"Tower glass".

An entry hides a truth when its section is `hidden-truths` or it has a `secret`, `secrets`, `guise`,
`mortal_life`, `truth` or `hidden` field. The editor will mark those rows.

## Checks

A folder is checked before it becomes a package. Every entry needs a lowercase kebab-case id that is unique in its
section, and references have to name an entry that exists: a settlement's `region` and `faction`, and a cast
member's `faction` and `settlement`. A broken JSON file is named. Nothing is written until the folder passes.

## Built-in worlds

Built-in worlds ship as folders. For now the game's own data for them stays in `dungeon/world/data`, and the build
gathers it into the package's `engine` part. That covers the world's travel map, arcs, factions in play and tiers,
and for each town on its map the town's adventure, items, finds, premades and city file. The package is built into
the data folder (`packages/<id>.sqlite`) when first asked for. It is built again whenever a source changes, which a
fingerprint of the contents tells.

Two worlds are built in: Vallarith (`packages/vallarith/`, grimdark fantasy, Kingswood its town) and Havenbrooke
(`packages/havenbrooke/`, modern fantasy in the autumn of 2009, Haven and its university its town). Havenbrooke's
school is in its own folder's engine data (`engine/institutions/havenbrooke.json`).

## In play

- **Lore.** A campaign that starts in a world with a package gets the package's `lore` section as one of the
  world's lore books, "<World> (world package)" (`dungeon/package_lore.py`). The narrator reads its entries by
  keyword like any imported lorebook (each keyword also counts without a leading "The" or a note in brackets) (docs/worlds.md "Lore"), and the player can switch entries off on the Lore
  screen. Only entries that hold in the campaign's era come in (the era is `world.json` `starting_place.era`; an
  entry with no `eras` holds in all). Hidden truths never come in this way. The book is read from the package file,
  so an edited or imported world plays as edited. When the lore changes, the next campaign start replaces the book. An entry may also carry timing as its own fields (`sticky`, `cooldown`, `delay`, `chance`, `group`,
  `group_weight`; docs/worlds.md "Lore"), kept within their ranges.
- **Engine data.** The game reads each town's adventure, items, finds and premades, and each world's travel map,
  arcs, factions and tiers, from the `engine` part of the packages in the data folder (`dungeon/world_data.py`),
  so an edited package plays as edited. The built-in worlds' packages are built (again) when the app starts. A
  loader that caches its data reads again when a package file changes. A key no package holds, or a script with no
  data folder, reads the shipped file in `dungeon/world/data`. When two packages hold the same key, the built-in
  world's wins. Town city files (`cities`) of the built-in worlds are read from `dungeon/world/data/cities`; a town
  only an imported package holds (a world made in Prospero's Worldsmith) is read from that package and joins the
  city list, loaded leniently like a city pack (`dungeon/world/catalog.py`), and the list is read again when a
  package file changes.

## The importer

An existing world comes in from its own files, one reviewed section at a time (`dungeon/package_import.py`; Worlds
screen > World packages > Import a world):

- **Files.** Markdown or text documents are kept as written (`canon/<name>.md`). A lorebook JSON in any format the
  Lore screen reads becomes the `lore` section straight away, with no model.
- **Drafting.** Every other section (regions, settlements, factions, powers, cast, personas, hidden truths, planned
  beats) is drafted by the World importer's model (Settings > Models; the Default without one) when the author asks
  for it. The model reads the documents (up to 60,000 characters) and the ids already in the other sections, and
  answers with JSON entries. Each entry gets a kebab-case id from its id, name or title, and repeated ids get -2, -3.
- **Review.** A drafted section waits for the author: they read it, edit its entries as JSON or write a section
  themselves, then approve or clear it. Sections with hidden truths say how many entries hold one, and the entry
  list marks them. Nothing reaches the package until it is approved, and sections left empty stay out.
- **Finishing.** The package is written once nothing drafted is still unread and the approved sections pass the
  validator. An entry that names an entry of a section left out (a settlement's region with no regions approved) is
  a problem too. An existing package with the same id is replaced only when the author says so. A built-in world's
  name is refused.

A draft is a JSON file in the data folder (`package-drafts/<id>.json`) until it is finished or discarded.

## The editor

Worlds are edited in place (`dungeon/package_edit.py`), built-in and imported alike, from Worlds > World packages >
Edit the world (`src/features/worlds/WorldEditor.tsx`). An entry opens as a form, one field per key (text, numbers,
switches, and JSON for lists), or as raw JSON; hidden-truth fields are labelled as hidden from the player.

- **Entries** are listed by section with counts, searched by words in their text, and filtered by whether they hold
  a hidden truth, which each entry's view marks with the fields that hold it.
- **Validation on save.** An entry needs a kebab-case id unique in its section, and each field naming an entry of
  another section (a settlement's region, a person's settlement) must name one that exists. Renaming or deleting an
  entry is refused while others still name it. Each entry's view lists what it names and what names it.
- **Undo.** Every change keeps the entry as it was (the package's `history` table, the last 500); undo takes back
  the newest.
- **Built-in worlds** keep their edits: an edited one (`meta.edited`) is no longer rebuilt from the shipped files
  until it is reset to them.

## API

- `GET /api/packages`: the built-in and imported worlds, each with its sections' entry counts (and how many hide a
  truth), documents, engine data, assets and size.
- `GET /api/packages/{id}/file`: the world as its SQLite file, to share.
- `POST /api/packages/{id}/export`: the world written out as a folder in the data folder (`exports/<id>-<time>`),
  and the path.
- `POST /api/packages/import` `{folder}`: a world folder on this computer, checked and made into a package. A
  built-in world's id is refused.

- `GET /api/packages/drafts`: the imports still being reviewed.
- `POST /api/packages/drafts` `{name, files: [{name, text}]}`: a new import.
- `GET /api/packages/drafts/{id}`: the import with its sections, entries, hidden counts, what is still unread
  (`waiting`), the validator's `problems` and whether it is `ready`.
- `POST /api/packages/drafts/{id}/sections/{section}/draft`: the section drafted by the model.
- `PUT /api/packages/drafts/{id}/sections/{section}` `{status, entries?}`: the author's edits, and `drafted`,
  `approved` or `empty` (cleared).
- `POST /api/packages/drafts/{id}/finish` `{replace?}`: the package written; the draft is removed.
- `DELETE /api/packages/drafts/{id}`: the import discarded.

- `GET /api/packages/{id}/entries?section=&q=&hidden=`: each section's counts and the matching entries.
- `GET /api/packages/{id}/entries/{section}/{entry}`: the entry, whether it hides a truth, and its links (`names`,
  `named_by`).
- `POST /api/packages/{id}/entries/{section}` `{entry}`: a new entry; `PUT .../{entry}` `{entry}` changes one (its id
  may change); `DELETE .../{entry}` removes one. Problems answer 422, an entry still named 409.
- `GET /api/packages/{id}/history`: the last 50 changes; `POST /api/packages/{id}/undo` takes back the newest.
- `POST /api/packages/{id}/reset`: a built-in world rebuilt from its shipped files, its edits gone.
