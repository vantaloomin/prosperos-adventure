# Havenbrooke world package (draft)

Havenbrooke is modern fantasy set in autumn 2009. Supernatural peoples have been legally
recognized in America since 1867, and Havenbrooke University in Haven, New York, is the one
campus where every kind of them studies together. The story follows nine sophomores sharing the
third floor of the Nexus dorm, and the families, courts, covens and fraternities that each claim
some part of them. It is adult, frank about sex, and willing to let things go badly.

This folder is Havenbrooke's world package in its Markdown and JSON form (see "World packages" in
`docs/requirements.md`). The app builds it, with Havenbrooke's engine data, into the world's
SQLite file on first use and rebuilds it when anything here changes (`dungeon/packages.py`,
`docs/packages.md`).

Built from Vanta's Havenbrooke source material (see [sources.md](sources.md)). Every entry is
rewritten in fresh prose; nothing is copied from the source files.

## Layout

| Path | Package section | What it holds |
| --- | --- | --- |
| `world.json` | Rules, settings | Name, calendar and terms, currency, default ruleset, tier and progression defaults, intensity and tone defaults, starting place |
| `canon/*.md` | Canon (world docs) | Overview, eras, the campus, Haven, peoples, law, intimacy, 2009 texture, tone and house rules |
| `lore.json` | Canon (lorebook) | Keyword-triggered entries for the narrator |
| `regions.json` | Canon, rules | Regions of the Northeast and beyond, with danger tier and travel notes |
| `settlements.json` | Canon | Haven, the campus, the nearby towns and the cities the story visits |
| `factions.json` | Canon, rules | Government, courts, councils, covens, families, the university, Greek houses and clubs |
| `cast.json` | Cast | The nine leads in full, plus side and minor cast, with Prospero stats |
| `personas.json` | Persona(s) | The nine leads as playable personas; custom personas allowed |
| `hidden-truths.json` | Hidden truths | What is true that the player character does not know |
| `beats.json` | Planned beats | Season spines and arcs the director can steer toward |
| `engine/institutions/havenbrooke.json` | Engine | The university: terms, classes, places and demands for the school schedule |
| `assets/maps/` | Assets | The Nexus third-floor plan |
| `sources.md` | (review) | Vanta's source files with checksums, and which source wins |
| `open-questions.md` | (review) | Contradictions in the source and how this draft resolves them |

The engine data that sits outside the package, in the shipped `world/data` folders:

| Path | What it holds |
| --- | --- |
| `world/data/cities/haven.json` | Haven and the campus: neighborhoods, places, 2009 prices, climate, notables |
| `world/data/travel/havenbrooke.json` | The travel map: Haven, Ithaca, Syracuse, Seneca Lake, New York |
| `world/data/tiers/havenbrooke.json` | The Standing track and the story clock's start date |
| `world/data/premades/haven.json` | The nine leads as premade characters, enrolled in their classes |
| `world/data/factions/havenbrooke.json` | Faction clocks and jobs for off-page beats |
| `life/decks/havenbrooke.json` | Havenbrooke's Life Cards (first pass) |

## Eras

Four times to start a campaign: the summer before sophomore year (the prequel), sophomore year
(the default, Fall 2009), junior year and senior year. Entries carry `eras` where they only exist
in some of them. See [canon/eras.md](canon/eras.md).

## Conventions

- **Ids** are lowercase kebab-case and unique within their file. Cross-references use ids.
- **`origin`** on an entry says where it comes from: `source` (Vanta's material) or `draft`
  (invented here to fill a gap, for Vanta to approve or cut).
- **Tiers** use the shared ladder from "Scaling and tiers": `local`, `regional`, `realm`, `world`,
  `mythic`. Most of this world is local and regional.
- **Prospero stats** run 1 to 30 with 10 as an ordinary adult. A mundane human's Essence is 1 to 3.
- **Money** is US dollars at real 2009 prices.
- **Hidden truths** live in `hidden-truths.json` and in `secret` fields, so an importer can mark
  them as hidden. `lore.json` holds only what a student could know or hear.
- **Adults only.** Every character is an adult. The freshmen in the cast are kept out of sexual
  content.

## Status

Draft for review. See [open-questions.md](open-questions.md) for the canon calls this draft makes.
