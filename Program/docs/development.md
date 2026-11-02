# Development

[Back to the README](../../README.md)

The backend is Python 3.12, FastAPI and SQLite; the interface is React 19, TypeScript and Vite.
Development and CI run on Linux, Windows and macOS, while Windows x64 is the launch target.

The checkout has three folders: `Windows/` and `Mac/` hold only the double-click scripts, and
`Program/` holds everything else (the `dungeon` Python package, `src/`, `public/`, `tests/`,
`scripts/`, these docs and the Python and npm manifests). Program is the project root for tools:
run every command in this guide from `Program/`, where `.venv`, `node_modules` and `dist` live too.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt      # Windows: .\.venv\Scripts\python.exe
.venv/bin/python -m dungeon                                  # serves http://127.0.0.1:8785
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q -n auto                         # -n auto spreads tests over every core
```

Writes require the `x-dungeon-client: workspace` header, which the local interface sends.

## Installing on Windows

Double-click `install.bat` in `Windows/` once. It finds Python 3.12+ and Node.js 22.13+ (installing them with
WinGet if they are missing), creates `.venv`, installs the locked dependencies and builds the
interface. Then double-click `launch.bat`: it starts the Dungeon on http://127.0.0.1:8785 and
opens it in the browser. Keep its window open while using the app; close it or press Ctrl+C to
stop. Launching again while it runs reuses the running copy, and a port taken by another program
is never stopped. `scripts/windows/install.ps1 -CheckOnly` verifies an existing installation. CI runs the
installer and a launch on Windows.

Each `.bat` in `Windows/` runs the PowerShell script of the same name in `scripts/windows/`;
`common.ps1` there holds the shared paths and port checks. `update.bat` runs
`git pull --ff-only origin main` and then `install.ps1`. In a copy without `.git` (a downloaded ZIP)
it downloads main's ZIP instead, copies it over the folder and records the copied files in
`.zip-update-files`, so the next ZIP update can remove files main dropped; `DUNGEON_UPDATE_ZIP`
points it at a local ZIP for tests. It refuses
while the Dungeon runs (Windows locks the files a reinstall replaces) or when the checkout is on
another branch. `status.bat` exits 0 when the Dungeon answers, 1 when nothing does and 2 when
another program holds the port. `stop.bat` ends the process tree that owns the port, but only after
the port answers as the Dungeon. `status.bat` and `stop.bat` take `-Port`, like `launch.bat`.
`create-shortcut.bat -Destination <folder>` writes the shortcut elsewhere, and names it
`Prospero Dungeon (checkout)` when the installed app already has a `Prospero Dungeon` shortcut.
`dev.bat` starts the backend with `uvicorn --reload` in its own window (or reuses one already
running), runs `npm run dev` in its own, and stops the backend it started when Vite exits.
Dev mode uses the real workspace unless `DUNGEON_DATA_DIR` points elsewhere. CI runs
`scripts/windows/helpers-test.ps1` after the installer to exercise each helper through its `.bat`.

Until October 2026 the scripts and the code sat together at the top of the checkout. On its first run
in the new layout, `scripts/windows/install.ps1` tidies what the old layout left at the top (`.venv`,
`node_modules`, `dist`, folders kept only by `__pycache__`), moves a top-level `private-cities/` into
Program and repoints desktop shortcuts at `Windows\launch.bat`.

On Linux, follow the commands above and below, then run `.venv/bin/python -m dungeon.launch`.

## Installing on a Mac

The `.command` files in `Mac/` are the twins of the `.bat` files; each runs the matching script in
`scripts/macos/` (bash 3.2 compatible, since that is macOS's `/bin/bash`), and `common.sh` there
holds the port checks (`curl` and `lsof`). They behave as their Windows twins, with `--port`,
`--no-browser`, `--check-only` and `--destination` in place of the PowerShell switches.
`install.sh` uses Homebrew where WinGet is used on Windows, and otherwise opens the python.org or
nodejs.org download page. `create-shortcut.command` writes a small `.app` bundle that opens
`launch.command` in Terminal. The `macos-install` CI job runs `install.command` without
setup-python or setup-node on Apple Silicon and Intel runners, then
`scripts/macos/helpers-test.sh`; the backend tests also run on macOS. On a pull request the
`macos-install` and `windows-install` jobs run only when the PR touches `Windows/`, `Mac/`, the
platform scripts, the manifests, `dungeon/launch.py` or `dungeon/main.py`; on main they always
run. No one has run these on a real Mac. User-facing instructions, Gatekeeper and what is missing on
a Mac are in
[Installing on a Mac](macos.md).

## Windows bundle

`python scripts/package/build_bundle.py` (after `npm run build`) assembles a self-contained
Windows x64 bundle in `build/package/`: `ProsperoDungeon-<version>-win-x64.zip` and
`SHA256SUMS.txt`. Inside, `Prospero Dungeon.cmd` starts the app with its own Python runtime, so
the machine needs neither Python, Node nor Prospero's Study.

| Part | Contents |
| --- | --- |
| `runtime/` | Python 3.12.10 from the python.org NuGet package, pinned by SHA-256, with the locked runtime dependencies as Windows wheels; pip and build headers removed |
| `app/` | `dungeon/`, the built interface in `dist/`, and `LICENSE` |
| `bundle.json` | Version, schema version, commit and the SHA-256 of every file |

The runtime's `python312._pth` fixes its import paths and the launcher runs it with `-I`, so
`PYTHONPATH`, `PYTHONHOME`, user site-packages and any other Python on the machine are ignored.
The workspace still lives in `%LOCALAPPDATA%\ProsperoDungeon`, separate from the program files.

The `Package` workflow builds the bundle on Windows and uploads it as a workflow artifact; it never
tags or publishes a release. A second job downloads it onto a fresh runner, checks the checksum,
unpacks it into a path with spaces and runs `scripts/package/smoke-test.ps1`: with no Python or
Node on `PATH`, poisoned Python variables and the Study's port 8765 taken, the app must verify
against `bundle.json`, answer on 8785, serve the interface, run on its bundled runtime, keep its
workspace and backups in its own data directory, and reuse the running copy on a second launch.

### Per-user installer

`scripts/package/dungeon.iss` wraps the unpacked bundle in an Inno Setup installer,
`ProsperoDungeon-<version>-win-x64-setup.exe`. It installs into
`%LOCALAPPDATA%\Programs\Prospero Dungeon` without administrator rights, adds a Start menu
shortcut (a desktop shortcut is optional) and a per-user uninstall entry, and offers to close a
running Dungeon before replacing files. An upgrade clears the old `app/` and `runtime/` first so
modules a release drops do not linger. The workspace in `%LOCALAPPDATA%\ProsperoDungeon` is
never installed, replaced or removed: uninstalling keeps it (a portable `Data/` folder in the
install folder is kept too), and the app upgrades it on first open
as described under [Upgrades](#upgrades).

```powershell
ISCC.exe /DAppVersion=0.1.0 /DSourceDir=build\package\ProsperoDungeon /DOutputDir=build\package scripts\package\dungeon.iss
```

The `Package` workflow builds the setup from the bundle artifact, publishes both with one
`SHA256SUMS.txt` as the `windows-release` artifact, and runs `scripts/package/installer-test.ps1`
on a fresh runner: install, launch, install again as an upgrade, launch, restore a backup with the
installed launcher, launch, uninstall, with no Python or Node on `PATH`.

A `beside-the-study` job installs Prospero's Study from its repository (pinned to `bbcbde4`),
starts it on 8765, installs the Dungeon and runs `scripts/package/beside-study-test.ps1`: a
Dungeon pointed at the Study's port refuses and stops nothing, the Dungeon runs on 8785 while
the Study keeps answering, neither data folder holds the other's files, and the Study's database
never gains the Dungeon's identity marker.

The bundle and setup are not code signed yet, so Windows SmartScreen may warn on first launch. Signing is an
open release decision.

### Release branches

Work is planned in releases, and each upcoming release has its own branch made ahead of time from `main`:
`release/v0.6.0`, `release/v0.7.0` and so on.

- **Every pull request targets the branch of the release it belongs to**, not `main`. CI runs on pull
  requests into any branch.
- **Only hotfixes target `main`** (a fix for something already released). After a hotfix merges, merge `main`
  into every open release branch so they keep it, and so a later release never undoes it.
- **Cutting a release** is one pull request from `release/v<version>` into `main`, carrying the version numbers,
  notes and title below. A merge commit keeps each feature's own commit on `main`.
  Then run the `Release` workflow on `main`, delete the release branch, merge `main` into the next release
  branch, and make the branch for the release after that.

Releases only ever publish from `main`.

### Publishing a release

1. Set the same version in `package.json`, `pyproject.toml` and `dungeon/identity.py`, and write the
   release notes in `docs/releases/v<version>.md` (plus an entry in the top-level `CHANGELOG.md`).
   A new minor version also needs its title in `docs/releases/titles.json`; patch releases share it, so
   every 0.4 release is named "v0.4.x: Small World, Big News".
2. Merge that to `main` (from the release branch, see above), then run the `Release` workflow from the
   Actions tab on `main` (pre-release is ticked by default).

`release.yml` checks the three version numbers agree and the notes and title exist, runs the whole `Package`
workflow on that commit, and only when every job passes tags `v<version>` on it and publishes the
setup, the portable zip and `SHA256SUMS.txt` as a GitHub release. It refuses a version that is
already released.

To change the notes of a published release (say, to warn about a bug in it), edit its
`docs/releases/v<version>.md`, merge, then run the `Release notes` workflow on `main` with the tags
to update, separated by spaces. Pick `title` instead of `notes` to rename releases after changing
`docs/releases/titles.json`.

## Interface

Node 22 or newer. `npm run build` writes `dist/`, which the backend serves at
http://127.0.0.1:8785 when it exists. For development, run the backend and Vite side by side;
Vite serves http://127.0.0.1:5177 and forwards `/api` to the backend.

```sh
npm ci
npm run dev        # http://127.0.0.1:5177
npm run lint
npm test           # pure UI logic in tests/ui, run with Node's test runner
npm run build
```

Views live in `src/features/<view>/`. Logic that can be tested without a browser (turn grouping,
draft handling) sits in plain `.ts` modules beside the components that use it.

Settings is split into tabs listed in `src/features/settings/sections.ts`, with the section
headings and keywords its search box looks through. A new settings section goes in that list and
in `TabContent` in `Settings.tsx`. Tabs are deep-linkable: `go('settings/models')` from any view,
or `#settings/<tab>` in the address; an unknown tab opens the first tab available.

## Workspace and identity

The Dungeon has its own identity so it can run beside Prospero's Study without collisions:

| Item | Dungeon | Study |
| --- | --- | --- |
| Data directory | `DUNGEON_DATA_DIR` if set, else `Data/` in the app folder if it exists (portable; `dungeon/data_folder.py`), else `%LOCALAPPDATA%\ProsperoDungeon` (Windows), `~/Library/Application Support/ProsperoDungeon` (macOS), `$XDG_DATA_HOME/prospero-dungeon` elsewhere | `data/` in the checkout |
| Database | `dungeon.sqlite3`; `DUNGEON_DB` overrides | `roleplay.sqlite3` (`ROLEPLAY_DB`) |
| Port | 8785 | 8765 |
| Credential service | `Prospero Dungeon` (`DUNGEON_API_KEY` fallback) | `Roleplay Interface` |
| Backup marker | `prospero-dungeon-archive` | Study archive format |

Every workspace database carries an `app_identity` marker. Opening any other non-empty SQLite
file, including a Study database, is refused with a read-only check before anything is written.

### Upgrades

The marker also records the schema version, the app version and a digest of `schema.sql`, so any schema change is noticed without anyone bumping a number. When a workspace
was written with a different digest, `dungeon/upgrade.py` runs before the server listens:

1. A workspace from a newer schema version, or another app's database, is refused untouched.
2. A verified backup in the original schema is written to `backups/pre-upgrade-<time>.zip`
   (the three most recent are kept).
3. The upgrade runs on a copy, which must pass `PRAGMA integrity_check`.
4. Only then does the copy replace the workspace. On any failure the original is left exactly as
   it was and the launcher names the backup, which restores like any other.

Bump `SCHEMA_VERSION` only when older releases must refuse the new schema.

Schema version 2 is Milestone 0's fresh schema. A version 1 workspace (the companion's) is not migrated: step 3
builds a new workspace instead and copies across only the user's settings, models, persona and cities
(`upgrade.fresh`); the pre-upgrade backup keeps everything else.

### Backups and restore

`POST /api/backups` writes `backups/dungeon-<time>.zip`: the database snapshot with its SHA-256 in
`manifest.json`. Restoring checks the marker, the schema version and the digest before writing anything. Replacing
a workspace keeps its current settings and connections instead of the backup's (`restore.KEPT_SETTINGS`). With no
workspace to replace (a new computer), saved keys are dropped, so the user enters them again.

In the app, Settings > Data lists the archives in `backups/` (`GET /api/backups`, read from
their manifests) and **Restore…** chooses one (`POST /api/backups/{name}/restore`, which verifies
it in full first and can be cancelled with `DELETE /api/backups/restore`). The running app cannot
replace its own open workspace, so the choice is recorded in `pending-restore.json` and the
launcher applies it on the next start, before the workspace opens; the request is consumed whether
or not the restore succeeds, so a failure is reported once and never retried. Outside the app, close
it and run the launcher with `--restore <backup.zip>` (`"Prospero Dungeon.cmd" --restore <file>`
in the bundle). The current workspace moves to `replaced-<time>/` beside it, not deleted, and moves back if the
restore fails.

### Logs

`python -m dungeon.launch` logs to its window and to `logs/dungeon.log` in the data directory
(1 MB, three older files kept). Request logging is off, since a URL can carry a search query, and
`dungeon/logs.py` masks anything shaped like a credential (bearer tokens, `api_key=` values,
`sk-`/`hf_`-style keys) in messages and tracebacks before a line is written. The app itself never
logs message text. An unexpected error returns `{"code": "server_error"}` with a message naming the log's
full path, and the page shows "Open the log folder" under it on the PC (`POST /api/logs/open-folder`).

**Record model calls** (Settings > Developer, PC only, off by default; `dungeon/model_calls.py`) is the one
exception: while it is on, every text model call (the narrator and anything else that asks a model) is appended in full to
`logs/model-calls/YYYY-MM-DD.jsonl`: which part of the app asked, provider, model, address without its query
string, the system prompt, messages and exact request body, and the streamed text, thinking, finish reason, usage
or error, with timing. Keys travel in headers and are never written. Files older than seven days are deleted.
"Save for support" downloads them as a zip (`GET /api/model-calls/download`); `PUT /api/model-calls`
`{"recording": true}` turns it on and `DELETE /api/model-calls` clears the files. Embedding calls are not recorded.

## Code reused from Prospero's Study

Modules were copied from [prosperos-study](https://github.com/vantaloomin/prosperos-study) at
commit `bbcbde4` and now evolve independently. Each copied file names its source path and the
changes made.

| Dungeon file | Study source | Changes |
| --- | --- | --- |
| `dungeon/memory/retrieval.py` | `server/memory/retrieval.py` | Removed Story stopwords (`continue`, `story`); in-process memoization only |
| `dungeon/memory/hybrid_recall.py` | `server/memory/hybrid_recall.py` | Takes chunks and a read limit from the caller |
| `dungeon/memory/chunks.py` | `server/memory/chunks.py` | No persistent cache format |
| `dungeon/memory/cache.py` | `server/memory/cache.py` | Persistent index backing removed |
| `dungeon/memory/phrases.py` | `server/phrases/detection.py` | Findings without evidence quotes; single-word check and context line added |
| `dungeon/memory/budget.py` | `server/memory/budget.py` | Estimates plain text |
| `dungeon/providers/scheduling.py` | `server/providers/scheduling.py` | Dungeon work kinds |
| `dungeon/providers/chat.py` | `server/providers/http.py`, `completion.py` | Conversation messages; token-limit and filter stops stay visible incomplete replies |
| `dungeon/providers/config.py` | `server/providers/config.py` | No LM Studio native protocol; Dungeon environment fallbacks |
| `dungeon/providers/capabilities.py` | `server/providers/capabilities.py` | No native protocol or safety margin |
| `dungeon/providers/requests.py` | `server/providers/requests.py` | System text plus alternating messages |
| `dungeon/providers/events.py` | `server/providers/events.py` | Dungeon `Chunk` with a normalized finish reason |
| `dungeon/providers/discovery.py`, `discovery_errors.py` | same files | No native model list |
| `dungeon/providers/codex.py` | `server/providers/codex.py` | Conversation sent as one transcript |
| `dungeon/providers/vault.py` | `server/providers/vault.py` | Dungeon credential service; delete; in-memory vault for tests |
| `dungeon/providers/urls.py` | `server/providers/config.py` | URL checks only |
| `dungeon/text_models.py`, `text_model_routes.py` | `server/profiles.py`, `profile_routes.py`, `roles.py` | Unversioned profiles; workspace job assignments |
| `src/features/settings/models/` | `src/features/models/` | Opens in Settings, not a dialog; no native protocol |
| `dungeon/database.py`, `errors.py`, `models.py` | `server/database.py`, `errors.py`, `models.py` | Identity marker and Dungeon helpers |
| `src/api.ts` | `src/api.ts` | Dungeon client header; offline and error codes |
| `src/styles.css` (palette, type, focus) | `src/styles.css` | Dungeon layout; one palette |
| `eslint.config.js`, `tsconfig.json` | same files | Dungeon paths |
| `dungeon/launch.py` | `scripts/launch_interface.py` | Dungeon identity, port and health check |
| `Windows/install.bat`, `scripts/windows/install.ps1`, `Windows/launch.bat`, `scripts/windows/launch.ps1` | `install.bat`, `install.ps1`, `launch.bat`, `start.ps1` | Dungeon name, checks and launcher |
| `dungeon/life/chance.py` | `server/mechanics/randomness.py` (`Draws`), `server/mechanics/table_engine.py` (`face`, `resolve`) | `Draws` unchanged; tables are plain dicts with no versions, disabled tables or excluded rows |
| `dungeon/imports/cards.py` | `server/library_formats/png_cards.py` (`chunks`, `embedded_card`), `server/library_formats/cards.py` (`card_data`) | Errors are `DomainError`s; no duplicate-payload or trailing-data refusal; the card becomes plain text for the paste box, not Library files |
| `dungeon/imports/formats.py` | `server/library_formats/json_formats.py` (signatures), `native_characters.py` (field maps), `containers.py` (ZIP checks), `charx.py`, `byaf.py` | One plain shape (character, lorebook, picture) instead of Library proposals; lighter BYAF validation; no asset review |
| `dungeon/imports/lorebooks.py` | `server/library_formats/native_lorebooks.py`, `card_lore.py`, `server/lore/import_rules.py` | Entries are used straight away; pattern entries stay off instead of awaiting review |
| `dungeon/lore.py` (keyword matching) | `server/lore/matching.py` | Whole-word, case-insensitive literal keywords only |

The Study's `assemble_memory` was not copied: it assumes an accepted Story path. The Dungeon's
narrator prompt is built in `dungeon/narration/prompt.py`.
