# Life Cards in Dungeon

Life Cards are the random events a world throws at the player: what happens on a day in town, a stretch of
road, a night outside safety, and in the lives of characters the player isn't with. They grow out of
Companion's Life deck (`Program/dungeon/life/deck.py`, seeded weighted cards gated by a drama level) and
Prospero's Study's d100 tables. Code draws them with the same seeded dice (`dungeon/life/chance.py`); no
model decides what happens.

This page is the schema. The engine is `Program/dungeon/life/cards.py`; each world's deck is
`Program/dungeon/life/decks/<world>.json` until world packages (Milestone 5) carry it in the world's
database. `Program/dungeon/happenings.py` draws them into town days, journeys and rests (Program/docs/story.md
"Life Cards"); off-page beats come with that system.

## What feeds what

| Requirement | How the cards serve it |
|---|---|
| Tone dial: drama | Each scene's `chance` rises with the drama level, and each card has a lowest `drama` it turns up at. Drama never touches roll odds. |
| Intensity sliders | A card lists the level each category must reach for it to happen. Below that, it is not drawn at all. |
| Veils | A card lists its veil `topics`. A veiled card still happens; the draw is flagged `veiled` and the narrator fades it to black. |
| Off-page beats | `beat` cards happen to `{them}`, an absent connected character, and can wound, capture, turn or kill them. |
| NPC minds | `feeling` effects move the trust, affection, respect, fear and desire axes; `rumor` effects feed "word gets around", true or false. |
| Hidden truth | `truth` is the fact the record keeps; `seen` is what reaches the character; `accuracy` says whether the journal entry is right, half right or wrong. |
| Markets, travel, injuries | `market`, `fight`, `wound`, `supply`, `time` and `pursuer` effects are applied by the Milestone 2 systems. |

## Scenes and drama

A card belongs to one or more scenes:

- **town**: a day in a settlement.
- **road**: a leg of a journey. Region danger tables (Milestone 2) sit beside these.
- **rest**: a rest outside a safe place, before precautions and region danger adjust the odds.
- **beat**: an off-page beat for one absent connected character.

Drama levels are 0 quiet, 1 uneasy, 2 eventful, 3 merciless. A deck's `chance` gives, per scene, the odds in
percent that a scene draws anything at each level. Then the pool is every card for that scene whose `drama`
is at or below the level, whose `needs` are met, whose `where` includes the region (or is empty), that
wasn't drawn in the last `repeat_days`, and that the intensity settings allow. One card is picked by weight.

Raising the drama or intensity only ever adds cards. At the lowest settings every scene still holds good
and bad cards, so turning everything down makes the world gentler, never safe. The tests check both.

## Intensity and veils

Categories: violence, sex, horror, cruelty, drugs. Levels: 0 Off, 1 Restrained, 2 Mature, 3 Unflinching,
so the presets set every category to 1, 2 or 3. A card's `intensity` is a map such as
`{"violence": 2, "cruelty": 2}`: it is drawn only when violence and cruelty are both at Mature or higher. A
category the settings leave out counts as Unflinching.

Veil topics: execution, slavery, mutilation, disease, self-harm, addiction, torture, sexual-violence,
sacrifice, child-harm.

## A card

```json
{
 "id": "beat-taken",
 "title": "Taken",
 "scenes": ["beat"],
 "tone": "bad",
 "drama": 2,
 "weight": 5,
 "intensity": {"cruelty": 2},
 "topics": ["slavery"],
 "truth": "{them} was taken by slavers and sold south.",
 "seen": "Nobody has seen {them} in a week. Their door was found standing open.",
 "accuracy": "partial",
 "effects": [{"kind": "fate", "who": "them", "state": "captured"}]
}
```

| Field | Meaning |
|---|---|
| `id`, `title` | Unique within the deck. The title may use placeholders. |
| `scenes` | Any of town, road, rest, beat. |
| `tone` | good, bad or grey. Grey is a moral weight more than a loss. |
| `drama` | Lowest drama level it can turn up at (default 0). |
| `weight` | How often it comes up next to the others; 10 is usual. |
| `needs` | What must be true: `bond` (a bonded character, `{bond}`), `party`, `debt`, `wanted`, `injured`, `caster` (the character uses Ley magic), `captive` (the beat's character is captured). |
| `where` | Regions it belongs to; empty means anywhere. Vallarith: cyrel, badlands, asania, trein, gulf, dwarfholds, brynwyr, kujuur, fjallagracht, etryona, wrenspire. |
| `intensity`, `topics` | See above. |
| `truth` | What actually happened, in the third person. The record keeps it as hidden fact. |
| `seen` | What the character sees or hears, in the second person. For a beat, how the news reaches them. |
| `accuracy` | true, partial or false: how far `seen` matches `truth`. Partial and false create a wrong-footing record. |
| `pressure` | Optional: the choice the moment puts to the player. The narrator offers it; code never answers it. |
| `effects` | What code applies (below). |

Placeholders: `{pc}` the player character, `{npc}` someone code picks from the scene or town, `{bond}` a
bonded character (needs `bond`), `{them}` the beat's character (beat cards only, and every beat card names
them), `{faction}` a faction code picks, `{town}` the settlement.

## Effects

| Kind | Fields | Applied by |
|---|---|---|
| `market` | `goods` (food, drink, medicine, ley, arms, cloth, lodging, any), `shift` in percent, `days` | Shops and economy |
| `stress` | `amount` | Injuries and recovery (stress track) |
| `wound` | `level` (Grazed, Hurt, Wounded, Maimed, Dying), to the player character | Injuries and recovery |
| `feeling` | `who` (npc, bond, them), `axis` (trust, affection, respect, fear, desire), `shift` | NPC minds |
| `fate` | `who`, `state` (wounded, sick, captured, dead, turned, missing, indebted, wanted, freed, addicted, conscripted) | Off-page beats |
| `coin` | `wages`: gained or lost, in an unskilled worker's daily wage in local currency | Shops and economy |
| `supply` | `shift` | Inventory, Ironsworn Supply |
| `rumor` | `about` (pc, npc, bond, them, faction, place), `true` | NPC minds: word gets around |
| `clock` | `shift` on the `{faction}`'s clock | Quests and factions |
| `reputation` | `shift` with the `{faction}` | Progression |
| `quest` | `from` (npc, bond, them, faction), `days` to its deadline | Quests and factions |
| `fight` | `foes` (bandits, deserters, gnolls, orcs, beasts, undead, corsairs, hunters, fiend, cultists, watch, fey), at the region's tier | Combat |
| `pursuer` | `days` behind the player character | Time and travel |
| `corruption` | `shift` | Progression (dark tracks) |
| `time` | `hours` (negative saves time) | Time and travel |

## Tables

A deck can also carry d100 tables in Study's shape: a top table names its scene, each row covers a
`low`–`high` range of the table's `die`, and a row with a `child` rolls on that table next. Event rows use
the same fields as a card. Their rows join the scene's pool as cards, weighted by their share of the roll so
the whole table takes `tables_weight` next to the deck. Vallarith's road table rolls Travellers, Hazards,
Signs, Threats or Finds (Study's Encounter, Obstacle, Foreshadowing, Direct Challenge and Opportunity), and
its town Hooks table adapts Study's Hooks. Companion's everyday tables left those out.

## Art

Every card, table rows included, has a picture in its world's backdrop style, plus one card back per world:
`world/packages/<world>/assets/cards/<id>.webp` (512x768), made with the OpenAI Images API by
`Program/scripts/art/cards.py` (key in `CHATGPT_API_KEY`; it only makes what is missing). The story shows the
cards drawn on a line under it, with the picture, title and tone and never the truth
(`happenings.with_cards`); a card on a veiled topic shows only the card back, and so does a card the image
model refused to draw.

## Checking a deck

`cards.problems(deck)` lists everything wrong with a deck: unknown fields or vocabulary, placeholders a card
can't fill, a `{bond}` without the need, gaps or overlaps in a table's ranges, missing child tables, and
duplicate ids. `Program/tests/test_life_cards.py` runs it on every shipped deck, runs the narrator's prose
checks over every line of card text, and checks the filters.

## Decks

- **Vallarith** (`vallarith.json`): grimdark, built from the Vallarith lorebook, Ley notes, deities and
  timeline. 103 cards and 70 table rows across all four scenes.
- **Havenbrooke**: Companion's everyday Life deck (`world/data/life_deck.json` and `random_tables.json`)
  stays as its base (Vanta, 2026-10-21), to be converted to this schema and darkened in a Havenbrooke pass.
