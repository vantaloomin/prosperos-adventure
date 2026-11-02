# Vallarith world package (draft)

Vallarith is a grimdark high-fantasy world. Magic is a physical current called the Ley, the Old
Gods are missing, the New Gods are a few lifetimes old, the Eternal Dragons cannot breed, and the
world itself was rebuilt as a prison for the King of the Nine Hells. Survival costs morality.

This folder is Vallarith's world package in its Markdown and JSON form (see "World packages" in
`docs/requirements.md`). The app builds it, with Vallarith's engine data, into the world's SQLite
file on first use and rebuilds it when anything here changes (`dungeon/packages.py`,
`docs/packages.md`).

Built from Vanta's Vallarith source material (see [sources.md](sources.md)). Every entry is
rewritten in fresh prose; nothing is copied from the source files or from outside wikis.

## Layout

| Path | Package section | What it holds |
| --- | --- | --- |
| `world.json` | Rules, settings | Name, calendar, currency, default ruleset, tier and progression defaults, intensity and tone defaults |
| `canon/*.md` | Canon (world docs) | Overview, the three campaign eras, history, the Ley, cosmology, peoples, atlas, tone and house rules, and the D&D name changes |
| `lore.json` | Canon (lorebook) | Keyword-triggered entries for the narrator, one per place, people, power or idea |
| `regions.json` | Canon, rules | Regions with terrain, Ley density, danger tier and travel notes |
| `settlements.json` | Canon | Towns, cities and sites with size, rulers, peoples, Ley dependence, trade and hooks |
| `factions.json` | Canon, rules | Factions with goals, methods, assets, rivals and clock seeds |
| `deities.json` | Canon | Creator Dragons, Eternal Dragons, Old Gods, New Gods, Fey powers, archdevils and demon lords |
| `cast.json` | Cast | NPC seeds with voice, wants, fears, secrets, relationships and Prospero stats |
| `personas.json` | Persona(s) | Player persona options for this world |
| `hidden-truths.json` | Hidden truths | What is true that a player character does not know, who knows it, and how it can surface |
| `beats.json` | Planned beats | Soft arcs the director can steer toward |
| `sources.md` | (review) | Vanta's source files with checksums, and which source wins |
| `open-questions.md` | (review) | Contradictions in the source and how this draft resolves them, plus questions for Vanta |
| `assets/maps/` | Assets | The Known World map and the Ley Line map |

## Three eras

Vanta's call: one world, three times to start a campaign in. Pre-Reform (about 2750 AOM), the
Brotherhood Years (3001 to 3135 BOM) and Post-Reform (about 300 RFM, the default, where Kingswood
is set). Entries carry `eras` and `by_era` where facts change. See [canon/eras.md](canon/eras.md).

## Conventions

- **Ids** are lowercase kebab-case and unique within their file. Cross-references use ids
  (`"region": "badlands"`, `"faction": "brotherhood-of-man"`).
- **`origin`** on an entry says where it comes from: `source` (Vanta's material), `m1-slice` (the
  Kingswood town built for Milestone 1, which is the authority for Kingswood), or `draft` (invented
  here to fill a gap, for Vanta to approve or cut).
- **`ip`** marks where a name comes from: `original` (Vanta's own) or `myth` (public-domain myth or
  folklore). Names coined by Wizards of the Coast for D&D are replaced (Vanta, 2026-10-21); entries
  that changed carry `renamed_from`, and [canon/names.md](canon/names.md) lists every change
  (approved by Vanta).
- **Tiers** use the shared ladder from "Scaling and tiers": `local`, `regional`, `realm`, `world`,
  `mythic`.
- **Prospero stats** run 1 to 30 with 10 as an ordinary adult (`Program/dungeon/rules/marvel.py`).
  Gods and Eternal Dragons in their true forms are beyond stats and carry a tier only.
- **Map positions** (`map: {x, y}`) are fractions of `assets/maps/vallarith.jpg`, from the top
  left, and are approximate.
- **Hidden truths** live in `hidden-truths.json`, in `secret` fields, and in the Eternal Dragons'
  `guise` and the New Gods' `mortal_life` fields, so an importer can mark them as hidden.
  `lore.json` holds only what a well-read local could know or hear.

## Status

Draft for review. See [open-questions.md](open-questions.md) for the canon calls this draft makes
and the ones still waiting on Vanta.
