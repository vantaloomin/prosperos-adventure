# Build roadmap

Drafted 2026-10-21 from [requirements.md](requirements.md). The goal is a **playable slice as soon
as possible**: one small place, one ruleset, the core turn loop working end to end. Everything else
layers on afterwards. Each milestone ends in something Vanta can play.

The code base is PR #1: Prospero's Companion v0.15.0 forked and renamed to Dungeon, with the
unneeded features removed.

## Milestone 0: Foundation (days)

- Merge PR #1 into `main`. It is waiting on Vanta's squash-or-merge-commit choice in the
  "Companion code fork" thread. Then sync the local `main` on Vanta's PC.
- **Fully remove the code Dungeon doesn't use before building** (Vanta, 2026-10-21: better that
  something breaks early than late). That covers the leftover unreachable code from the removals
  (big-day invitations, babysitting asks, knocks, companion-started calls, the Guests slider) and
  the companion-relationship screens and routes the game won't use (companion chat, phone and
  similar). It also drops the old database columns kept only for Companion
  workspaces, since Dungeon has no existing saves to migrate. Keep what the slice reuses: Story
  mode, timelines and lineage, world data and townsfolk, the life engine and Life deck, memory,
  model providers, the Study importer, LoRA training, voice notes, and the steps ladder with rough
  patches (all kept in the earlier removal list). Every removal lands with the full
  test suite and CI green.

## Milestone 1: Playable slice

**Fastest path:** build on Companion's **Story mode** (`story.py`, `story_people.py`). It already
has a narrator walking a city, with places, local time, weather and townsfolk all decided by code.
The slice turns it into a game loop.

**Slice world:** one hand-authored small town from Vallarith, written in Companion's existing city
JSON format (places, prices, pay bands, townsfolk), with 4 to 6 named NPCs, one authored quest with
a deadline, and one dangerous place nearby. The world package format and importer wait until
Milestone 5.

**In the slice:**

1. **Campaign start:** pick a premade persona or make a quick custom one. Prospero stats only.
2. **Turn loop:** the player writes intent, a text model splits it into actions, the Referee
   decides needs-a-roll, stat and difficulty (Jev if a key is set, keyword rules otherwise), and
   code rolls d100 plus stat onto the six-band outcome ladder. The narrator writes the result in
   the persona's voice and never contradicts a roll.
3. **Roll visibility toggle:** hidden or exposed.
4. **Record v0:** code records facts (deaths, items, wounds, promises, locations). Recall is the
   recent turns plus one rolling summary.
5. **NPCs v0:** named NPCs act on their own initiative, with trust, affection, respect, fear and
   desire axes, and short memories of the player.
6. **Combat v0:** zones, one post per round, code tactics for mooks, morale rolls, Prospero wound
   levels, and the defeat table.
7. **Inventory and one shop:** carry slots, finite stock and prices from Companion's pricing, plus
   buying and selling in the shop window and in-story.
8. **Death and branching:** every turn is a save point, and going back to any turn gives new dice.
   This builds on Companion's timelines (`timelines.py`, `lineage.py`).
9. **Intensity v0:** one preset (world default) that shapes narration. Per-category sliders come
   later.
10. **Screen:** a fixed layout with story text, character sheet, inventory, journal, shop window,
    and clock with location. The free grid comes in Milestone 6.
11. **Turn speed budget** (added 2026-10-21 from the competitive research): each turn has a time
    budget, and how long each step took is logged. The narration streams, fact
    extraction runs after the text is on screen, and the contradiction check runs only when the
    narration names a record entity that is dead, spent or elsewhere. Obvious actions go through
    the keyword Referee with no model call. Anything a check flags but doesn't fix in time is
    highlighted with a Rewrite button, and the player can rewrite any passage on request (same
    dice and facts, new wording; added 2026-10-22). See "Turn speed" and "Flagged passages and
    Rewrite" in the requirements.
12. **Decide before describing** (added 2026-10-21): when the player looks into something unseen
    (a chest, a room, a pocket, a stranger's purse), code rolls and stores what is there in the
    record before the narrator mentions it. The narrator describes only what is stored.

**Not in the slice:** other rulesets, travel map, factions and clocks, off-page beats, Life Cards
events, the director, art, tiers, chapters and the branch tree, world packages, DB editor, themes.

**Done when:** Vanta can start a character in the town, talk, haggle, take the quest, fight, get
hurt or die, and go back to an earlier turn and try again with new dice.

## Milestone 2: Living world

- Time and travel: story clock, map crawl with fog of war, region danger tables, rest
  interruptions.
- Life Cards events drawn into play, with the tone dial's drama level.
- Factions with goals and clocks; generated quests from NPC and faction needs; emergent quests from
  promises.
- Off-page beats on world time with a turn minimum; news spreads with "word gets around".
- Injuries and recovery (treatment, permanent injuries, stress track) under the Injury
  persistence setting.
- Scaling and tiers: per-world track on the shared tier ladder, banded offers, start, ceiling and
  pace sliders.
- Progression: use-based Prospero growth plus milestones; dark tracks.
- **Director v0** (added 2026-10-22 from a friend's feedback; see "The director" in the
  requirements). It comes after factions, quests and off-page beats, since it reads them all. It
  covers the spine arc and the thread list, the Soft/Guiding/Firm hand slider, the hidden GM note on
  every turn, side-quest ties, the tension curve with escalating arc stages, and nemesis promotion.
  It starts with Kingswood: the Heartwood contract seeds the Eight Pieces.

## Milestone 3: Memory and campaigns

- **Schema-first fact extraction** (added 2026-10-21 from the competitive research): the extractor
  fills a JSON Schema for record entries, constrained by grammar or structured output where the
  backend supports it, and falls back to one field at a time on weak local models. The GM view
  can regenerate or clear a single extracted fact. See "Fact extraction" in the requirements.
- Full layered recall, model fact extraction checked by code, rewrite-on-contradiction (with skip
  toggle), forgetting with grudges.
- Chapters at scene breaks, the chapter list, the branch tree, bookmarks, Ironman mode, the
  player-only notebook.
- Memory view of what the character knows, plus the GM view toggle.
- **Director, full** (added 2026-10-22): seeds and payoffs (the Chekhov list), adopting
  improvised details (checked by the fact extractor against the record and hidden truths), the
  director model slot that drafts each arc stage's beats, the GM-view co-planning setting, and
  "previously" chapter openers.
- Export as a backup file and as a book (Markdown, EPUB, PDF); legacy import.

## Milestone 4: Rulesets

- D&D 5e via SRD 5.2, then Ironsworn/Starforged (with Supply), each mapped onto the shared outcome
  ladder with full content packs.
- Basic Roleplaying next. Fate, Blades and Dungeon World only after the license check thread
  reports back.

## Milestone 5: Worlds

- The SQLite world package format.
- The importer (built on Study's) with per-section review.
- The built-in world DB editor and the Markdown/JSON round-trip.
- Import Vallarith in full, then Havenbrooke (institutions, Grades, class schedule), then BABEL.

## Milestone 6: Presentation

- Art on request, passive art toggle, reference images, live-state portraits.
- Map widget, VN portraits, background art.
- The four-part screen (story stage, status strip, scene panel, drawer), the entity card, pins,
  the three modes plus per-world scene-panel rules, themes, phone tabs. The status strip and the
  turn receipt need no art and can ship before Milestone 6 (decided 2026-10-22).
- Last, optionally: a free grid with saved layouts as a "Customize layout" mode.
- Full intensity sliders with veils and table filtering; tone voice setting.

## Hex crawl (added 2026-10-23)

Requirements "### Hex crawl". Small PRs, in order:

1. Hex engine: the grid, terrains, seeded generation past the authored hexes, fog of war per hex,
   journeys walked hex by hex. Vallarith's authored core painted from its world map.
2. Directions ("I head north-east"), searching a hex, sites, getting lost, weather.
3. The map widget draws hexes.
4. Havenbrooke's on-foot wild regions; BABEL marked `travel: "roads"`.

## Order and parallel work

Milestone 0 and 1 are sequential and come first. After the slice, Milestones 2 and 3 can run in
parallel threads. Milestones 4, 5 and 6 can each start once Milestone 1 has merged.
