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
  learned. (Since the 2026-11-02 review, "public" means lore not marked secret: see "Who sees what".)
- **Agents can talk privately to each other.** Whispers and plots between characters are hidden from the user's
  character and from anyone not party to them, but readable in the GM view.
- **Personality is the world's cast sheet plus the user's notes.** The world package's sheet (voice, wants, fears,
  relationships, stats, Companion's "others see / I see myself" perception lines) is the base; the user can add
  short notes per character to nudge them.
- **In-turn conversations have a user-set cap.** A setting from 1 to 12 exchanges per turn, default 4, so the user
  trades depth against cost and wait.
- **When an agent speaks to the user's character mid-turn, the Writer pauses and asks.** The turn waits for a quick
  reply from the user, then carries on in the same turn. The Writer never answers for the user's character unless
  the user picks "Let my character answer" on the reply card (added 2026-11-02, see "Waiting and pauses").
- **Showing hidden motives depends on the mode.** Hidden in Play, so betrayals can surprise the user. Shown by
  default in Author and Watch, where the user is the audience. The GM view shows everything in any mode, behind a
  warning in Play (added 2026-11-02, see "Waiting and pauses").

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

Review follow-ups, decided 2026-11-02 (Vanta's cards, after the concurrency, prompts and UX reviews):

- **In Converse, the asking character's own agent writes the question;** the Writer only picks who asks whom.
- **Untagged world lore counts as public.** Hidden truths and cast secrets count as marked; anything else secret must
  be marked by the world's author.
- **Re-asking an agent keeps everyone else's declarations** and redoes reactions, conversation, dice and the write-up
  for everyone.
- **The reply card offers Reply, Say nothing, or Let my character answer** (an explicit, one-line opt-in).
- **Opening the GM view in Play asks first** and marks the turns where it was open.
- **Switching out of Play asks once whether to reveal missed motives,** defaulting to hidden.

Isekai Pipeline PRD follow-ups, decided 2026-11-02 (Vanta's cards; see "Writing rules, checks and corrections"):

- **Roll overrides are allowed from the GM view in any mode,** logged and marked on the turn, and off in Ironman.
- **Writer inventions are kept unless the user strikes them.**
- **A separate Reviewer pass is on by default in Rich** and a toggle elsewhere; the code scan always runs.
- **In Play, the turn post can add beats beyond the user's own character, as nudges.**
- **Offscreen agents: code rolls the outcome, the character's agent writes their lines.**

Dungeon systems follow-ups, decided 2026-11-02 (Vanta's cards, after comparing Dungeon's plan with this one; see "Dungeon systems in agent play"):

- **Factions feed agents' goals, and a nemesis becomes an agent automatically,** counting toward the cap.
- **When the party disagrees on where to go, a lead proposes and anyone can split off.** You lead in Play; the party's leader leads in Author and Watch. A character who splits off runs as an off-page thread until they rejoin.
- **Lore timers and off-page beats count rounds, in every mode,** instead of the player's lines.
- **The Ideas button stays, in Play and Author.** Play suggests moves for your character; Author suggests nudges. Watch has none.
- **A book export asks whether to include hidden motives and whispers,** with a switch on the export screen.

The rest of the reviews' findings were engineering and design fixes that don't change what Vanta decided. They are
folded into "The turn loop", "Agent output", "Who sees what", "Turn state and persistence" and "Waiting and pauses".

## Open questions

*None open. 27 questions answered across four batches, plus 6 review follow-ups, 5 PRD follow-ups and 5 Dungeon systems follow-ups; the two topics under "Later batches" are still to cover.*

## The turn loop

Put together from the decisions above and revised after the 2026-11-02 reviews (concurrency and state, prompts and
leaks, UX). Steps marked *(Dungeon)* are carried over unchanged. The state each step runs in is in brackets; see
"Turn state and persistence".

1. **Gather** `[Gathering]`. Code takes one frozen **snapshot** of the scene: who is present, the record, every
   character's committed memory and feelings, and the settings in force. Every context this turn is built from that
   snapshot, and it is stored with the turn so a re-ask reads exactly what the original read. Code picks the agents
   (up to the cap: party first, then nemeses and characters promoted by hand, then by role in the scene, ties by seat order);
   the rest are Program characters. The user's seat is a character in Play and none in Author and Watch. In Author,
   the nudge for the turn is taken here.
2. **The director's note** *(Dungeon)*. The director adds its hidden GM note: scene pressure, a seed to plant, what
   antagonists are doing. Warning signs owed before a betrayal go in as **the sign itself** ("Hesk's purse is heavier
   than it should be"), never the secret behind it. The Author's nudge and beat edits join it.
3. **Declare** `[Declaring]`. In parallel, each agent gets its own context (see "Who sees what") and returns its
   structured output (see "Agent output"). Program characters' moves come from code *(Dungeon)*. The user, when
   playing, declares too. Results are merged in seat order, not in the order they arrive.
4. **Lies are rolled when heard.** Before anyone reacts, code rolls insight against deception for every declared
   deception, for each listener it is aimed at or overheard by. Each listener's in-turn knowledge gets the line as a
   belief or as a caught tell. The same happens for any lie told later in the turn.
5. **React** `[Reacting]`. Each agent sees the others' declared intents and lines (never their motives), filtered by
   what it could see and hear, with lie outcomes applied, and may react once. Private whispers between agents are
   exchanged here, delivered by code only to their audience.
6. **Converse** `[Conversing ⇄ AwaitingUser]`. The Writer may set up follow-up exchanges between characters, up to the
   user's cap. The Writer only picks who asks whom; the **asking character's own agent writes the question**, from its
   own knowledge, so the Writer can't slip a secret into it. Each answer is added to the in-turn
   knowledge of the characters who heard it. If anyone addresses the user's character, the turn waits for the user
   on the reply card (see "Waiting and pauses").
7. **Resolve** `[Resolving]` *(Dungeon)*. Code first classifies intents into risky kinds where it can (attack, steal,
   deceive, persuade or threaten against someone's interest); the Referee rules on the rest, seeing the bare intent,
   not the speaker's pitch. Anything opposed, dangerous or uncertain is rolled by code. Life Cards may inject an
   event. The output is an immutable **turn result**: intents, rolls, outcomes, who saw and heard what, and the brief
   with its stop point (see "The turn brief and the stop point").
8. **Write** `[Writing]`. The Writer renders the turn result into the turn's post, from the mode's point of view,
   streamed as it is written, never contradicting a roll or the record. What the Writer may see depends on the mode
   (see "Who sees what"). Code then scans the draft, and any Reviewer pass runs; a hard failure is rewritten before
   commit (see "The draft scan and the Reviewer").
9. **Commit** `[Committing]`. In one SQLite transaction, code writes the record from the turn result, folds each
   character's in-turn knowledge into their memory, moves feelings, and saves the branch point. Code, not a model,
   routes every memory by visibility: who was present, who a whisper was for, whose motive it is. Fact extraction
   only adds colour from the prose (descriptions, named objects) and never overrides an outcome or decides who
   learns what. Off-page threads that ran alongside Write are committed in the same transaction. Then the turn is marked committed and
   the turn report is written.
10. **Pace** `[Idle]`. Queued mode, cap and model changes take effect now. In Watch, the next turn starts on the timer
    unless this turn hit a big moment or the session cap.

## Agent output

Each agent returns a structured object that code validates:

- **intent:** what the character *attempts*, never a result. An intent or line that claims an outcome ("as my blade
  finds his heart") is cut back to the attempt before anyone else sees it.
- **lines:** what they say aloud, and to whom.
- **motive:** their private reason. Goes only to their own memory, the minds panel where the mode allows, and the GM
  view.
- **deceptions:** each lie as a field: what they claim, what they believe is true, and who it is aimed at. Code rolls
  only these. A line with no declared deception is honest as far as the speaker knows.
- **whispers:** private lines and their audience.

Veils and intensity apply to every field, hidden ones included. The agent's prompt says so, and code filters motives,
whispers and memories the same way it filters the post.

## Who sees what

Privacy is enforced by building context, not by asking a model to keep quiet. **Nothing is ever "in the prompt but
don't mention it."** One context builder per reader decides what goes into each model call:

| Reader | Gets | Never gets |
| --- | --- | --- |
| An agent | Its sheet and user notes, its committed memory plus this turn's in-turn knowledge, its beliefs (lies included), lore tagged public or known to it, what it saw and heard, its feelings | Other characters' motives, whispers not meant for it, GM-only lore, the director's note, truth flags on lies it heard |
| The Writer in Play | Declared intents and lines, the turn result, the director's signs to place | Offstage motives and whispers, hidden truths behind the signs |
| The Writer in Author and Watch | As in Play, plus motives and whispers | Hidden truths nobody in the scene knows |
| The Referee | Bare intents and the scene state | Motives, whispers, speakers' pitches |
| The minds panel | Per mode: "Hesk has decided" in Play; intents, motives and whispers in Author and Watch | |
| The GM view | Everything | |

**World lore carries a visibility tag:** public, known to listed characters, or GM only. **Untagged lore counts as
public.** A world package's hidden truths and its cast's secrets count as marked GM only (or known to the
characters they belong to), so they never reach an agent untagged. Anything else secret has to be marked; see
"Later batches" for Worldsmith's part in catching what wasn't.

**Untrusted text is fenced.** The player's typed action, the Author's nudge, the user's character notes, cast sheets
from world packages (which may come from other people), character names and other agents' lines all arrive in
labelled blocks the prompt treats as in-fiction content, never as instructions.

Each context builder has tests that seed a sentinel motive, whisper and GM-only fact and assert they never appear in
any other reader's context.

## Turn state and persistence

- **One state machine.** A turn moves `Idle → Gathering → Declaring → Reacting → Conversing ⇄ AwaitingUser →
  Resolving → Writing → Committing → Idle`. `AwaitingUser` is keyed by seat, not "the user", so hotseat and online
  play fit later without a schema change.
- **One command queue.** Every input (the Watch timer, Next, a reply, a mode switch, rewind and re-ask, the session cap,
  settings changes, a second browser tab) is a command on one serialized queue, carrying the turn id it was issued
  against. A command whose turn is no longer the head is dropped. Mode switches and cap and model changes are
  accepted at any time and take effect at the next `Idle`, so "switch any time" means the current turn finishes in
  the mode it started in. Cancelling a turn is the one command that acts at once: it discards the draft.
- **A turn is a transaction.** Steps 1 to 8 build a **turn draft** nothing else reads; step 9 commits it in one
  transaction. On restart, a draft paused in `AwaitingUser` resumes from its checkpoint, and any other open draft is
  discarded and the turn re-run from its snapshot.
- **Memory follows branches.** Every per-turn write (memories, beliefs, feelings, whispers, motives) is keyed by the
  turn that made it and read through the branch's ancestry, like Dungeon's record. Fading is a read-time function of
  age and importance, never an in-place rewrite of shared rows.
- **Re-asking an agent.** Everyone else keeps their declaration (step 3); that character's declaration is replaced,
  and steps 4 onward are redone for everyone, since they responded to the old choice. It reads the stored snapshot
  and brings new dice, per the branch rule.
- **World packages are imported, not shared.** Adventure copies a package into its own data folder with a version
  stamp, so it never opens a file Dungeon or Worldsmith may be writing. Campaign state lives in Adventure's own
  database.
- **Budgets hold across parallel calls.** Each call reserves its estimated cost before it starts and settles after,
  under one lock. The session cap applies in every mode and stops play only at `Idle`: a turn that has started
  finishes, using only its required steps.
- **Failures fall back, never leave a hole.** Each call has a deadline inside the turn budget and one retry (with the
  parse error, for broken output). After that, or on a refusal, the character runs on its Program mind for the turn,
  and the minds panel marks it. Deadlines account for local models that serialize calls.

## Waiting and pauses

A round can take 20 or more model calls, so waiting is designed, not left blank. How these look and read follows
`docs/style-guide.md`.

- **The round timeline.** Above the minds panel: Declare · React · Converse · Resolve · Write, with the current step
  lit. Each character's row moves through thinking, declared, reacting, done. In Play a row says only "Hesk has
  decided"; in Author and Watch, intents appear as they arrive. The Writer's post streams.
- **The reply card.** When a character addresses the user's character: who is speaking, their line in full, the last
  two lines of context, and a text box, plus **Say nothing** and **Let my character answer**. The second is an
  explicit opt-in for that one line: the Writer answers in character from the user's declared intent, so nothing
  speaks for the user uninvited. If the tab is not in
  focus, a sound or title badge; the minds panel shows "Mara is waiting for your answer".
- **Every pause says why and what next.** One banner: "Paused: Hesk betrayed the party. [Continue] [Switch to
  Author]", or "Paused: this session reached its $2.00 cap. [Raise cap] [Stop here]". A dropped optional step and a
  fallback to a Program mind are noted too.
- **Agent or Program is visible.** A small accent dot, with an accessible name, on the portrait of each character who
  thinks for themself, in the cast list and on the Cast page; never in the story text (see `docs/style-guide.md`).
- **Author nudges get feedback.** After the turn, a line under the nudge box: "Used: the director moved the storm
  forward" or "Not yet: no character chose to go north." The beat board shows which beats have landed.
- **The GM view asks first in Play.** Opening it during Play shows a warning ("This shows every secret and motive.
  Open anyway?") with a remember-for-this-campaign option, and the turns where it was open are marked, so the user
  knows which surprises they spoiled. No gate in Author or Watch.
- **Switching out of Play doesn't spoil the past.** On a switch to Author or Watch, the user is asked once whether to
  see the motives they missed, defaulting to hidden. Turns played in Play keep Play's visibility unless they choose
  otherwise; new turns show motives as Author and Watch normally do.
- **Lies read as story.** Beliefs use belief language on sheets and in memories ("Ilsa *believes* the bridge is
  guarded"). An uncovered lie gets a short moment in the prose and a strike-through in memory; a caught tell gets the
  same treatment.
- **Settings have three paces.** Quick, Balanced and Rich set the agent cap, conversation cap and models together,
  each showing its time and call count per turn as data ("~25 s · 14 calls"). Everything else is under Advanced, with
  labels and values and no explanatory sentences (see `docs/style-guide.md`, SE-2 to SE-5).
- **Behind-the-scenes names stay behind the scenes.** The play screen names only the Writer. The director, Referee
  and GM view are named in settings and the GM view.
- **Accessibility.** A polite live region announces status changes in summary ("3 of 5 characters have decided"),
  every control is keyboard reachable, and the timeline respects reduced motion.
- **Branches read as questions.** A re-ask branch is labelled "What if Hesk had stayed?" with the character's
  portrait.

## Writing rules, checks and corrections

Added 2026-11-02 after checking the spec against Vanta's "Isekai Pipeline" PRD (a turn-based collaborative fiction
workflow with a Director, a Writer, a Reviewer and dice). That PRD's Director maps to the user in Play; its Writer
maps to Adventure's Writer plus code. Coverage, epic by epic, is in the table at the end of this section.

### House rules and rulings

- **House rules are campaign data, not prompt folklore.** Each campaign holds a house rulebook: POV and tense, content
  scope (the intensity settings), dialogue rules, how thoughts are formatted, the **System pane** format, and lists
  of forbidden punctuation, outlawed words and phrases, and outlawed names (starting from Worldsmith's list of names
  that read as model-made). The world package supplies defaults; the user edits them at the Table. The Writer and
  any Reviewer get them every turn, and the draft scan checks them in code.
- **Rulings are recorded.** A ruling is a standing decision by the user ("Hesk's limp is permanent", "no one in town
  knows the Tower has floors above twelve"). Each is stored with the turn it was made, goes to the Writer, Referee
  and Reviewer as a house rule, and applies from that turn forward. Applying one backward is a correction (below).
  The rulings list is a GM view page, so nothing gets re-argued later.

### The turn brief and the stop point

- **Ambiguity gets one question.** If the user's declared move is ambiguous on something pivotal (who they attack,
  whether they hand over the key), the turn asks one focused question on the reply card before Resolve, instead of
  guessing.
- **Beats beyond the user's own character in Play** (decided 2026-11-02). Besides what their character does, says and
  decides, the user's turn post can add beats they'd like to see (a storm, a stranger arriving). These go to the
  director as nudges, exactly like Author nudges, with the same "Used / Not yet" feedback; other characters still
  choose for themselves.
- **Resolve produces a brief.** The turn result (step 7) carries the brief: when and where the turn happens, the
  user-set beats, each uncertain outcome with its roll, any math the turn needs (damage, XP, costs), and the **stop
  point**.
- **The Writer renders every user-set beat in full** and adds no beat the user's move didn't open: it never compresses
  or skips one for pacing.
- **The stop point is fixed before prose.** In Play the turn ends before the user's character's next real decision,
  never past it. In Author and Watch it ends at the scene's next natural break or the next big moment.

### Numbers, System panes and who can see them

- **Numbers live in panes.** Health, status, quests and loot appear on the page only in the house System pane format,
  generated by code from the record, so every number on the page traces to a stats entry. Ordinary narration carries
  no numbers and never mentions dice.
- **Game knowledge is knowledge too.** Whether a character can see System panes or game numbers is a fact about them
  (a world flag per people or per character: in BABEL, natives don't see them). Agents and the Writer only get the
  numbers their reader is allowed to see, through the same context builders as every other secret.

### Inventions

- **The Writer may invent only where canon is silent,** and every new name or detail is listed in the turn report and
  stored in the record as invented. **Inventions are kept unless the user strikes them** (decided 2026-11-02), so
  Watch never stalls on approvals; striking takes one tap in the turn report.
- Striking an invention rewrites the passage that used it and removes it from the record and from every character's
  in-turn knowledge, before or after commit (after commit, as a correction).

### The draft scan and the Reviewer

- **Code scans every draft.** After Write, code checks the draft against the house rules: forbidden punctuation,
  outlawed phrases and names, scene-closing tells, numbers outside panes, mention of dice, and beats past the stop
  point. **Hard failures** must be fixed; **soft warnings** go in the turn report. It also reports word count and
  a density read.
- **A draft with a hard failure is never committed.** The prose still streams, so the user reads early; a passage
  with a hard failure is rewritten (Dungeon's flagged passages and Rewrite) and re-scanned before step 9 commits.
- **The Reviewer.** A separate model call that has not seen the Writer's working checks the draft against the hard
  dialogue rules (no echoed phrases, no summarised speech, rationed verbal tics, questions present), formatting,
  counting, continuity with earlier chapters, pane arithmetic, character voice and the stop point, and returns a
  prioritised list of quote, problem and concrete fix. The Writer applies each or declines it with a reason, and the
  result is scanned again. **The Reviewer is on by default in the Rich preset** and a toggle in the others
  (decided 2026-11-02). The code scan always runs.
- **The user can flag anything missed** with Dungeon's flagged passages and Rewrite; the fix goes through the same
  scan.

### Rolls, overrides and the turn report

- **Every uncertain beat maps to one roll,** labelled with who acts, what's at stake and the stat applied, and the dice
  log records turn, label, stat, natural result, modifiers and band *(Dungeon)*. No re-roll without a recorded reason
  (re-asking an agent and rewinding are recorded reasons).
- **Overrides** (decided 2026-11-02). From the GM view, in any mode, the user can override a roll's result. The
  override is logged with the turn and the reason, the turn is marked (like a turn where the GM view was open), and
  the affected passage is rewritten; after commit it is a correction. Overrides are off in Ironman.
- **The turn report.** After each turn, a report the user can open (and, in Play, a short recap under the post): what
  the user set, each roll and what it produced in plain words (with the numbers, unless the user set rolls to hidden),
  the numbers that changed, inventions, scan and Reviewer fixes, off-page beats that ran and when the next are due,
  and open questions. Hidden truths and motives appear only where the mode or the GM view allows. It ends with the
  user's next decision pending; nothing is decided for their character.
- **The status line.** Always visible: the turn just played, what's pending, and when the next off-page beats are due.

### Off-page threads

- **Offscreen characters keep living** *(Dungeon's off-page beats and the director's threads)*: a list of active
  offscreen threads, each advanced on its own cadence with its own roll, logged with what happened, how well it went,
  a few lines of actual dialogue, and who was involved. Outcomes are recorded before they surface on the page, and a
  thread can collide with the main scene (arrive, interrupt, catch up) when timing and rolls say so.
- **For offscreen agents, code rolls and the agent writes the lines** (decided 2026-11-02). Code rolls the thread's
  outcome as Dungeon's off-page beats do; the character's own agent then writes the few lines of what they said,
  from its own knowledge and the rolled outcome, in one cheap call. Program characters' threads are code only.
- Due threads run alongside Write (step 8), staged in the turn draft, and are committed in step 9 with the rest of the
  turn, so a thread's result is in the record before the next turn's snapshot.

### Corrections

- **A correction is a turn-keyed patch.** From the GM view (or by striking an invention, or a ruling applied
  backward), the user can correct a committed turn: a character knew something they couldn't, a number was wrong, a
  mechanic was misapplied. Code writes the correction as an entry keyed to that turn, in one transaction across the
  record, every affected character's memory and beliefs, feelings and stats, so every later read through the
  branch's ancestry sees it. The affected passage is rewritten and re-scanned, and the correction is logged.
- Later turns already played on that branch are not re-run; the turn report says which later turns referenced the
  corrected fact, so the user can rewind if it matters.

### Keeping records readable

- **Nothing is deleted.** The record and per-character memory keep every row *(Dungeon)*; summaries are written on top,
  never in place, so the "archive before squeezing" is built in.
- **Compaction keeps what's live.** Old turns are folded into chapter and era summaries, keeping recent turns word for
  word and, from older ones, every exact quote that might be needed later (promises, oaths, threats, confessions are
  stored verbatim when they happen), every number, every name and every open thread.
- **A check before a summary is used:** every open thread, hidden truth, ruling and live promise present before
  compaction must still be reachable after it; a summary that drops one is rejected and redrafted.
- **Character sheets are refreshed from the page.** At each chapter close, code drafts a "shown so far" update to
  each main character's sheet (habits, injuries, what they've revealed); it applies after the user's review in the GM
  view, or automatically in Watch.

### Coverage of the Isekai Pipeline PRD

| Epic | Where the spec covers it |
| --- | --- |
| 1. Setup and canon | World packages and cast sheets (What it builds on); house rules and rulings (above); "last updated through turn N" is built in, since every record and memory row is keyed by turn |
| 2. Receive a turn | Turn loop steps 1 to 3; one question on ambiguity, the brief and the stop point (above) |
| 3. Resolve uncertainty | Dice decide risky acts (Batch 1); turn loop step 7; dice log and overrides (above); roll visibility *(Dungeon)* |
| 4. Off-screen threads | Off-page threads (above), Dungeon's off-page beats and the director's threads |
| 5. Write the chapter | Turn loop step 8; every beat in full, stop point, System panes, inventions, game knowledge (above); Who sees what |
| 6. Scan the draft | The draft scan (above) |
| 7. Deliver and review | Streaming (Waiting and pauses); the Reviewer and flagging (above) |
| 8. Record the turn | Turn loop step 9; the record, hidden truths and per-character memory (Batches 2 and 3, Turn state); turn report and status line (above) |
| 9. Corrections and rulings | Corrections and rulings (above); striking inventions |
| 10. Keep records readable | Keeping records readable (above); Dungeon's chapters and fading (Batch 3) |
| 11. Reply to the Director | The turn report (above); the reply card and "nothing decided for your character" (Batch 2) |
| Non-goals | Held: house rules shape prose without prescribing style; nothing automates the user's own choices in Play; dice are shown to the user unless they choose hidden rolls, never on the page |

## Dungeon systems in agent play

Added 2026-11-02 after comparing Dungeon's requirements and roadmap with this spec. These Dungeon systems came over with the fork; the decisions above say how they work once characters have agents.

### Factions and nemeses

- **Factions give agents goals.** A faction's goals, clocks and agenda run in code as in Dungeon. An agent who belongs to a faction, or owes it something, gets what that character knows of it (its aims, its orders, their standing in it) in its context, weighed with its own wants. What the character doesn't know of the faction stays out, through the same context builders as every other secret.
- **A nemesis becomes an agent.** When the director promotes a foe to nemesis (Dungeon's rule: one who escaped, was humiliated, lost someone to the party or was spared), that character gets an agent automatically. Its grudge and what it remembers of the party and how they fight are its own memory. It counts toward the agent cap and takes a slot ahead of characters picked by role; if the cap is full, the user is told who dropped to a Program mind. The user can still demote it by hand.

### Travel and splitting the party

- **A lead proposes where the party goes.** In Play that is the user's character. In Author and Watch it is the party's leader (proposed: set on the cast page, by default the first seat), and the Author can nudge the destination like any other beat. Directions, hex searches and journeys from Dungeon's travel and hex crawl take the lead's proposal as their line.
- **Anyone can refuse and split off.** Agents declare whether they follow in Declare and React, from their feelings and goals. Program characters follow Dungeon's party rules. A character who refuses leaves the scene and runs as an off-page thread (code rolls, the agent writes its lines, as for any offscreen agent) until the party meets them again.

### Timing

- **Lore timers and off-page beats count rounds.** Dungeon counts the player's lines, which Author and Watch don't have. Adventure counts rounds in every mode, so switching modes never changes when lore lingers or rests, or when a beat is due. The count is kept with the timeline (going back rewinds it) and chance rolls stay seeded, as in Dungeon.

### The Ideas button

- **Play:** as in Dungeon. Two or three short moves for the user's character, built only from what that character knows.
- **Author:** two or three short nudges for the story, built from what the Author's view shows (intents, motives, whispers, the beat board), never from hidden truths nobody in the scene knows.
- **Watch:** no button.
- Ideas are never stored or shown to any other model call, as in Dungeon. A sent idea becomes the user's own line or nudge.

### Book export

- **Dungeon's export as a book (Markdown, EPUB or PDF) has a switch for hidden material:** the story only, or the story with each turn's motives and whispers set beside the Writer's post. (Proposed default: story only.) The Writer's posts themselves are exported as written. Hidden truths nobody learned stay out either way; the GM view is the place for those.

### Unchanged, and later

- **Unchanged:** shops and the economy, town maps and interiors, tiers and scaling, and rule passages. Agents' moves go through the same Resolve step and record as the user's, so these work as in Dungeon.
- **Later, after the first milestone:** art (on request and passive), themes, the phone layout and legacy campaigns. A round already takes many model calls, so passive art waits until costs are measured.

## Later batches (planned)

- Worlds: what Adventure needs from Worldsmith beyond today's package: visibility tags on lore, facts and cast
  secrets, with a check that flags lore that reads like a secret but isn't marked (since untagged counts as public), voice anchors on cast sheets (sample lines and verbal habits), and marking which cast
  members default to agents.
- First milestone: the smallest playable slice to build first. It should include the round timeline and reply card
  from day one, the per-reader context tests, and a red-team regression set of leak probes for each surface above,
  run across the default agent model and the cheapest local one, plus a "stayed in character" check.
