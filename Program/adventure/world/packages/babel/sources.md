# Sources

Vanta's Mabry Curve roleplay archive, `mabry_curve_reset_archive_2026-10-19.zip` in the project
files (52 files in 7 folders, extracted 2026-10-22). The originals are not copied into this public repo. Every
entry here is rewritten in fresh prose; short phrases that are the world's own (MIND THE STAIR, NO
MARKED BEYOND THE FORD BY ORDER OF THE CLOSE, OUT IS NOT DOWN, "Up one. Varrow. Mind how you go.")
are kept as canon. The explicit off-page record of Bri and Chase is summarized, not carried over.

| File | What it is | Used for | SHA-256 |
| --- | --- | --- | --- |
| `mabry_curve_reset_archive_2026-10-19.zip` | The whole archive | (checksum of the bundle) | `0c86bcf83527868027b22c45de33d0405699dd1a6aa0682076643453d0687956` |
| `README.md` | Status, world summary, game summary, cast, how-to-play and hard rules | world.json, canon/overview.md, canon/the-system.md, canon/tone-and-house-rules.md | `f69a052d616bc8339b02ecd0a54e2bd4456a39711f76a81d48383d050827a297` |
| `canon/side_cast.md` | NPCs met in play, with hidden wants and fears | cast.json, settlements.json, the town files | `62110a7ac756309f49af0847117c803341bcf177ada30421c6381f99a08c0c09` |
| `hidden/tower_truths.md` | What is true that Grant doesn't know; the Season schedule | hidden-truths.json, factions.json, beats.json | `c78a98ca0f9d5fb76f15c249c3618a92bcef51dfa23e5d30ba0def79decd4486` |
| `hidden/bri_and_chase.md` | The off-page record of Bri and Chase on the Bazaar and the Marches | cast.json, hidden-truths.json, beats.json (summarized) | `93fd786c5edcde49778e52abbc5fc47d9111a62146eaacea83f5654ccde66c71` |
| `hidden/roll_log.md` | Every roll and its effect | Not used | `564f73a59e513cf53a2bd321655e36fe8d34837a65d1d95b1bd017367c550822` |
| `continuity/grant_continuity.md` | What Grant knows and believes, turn by turn | canon/the-tower.md, lore.json (what a climber could know) | `add43e2e4f7c0b8af6295d44b17d2b4f1924199ca75a16a1112b0394fd42cf49` |
| `rng/stats.json` | Prospero sheets for Grant and Kenzie | cast.json, personas, premades (base sheets at creation) | `5954f521512d5a003c82e3a34ddb939147dbe0b78f38ea62c67543602d55d350` |
| `tracker/tower_tracker.html` | The Tower Ledger page: Prospero, ranks, classes, beta floors, deviations, ~150 skills | canon/the-system.md, canon/the-tower.md, regions.json | `90314f4a8a78640c25a2817b55fdb33aba1cca00c82a018f38c9207c695e1ede` |
| `story/00_prologue.md` to `story/43_glass.md` | The story, Turns 0 to 43 (44 files) | Places, voices and texture throughout | `21f93c51a7e344e3bcea6aff9e7eb5819173be1221912d111b4bda04bad55cf0` (the 44 files concatenated in order) |

## Not in the archive

The README's folder map lists five canon files the archive does not contain:
`world_building_qa.md` (every design ruling, Rounds 1 to 36), `tower_character_bible.md` (full
character sheets, voices and punctuation profiles), `babel_game_bible.md` (Nth Floor, the game, the
deviation table), `babel_skill_compendium.md` (the full skill library) and `lineages.md` (bodies,
tells, Long House names, breeding, Advanced lineages), plus `rng/rng_rules.md` and `rng/roll.py`.
This package is built from what the README, the tracker and the story establish about them; see
[open-questions.md](open-questions.md).

## Which source wins

Mabry Curve's own precedence: the Q&A rulings, then the bibles, then the compendium, then the
Ledger; anything written in play is canon unless it contradicts something already set. Here, with
those files missing, the order is: the README, the hidden files, the side cast, the story turns
(later turns win), then the tracker.
