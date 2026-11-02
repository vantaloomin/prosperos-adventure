# BABEL world package (draft)

BABEL is the tower world from Vanta's Mabry Curve roleplay: a living tower of themed floors that has
dressed itself up as the unreleased full-dive game one of its new arrivals helped build. The rules
on the screen are his rules, until they aren't. Lives are hidden, the System lies by leaving things
out, and desire, taboo, power exchange and broken vows are a secret source of power that changes
whoever uses it and binds whoever they use it on.

This folder is BABEL's world package in its Markdown and JSON form (see "World packages" in
`docs/requirements.md`). The app builds it, with BABEL's engine data, into the world's SQLite file on
first use and rebuilds it when anything here changes (`dungeon/packages.py`, `docs/packages.md`).

Built from Vanta's Mabry Curve archive (see [sources.md](sources.md)). Every entry is rewritten;
nothing is copied from the story files.

## Layout

| Path | Package section | What it holds |
| --- | --- | --- |
| `world.json` | Rules, settings | Name, calendar and floor clocks, Talents, default ruleset, rank-to-tier mapping, progression (rank, Resonance, Tethers), intensity and tone defaults, house rules |
| `canon/*.md` | Canon (world docs) | Overview, the tower and its floors, the System, lineages, the four from Halvorsen's, tone and house rules, names |
| `lore.json` | Canon (lorebook) | Keyword-triggered entries for the narrator: what a climber could see or be told |
| `regions.json` | Canon, rules | The floors (and the Stair and the Reach) with their tropes, beta ranks and tiers |
| `settlements.json` | Canon | The Concourse, Hollin, Saint Aurel, Varrow Keep, the Reachwall, the Marches, the Gilded Bazaar and the floors beyond |
| `factions.json` | Canon, rules | The Landing, the Close, House Corve, the Reach giants, the Lantern Room and the rest, with clock seeds |
| `cast.json` | Cast | The four, Rachel, and the people of the Concourse, Varrow and the Bazaar, with voice, wants, fears, secrets and Prospero stats |
| `personas.json` | Persona(s) | The four from Halvorsen's as playable personas, and what each one knows |
| `hidden-truths.json` | Hidden truths | What is true that an arrival doesn't know |
| `beats.json` | Planned beats | The climb, the Season on the Reachwall (ten events), the First Frost and the other arcs |
| `sources.md`, `open-questions.md` | (review) | The archive with checksums; the calls this draft makes |

## Engine data

The game's own data for BABEL lives in `Program/dungeon/world/data` and is gathered into the package
as it is built: `cities/the-concourse.json`, `cities/hollin.json`, `cities/the-gilded-bazaar.json`
and `cities/babel-floors.json` (the other floors and the Stair's landings, as travel nodes);
`travel/babel.json`; `tiers/babel.json` (with the arrival-morning `start`); `arcs/babel.json`;
`factions/babel.json`; the Concourse and Bazaar premades and items; and the Life Card deck in
`Program/dungeon/life/decks/babel.json`.

## Conventions

- **Ids** are lowercase kebab-case and unique within their file. Cross-references use ids.
- **`origin`** says where an entry comes from: `source` (Vanta's archive) or `draft` (invented here
  to fill a gap, for Vanta to keep, change or cut).
- **Floors** are regions; `floor` counts from the Concourse (0), up positive.
- **Tiers** use the shared ladder (`local`, `regional`, `realm`, `world`, `mythic`); `world.json`
  maps BABEL's ranks onto it.
- **Prospero stats** run 1 to 30 with 10 an ordinary adult (`Program/dungeon/rules/marvel.py`), which
  matches BABEL's own range at creation.
- **Hidden truths** live in `hidden-truths.json` and in `secret` fields, so an importer marks them
  hidden. `lore.json` holds only what a climber could know.
- **Adults only.** Every character in the package is an adult.

## Status

Draft for review. See [open-questions.md](open-questions.md).
