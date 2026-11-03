# Prospero's Adventure

A local-first AI tabletop RPG where every party member can think for themselves. It keeps [Prospero's Dungeon](https://github.com/vantaloomin/prosperos-dungeon)'s game underneath, and gives each character in the party their own agent that decides what that character wants to do each round.

It builds on Prospero's Dungeon, [Prospero's Companion](https://github.com/vantaloomin/prosperos-companion) and [Prospero's Study](https://github.com/vantaloomin/prosperos-study), and plays worlds made in [Prospero's Worldsmith](https://github.com/vantaloomin/prosperos-worldsmith).

## Status

v0.1.0 is the first release, a pre-release for playtesting: characters who think for themselves, the round Writer, and Play, Author and Watch are all in. It started as a clean copy of Prospero's Dungeon (main at `a4663f1`, 2026-11-02), renamed to Adventure so it runs beside Dungeon. The product spec is in [docs/spec.md](docs/spec.md), and what each release brings is in the [Changelog](CHANGELOG.md) and on the [Releases](https://github.com/vantaloomin/prosperos-adventure/releases) page.

It runs on your computer and talks to whichever model you choose: a hosted API (OpenAI, Anthropic, Google, OpenRouter, any OpenAI-compatible service, your Codex login) or a local model through LM Studio, Kobold or any OpenAI-compatible server.

## Getting started

### Windows

1. Install [Git](https://git-scm.com/download/win) and clone this repository.
2. Open the `Windows` folder and double-click **`install.bat`**. It finds or installs Python 3.12+ and Node.js 22.13+, installs the locked dependencies and builds the interface.
3. Double-click **`launch.bat`**. Adventure opens in your browser at http://127.0.0.1:8805. Keep its window open while you use it.
4. Add a model in **Settings > Models**.

### Mac

Clone the repository, open the `Mac` folder and double-click **`install.command`**, then **`launch.command`**. [Installing on a Mac](Program/docs/macos.md) walks through it.

### Linux

There are no helper scripts yet; [Development](Program/docs/development.md) shows how to run it from the `Program` folder.

Data lives outside the program folder: `%LOCALAPPDATA%\ProsperoAdventure` on Windows, `~/Library/Application Support/ProsperoAdventure` on a Mac and `~/.local/share/prospero-adventure` on Linux. **Settings > Data** shows where it is and can move it into a portable `Data` folder beside `Windows`, `Mac` and `Program`.

## Running beside the other Prospero apps

Each app keeps its own port, data folder, credential store entry and backup format, so none of them can open the others' data by mistake:

| App | App port | Dev interface | Data folder (Windows) |
| --- | --- | --- | --- |
| Prospero's Study | 8765 | 5173 | its own |
| Prospero's Companion | 8775 (phone LAN 8776) | 5175 | `%LOCALAPPDATA%\ProsperoCompanion` |
| Prospero's Dungeon | 8785 | 5177 | `%LOCALAPPDATA%\ProsperoDungeon` |
| Prospero's Adventure | 8805 | 5197 | `%LOCALAPPDATA%\ProsperoAdventure` |

Environment variables use the `ADVENTURE_` prefix (for example `ADVENTURE_DATA_DIR`, `ADVENTURE_PORT`).

## Which folder is for you

| Folder | Who it is for |
| --- | --- |
| [`Windows`](Windows) | Running Adventure on a Windows PC. |
| [`Mac`](Mac) | Running it on a Mac. |
| [`Program`](Program) | The app itself: code (`Program/adventure`), interface (`Program/src`), tests, build scripts and docs. |
| [`docs`](docs) | Design: Adventure's product spec. Dungeon's design notes stay in [its repository](https://github.com/vantaloomin/prosperos-dungeon/tree/main/docs). |

| Script | What it does |
| --- | --- |
| `install.bat` | Finds or installs Python and Node.js, installs the locked dependencies and builds the interface. |
| `launch.bat` | Starts Adventure on http://127.0.0.1:8805 and opens it in the browser. |
| `update.bat` | Gets the latest `main` and reruns the install. Close Adventure first. |
| `status.bat` | Says whether Adventure is running, and on which address. |
| `stop.bat` | Stops a running Adventure, for when its window is lost. Never stops another program on the port. |
| `create-shortcut.bat` | Puts a Prospero Adventure shortcut to `launch.bat` on the desktop. |
| `dev.bat` | Development mode: the backend reloads on Python changes and Vite serves http://127.0.0.1:5197. |

Each script has a Mac twin in `Mac` with the same name ending in `.command`.

## Documentation

- [Product spec](docs/spec.md)
- [Style guide and UI requirements](docs/style-guide.md)
- [Development](Program/docs/development.md)
- [End-to-end user flow testing](Program/docs/e2e-testing.md)
- [Backbone architecture](Program/docs/architecture.md)
- [Models](Program/docs/models.md)
- [The story](Program/docs/story.md)
- [Worlds and personas](Program/docs/worlds.md)
- [World data](Program/docs/world-data.md)
- [Image backends](Program/docs/images.md)
- [Safety](Program/docs/safety.md)
- [Changelog](CHANGELOG.md)

## License

Licensed under the [GNU Affero General Public License v3.0](LICENSE), matching the Prospero's Dungeon, Study and Companion code it reuses.
