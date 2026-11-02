# Backbone architecture

[Back to the README](../../README.md)

This is what the code in `Program` holds after Milestone 0: the engines kept from Prospero's Companion, with
the companion itself removed. The game systems in [the requirements](https://github.com/vantaloomin/prosperos-dungeon/blob/main/docs/requirements.md) are built on
top of it, milestone by milestone, as set out in [the roadmap](https://github.com/vantaloomin/prosperos-dungeon/blob/main/docs/roadmap.md).

## Shape

- **Backend:** Python and FastAPI in `adventure/`, started by `python -m adventure` on http://127.0.0.1:8805.
  `adventure/main.py` `create_app` wires the routers and keeps the shared services on `app.state`: the database,
  the credential vault, the model provider, the scheduler that queues model work, the embedder, the built-in
  recall and chat models, the launcher for local programs, the hardware check, "Set it up for me", and the
  image adapters.
- **Interface:** React, Vite and TypeScript in `src/`. The app opens on the Story; Worlds and Settings load the
  first time they are opened. `src/workspace.ts` names the views the address can hold (`#story`, `#worlds`,
  `#settings/<tab>`).
- **Storage:** one SQLite database per world, created from `adventure/schema.sql`. Worlds and personas are listed
  in a small registry beside them (`adventure/worlds.py`).
- **Code decides, the model narrates.** Odds, rolls, draws and the state of the town live in code. The model is
  given the outcome and writes the prose.

## Tables

| Table | Holds |
| --- | --- |
| `app_identity` | Which app and schema version made this database, so the Study or the Companion can never open it |
| `workspace_settings` | Timezone, colors, hidden-value switches, the adult side, model-call recording, automatic backups, the AI notice |
| `model_profiles`, `model_routes`, `builtin_recall`, `prompt_overrides`, `local_programs` | Text models and which job each one does; the built-in recall model; reworded prompts; LM Studio, Kobold and other local programs |
| `image_backends` | ComfyUI, Codex and hosted image backends, in the order they are tried |
| `debug_time` | A frozen or shifted clock for testing |
| `persona` | Who the user is in this world, with their birthday |
| `world_cities`, `world_changes`, `world_change_dismissals` | Custom cities and what has changed in the town since it was generated |
| `lore_books`, `lore_entries` | World lore, imported from lorebooks or a Marinara map |
| `story_scene`, `story_messages`, `story_people` | Where the story is, the story so far, and the people the user has met |
| `story_branches`, `story_timeline`, `story_saves` | The story's branches, which one is played, and the game state at each of the player's lines |
| `character_stats`, `story_rolls` | Prospero stats, and the rolls of each turn |
| `record_entries`, `record_corrections`, `story_summary` | The record, the player's corrections to it, and the story so far |
| `story_inventory`, `story_purse`, `story_stock`, `story_trades` | What the character carries, their money, the shops' stock and the trade log (`adventure/inventory.py`) |
| `story_finds`, `story_looks` | What is inside things the player looked into, and what each line looked into and took (`adventure/finds.py`) |
| `story_messages.flags`, `.previous` | A narration's flagged paragraphs and its wording before the last rewrite (`adventure/passages.py`) |
| `story_map`, `story_journeys` | The places on the travel map the character knows, and each line's journey (`adventure/travel.py`) |
| `story_injuries`, `story_treatments` | The character's lasting injuries, and each line's treatment (`adventure/injuries.py`) |
| `story_clocks`, `story_reputation` | The factions' clocks and the character's standing (`adventure/factions.py`) |
| `story_cards` | The Life Cards drawn into the story, by line and scene (`adventure/happenings.py`) |
| `story_stress` | The character's stress track and kill count (`adventure/stress.py`) |
| `story_rests` | Each line's rest: its nights and what one of them turned up (`adventure/rest.py`) |
| `story_turn_steps` | How long each step of a turn took and what gave way for time (`adventure/pace.py`) |
| `story_haggles`, `story_counter` | Each shop's haggled prices for the story day, and what happened at the counter on each line (`adventure/inventory.py`) |
| `story_wounds`, `story_fight`, `story_rounds` | The character's wound level, the fight under way, and each line's decided round (`adventure/combat.py`) |
| `story_clock`, `story_quests` | The story's own time, and its quests with their deadlines (`adventure/quests.py`) |
| `authors_notes` | The user's note that rides along with every narrator turn |
| `round_turns` | Each turn of the round loop: its state, the snapshot it was built from, its draft until commit, and marks such as a GM view left open (`adventure/rounds/turns.py`) |
| `round_seats`, `round_settings` | Who sits at the table and how each decides (agent, Program mind or the human); the mode (Play, Author, Watch), the agent and conversation caps, and changes waiting for the next Idle (`adventure/rounds/seats.py`) |
| `character_memories`, `character_memory_refreshes`, `character_feelings` | What each character remembers and how they feel toward everyone else, keyed by the turn that wrote it and read through the branch's ancestry (`adventure/rounds/memory.py`) |
| `townsfolk_mix`, `townsfolk_personality`, `birth_dates`, `town_levels` | How the town is generated and how it ages |

A database from before Milestone 0 is not upgraded: Adventure starts a fresh schema, and `upgrade.py` only handles
changes made from here on. New tables come from `schema.sql`; a column added to an existing table is listed in
`database.ADDED_COLUMNS` as well.

## Engines kept

| Engine | Where | What it does now |
| --- | --- | --- |
| Round loop | `rounds/`, `round_routes.py` | The state machine every turn runs through (today's single-player turn as one step of it), its step registry, the turn draft committed in one transaction, one writer at a time with stale commands refused, the reply card, re-asking an agent on a new branch, picking up after a restart, and per-character memory that follows branches |
| Narrator | `story.py`, `narration/` | Builds the layered narrator prompt, checks the prose in code, and writes each story turn |
| Odds and rolls | `consequences.py`, `life/chance.py` | Weighted outcomes and seeded rolls, the base for the Milestone 1 dice |
| Life Cards | `life/deck.py` | The deck of life events, drawn by code |
| Townsfolk and the town | `world/` | Generates and ages the people and places of a city; each built-in world's towns ship with the app |
| Calendar and sky | `almanac/` | Holidays, seasons, sunrise and moon phase for a city's date |
| Memory recall | `memory/`, `providers/builtin_recall.py` | Hybrid recall (words and embeddings) over long text, ready for the story's memory |
| Models | `providers/` | Every text model kind, including claude -p and Codex, with queueing and balance |
| Images | `images/` | Backend setup and checks; nothing is generated until the story asks for pictures again |
| Voice | `voice/` | The speech engines, waiting for their place in the story |
| Safety | `safety.py` | The crisis note under any message that sounds like self-harm |

## What was removed

The focal companion, its chat and phone, its daily life and chores, memory extraction from chat, relationship
arcs, the sidecar, the Study importer, LoRA training, voice notes and chat photos. Their tables, routes, screens
and tests are gone; the wording banks they drew on stay in `world/data/`.
