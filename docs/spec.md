# Prospero's Adventure: product spec

*Started 2026-11-02 in the "Spec out Prospero's Adventure" thread. A living document: **Decided** items are
settled by Vanta, **Proposed** items are open to change, and **Open questions** are still being asked.*

## Vision

A local-first AI tabletop RPG where **every party member can think for themselves**. It keeps Prospero's
Dungeon's game underneath (stats, XP, HP, mana, inventory, dice, the record), but each character the user picks
gets their own agent: a model with its own private view of the world that decides what that character wants to do
each round. Sometimes they go along with the user, sometimes they push back, scheme or betray. A narrator agent
gathers everyone's moves and writes the round.

The user chooses how to take part:

- **Play a character** in the party, like Dungeon.
- **Author**: give general guidance about what should happen, without controlling any one character. (Called
  "Director" in the starting brief; renamed so it doesn't clash with Dungeon's code director, which keeps its name.)
- **Watch**: push the turns and let everyone act on their own.

## Starting brief (Vanta, 2026-11-02)

1. The base of Dungeon: it tracks stats, XP, HP, mana, inventory and the rest.
2. Each party member can get their own agent, which gives input on what they want to do next as turns progress.
   They are sometimes aligned with the user, sometimes against them.
3. The user designates which characters get the agent approach and which get the "Program" approach (code-driven,
   like the world sim running in the background).
4. The user plays a character, or is a Director giving general guidance, or uses Watch mode to push turns.
5. Companion's sliders for drama, realism and the rest.
6. A narrative agent compiles all input from characters (agents or players) into the narrative post for each round.
7. Hidden truths and lies, with memory per character.
8. Uses the memory system from Companion and Dungeon.
9. Plays worlds built by Worldsmith.

## What it builds on

| Source | What Adventure takes |
| --- | --- |
| Prospero's Dungeon | The game: rulesets (Prospero, 5E SRD, Ironsworn, Percentile), sheets, combat, inventory, injuries, progression, the record (world truth vs character belief), branching timelines, the code director (arcs, threads, seeds), Life Cards and drama, intensity and tone, lies (`lies.py`), feelings, party and allies (`party.py`, `allies.py`), world packages |
| Prospero's Companion | The memory system (typed memories, recall, the Memories page), group chat's per-person private context (secrets, "others see / I see myself" perception lines, who knows what), moods, and the Settings > Realism sliders and presets |
| Prospero's Worldsmith | Worlds: Adventure loads the same `.sqlite` world packages Worldsmith installs into Dungeon |
| Prospero's Study | Indirectly, through Dungeon: the randomness engine and branching |

### What is genuinely new

Dungeon's rule is "the program makes the decisions; the language model narrates them," and its party members are
code: they decide whether to join by their feelings, and in a fight they take no orders and go for the foe worst
hurt (`allies.py`). Adventure's core is the opposite for the characters you choose: **a model decides what a
character wants**, from inside that character's own knowledge, and code still rolls whether it works.

## Standalone app or a Dungeon mode

**Decided (2026-11-02): a standalone app**, started as a clean copy of Dungeon (the same way Dungeon started from Companion),
sharing Dungeon's world package format so Worldsmith worlds load unchanged.

Why not a mode:

- **The turn loop is different.** Dungeon's turn starts from one player's intent. Adventure's starts from several
  minds deliberating, possibly with no player at all. Folding that in means a second turn pipeline inside Dungeon.
- **The cost and speed budget is different.** Dungeon is built to keep a turn to a few cheap calls. A round with
  four agents plus a narrator is five or more calls; Adventure needs its own budget, model slots and caching.
- **Dungeon assumes "the player character" everywhere** (journal, sheet, the record's "character belief"). Director
  and Watch modes have no single protagonist, and every agent needs its own belief layer.
- **It keeps Dungeon simple** while Dungeon is still finishing its own roadmap.

The cost: fixes to shared systems (rulesets, the record, world loading) have to be carried across. That can be
handled the way Worldsmith already does it, by vendoring Dungeon code with a sync script and a CI check, or later by
pulling shared code into a common package.

Proposed defaults, to confirm: app port **8805** (dev interface 5197), data folder `ProsperoAdventure`, environment
prefix `ADVENTURE_`.

## Decided

Batch 1, decided 2026-11-02 (Vanta's cards):

- **Standalone app, forked from Dungeon.** A clean copy of Dungeon with its own turn loop, port and data folder,
  keeping Dungeon's world package format so Worldsmith worlds load unchanged.
- **An agent gives back intent, spoken lines and a hidden motive each round.** The intent is what the character
  tries to do; the lines are what they say aloud, in their own voice; the hidden motive is a private thought that
  goes into that character's memory and is never shown to other characters. It is what powers lies, scheming and
  betrayal.
- **A round is "declare at once, then one reaction."** All agents (and the user, when playing) declare in parallel
  without seeing each other's moves. Then each agent sees what the others declared and may react once: step in,
  object, change course, or let it stand. Then code resolves.
- **Dice decide risky acts only.** Plain talk and small choices are settled among the characters without rolls.
  Anything opposed, dangerous or uncertain goes to the Referee and code rolls it, as in Dungeon, and the narrator
  never contradicts a roll. Agents never decide their own success.
- **Agents: party members plus key NPCs, up to 6 at once.** Rivals, villains and other key NPCs in the scene can be
  agents too. The user sets the per-scene cap (default and maximum 6); everyone else runs on Dungeon's code minds
  (the "Program" approach).
- **The narrator (the "Writer") can question agents within a round** (Vanta, 2026-11-02). While composing the round,
  the Writer can send follow-up questions and lines to agents ("Mara asks Hesk where he was last night: what does he
  say?"), and their answers come back in the same round. A conversation can run for several exchanges inside one
  turn instead of costing a full round per line. Each answer is still limited to what that character knows, and
  anything risky it leads to still goes to the dice.
- **The play modes are Play, Author and Watch.** The code GM that steers arcs keeps Dungeon's name, the director.

Batch 2, agent minds, decided 2026-11-02 (Vanta's cards):

- **Siding with or against the user comes from feelings plus the character's own goals.** Each agent reads its
  Dungeon feelings tracks (trust, affection, respect, fear, desire) toward every other character, weighed against its
  own wants, fears and secrets. Code moves the tracks from events and rolls, so a turn against the user is earned
  and stays consistent from round to round.
- **An agent can do anything when it turns, but signs come first.** Lying, stealing, deserting, attacking and killing
  are all possible, within the intensity settings. Before a major betrayal, the director plants warning signs on the
  page (its seeds), so a betrayal is fair in hindsight.
- **An agent knows its own knowledge plus the world's public canon.** Its sheet, its memories, what it saw and heard,
  what it believes (lies included), and the world's public lore as common knowledge. Never a hidden truth it hasn't
  learned.
- **Agents can talk privately to each other.** Whispers and plots between characters are hidden from the user's
  character and from anyone not party to them, but readable in the GM view.
- **Personality is the world's cast sheet plus the user's notes.** The world package's sheet (voice, wants, fears,
  relationships, stats, Companion's "others see / I see myself" perception lines) is the base; the user can add
  short notes per character to nudge them.
- **In-turn conversations have a user-set cap.** A setting from 1 to 12 exchanges per turn, default 4, so the user
  trades depth against cost and wait.
- **When an agent speaks to the user's character mid-turn, the Writer pauses and asks.** The turn waits for a quick
  reply from the user, then carries on in the same turn. The Writer never answers for the user's character beyond
  what they declared.
- **Showing hidden motives depends on the mode.** Hidden in Play, so betrayals can surprise the user. Shown by
  default in Author and Watch, where the user is the audience. The GM view shows everything in any mode.

Batch 3, secrets, memory, Author and Watch, decided 2026-11-02 (Vanta's cards):

- **Lies between agents are rolled, as in Dungeon.** The listener's insight is rolled against the liar's deception
  (Dungeon's `lies.py`). A believed lie goes into the listener's memory as belief, not truth; a caught one shows its
  tell on the page and in the listener's memory. The listening agent never judges a lie by itself, so it can't be
  suspicious of a lie it failed to catch.
- **Each character has Companion's memory, with Dungeon's fading.** Typed memories per character with Companion's
  recall and Memories page, filtered to what that character witnessed or was told. Detail fades with importance and
  age, while betrayals, deaths, debts and strong feelings stay sharp. The record stays the source of truth.
- **Program characters run on Dungeon's code minds as they are.** Feelings, party rules, allies' tactics and life
  schedules decide what they do, and the Writer voices them. No extra model calls. The user can promote anyone to
  an agent by hand.
- **The Author gives nudges and edits story beats.** Free-text guidance each turn goes to the Writer and director as a
  hidden note, and the Author can add, cut and reorder upcoming beats on the director's plan. Characters still
  choose for themselves; to drive one directly, switch to Play.
- **Watch autoplays and pauses on big moments.** Turns play on a timer the user sets, pausing at deaths, betrayals,
  chapter ends and other big moments, with a Next button for stepping by hand.
- **Modes can be switched any time.** On any turn. When the user leaves Play, their character becomes an agent or a
  Program character, their pick.

Batch 4, the Writer, sliders, models, campaigns and the screen, decided 2026-11-02 (Vanta's cards):

- **The Writer's point of view has a default per mode, and stays a setting.** Close on the user's character in Play,
  so other characters' scheming stays offstage; roving across the cast in Author and Watch. Length, POV and tense
  remain a player setting, as in Dungeon.
- **Sliders: a Companion-style Realism panel plus agent dials.** Companion's Realism presets and drama slider (from
  realistic to soap opera), Dungeon's intensity per category, veils and voice, and new agent dials: how much the
  agents scheme, and how fast loyalty shifts. As in Dungeon, no slider ever changes roll odds.
- **Models are assigned per role, with a per-character override.** Slots for the Writer, agents, the Referee (and
  Referee decisions) and fact extraction, like Dungeon's model per job. Any character can be given its own model,
  so a villain can run on a strong hosted model while minor agents use a cheap or local one.
- **Cost is held by a turn budget plus a session cap.** Dungeon's per-turn time and token budget, where optional steps
  give way first, plus a spend cap per session that pauses Watch when it is reached.
- **Branching is Dungeon's, plus re-asking an agent.** Every turn is saved, branches bring new dice, bookmarks and
  Ironman work as in Dungeon. New: rewind one agent's choice so that character decides again, on a new branch.
- **The play screen is Dungeon's widget layout plus a minds panel.** The minds panel shows each character's declared
  move every turn and, where the mode allows, their hidden motive and whispers (hidden in Play, shown in Author and
  Watch, everything in the GM view).
- **One human per campaign for now.** The turn loop treats a human seat as one more character that declares each
  round, so hotseat or online play can be added later without redesigning it.

## Open questions

*None open. 27 questions answered across four batches; the two topics below are still to cover.*

## The turn loop

Put together from the decisions above. Steps marked *(Dungeon)* are carried over unchanged.

1. **Setup.** Code gathers the scene: who is present, which of them are agents (up to the cap), which are Program
   characters, and the user's seat (a character in Play, none in Author and Watch). In Author, the user's nudge for
   the turn is taken here.
2. **The director's note** *(Dungeon)*. The director adds its hidden GM note: scene pressure, a seed to plant, what
   antagonists are doing, and any warning signs owed before a betrayal. The Author's nudge and beat edits join it.
3. **Declare.** In parallel, each agent gets its own context (sheet, user notes, its memories, its beliefs, public
   canon, what it has seen this scene, its feelings toward everyone present) and returns intent, spoken lines and a
   hidden motive. Program characters' moves come from code *(Dungeon)*. The user, when playing, declares too.
4. **React.** Each agent sees the others' declared intents and lines (never their motives) and may react once.
   Private whispers between agents are exchanged here.
5. **Converse.** The Writer may put follow-up questions to agents and take their answers, up to the user's cap. If
   anyone addresses the user's character, the turn pauses for the user's reply.
6. **Resolve** *(Dungeon)*. Plain talk and small choices stand as declared. The Referee splits out anything opposed,
   dangerous or uncertain; code rolls it, applies the bands, and rolls lies against insight. Life Cards may inject
   an event.
7. **Write.** The Writer turns the results into the turn's post, from the mode's point of view, never contradicting
   a roll or the record.
8. **Remember** *(Dungeon, per character)*. Fact extraction updates the record. Each character's memory gets what
   they witnessed, said, were told and now believe; motives and whispers go to the speaker's memory only. Feelings
   move. The turn is saved as a branch point.
9. **Pace.** In Watch, the next turn starts on the timer unless this turn hit a big moment or the session cap.

## Later batches (planned)

- Worlds: anything Adventure needs from Worldsmith beyond today's package (for example, marking which cast members
  default to agents).
- First milestone: the smallest playable slice to build first.
