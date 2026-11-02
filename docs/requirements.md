# Prospero's Dungeon: requirements

*Gathered 2026-10-20 to 2026-10-21 in the "Requirements and system design" thread. A living document: decisions are settled, proposals are open to change.*

## Vision

An all-in-one, local-first AI TTRPG simulator for adult, morally complex, dark stories where good
outcomes are not guaranteed. Complex underneath, easy for the player. The program makes the
decisions; the language model narrates them.

## Foundations

| Source | What Dungeon takes |
| --- | --- |
| Prospero's Companion | The backbone, as a clean copy: Python backend, React/Vite UI, any model provider, model per job, timelines, memory, life simulation, world data format, townsfolk, Story-mode narrator |
| Prospero's Companion (cont.) | "Life Cards": the Life deck (`companion/life/deck.py`, `world/data/life_deck.json`): seeded draws of weighted cards into the day, gated by a drama level, alongside Study's d100 random tables reworded for life |
| Prospero's Study | The Story randomness engine Life Cards grew from (`server/mechanics/`): seeded d100 activation, cooldown, major-disruption cap, ~30 event / extra / handling tables |
| Mabry Curve (RP archive) | The reference turn loop, hidden-information model, continuity tracking, off-page cadence and house rules |

## Decided

- **Start from a clean copy of Companion's code** (no git history carried over), then grow from there.
- **Rule systems are selectable** (Vanta, 2026-10-21): the player can pick from several built-in
  TTRPG rulesets, including Prospero and open-licensed systems. See "Rulesets" below.
  - Each world names a default ruleset. The player can change it when starting a campaign; after
    that it is locked, so sheets never need converting.
  - Each ruleset ships with its full open content from the start (classes, spells, monsters, items,
    oracles), not resolution only.
  - First three: **Prospero**, **D&D 5e via SRD 5.2** (2024 rules), **Ironsworn/Starforged**.
    Basic Roleplaying is next.
- **Prospero is the house ruleset** (called MARVEL until 2026-10-26, Vanta's rename; its six stats still
  spell MARVEL, and the code keeps the id `marvel` so saves and world files load unchanged. BABEL's
  in-world System still calls its stats MARVEL).
- **Prospero dice:** d100 plus a stat-based bonus, with a difficulty shift, landing in six bands:
  Critical failure, Fail, Fail with an upside, Success at a cost, Success, Critical success.
- **Prospero stats:** Mind, Allure, Resolve, Vitality, Essence, Luck.
- **Roll visibility:** a toggle between hidden (felt only through the story) and exposed.
- **Worlds:** Dungeon's own versions built from Vanta's bases: **Vallarith** (grimdark D&D-style),
  **Havenbrooke** (modern fantasy, supernatural university, 2009), and Mabry Curve's **BABEL** tower.
- **Player voice:** the narrator expands the player's input rather than refusing to write their
  character. "I taunt the demon and attack" becomes a taunt in the Persona's own voice, shaped by
  the roll.
- **Persona:** each world defines its own player Personas (sheet, voice, stats). The player can pick
  any main-cast member (any of Havenbrooke's nine, say) or create their own; every world allows
  player-made personas.
- **Branching and dice:** going back always brings new dice, even for the same actions.
- **Progression:** per world, built from track types the engine provides: Rank, XP, Grades, Time,
  Reputation, Bonds, Milestones, Corruption, Use-based skill growth, Wealth. A world can use several
  at once (see "Progression").
- **Narration format:** a player setting (length, POV, tense), not fixed per world.
- **Platform:** like Companion: local web app (Python backend, browser UI) on Windows, Mac scripts,
  phone access over the player's own Tailscale.
- **Play screen:** a customizable widget layout. Candidate widgets: story text (with clickable lore
  and character links that open modals), background art, map plus current location, VN-style
  portraits of characters in the scene, character sheet, party and relationships, inventory,
  status windows, a "what I know" journal, progression tracks. Layout presets (classic RPG,
  visual novel, text-first) on top of free arrangement.
- **Content limits:** no hard lines beyond adults only, which is the premise and always on.
- **NPCs and party:** always autonomous. They can be influenced like real people, never commanded.
- **Death:** always possible. Recovery is Study's infinite branching: go back to any earlier point
  and take another path; the dead branch is kept.

## Rulesets

Code still decides and the model still narrates, whatever ruleset is active. A ruleset is a
pluggable module that supplies:

- **Character sheet:** attributes, skills, derived values, character creation steps.
- **Resolution:** how a check is rolled (d100 roll-under, d20 + modifier vs DC, 2d6 moves, action
  die vs challenge dice) and its result.
- **Outcome mapping:** every result is translated onto one shared outcome ladder (Critical failure
  through Critical success), so the narrator, Life Cards, continuity and the UI work the same way
  under any ruleset.
- **Referee questions:** what the Referee and Jev must decide per action (Prospero: stat + difficulty;
  5e: ability, skill and DC; Ironsworn: which move; PbtA: which move and stat).
- **Progression:** which tracks it uses (levels and XP, ranks, milestones, momentum).
- **Content packs (data, not code):** classes, spells, monsters, items, oracles, where the license
  allows. Shipped in full with the ruleset.
- **Attribution:** each pack carries its license notice, shown in the app (SRD 5.2 needs one
  attribution sentence; WotC trademarks such as "Dungeons & Dragons" are not used).

### Narrative Only

Asked for 2026-10-22 (Vanta): a ruleset with few or no stats that runs on "gut check" realism. "I want to seduce the
barmaid" from a character described as an overweight NEET is a long shot because of who they are, what they say, and
what the barmaid wants, not because of a number on a sheet.

- **The judge decides, with no dice** (Vanta, 2026-10-22). A judge model (the Referee's text model, else the
  narrator's; keyword rules with no model) gives each action one of four verdicts: **No**, **No, but**, **Yes, but**
  or **Yes**, with a one-line reason. The verdict is fixed before the narrator writes, as a roll is, and the
  narrator writes it as given and never overturns it. On the shared ladder: No is failure, No, but is failure with
  something gained (the but), Yes, but is success at a cost, Yes is success. So feelings, Life Cards, continuity and
  the record work unchanged. The judge is not the narrator: it sees the facts below, not the prose.
- **The sheet is the character's description.** The persona's About text, kind, age and look, plus what play adds
  (lasting injuries, gear, reputation, the record's facts about them). There are no stats. Optional short lists the
  player can fill in, "good at" and "bad at", sharpen the judge's read but are not required.
- **The verdict comes from four things,** each given to the judge in plain words:
  1. Who the character is: the description, injuries, gear and what they have done (the record).
  2. What the player writes: a careful, specific approach moves the verdict, and a line that only states the goal
     ("I seduce her") does not.
  3. Who they are dealing with: the target NPC's feelings toward the character (trust, affection, respect, fear,
     desire), their wants, fears and secrets, their mood and the scene (a busy bar at closing time).
     With the adult side switched on, the judge also reads who each adult present is drawn to (orientation, what
     draws them in such as a sharp mind or a quick wit, what they are into, drive; Vanta, 2026-10-26). It only
     weighs a romantic or seductive action, and it is never shown or given to the narrator.
  4. The world and its tone: what is physically possible, and the intensity and drama dials.
- **No roll card** (Vanta, 2026-10-22). The verdict and its reason ("No, but: she is tired and he opened with her
  looks; she does laugh at the joke") go to the narrator only, and the story just tells what happened. The GM view
  can show the verdicts for debugging. Plain acts with nothing at stake get no verdict, as obvious actions get no
  roll now.
- **Fights, harm and death** use the shared wound levels (Prospero's), judged the same way per exchange: who has the
  upper hand, weapons, numbers, injuries. Defeat follows the foes' aim, as the defeat table has it.
- **Progression is narrative.** No XP. What the character does well, often, and in front of people becomes part of
  who they are (the record and reputation), which moves the judge's verdicts next time. The Referee sees "known for:
  ...".
- **No-model fallback:** keyword rules plus the feelings. A plain try is Yes, but; persuasion of someone who
  distrusts or fears the character is No, but; of an enemy, No.
- **It is a ruleset like the others** (`rules/narrative.py`), picked at session zero and locked at the start. It is
  shown as "Narrative" with the hint "No stats or dice: what happens comes from who your character is and what they say."

### Fate

Built 2026-10-23 from Fate Accelerated and Fate Condensed (CC-BY-3.0, Evil Hat's attribution shown with the sheet),
the first of the three rulesets the license check cleared (Fate, then Blades-style, then Dungeon World).

- **The sheet is words.** A high concept and a trouble, up to three more aspects and up to three stunts, all the
  player's own; six approaches (Careful, Clever, Flashy, Forceful, Quick, Sneaky) at +3, +2, +2, +1, +1, +0;
  refresh 3; three stress boxes; mild, moderate and severe consequences.
- **Resolution:** 4dF plus the approach the action's words name, plus 2 for a stunt whose words fit, against
  passive opposition on the Fate ladder from the Referee's difficulty. Fail is failure, a tie success at a cost,
  success success, success with style (3+ shifts) critical success; no critical failure.
- **Fate points are spent by code,** like Ironsworn's momentum: a fitting aspect is invoked (+2, one Fate point)
  only when the +2 changes the outcome. An aspect fits when it shares two telling words with the action (one
  shared name is not enough); a stunt when a word of what it is for (after "when") is in the action. An action the
  trouble fits is a compel: it pays a Fate point, and a success comes at a cost. A line that acts on the trouble
  with nothing rolled pays the point too (once a turn). A premade's trouble is the first
  later sentence of its About with trouble in it (a debt, a secret, someone hunting them). Fate points come back to
  the refresh after a night's sleep, silently: the sheet shows them and the narration never does.
- **Progression:** a milestone raises the weakest approach by one, to +4 at most.
- **Fights** use the shared wound levels for now; stress and consequences as their own harm track come later.

### Candidate systems and licenses

Dungeon is public, AGPL software, so a ruleset ships only if its license covers software. Licenses
marked "unverified" were checked from memory or secondary coverage, not the license text. Checked
2026-10-21; this is not legal advice. CC-BY 3.0 and 4.0 cover any medium, including software, and
allow commercial use and adult content; they require attribution and no DRM on the licensed text.

| System | License | Fit | Notes |
| --- | --- | --- | --- |
| **Prospero d100** | Vanta's own | House default | Mabry Curve's system. |
| **Narrative Only** | Dungeon's own | Asked for | No stats; a judge sets odds from the character, the words and the NPC (see above). |
| **D&D 5e: SRD 5.2** (2024 rules) | CC-BY-4.0, irrevocable (Apr 2025) | Strong | One attribution sentence. Excludes D&D Beyond Basic Rules and WotC trademarks. |
| **D&D 5e: SRD 5.1** (2014 rules) | CC-BY-4.0 | Strong | Pick 5.1 or 5.2, or both. |
| **Basic Roleplaying (Chaosium)** | ORC (2023 Universal Game Engine) | Strong | d100 percentile skills, close kin to Prospero. |
| **Pathfinder 2e Remaster** | ORC (Archives of Nethys is the official SRD) | Medium | Very crunchy; big lift to do well. |
| **Ironsworn / Starforged** | CC-BY-4.0 for SRD, moves, assets, oracles | Strong | Built for solo play with oracles; fits an AI GM. |
| **Fate Core / Accelerated / Condensed** | CC-BY-3.0 Unported (verified; OGL route also offered) | Medium | Narrative; aspects map well to LLM play. Use the official CC-BY SRD ZIP, not the website text. Attribution: "This work is based on Fate Core System and Fate Accelerated Edition, products of Evil Hat Productions, LLC..." (Condensed has its own line). "Powered by Fate" logo and Fate font optional, with their own notices. Source: fate-srd.com/official-licensing-fate |
| **Blades in the Dark / Forged in the Dark** | CC-BY-3.0 Unported, SRD only (verified) | Medium | Position and effect, clocks. Attribution: "This work is based on Blades in the Dark (found at http://www.bladesinthedark.com/), product of One Seven Design, developed and authored by John Harper...". Excluded: Doskvol/Duskwall setting, NPCs, art, maps. Don't use "Blades in the Dark" in a product title, don't imply endorsement. The licensing page also asks that nothing be "prejudicial to One Seven Design's honor or reputation" (vague; low risk for rules-only use). Source: bladesinthedark.com/licensing |
| **PbtA** | Per game, not one license | Varies | Apocalypse World isn't open. **Dungeon World** (2012 text) is CC-BY-3.0 Unported (verified, LICENSE in github.com/Sagelt/Dungeon-World); credit Sage LaTorra and Adam Koebel; art not included; it also contains SRD 5.1 text (CC-BY-4.0, needs that attribution too). Dungeon World 2 (new owners, Kickstarter Jan 2027) has no announced license; only the 2012 text is covered. |
| **Cairn** | CC-BY-SA-4.0 (unverified) | Medium | Share-alike applies to derived text. |
| **Year Zero Engine** | Free League Free Tabletop License | Not usable | Allows virtual tabletop modules but excludes video games (per third-party copies of the license text; official page blocked our fetch). An AI game app is likely outside it. |
| **Cypher System** | Cypher System Open License | Not usable | Grant covers "tabletop roleplaying game materials" only, and bans "rape or other acts of criminal perversion; or other obscene material", which conflicts with Dungeon's adult content. Breach terminates the license. Source: csol.montecookgames.com/license |
| **The Black Hack** | OGL 1.0a (unverified) | Low | OGL obligations; low priority. |

## Shops and economy

Code decides what a shop has and what it costs; the narrator only voices the shopkeeper. The
narrator never invents an item, a price or money: it gets the shop's real stock and quotes.

**What already exists in Companion:** each city has a `currency`, places with a price level,
careers with pay bands, rents, and a `prices` list of everyday goods as low–high ranges with a
seeded `price()` picker. Dungeon extends this rather than starting over.

- **Shops are places with an owner.** A shop is a world place with a type (general store, smith,
  apothecary, tailor, bookseller, fence, black market, campus store, and so on), a wealth tier, and
  a shopkeeper who is a townsperson with a schedule. Opening hours come from that schedule, so a
  shop can be closed, or the owner out sick.
- **Item catalog per world and ruleset.** Each item has a base price in the world's currency,
  category, rarity, legality, and its rules stats for the active ruleset. 5e uses SRD 5.2's
  equipment and price lists as written (in gp). Prospero items are priced in the world's own currency;
  Havenbrooke uses real 2009 prices.
- **Realism check.** Base prices are anchored to the world's wages and rents (what a day's work
  buys), and a data test flags items that are out of line.
- **Services are priced the same way.** Inns and taverns (a night's lodging, meals, drink),
  stabling, baths, healers, scribes, guides, passage and hirelings come from the same catalog and
  modifiers. Lodging comes in comfort tiers (a floor by the fire up to a private suite), and the
  narrator only quotes the tier's real price.
- **Affordability guard.** Every catalog price is checked against what each class of people earns
  in that world, so ordinary things stay within ordinary means. Example rule: a common-room night
  plus a meal costs no more than about a day's wage for an unskilled worker, and a modest room
  about a skilled worker's day. A night at an inn never costs a year of a peasant's life. The data
  tests fail on any price that breaks its tier's bounds.
- **Stock generation.** Seeded and deterministic from shop type × settlement size × wealth tier ×
  rarity. Quantities are finite; what the player buys is gone. Rare items are few or absent in
  small places.
- **Restocking.** On the life-sim clock (deliveries on a cadence per shop type), so stock changes
  while the player is away. Shopkeepers buy the player's goods at a markdown and resell them.
- **Price modifiers.** base × region (distance from the source, local scarcity) × settlement ×
  shop tier × reputation and relationship with the owner × current events × legality markup
  (a fence pays little, a black market charges a lot). Each modifier is clamped and logged.
- **Life Cards and world events move markets.** A shortage, a caravan raid, a festival, a war or a
  plague changes stock and prices for a while. Shops can open and close as Companion's cities
  already do.
- **Haggling is a roll.** An opposed check in the active ruleset (Prospero: Allure vs the owner's
  Resolve; 5e: Persuasion, Deception or Intimidation vs Insight; Ironsworn: Compel) mapped onto the
  outcome ladder. Success lowers the price; success at a cost gets the price but the owner
  remembers; a critical failure can raise prices or get the player thrown out.
- **Money is tracked by code.** Wallet, carried goods and a transaction log live in the database.
- **Shop window and story both (decided).** Talking to a shopkeeper in the story opens a shop
  window with the stock list, prices and buy/sell; either side can drive the purchase.
- **Selling and fencing (decided).** The player can sell loot and fence stolen goods. Stolen goods
  are tracked as such; fences pay less, and honest shops may refuse them or call the watch.
- **Shopkeeper cash (decided, toggle).** Shopkeepers have finite cash by default, so a village smith
  can't buy a dragon hoard. A setting turns this off.
- **Ironsworn (decided):** keeps its abstract Supply track and buys with moves; the world's
  currency is color only.

## Combat

Decided 2026-10-21. Code runs the fight; the narrator writes it. Whatever the ruleset, every
attack, save and morale check is rolled by code and mapped onto the shared outcome ladder.

- **Positioning: zones, grid optional.** Every ruleset tracks range bands (engaged, near, far) and
  named areas ("the bar", "the stairs") in code. An optional grid battle-map widget is available
  for 5e fights.
- **Pacing: one post is one round,** with a plan option. The player declares an action; code
  resolves every combatant in initiative order and the narrator writes the whole round. A "fight
  on my plan" option takes an intent ("hold the door, protect Kenzie") and auto-resolves rounds
  until a turning point: someone falls, morale breaks, a new threat arrives, or the plan stops
  making sense.
- **Who decides enemy actions.** Code lists the legal actions each round. Ordinary enemies use
  rule-based tactics per creature type; named enemies and autonomous allies have the Referee model
  pick using their personality and goals. Code checks legality either way.
- **Morale.** Code tracks morale per side. Losses, a fallen leader, fear and being outmatched
  trigger morale rolls; a broken side flees, surrenders or begs. That leaves the player choices
  like sparing, ransoming, interrogating or executing.
- **Surprise and ambushes are rolled.** Before a fight, code rolls stealth against awareness for
  both sides, including ambushes on the player while travelling or asleep. The surprised side
  loses its first round or acts last.
- **Damage per ruleset.** 5e keeps HP; Ironsworn keeps Health and harm. **Prospero uses wound
  levels:** a hit lands as Grazed, Hurt, Wounded, Maimed or Dying, set by the roll band and the
  weapon, and each level carries penalties until treated.
- **Enemy status visibility follows the roll toggle.** With rolls exposed, the combat widget shows
  exact HP, wounds and conditions; with rolls hidden, only descriptive states ("bloodied",
  "staggering", "won't last").
- **Losing a fight: the defeat table.** The ruleset's own rules apply first (5e death saves,
  Ironsworn's Face Death, Prospero's Dying level). If those are lost, code rolls the outcome,
  weighted by what the winners want: death, capture, robbed and left for dead, or rescued.
  Slavers capture, bandits rob, beasts kill. Death stays possible, and the player can always
  branch back.

## Injuries and recovery

Decided 2026-10-21. Code tracks every wound, treatment and condition; the narrator describes them.

**Everything here sits under one campaign setting, Injury persistence** (Vanta):
- **Permanent** (default): lasting injuries and stress conditions stay until something
  extraordinary fixes them.
- **Temporary:** they still happen but fade on their own over time.
- **None:** no lasting injuries or conditions; wounds matter only until they heal.

- **Healing speed: as written, with a gritty toggle.** Each ruleset heals as written by default
  (5e long rests, Ironsworn's recovery moves). A campaign setting switches on gritty healing, where
  serious wounds take days to weeks of in-game time in any ruleset. **Prospero is gritty by
  default:** a wound drops one level after a stretch of rest set by its severity.
- **Permanent injuries are rolled.** A Maimed result, a critical hit or a failed death save rolls
  on a lasting-injury table (a lost eye, a limp, a ruined hand, a disfiguring scar). Each has a
  mechanical effect and a social one that NPCs react to. Under Permanent it stays until something
  extraordinary fixes it, such as rare magic or a master healer, at a price.
- **Treatment takes a healer, supplies and a roll, and can go wrong.** The roll uses the healer's
  skill and what they have on hand. A bad roll can mean infection, a badly set bone or a wound that
  reopens. Magic healing still works where a world has it (Vallarith's clerics, BABEL potions),
  under that world's rules. Healers and medical supplies are shop and service items with real
  prices, and Life Cards can bring plague or contaminated supplies.
- **Mental harm: a stress track.** Code tracks stress from traumatic events: horror, torture,
  loss, a first kill, betrayal. Prospero resists with Resolve; other rulesets use their nearest
  equivalent (5e Wisdom saves, Ironsworn's Spirit). Past thresholds, code rolls a lasting condition
  such as nightmares, a phobia, numbness or a compulsion. Conditions can ease with rest, support
  and time, and the narrator plays them consistently across the campaign.

## Time and travel

Decided 2026-10-21.

- **World clock: story time, with a per-world option.** In-game time advances with what the player
  does (a conversation takes minutes, a journey days), and the life sim, shops, NPC schedules and
  deadlines all run on that clock. A world can opt into Companion-style real-time living instead,
  so it keeps moving while the app is closed (a natural fit for Havenbrooke).
- **Journeys: map crawl.** Each world has a travel map: a node graph of places joined by routes
  (with distance, terrain and danger), plus optional hex regions for open wilderness. A map
  widget shows it with fog of war, so unexplored places stay hidden until found. Every step costs
  in-game time and supplies (or Ironsworn Supply) and rolls weather and events. Vallarith's maps
  are the first candidates to digitize.
- **Hex crawl by default (Vanta, 2026-10-23).** Travel between towns is a hex crawl in every world unless
  the world's travel map opts out. See "### Hex crawl" below.
- **Road encounters: region danger plus Life Cards.** Each region has a danger level and its own
  encounter tables: monsters, bandits, patrols, travellers, merchants, strange sights. Life Cards
  and world events shift them (a war brings patrols and deserters, a plague empties the roads).
  Fights that follow use the Combat rules, including rolled ambushes.
- **Resting is risky and the world moves.** Resting outside a safe place can be interrupted by a
  roll weighted by region danger and precautions taken (watches, hidden camp, wards). While the
  player rests, time passes: NPCs act, deadlines tick, rumors spread, shops restock, and wounds
  and stress recover under the Injuries rules.

### Hex crawl

Decided 2026-10-23 (Vanta: "Hex default, worlds can opt out"; maps extend "Minecraft style"). Code owns the
map; the narrator describes what code says is there.

- **Per world.** A travel map sets `travel: "hex"` (the default) or `"roads"` (opt out: the node graph and
  one-turn journeys as before). Vallarith is a full hex crawl. Havenbrooke keeps roads by car or bus between
  towns, plus small on-foot hex regions for the wild places around Haven (the woods, the reservation land),
  entered from a place in town. BABEL keeps the Stair as roads (floors and landings).
- **The grid.** Flat-topped axial hexes, six miles across by default (a map's `hex_miles` changes it;
  Havenbrooke's woods are one mile). Each hex has a terrain, a region, and may have a road, a river, a town
  (a place on the travel map) or a site. Each terrain has its hours to cross on foot, how far one sees from it
  and how easy it is to get lost in it (a road always halves the hours and never gets you lost). Water and
  sheer peaks can't be walked.
- **Authored core, generated beyond.** A world's authored hexes are canon (Vallarith's are painted from its
  world map). Any hex not authored is generated the first time it comes into sight, from the campaign's world
  seed and its coordinates, so the same campaign always gets the same land. Generation follows the
  neighbours: terrain spreads (forests grow in patches, hills run into mountain ranges, coasts stay coasts),
  a region carries on past the map's edge until a roll drifts into one of the map's frontier regions, and roads
  and rivers that reach the edge carry on. The map can grow in any direction without end. A generated hex is
  stored with the campaign and branched with the story, so going back to an earlier turn forgets land seen
  after it, and seeing it again generates it again exactly as before.
- **Rivers and lakes** (Vanta card 2026-11-02: "Yes, rivers in play"). An authored map can list its rivers,
  each the hexes it runs through from source to mouth with how much water each carries, and its lakes (water
  hexes). Prospero's Worldsmith's map painter works both out from the author's paint (water runs downhill,
  joins and reaches the sea; basins fill into lakes). Crossing a river off the road costs an hour more to ford
  (for a six-mile hex), and bad weather slows it like any off-road step; walking along a river's bank crosses
  nothing. A road crosses a big river on a bridge and a small one by a ford, at no extra time. The narrator is
  told every river a journey crossed and how, and the river where the character stops out in the wild; the hex
  map on screen draws the rivers the character has seen.
- **Sites.** Hexes can hold sites: ruins, lairs, camps, shrines, caves, battlefields, hamlets. Authored sites
  come from the world package; generated hexes roll on their region's site table (filtered by intensity, like
  every table). Some sites can be seen from a distance (a tower, smoke), others are hidden and are only found
  by searching their hex. A found site becomes a place on the map one can travel to, and a generated hamlet
  becomes a place on the Road with a generated name until it is built out.
- **Moving.** "I set out for Eriane" plans the quickest way (along roads, across country where that
  is quicker) and walks it hex by hex. "I head north-east" or "I strike out east into the hills" walks
  one day in that direction (due east or west zigzags between the two hex sides either way). "I search the
  area" spends the hex's crossing time to look for hidden sites (a Mind roll). Clicking a known hex on
  the map puts the line in the box.
- **Each hex entered.** It is revealed with the ring around it (two rings from hills, three from a mountain,
  only itself in forest or marsh), rolls an encounter against its region's danger (one step safer on a road),
  and sees any visible site. A journey stops when foes attack, when it comes upon a site it didn't know about
  (the player decides whether to go in), or when the character gets lost.
- **Getting lost.** Each day off road in terrain one can get lost in, a Mind roll whose difficulty comes from
  the terrain and the weather. A failure veers one hex off course without the character knowing; the map shows
  where they think they are until they reach a road, a town or a known landmark.
- **Weather.** Rolled once a day per region and season (clear, rain, storm, snow, fog). Bad weather slows
  crossing, makes getting lost likelier and is passed to the narrator.
- **Time, food, rest.** As before: ten walking hours a day, nights camped by the Rest rules, a food (or a point
  of Ironsworn supply) per day, and the story clock moves by all of it.
- **The map widget.** Draws the known hexes with their terrain, roads, rivers, towns and found sites; the rest
  stays dark. Where the character thinks they are is marked when they are lost.

### Town maps

Asked 2026-10-23 (Vanta: city maps that look good, with destinations and stores, "without having to pre-gen
every single aspect"). Code lays a town's street map out from its data and the campaign seed, like the hex
crawl; nothing is drawn by hand or by an image model, and only what the player looks at is filled in.

- **From the town's data.** Neighborhood positions, places, employers, colleges and water already in the city
  file are enough. The town is cut into patches (a Voronoi diagram, spread from the middle out, or a grid for a
  modern town); each patch belongs to the nearest neighborhood, weighted so a busy neighborhood gets more; patch
  edges are streets, and main roads run from the square to the map's edge. A neighborhood far out of town is a
  road off the map. A sea is a coast past the town's last neighborhood on its side; a lake and a river take no
  buildings.
- **Seeded and stable.** The same town and seed give the same map, so it is never stored. Authored places,
  employers and colleges are given lots in their own neighborhood (a park or square takes a whole patch); every
  other lot is blank until the character looks at it, when code decides what stands there from the seed and the
  look's table (world/data/town_lots.json: homes, trades, shops, taverns, and vice gated by the intensity
  levels; a shop is likelier on a main road), names it from the town's own names, and keeps it as found. A lot
  looked at is a place of the town from then on: the player can walk there by name and the narrator knows it.
- **The street outside.** The narrator is told the few buildings nearest where the character is (the town's own
  places and lots decided as above), and arriving somewhere keeps them as seen, so the map shows them and the
  player can walk into one by name.
- **Found, not known** (Vanta, 2026-10-26: "Surely there should be some discovery"; card: landmarks, and more for
  locals). The map and its place list name only the places the character knows of: where they have been, what
  they passed on the street, a building they looked at, and any place the story names to them (the narration or
  an NPC). A stranger also knows the landmarks anyone could find (squares, parks, temples, markets, the library,
  docks, the way in, big employers); a character whose home is the town knows all of it except places tagged
  hidden or secret. An unfound place is a blank lot (or unnamed open ground) until then. Typing a place's name
  still goes there, as asking the way would. Kept per branch (story_places). The travel map between towns already
  works this way (heard of one road away, famous places, visited).
- **Looks.** 'ink' (an old hand-inked town, for fantasy and past eras), 'street' (a modern grid) or 'floor' (a
  town on one floor of BABEL's tower, walled by it). The era chooses unless the city's `town_map.style` says
  otherwise; a world's road or wilds says `"none"` and has no town map.
- **The Town widget.** Shows the map of the town the story is in (separate from the travel Map widget), with
  where the character is; clicking a place shows it and offers to go there.

### Interiors

Asked 2026-11-02 (Vanta, in the Worldsmith thread: maps for "towns, dungeons, the world"; card: "Rooms map,
authored + generated"). The inside of a keep, cave, crypt, mine or tower is a map of rooms joined by passages,
walked room by room, the way the hex crawl walks hexes and the town map walks streets.

- **Rooms and passages, not a grid.** An interior is a graph: rooms (a name, a short description, a kind such as
  hall, cell, shrine, cavern or stair, a size, and its light: lit, dim or dark) joined by passages (open, door,
  stairs, ladder, shaft, crawlway, water or secret). Rooms sit on levels (the upper galleries, the flooded deep).
  A passage can be locked (a key item, or a roll to pick or force it), hidden (found by searching), one-way, or
  trapped (an action, a difficulty and a threat, like a road encounter). A room can hold foes (the encounter foe
  shape), a hazard, loot (the finds tables) and lore. Combat inside uses the ruleset's own rules; a room's size
  sets the ranges.
- **Authored core, generated beyond.** Key interiors are authored, in a world package's engine data
  (engine/interiors/<id>.json, or world/data/interiors for a built-in world) and drawn in Worldsmith as a rooms
  map (rooms are boxes, levels are groups, passages are labelled links, with the Mermaid text kept in step; a
  room keeps where it was drawn as its `map` x/y). A place of a town, a travel-map stop or an authored site names its interior. A rolled site (a ruin, cave, lair or
  ward fort from the hex crawl) gets a generated interior the first time it is entered: laid out from the
  campaign seed and the site's kind (an interior table per kind: how many rooms, which kinds, how deep), so the
  same campaign always finds the same rooms and nothing is stored until it is seen. Generation follows the
  intensity levels, like every table.
- **Walking it.** "I go down into the mine" at the entrance enters the interior's first room. The narrator is
  told the room and the ways out the character can see; "I take the stairs down" or "back to the shaft head"
  moves along a passage (or the quickest known way to a room named). Each move takes time on the story clock.
  "I search the room" spends time and makes a Mind roll for hidden passages and anything hidden there. A locked
  door wants its key, a pick or force roll, or another way round. Dark rooms without a light source make every
  roll harder and hide the far exits. Wandering foes roll from the interior's own encounter table every few
  moves, like a region's road encounters. Leaving by the entrance (or any other way out) returns to the place or
  hex outside.
- **Found, not known.** The interior map widget shows only the rooms the character has seen and the passages
  they know of, like the town map. A cleared room, an opened door, a sprung trap and taken loot stay that way,
  kept per branch (story_interiors), so going back to an earlier turn restores them.

## Inventory and equipment

Decided 2026-10-21. Code owns every item; the narrator can't add, remove or invent gear.

- **Carrying limits: slots, with a toggle.** Every character has carry slots in every ruleset:
  more with Vitality (or the ruleset's strength stat), packs, and mounts or vehicles. A dagger
  takes a fraction of a slot, a sword one, armor several. A campaign setting turns carrying limits
  off entirely.
- **Visible gear is tracked.** Code knows what is worn, wielded and on display (a drawn sword,
  fine silks, a guild badge, blood on your clothes, a stolen ring its owner would recognize).
  It feeds NPC reactions, guards, thieves, reputation and shop prices.
- **Wear: breaks on bad rolls.** No durability numbers. Critical failures and heavy hits can
  damage or break weapons, armor, tools and clothes. Damaged gear works worse until repaired;
  repairs are a priced shop service (smiths, tailors, tinkers).
- **Loot: plausible, plus hoards.** Bodies and pockets hold what that person plausibly carried,
  built by code from who they were (a bandit's few coins, knife and stolen ring; a noble's signet
  and purse). Lairs, vaults and bosses use the ruleset's own treasure tables (5e SRD treasure,
  Ironsworn rewards), adapted to the world's currency.
- **Appearance state (Vanta).** Code tracks how each character looks right now, and the narrator
  describes it consistently:
  - **Cleanliness:** clean, worn, grimy, filthy, plus specific marks (blood, mud, sweat, other
    fluids, scent). Travel, fights, weather, work and sex raise it; washing, baths and laundry
    clear it. Baths and laundry are priced services.
  - **Clothing condition:** intact, rumpled, torn, ruined, per garment. Bad rolls, fights and
    deliberate tearing damage clothes; tailors repair them.
  - **State of dress:** per clothing layer (outer, under, accessories): worn, loosened, partly
    off, removed, and where a removed item ended up.
  - All of it is visible gear, so NPCs react to it. Companion's grooming data (hair, nails and
    facial hair changing over time,
    `world/data/grooming.json`) rounds out looks for modern worlds. A world can switch the
    detail level down (Vallarith might only track cleanliness and condition).

## Quests and factions

Decided 2026-10-21.

- **Quests come from three places.** Authored arcs in the world package (Havenbrooke's seasons,
  Mabry's Season events); jobs code generates from what NPCs and factions need right now (a debt,
  a missing daughter, a rival to remove); and emergent quests from promises, threats and bargains
  the player makes in play, which code records as obligations.
- **The journal shows what the character believes.** Objectives, leads and suspicions are recorded
  as the character understands them, which can be incomplete, wrong, or a lie someone told them.
  The truth is stored separately as hidden fact and surfaces only when discovered in play; where
  belief and truth differ, code keeps a wrong-footing record, as Mabry Curve does.
- **Factions act on their own goals, with clocks.** Each faction (guild, church, gang, noble house,
  campus society) has goals, resources, relationships with other factions, and progress clocks
  that advance on the world clock. They scheme, ally, trade and go to war whether or not the player
  is involved, and their needs feed generated quests. The player's standing with each is a
  Reputation track.
- **Quests have real deadlines.** Many quests carry a deadline on the story clock. If the player is
  late, the hostage dies, the rival wins or the job goes to someone else, and the world remembers
  it (reputation, NPC memory, follow-on consequences).
- **Institutions are factions; their demands are quests; the result is a track.** A university,
  guild, army or church is a faction the player belongs to. Its recurring demands become generated
  quests with deadlines on the story clock: Havenbrooke's assignments, exams, labs and club duties;
  a guild's dues and contracts. How the player does on them feeds a progression track (Grades,
  Rank) and their standing with the institution. Classes and shifts occupy fixed slots in the
  player's schedule, the same way Companion's careers do, so skipping class is a real choice with
  consequences.

## NPC minds

Decided 2026-10-21. "Autonomous but influenceable" rests on this model. Code holds each NPC's
state; the Referee and narrator read it and never contradict it.

- **Memory is tiered.** Key NPCs keep full, typed memories of the player, like Companion's
  companions. Minor NPCs keep a few short impressions ("stiffed me on the bill", "was kind to my
  daughter"). Crowds keep none. An NPC is promoted to a higher tier when they start to matter, and
  keeps what they had.
- **Feelings run on several axes.** Separate tracks for trust, affection, respect, fear and
  desire, each moved by events and rolls. An NPC can fear and want the player while trusting them
  not at all. The axes feed persuasion difficulty, what NPCs will do for the player, and when they
  turn on them.
- **Word gets around.** Code spreads news along NPC relationships and factions over time, as
  Companion already does. Accuracy degrades with each retelling, some NPCs keep what they know to
  themselves, and the player's reputation can arrive before they do.
- **NPCs keep secrets and lie, and detection is rolled.** Each NPC has hidden goals and secrets
  stored apart from what they say, like the player's own hidden truths. They may lie when it
  serves them. An insight roll against their deception decides whether the player notices, and a
  lie believed goes into the player's journal as belief, not truth.
- **NPCs have their own lives.** Key NPCs pursue their goals and follow life-sim schedules when
  they are off-scene (Companion's townsfolk and life engine), so they are somewhere, doing
  something, when the player looks for them.
- **Leaving a scene: NPCs can stop you, and the Table can turn it off.** Decided 2026-10-26 (Vanta's
  card: "Hostile and fond both"). A fight holds the character until a flight succeeds, as before.
  Outside a fight, someone there who is hostile (hates or distrusts the character and isn't afraid
  of them) blocks the way, and someone fond of them begs them to stay. Code decides who from their
  feelings, and getting away is a roll; a failure keeps the character in the scene for that line.
  The Table rule "Who can stop you leaving" picks anyone with a reason (the default), only fights,
  or nobody (a character can walk out of a fight too). Being held prisoner is not leaving.

## Memory and context

Decided 2026-10-21 (round 1). A campaign runs far longer than any model can read at once, so code
decides what the narrator sees each turn.

- **Layered recall.** Each turn the narrator gets the recent turns word for word, older scenes as
  chapter summaries, and facts pulled in by relevance: who is present, where the scene is, and
  anything just mentioned (names, places, items, promises). This builds on Companion's and Study's
  summarizing, and on Mabry's continuity file.
- **A code-kept record is the source of truth.** (Called "the record" since 2026-10-22, Vanta's
  choice; earlier docs and code said "ledger". Hidden truth is what is "off the record" for the
  character.) Code records facts as structured entries:
  deaths, items, injuries, promises, locations, secrets, relationships, clock states. After each
  narration a cheap model extracts new facts the narrator introduced (a scar, a name, a rumor).
  Code checks them against the record and stores them, and rejects any that contradict it.
  Summaries are prose on top, and the record wins any conflict.
- **Hidden truth and character knowledge are separate.** Each record entry is marked as world
  truth, character belief, or both, which keeps the journal and wrong-footing rules from
  "Quests and factions" and "NPC minds" intact.
- **The player sees and edits what their character knows.** Corrections are logged, so a model
  mistake is easy to fix. Hidden truth stays hidden by default. A settings toggle opens a full
  GM view that shows and edits everything, secrets included.
- **Context auto-fits each model, with a player cap.** Code knows each model's window and fills it
  in a fixed priority order: ruleset and persona, the current scene and state, the NPCs present,
  recent turns, recalled facts, then summaries. It trims from the bottom. A setting caps tokens
  per turn to control cost and speed on paid models.

Round 2, decided 2026-10-21:

- **Contradictions are rewritten before the player sees them.** If a narration clashes with the
  record (a dead NPC waves, spent coin reappears), code has the narrator redo that passage first.
  A setting skips the check for speed on slow local models; a skipped contradiction is then
  flagged for the player to rewrite (see "Flagged passages and Rewrite").
- **Chapters close at scene breaks.** Code starts a new chapter on a location change, time skip,
  rest, or the end of a fight or quest step, and summarizes the one that ended. The player can
  also close a chapter themselves and name it. Chapters give the story view and branch view
  their structure.
- **Branches are sealed, except a player notebook.** Each branch forks the record at the branch
  point (with new dice). The character and NPCs know only what happened on their branch. A
  player-only notebook spans every branch, and no model ever reads it as character knowledge.
- **Characters forget, but grudges stick.** The record keeps every fact. What NPCs and the player
  character are treated as remembering fades by importance and age, while big events (betrayal,
  a death, a debt) stay. Memories tied to strong feelings (fear, hatred, love) stay sharp
  regardless of age. A roll can recall a faded detail.

Added 2026-10-21 from the competitive research (Vanta: "do all 3"):

- **Fact extraction is schema-first.** The cheap model that pulls new facts out of each narration
  fills a JSON Schema of record entry types (death, item, wound, promise, location, secret,
  relationship, clock), not free text. Where the backend supports it, the schema constrains the
  output directly (grammar sampling on llama.cpp-style servers, structured output on hosted APIs,
  `--json-schema` / `--output-schema` on the CLIs). Weak local models fall back to asking one
  field at a time. Code still checks every fact against the record before storing it. In the GM
  view, a single extracted fact can be regenerated or cleared without redoing the whole turn.
  (Pattern from the zTracker SillyTavern extension.)

## Campaign management

Decided 2026-10-21.

- **Every turn is a save, plus bookmarks.** Each turn is saved automatically as a point in the
  branch tree, and going back from any point gives new dice. The player can bookmark and name
  moments to find them fast. A per-campaign **Ironman** mode, chosen at campaign start, turns off
  going back, so death is final.
- **Branches have two views, as widgets.** A chapter list reads the current branch like a table of
  contents, with a switcher between branches. A tree view maps every chapter and branch; clicking
  a node reads it or plays on from there, and dead ends are marked by how they ended.
- **Campaigns are separate, with a legacy option.** Each campaign starts from a fresh copy of its
  world. At campaign start the player may import a finished campaign's outcome as world history,
  so an old character can be a legend, a villain or a corpse.
- **Export as a backup or as a book.** A full campaign file (record, branches, saves, settings)
  for backup or moving machines, importable again. The story of one branch also exports as a
  readable book in Markdown, EPUB or PDF.

## Art

Decided 2026-10-21. Builds on Companion's image pipeline. By default art is made only when the
player asks, so play never waits on it and costs nothing. A **Passive art** setting adds automatic
art on top.

- **Passive art (setting, off by default).** When on, code triggers images from game events: a new
  named character appears, the scene moves to a new location or time of day, a portrait goes out
  of date, or a big moment happens (a death, a reveal, a defeat, a chapter end). Most triggers are
  plain code checks on record and state changes; for less clear moments the decision model (Jev)
  answers "is this worth illustrating?". Passive art runs in the background and never holds up
  the text. A per-session cap limits how many images it makes.

- **Anything can be illustrated, on request.** VN-style character portraits with expressions,
  location backgrounds by time of day, full scene illustrations, and a button to illustrate any
  passage. Images are saved with their chapter, are reused
  until something changes, and go into the book export.
- **Every named character gets one reference image.** The first portrait of a named character
  becomes their reference, reused in every later image so they keep looking like themselves. No
  LoRA training is required (Companion's trainer stays available as an optional upgrade).
- **Portraits show full live state.** Images are built from what code tracks: wounds, scars and
  maims, gear, cleanliness, clothing condition, state of dress, and mood from the NPC feeling
  axes. When that state changes, the portrait is marked out of date, and the player can refresh
  it with one click.

## Intensity and tone

Decided 2026-10-21. There are no hard lines beyond adults only. These settings control what is
shown and what the tables can produce, so each player can tune the game to their comfort.

- **Intensity is set per category, with presets and veils.** Each category has its own slider:
  violence and gore, sex, horror, cruelty and abuse, drugs, and others the worlds need. Presets
  such as Restrained, Mature and Unflinching set them all at once. **Veils** name specific topics
  that may still happen but always fade to black on the page.
- **Worlds set the default, and the player can change it at any time.** Each world suggests its
  levels (Vallarith grimdark, for example). The player can adjust them at any point, even
  mid-scene, without restarting. Unlike rulesets, intensity never locks.
- **Lower settings also change what can happen.** Code filters event tables, Life Cards, defeat
  tables and injury results by the current levels, so a lower setting removes some outcomes
  entirely (for example, no sexual-violence results or fewer maims), not just their description.
  At the top setting, every outcome stays in play. Veiled topics stay in the tables but are
  narrated off the page.
- **Tone is a separate dial with two parts.** A **voice** setting (grim, wry, romantic, hopeful
  and so on) shapes how the narrator writes. A **drama** setting weights Life Cards and event
  tables toward calmer or more eventful draws, building on the Life deck's drama level. Neither
  part ever changes roll odds, so good outcomes are never guaranteed.

## Scaling and tiers

Decided 2026-10-21. Supports the classic "save cats, kill rats, eventually kill a god" arc as an
option. Work that finds the player matches their standing: nothing below it unless they go looking,
and never two or more tiers above it.

- **Standing comes from a per-world track.** Each world names which progression track sets the
  player's tier (Rank, Grades, XP, renown and so on), mapped onto one shared tier ladder (for
  example Local, Regional, Realm, World, Mythic) so code can compare quests, foes and regions
  across rulesets.
- **Offers come at your tier, with a rare +1 stretch.** Quests that come to the player unasked are
  at their tier. Now and then a +1 offer appears, flagged beforehand by a rumor or an NPC's warning
  as beyond them. Offers at +2 or above never appear. Lower-tier work is always there for a player
  who seeks it out (a notice board, a favor for a friend), but it never comes to them.
- **The world is fixed, but threats can find you.** Regions, foes and treasure keep their own tier
  and do not rise with the player. A player can walk into a region far above them; signs, rumors
  and NPCs warn first, and death is real. Faction clocks can also send higher-tier trouble after a
  player who has made powerful enemies.
- **The arc has start, ceiling and pace sliders.** Each world sets defaults. At campaign start the
  player picks a starting tier, a ceiling tier (Grounded stays low, Classic runs rats to gods,
  Epic starts high) and a pace from slow burn to fast rise. Pace controls how fast the world's
  track climbs; the tier ladder itself stays the same.

## Progression

Decided 2026-10-21. Each world builds its progression from the engine's track types, and one of
them sets the player's tier (see "Scaling and tiers").

- **The engine ships all ten track types:** Rank, XP, Grades, Time, Reputation, Bonds,
  Milestones, Corruption, use-based skill growth and Wealth. Wealth reads from the economy and
  Time from the world clock, rather than being separate counters, so a merchant-prince or
  race-the-curse campaign can use either as its tier track.
- **Prospero characters grow by use, plus milestones.** A stat used under pressure (a rolled action
  that mattered) gets marked. At rest, code rolls to raise each marked stat, Basic Roleplaying
  style. Hitting a milestone or rising a tier also grants a bigger boost or a new ability. 5e and
  Ironsworn keep their own growth rules (levels, legacy tracks).
- **Dark tracks bite.** Corruption and tracks like it (addiction, infamy) grant power as they
  rise. Crossing a threshold also rolls a lasting change to body, mind, or how NPCs and factions
  treat the character, and the top of the track can cost the player the character. The intensity
  settings can filter which changes are possible.
- **Tracks follow the roll visibility toggle.** In hidden mode the sheet shows words ("known on
  the Docks", "Rank: Journeyman"). In exposed mode it shows numbers and progress bars.

## Off-page beats

Decided 2026-10-21. Characters the player isn't with keep living. Key NPCs already follow life-sim
schedules and factions run clocks; a beat is a rolled event in an absent character's own story,
stored in the record as hidden truth.

- **Beats run on world time, with a turn minimum.** Beats fire as in-world time passes (for
  example each day), so a long rest or journey moves everyone along. A beat also fires at least
  every few turns (default 3, as in Mabry), so a long scene doesn't freeze the world.
- **Connected characters get detailed beats.** Absent party members, bonds, rivals and quest NPCs
  get rolled beats. Everyone else just follows their schedule in code, which keeps model calls
  down.
- **The player learns through the world, with cutaways as a toggle.** By default what happened reaches the
  character only through news, letters, rumor and meeting people again, distorted as usual
  ("word gets around"). A setting turns on short "meanwhile" cutaways that show the player what
  the character can't know. Cutaway content also shows in the GM view.
- **Anything can happen off-page.** Beats can kill, capture or turn anyone, bonded characters
  included, with no guaranteed warning. The player may find out late, or only by going back to an
  earlier branch.

## The director

Decided 2026-10-22 (Vanta's cards), from a friend's feedback that Vanta shared: play should feel like a game
master is steering toward a larger story. Not a preset list of beats, and not an open sandbox
with nobody's hand on it. The director is that hand. It is code that holds the campaign's plot
state, and it gets a model's help with ideas. It decides what the world pushes toward. It never
decides what the player does, and like everything else it never changes roll odds.

- **The campaign's spine emerges from play.** In the first chapters the director seeds several
  arcs at the player's tier (Vallarith Post-Reform: the Eight Pieces through the Heartwood, the
  Long Border through Bastion's deserters, the Failing Wards through the keep). It commits to
  the one the player bites on hardest, measured by thread heat, as the campaign's spine. If the
  player hasn't bitten on any by the end of the third chapter, the director falls back to the
  world's default spine for that era. Arcs that aren't chosen don't vanish: they carry on in the
  background on their own clocks and can come back as side arcs. If the player later turns hard
  toward another arc, the director can promote it, so the player's choices can still take canon
  somewhere else.
- **Threads are the GM's notebook.** Code keeps a list of open threads: leads, mysteries, grudges,
  debts, promises and oaths, unanswered questions, and villains' agendas. Each one has an arc it
  feeds (or none yet), a stage, a heat score (how recently and strongly play touched it), the hidden
  truth behind it, and what would close it. Quests, factions, NPC secrets and off-page beats all
  open threads and move them along. The player's journal shows each thread as the character
  understands it. The GM view shows the real thing.
- **How hard the hand pushes is a campaign slider.** The setting is **Soft**, **Guiding** (the
  default) or **Firm**, picked at campaign start next to the tier sliders.
  Under Soft, beats wait or lapse as before. Under Guiding, the arc comes to the player: its people
  and clocks go looking for them, ignoring it has consequences, and the arc moves on without them.
  Under Firm, arc beats fire on schedule wherever the player is. In every mode the player's
  choices can take canon somewhere else, and nothing writes the player's actions for them.
- **Every turn carries a hidden GM note.** Before the narrator writes, the director adds a short,
  hidden note to the turn's facts. It says what pressure this scene is under, which seed to plant
  if it fits, which thread an NPC present is carrying, and what an antagonist nearby is doing.
  The narrator works these in where they fit the scene and the dice. The note never
  overrides a roll or the record, and code checks afterwards which planted seeds actually reached
  the page.
- **Seeds pay off.** Clues, omens and odd details the director plants are logged against the
  thread and hidden truth they point to (a Chekhov list). Each seed gets a payoff window. As a
  thread nears its turn, code makes sure the seeds that reached the page come back. A seed that
  never paid off is either cashed in or quietly retired in the GM view, never just left dangling.
- **The director can adopt improvised details.** When the player engages with something the
  narrator made up (a stranger watching from the bar, a symbol on a door), the director may give
  it a meaning and tie it to a thread. The meaning is stored as hidden truth and checked against
  the record and the world's hidden truths first, so nothing already established is contradicted.
- **Side quests leave a mark.** Every generated or authored side quest carries at least one tie
  the director can pick up later: a recurring NPC, a clue, an item that matters, a faction that
  noticed. About one in three links straight into an active arc. The rest stay self-contained
  stories that still leave something behind. Ties respect the tier rules: a local job can carry a
  clue to a world-tier arc, but never its fight.
- **Pacing follows a tension curve.** The director tracks each chapter's tension from scene kinds
  (quiet, social, pressure, reveal, crisis) and recent outcomes. When the story has gone slack for
  a few turns, it picks the next pressure from the hottest threads and the arcs that are due. After
  a crisis it allows a quiet scene before the next one. The tone dial's drama setting moves the curve,
  as it does for Life Cards. Arcs escalate in stages on their own clocks, so a thread left
  alone grows worse.
- **Antagonists recur.** Arcs and factions name their antagonists, who have agendas and clocks.
  Any foe the player has a history with (one who escaped, was humiliated, lost someone to them,
  or was spared) can be promoted to a **nemesis**. A nemesis has a grudge, remembers what the
  player did and how they fight, adapts to it, and comes back with a plan. A foe confirmed dead on the page
  stays dead unless the world's own magic allows a return, and then signs come first.
- **Arcs are planned a stage at a time, Mabry style.** At each arc stage the director drafts the
  next few candidate beats from the world's planned beats, the hottest threads and the faction
  clocks. A director model slot drafts them, and code checks them against the record, the tier
  rules and the intensity settings before storing them as hidden truth. By default the plan stays
  hidden and the player only meets it in play. A GM-view setting lets the player pick, cut and
  reorder the drafted beats, as Vanta did with Mabry's Season events. With no model, beats come
  only from authored arcs and tables.
- **Chapters open and close like sessions.** A chapter opens with a short "previously" drawn from
  the hottest threads, and when it closes it leaves at least one open hook.

## Play screen and widgets

Decided 2026-10-21. Builds on the widget layout under "Decided".

- **The first playable version ships the systems widgets.** Story text (with lore and character
  links), character sheet, inventory, journal, shop window, combat zones, clock and location,
  and the chapter list. Visual widgets (VN portraits, background art, the map with fog of war)
  come in the next release, followed by the branch tree, dice log, party and relationships panel,
  and the grid map.
- **The screen has four parts, and the scene picks what's beside the story** (Vanta, 2026-10-22,
  from the UX review: "Widgets: a hard look"). The **story stage** (prose, the player's lines, roll
  cards, turn receipts, the composer) is always the centre. A **status strip** shows condition,
  nerve, coin, time and place at a glance. A **scene panel** beside the story shows the one or two
  widgets the current scene needs, chosen by code from the game state, with no model call: a fight
  shows the fight, a shop its shop window, the road the map, a conversation the people here. A
  **drawer** holds everything else (sheet, pack, journal, map, people, factions, chapters, tone and
  rules), one click away. The player can **pin** a widget to keep it in the scene panel, and a pin
  wins over the scene.
- **Five rules every widget follows.**
  1. **Widgets propose, the story decides.** Buying, travelling, using an item or talking to someone
     from a widget writes a line into the composer; the turn loop rolls and applies it. Only settings
     and out-of-character tools act directly.
  2. **One entity card.** A name in the prose, a person in the people list, a place on the map, an
     item in the pack and a faction all open the same card: what the character knows, their history
     with it, and what they can do (each action writes a line).
  3. **Numbers follow the roll toggle, everywhere.** Dice shown: exact coin, wounds, standing and odds.
     Dice hidden: words only. One switch for every widget.
  4. **Widgets show what the character knows, not what's true.** Hidden truth is only in the GM view.
  5. **Every turn leaves a receipt.** Under each narration, a row of chips names what code changed that
     turn (coin, wounds, journal entries, standing, time); each chip opens its widget.
- **Three presets become modes, plus per-world defaults.** Classic (story centre, scene panel
  beside it), Reader (wide story, the scene panel folded to a chip row) and Visual novel (text box
  over scene art with portraits; needs the M6 art, Classic until then) recompose the same four parts.
  A world can ship its own scene-panel rules and theme (Havenbrooke's class schedule on school days,
  for example), as a small file, not a saved grid.
- **Phones get the story plus tabs.** On a phone the story fills the screen with the status strip
  under the header, and a bottom bar opens the scene panel and the drawer as slide-up sheets. The
  scene panel's tab gets a dot when the scene changes (a fight starts), so nothing opens over the
  reading.
- **Themes now, a free grid later.** Fonts, colors and per-world themes are customizable, so a
  grimdark world and a 2009 campus can look different. A free snapping grid with saved layouts is an
  optional "Customize layout" mode late in Milestone 6, on top of the four parts, never the default.

## World packages

The three bases arrive in three shapes: Mabry (canon / hidden / continuity markdown plus dice
files), Havenbrooke (character bibles with verbal fingerprints, world docs, season story beats,
a floor plan), Vallarith (a 102-entry keyword lorebook, magic and timeline docs, deities, maps).
Dungeon would normalize them into one package per world:

- **Canon:** world docs and lorebook entries (keyword-triggered, as Study's lore engine does).
- **Cast:** NPC sheets with voice, wants, fears, relationships, stats.
- **Persona(s):** the player character sheet(s) for this world.
- **Hidden truths:** what is true that the player character doesn't know.
- **Planned beats:** optional season or arc schedules (Havenbrooke's beats, Mabry's Season events)
  that the director steers toward but doesn't force.
- **Rules:** progression ladder, death rule, Life Cards tables, house voice and hard rules.
- **Assets:** maps and images.

Decided 2026-10-21:

- **A world is one SQLite database file.** All of the above (canon, cast, personas, hidden truths,
  planned beats, rules, tables, prices and assets) lives in one compact file per world, which is
  also the file shared between players.
- **Existing worlds come in through an importer, with review.** An importer built on Study's reads
  any source shape (Mabry's markdown, Havenbrooke's bibles, Vallarith's lorebook JSON). A model
  drafts each package section, and the author reviews and approves each one before it is used.
- **Worlds are edited in a built-in DB editor.** Dungeon ships its own world database editor
  (Vanta, 2026-10-21). It has friendly forms for common things (cast, lore entries, personas,
  shops and prices, tables, world settings) and a raw table view for everything else, with
  search, filters, linked records (click an NPC's faction to open it), validation on save, and an
  undo history. Hidden truths are marked clearly so an author can't leak them by accident. For
  bulk edits, the app can also export a world to a folder of Markdown and JSON and import it back,
  with a validator checking it before it replaces the database.
- **Planned beats feed the director.** The director (see "The director") steers the story toward
  a world's planned beats (Havenbrooke's seasons, Mabry's season events). How hard it pushes
  depends on the campaign's hand setting (Soft, Guiding or Firm). It never writes the player's
  actions, and the player's choices can take canon somewhere else entirely.
- **Peoples by share (Vanta, 2026-11-02).** Every world can be home to the standard fantasy
  peoples and more: 75 built-in kinds of beastkin (canids, felines, serpents, equines, bovines,
  lagomorphs, cervids, ursines, avians, draconic), fantasy humanoids (four kinds of elf, dwarves,
  orcs and half-orcs, goblins and hobgoblins, halflings, gnomes, giant-kin, fiends, merfolk and
  sea-kin) and other peoples (oni, tengu, kappa, mind-eaters, centaurs, fae and more), each with a
  lifespan and its own naming scheme of at least a hundred given and a hundred family names or
  titles. A town sets each people's share of its townsfolk (humans are the rest), in the same
  format as Prospero's Companion's kinds by share; Worldsmith offers the list with a share for
  each. See docs/world-data.md, "The peoples of fantasy worlds".

### Worlds set in a past year

Ported from Companion's "Back when" decade banks (2026-11-02, Vanta). A modern city whose story clock
reads a year before today (Havenbrooke's autumn 2009) keeps to that year, by rule
(dungeon/world/decades.py, world/data/decades.json):

- **Jobs and pastimes** with `years` are only offered in those years: a video store clerk or a web
  designer is work in 2009 and not today; no townsperson drives for a ride-hailing app in 2009.
- **The narrator is told the year:** the decade's phones, computers and media, the slang of that
  year, a few real books, shows and songs out by then, typical prices in that year's money (a city's
  prices are written in its own year, its `names.year`, and scaled by a price index for any other),
  and the things that don't exist yet.
- **Anachronisms are checked:** narration naming something from a later year (Instagram, a selfie,
  "YOLO" in 2009) gets one rewrite while the turn has time; a passage that still names one is flagged
  for the player with why.
- **Pictures** are told the year, so clothes, phones and cars are of it.

A world in the present, and any city of another era, is untouched.

## Narrator prompting

Decided 2026-10-21. Vanta's three writing documents are the inspiration (kept verbatim in the
project files under `dungeon/prompting/`): the adult literary fiction instructions, the AI-ism
blocklist and the writing ruleset. Dungeon adapts them for turn-by-turn play rather than copying
them. Code is `Program/dungeon/narration/`.

- **A layered prompt, short enough for local models.** In order: the core (who the narrator is
  and its contract with the code), the craft rules, the player's narration format, intensity and
  voice, the persona, the scene, then this turn's outcomes, so the facts sit nearest the player's
  words. The core and craft run to about 900 words; models with a context window under 16k tokens
  get a compact craft layer of about 110 words instead. Both layers can be reworded in Settings >
  Advanced like Companion's other prompts.
- **Code decides, the model narrates.** The core says the outcomes are fixed: write the band the
  code gives, no better and no worse, and never invent rolls, numbers, items, money, prices,
  wounds, deaths or moves. If the story needs something the facts don't settle, leave it open.
  Hidden rolls are never mentioned in the prose; shown rolls may be named.
- **The player's words are expanded, not replaced.** "I taunt the demon and attack" becomes the
  taunt in the persona's voice and the attack landing as the band says. The narrator adds no
  decisions, speeches or feelings the player did not ask for, apart from reflexes and sensation.
- **The two always-on rules map onto the systems.** "A living world" becomes the NPC rules
  (everyone pursues their own goals, lies on the page as dialogue, can be influenced but never
  ordered, helps only at a cost) and feeds from NPC minds and off-page beats. "Two steps forward,
  one back" sits on top of the outcome ladder: the bands decide how a roll went, and the narrator
  makes wins carry a bill and never resolves a scene entirely.
- **Format is a player setting.** Point of view (first, second or close third), tense (past or
  present) and length (short, medium, long). The default for a persona is close third person,
  past tense, as in Mabry Curve and Vanta's guide. Story mode, which has no persona yet, keeps
  second person and present tense. Inner thoughts use single-quoted italics; game windows go in
  code blocks.
- **Content.** Adults only is absolute and stated in the core. Nothing else is a hard line; the
  intensity layer tells the narrator how far each category goes (off the page, restrained,
  mature, unflinching) and which topics are veiled. Until worlds set defaults, every category is
  unflinching. The Story narrator no longer carries Companion's self-harm rule, since characters
  in a dark story may come to harm; the app's crisis note on the real player's own words stays.
- **Prose rules that code can check are checked in code** after every narration, before the
  player sees it (`prose.py`), the same principle as rewriting record contradictions:
  - **Hard:** em dashes in any form (the character, a double hyphen, a spaced hyphen or en dash).
    Always fixed: the rewrite pass first, then a mechanical replacement that cannot fail.
  - **Strong:** dialogue echoes, reported speech, more than four bare lines of dialogue in a row,
    scene-closing tells, stock intimacy phrases, thinking tics, performed emotion, emotional
    shorthand, filler, and unambiguous AI vocabulary. Any of these asks the model for one rewrite
    of the flagged wording, used only if it keeps roughly the same length and has fewer problems.
  - **Watch:** words with ordinary literal uses in a game world (a merchant's ledger, a tapestry
    on a wall, navigating a river), the echo chamber, punctuation collapse, and dialogue with no
    question. Logged only, per the guide's "scrutinize, don't ban."
  - Phrases inside quoted dialogue are a character's own voice and are not flagged. Game windows
    in code blocks are left alone. A setting will skip the rewrite pass for slow local models
    (the dash fix always runs). Vanta chose this strictness (rewrite strong tells only) on
    2026-10-21.
- **Wired (2026-10-23):** the narration format is a Table rule (`pov`, `tense`, `length`), set at session zero or
  any time under Tone and rules. A new campaign starts in close third person, past tense, short.

### What the model CLIs send

Dungeon's prompt should be the only instruction a model gets. Checked by capturing the real
requests (Claude Code 2.1.306, Codex CLI 0.163.0):

- **claude -p:** `--system-prompt-file` replaces Claude Code's prompt; no built-in tools, an
  explicitly empty strict MCP config, no settings sources (so no user or project hooks, plugins
  or permissions), no slash commands or skills, one turn, no session saved, and `--safe-mode` plus
  `--permission-prompts none` when the installed CLI lists them. Environment variables turn off
  CLAUDE.md, auto memory, git instructions and @-file attachments, and a parent Claude Code
  session's own variables are not passed on. Left over, with no switch: a one-line Claude Code
  identity and a short environment note (folder, platform, model, date). `--bare` would remove
  more but ignores the plan login, so it is not used.
- **Codex (ChatGPT login):** before, Dungeon's prompt rode in the transcript under Codex's own
  21,000-character coding-agent prompt, a skills catalog, AGENTS.md files and seven tools. Now
  `model_instructions_file` replaces Codex's prompt, and AGENTS.md from the folder, the
  environment, permissions, apps, collaboration, skills and memories notes, and the extra tools
  are off. Left over: the global `~/.codex/AGENTS.md` if the player has one (always loaded; the
  prompt tells the model to ignore it) and two tools Codex always registers, which can't act in a
  read-only folder.
- **Later:** both CLIs accept a JSON schema for structured output (`--json-schema`,
  `--output-schema`), which the Referee and fact extraction can use.

## Turn loop (proposed, from Mabry Curve)

1. Player writes intent only.
2. **Referee** splits the turn into actions and decides what NPCs do on their own initiative.
   The **director** adds its hidden GM note (scene pressure, a seed to plant, what antagonists
   nearby are doing; see "The director").
3. For each uncertain or opposed action: needs-a-roll, stat, difficulty, opposing actor.
4. **Code** rolls, logs, and applies the band. Life Cards may inject an event.
5. **Narrator** writes the turn from the results; never contradicts a roll.
6. **Code** updates continuity (what the player character knows vs what is true), hidden records,
   character sheets and relationships; off-page characters get rolled beats on a cadence.

### Decide before describing

Decided 2026-10-21 (from the competitive research). Whenever the player looks into something the
record doesn't yet cover (a chest, a room, a body, a stranger's purse, what's behind a door), code
decides and stores what is there before the narrator writes a word about it: rolled from the
place's or NPC's tables, or drawn from the world data. The narrator gets it as a fact and
describes only that. Nothing is decided at the moment the player checks for it, so a trap exists
or doesn't before anyone looks. (Hidden Door's design review names the lack of this as its main
flaw.)

### Turn speed

Decided 2026-10-21 (from the competitive research). A turn can chain the action splitter, the
Referee, the narrator, fact extraction and a contradiction rewrite, so speed is a requirement:

- **Each turn has a time budget,** a setting with a sensible default per model type (local or
  hosted). How long each step took is logged with the turn and shown in the dice log once it
  ships, so slow steps are visible.
- **The narration streams** as it is written.
- **Fact extraction runs after the text is on screen,** not before. Its results land in the record
  before the next turn starts.
- **The contradiction check runs only when it is needed:** when the narration names a record
  entity that is dead, spent, held elsewhere or somewhere else. A clean turn costs no extra call.
- **Obvious actions skip the model.** The keyword Referee handles clear cases (walking, looking,
  plain talk) with no model call.
- **Over budget, the optional steps give way first:** the prose rewrite pass, then the
  contradiction rewrite. Dice and the record are never skipped. A skipped rewrite becomes a
  flagged passage (below), so it is offered to the player rather than lost.

### Flagged passages and Rewrite

Decided 2026-10-22 (Vanta's idea). Automatic rewrites still run when there is time; the player
picks up whatever they didn't fix.

- **Problems left in the text are highlighted.** When a check finds a record contradiction or a
  strong prose tell it did not rewrite (over budget, or the skip setting is on), that passage gets
  a soft highlight and a **Rewrite** button. Hovering or tapping shows why it was flagged.
- **The reason never leaks hidden truth.** If the clash is with something the character knows
  ("Brother Aldous is dead"), the reason says so. If it is with hidden truth, it says only that the
  passage conflicts with the story so far; the full reason is in the GM view.
- **Any passage can be rewritten on request,** flagged or not: the player selects text and picks
  Rewrite, with an optional note ("less purple", "she wouldn't say that").
- **A rewrite changes wording only.** It keeps the same dice, bands and record facts, so it never
  rerolls; going back to an earlier turn is still the way to get new dice. The rewritten passage
  goes through the same checks, and the fact extractor reruns on it. The original is kept, so
  the player can switch back.

### Suggested actions

Decided 2026-10-26 (Vanta approved the spec from the competitive research). An **Ideas** button
beside Send gives two or three short things the character could do now, as chips over the
composer. Tapping one puts it in the composer for editing; nothing is sent until the player sends.

- **Used once, kept out of every model's history** (Vanta's rule). Ideas are never stored: not in
  the story, the timeline, the record, the journal, receipts, the dice log, exports or browser
  storage. No other prompt can see them, and each Ideas call is built fresh from the scene, never
  from an earlier list. An idea the player sends is their own line from then on; the rest go
  nowhere. The only copy is the model-call log in Settings > Developer when the player has turned
  it on (off by default), which no model reads.
- **Only what the character knows.** The prompt holds the scene as the screen shows it, what the
  record says the character knows, the quests and threads they have come across, who they are and
  the last few lines; never hidden truth, the director's note, off-page beats or secrets.
- **Actions, not outcomes:** first person, under twenty words, no results, rolls or odds, within
  the player's intensity levels and veils. The Referee's model writes them, else the story's;
  with no model, code offers some from the scene.
- The ideas go when the player sends a line, goes back or the story moves on. Showing them on
  their own after a minute idle was left out for now (the spec's default was off).

### Lore timers

Decided 2026-10-26 (same spec). A lore entry can **linger** for some lines after it comes up,
**rest** for some lines after that, **wait** until a given line, come up on a **chance**, or be
**one of a group** (only one entry of a group goes in at a time, picked by weight), as
SillyTavern's world info does. Lines are counted in the player's lines, kept with the timeline
(going back rewinds them) and the chance roll is seeded, so a retry gives the same lore.
SillyTavern imports bring their timing; the Lore screen sets it per entry. Always-on entries
take no timing.

### Rule passages

Decided 2026-10-26 (same spec). Each turn the narrator gets the few lines of rule text that fit
what the turn resolved: the Ironsworn move rolled and the text of the outcome it landed on, the
5E skill or spell used and any condition the fight names, a Percentile spell. They go in a
`## Rules that apply` layer between the scene and the outcomes, which says the results are fixed.
They are picked by the name the roll resolved, else by a toolbox section or condition the
player's line names; at most three passages and 250 words (one and 100 for a small model). Prospero,
Fate and Narrative Only have no rule text and get none. "Give the narrator rule text" under Tone
and rules turns it off.

## Referee model

- Its own model slot. A cheap text model (Haiku or local 3–4B) splits actions.
- **Referee decisions** (decided 2026-10-22, Vanta: "allow both") is a second slot for a decision model, which
  answers per-action questions with probabilities: needs a roll (yes/no), which stat (choice of six), difficulty
  (score over Prospero's five steps, easy to extreme). It takes a decisions profile (**Jev** via OpenRouter, OpenAI
  Decisions, or a local/compatible model) or any text profile on a local or compatible server, including the
  narrator's own. Local models are scored by the odds of each answer's letter from one token's log probabilities,
  so they write nothing. Without a Referee profile, each sentence of the turn is an action. Close stat calls can
  later be resolved by rule (higher stat, ask, or roll both).
- Fallbacks: the Referee text model's own answer; with no model, keyword rules.
- Note: turn text sent to hosted services is subject to their content policies.

## Open questions

- None. Ruleset licenses were checked 2026-10-21 (see "Candidate systems and licenses").

