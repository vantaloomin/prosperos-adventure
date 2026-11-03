# Prospero's Adventure: style guide and UI requirements

*Written 2026-11-02 from the approved before/after mocks ([Adventure, before and after](https://claude.ai/artifact/U6EkNY5xDgz8xd6vzfVaek)) and the screens already merged (#9 to #13). Every new screen and change follows this guide. Where it and `docs/spec.md` differ on how something looks or reads, this guide wins; where they differ on what the game does, the spec wins.*

## Contents

- [Principles](#principles)
- [Style](#style): color, type, spacing, radius, icons, motion, copy, components, accessibility
- [Requirements](#requirements): the app shell and each screen
- [Checking a change](#checking-a-change)

## Principles

1. **Simple purpose, simple architecture, simple design, simple implementation.** The bar is Linear's website and Apple Notes: each screen does one job, and nothing on it needs explaining.
2. **No taglines, helper text or secondary labels.** If a screen needs a sentence to make sense, fix the layout instead. Data is not helper text: a time estimate, a count or a state ("Decided") is fine; a sentence telling the player what a control does is not.
3. **Every change improves UX, DX and AX together, and breaks nothing.** UX: the player sees less and understands more. DX: fewer components, one source of truth, copy in one place. AX: every visible state has a name that agents and tests can drive and assert on, through the same commands the buttons use.
4. **Quiet chrome, rich content.** Navigation, buttons and labels stay neutral. Color, light and detail belong to the world: its key art, portraits, scene pictures and prose.
5. **No inert controls.** A control ships only when the backend behind it works. Layouts can land first; agent controls (Thinks/Rules, modes, the round timeline, the reply card, Watch, Pace and Roles) land with the turn loop that drives them (Vanta, 2026-11-02).
6. **Never cut "Characters are AI and can make mistakes."** It stays under the composer, word for word with its period, for legal reasons (Vanta, 2026-11-02). It is the one exception to the copy rules below.

## Style

### Color

- **Tokens only.** Every color comes from the tokens in `Program/src/styles.css`: `--canvas`, `--surface`, `--raised`, `--border`, `--text`, `--muted`, `--faint`, `--accent`, `--accent-hover`, `--accent-tint`, `--on-accent`, `--danger` and their tints. No literal colors in components, except the dark scrim over art (`rgb(0 0 0 / .72)` fading to transparent).
- **Schemes.** Ink is the default (dark); Paper is the light scheme; Slate, Umber, Moss, Wine and Ash change only the neutrals. A component must read correctly in Ink and Paper.
- **Three text roles.** `--text` for content and labels, `--muted` for secondary text, `--faint` for meta. Nothing else.
- **One accent, used rarely.** The primary action, the current selection, the "You" mark, the dot on characters who think for themselves, and the lit step of the round timeline. Never a background for whole regions.
- **World themes.** Inside the story screen, a world's own palette (Vallarith's ember, Havenbrooke's autumn quad) replaces the tokens when the player has world colors on and the palette passes the readability check (text 4.5:1, accent 3:1). The app shell (nav rail, Settings, Worlds) keeps the app's accent. Two accents on one screen are a bug.
- **Semantic color carries meaning only.** Success on a roll, danger for errors and destructive actions, the warm warning tone for motives in Author and Watch.
- **No** hue gradients on surfaces, gradient text, glows, colored shadows, radial color washes, blobs, neon borders or glass effects. The one allowed gradient is the neutral scrim that keeps text legible on art. (The world pitch on hover, #13, is a frosted card by Vanta's choice; it stays the only one.)
- **Depth.** Dark schemes use surface steps (`--canvas` → `--surface` → `--raised`) and 1px `--border` hairlines. Shadows are neutral and small, and only on things that float (dialogs, menus, the arrows over the world row).

### Type

- **Two families.** IBM Plex Sans (`--ui-font`) for the interface; Literata (`--read-font`) for prose, page titles, world names and character dialogue. The reader can swap the reading font in Settings (Atkinson Hyperlegible, OpenDyslexic); layouts must survive that.
- **Sizes.** 0.75rem meta and counts; 0.8125rem secondary text and labels; 0.875rem interface body and buttons; 1rem story prose (scaled by the reader's text size); 1.25 to 1.5rem page titles; 1.6rem names on world tiles. Use these and nothing in between (0.8rem, 0.82rem and 0.95rem are legacy; replace them when touched).
- **Weights.** 400 and 500. 600 only for a rare emphasis inside a sentence. Hierarchy comes from size and color, not weight.
- **Case.** Sentence case everywhere. No uppercase labels with wide tracking (no "THIS SCENE", "PACE"); no letter spacing under 16px.
- **No italics for emphasis** in interface text. Prose may use italics where the story needs them (a thought, a title, a foreign word).
- **Numbers** use `tabular-nums` where they line up, and one format per screen ("3.40 cr.", "$2.00").

### Spacing and layout

- **4px grid.** Paddings, gaps, margins and fixed heights are multiples of 4. A 2px nudge inside a small control is allowed.
- **Equal things are equal.** Rows in one list share one height and gap; cards in one row share one padding.
- **Space shows grouping.** Gaps inside a group are smaller than gaps between groups. `--stack-gap` (16px) is the least space between stacked panels.
- **Density.** Nav rail and cast list 12 to 16 padding; cards 12 to 24; page edges 24 to 32; rows 32 to 40 tall.
- **Phones.** Everything stacks in reading order, the side gutter is at least 16px and respects safe-area insets, and no page scrolls sideways. Rows that scroll sideways (the world row) scroll inside themselves.

### Radius

- 4 to 6px for tags, small toggles and keycaps; 8px for buttons, inputs and rows; 12px for cards and tiles; 16px for dialogs and the reply card.
- **Nested radius.** Inner radius = outer radius minus the padding between them, never below 4.
- **No pills** for chips, counts or toggles (`border-radius: 999px` is legacy; replace it when touched). Only circles stay round: portraits, status dots, the round arrow buttons.

### Icons

- One set: `lucide-react`, at 16 or 18px, stroke 1.5, in the color of the text they sit with. One icon box width per list so labels align.
- No emoji in the interface. No sparkle or brain icons for anything AI. A character who thinks for themself is marked by a small accent dot, not an icon.
- Drop icons that add nothing. An icon-only button always has an `aria-label`.

### Motion

- One easing curve: `--ease` (`cubic-bezier(0.22, 1, 0.36, 1)`). Durations: 120 to 180ms for hover, press and toggles; 160 to 240ms for menus, popovers and the world pitch; 300 to 500ms for entrances and sheets.
- Animate only color, background, border, opacity and transform. Never width, height, top, left or large blurs.
- Loops only for things that are live: a character thinking (a ring), the current round step, a character waiting for the player, the streaming caret. Nothing else pulses, floats or shimmers.
- No hover lifts or scale on cards. Hover is a surface or scrim change.
- Dice keep their landing animation; it explains a result.
- `prefers-reduced-motion` turns every loop and transition off, and streaming text appears at once.

### Copy

- Write from the player's side: name things by what people recognize (Worlds, Pace, Writer), never by how the code is built.
- **Buttons say what happens**: "Enter", "Begin", "Send", "Add a model", "Say nothing". One primary action per view.
- **No trailing periods** on titles, labels, buttons, banners or chips. Only multi-sentence paragraphs keep periods.
- **No exclamation marks, greetings, hype or emoji** in interface text.
- **Status is a fact.** "Thinking", "Decided", "Waiting for you", "Paused: Tobin lied to the party".
- **Errors say what went wrong and what to do next**, without apology.
- **Behind-the-scenes names stay behind the scenes.** The play screen names only the Writer; the director, Referee, Reviewer and GM view appear in Settings and the GM view.
- **Belief language for lies.** "Ilsa believes the bridge is guarded", never a contradiction presented as fact.
- **Copy lives in `*Text.ts` modules** next to the feature (as `titleText.ts`, `menuText.ts` do), so strings are tested and found in one place.

### Components

| Component | Rules |
| --- | --- |
| Button | 40px tall, 8px radius, 8×16 padding. Primary: `--accent` fill, `--on-accent` text. Secondary: `--surface` with a hairline. Quiet: no border, `--muted` text. |
| Segmented control | `--raised` track, 4px padding and gap, selected segment on `--surface`. Used for Before/After-style choices and Play / Author / Watch. |
| World tile | Key art filling a 3:4 tile, the world's name in Literata on the scrim, nothing else. The tile is the button. The pitch shows as the frosted card on hover or focus. |
| Portrait | Round, from the world package's portraits; initials only as a fallback. 32px in lists, 52px on the Cast page. The accent dot at the lower right marks a character who thinks for themself. |
| Cast row | Portrait, name, one line of state, a status dot. Expands in place; never opens a page. |
| Roll chip | 8px radius on `--raised`: who, what, the number, the result. Lives in the story where the roll happened. |
| Reply card | Replaces the composer: the speaker's portrait and full line, a text field, then Say nothing, Let <name> answer, Reply. Accent border, 16px radius. |
| Banner | One line: the reason, then one primary and at most one quiet action. Replaces the composer while it is up. |
| Dialog | Title, the control, the action. No paragraphs; long text lives on its own page and is linked. |

### Accessibility

- Contrast: text 4.5:1 and accent 3:1 against its surface, in every scheme and world theme.
- Everything is reachable by keyboard, with the visible focus ring from `styles.css`. Rows that scroll sideways take arrow keys, Home and End.
- Status changes in the round are announced through one polite live region, in summary ("3 of 5 characters have decided").
- Meaning never rests on color alone: the "thinks" dot also has an accessible name; "You" is written, not only highlighted.
- Every image has alt text or is marked decorative; every icon-only button has a label.

## Requirements

IDs are stable so PRs and tests can cite them. "Loop" marks requirements that ship only with the agent turn loop (Principle 5).

### Shell

- **SH-1** The nav rail holds the persona, Story and Settings, icons and short labels only.
- **SH-2** Commands that aren't the screen's job (Ideas, the notebook, start a new story, export) live in one menu opened by ⌘K / Ctrl+K and a menu button, not as buttons on the play screen.
- **SH-3** No app-wide banners. A missing model is shown where it matters: Send becomes "Add a model".

### Enter (first run)

- **EN-1** One dialog over the title painting (`public/title.webp`): the title "Everyone here is AI", one "I'm 18 or older" checkbox, a "Safety" link and "Enter".
- **EN-2** The safety explanation lives on the Safety page; the app's self-harm behaviour is unchanged.
- **EN-3** Consent is one stored flag that tests and agents can set directly.

### Worlds

- **WO-1** Worlds are one row of world tiles that scrolls sideways with scroll snap, most recently played first, and a "+" tile at the end that makes a new world.
- **WO-2** A faded edge and an arrow button appear only on a side with more tiles past it; arrow keys, Home, End and trackpad scrolling work; on phones the next tile peeks in.
- **WO-3** No hero, tagline, genre line, paragraph or "Begin in…" button. The world's pitch appears only as the frosted card on hover or focus.
- **WO-4** Worlds are chosen by package id; a tile's picture and name come from the package, so there is no per-world copy in the app.

### Cast

- **CA-1** One page after choosing a world: the world name as title, a grid of portraits, the selected character's bio under the grid, and a footer with Rules, Tone (As written, Gentler, Harsher) and Begin.
- **CA-2** Tap a portrait to play as that character; the card is marked "You". A "+" card makes your own.
- **CA-3** No secondary labels ("a woman, 29"), no "Play as" buttons, no preset descriptions, no second page.
- **CA-4** Rules is chosen here and locks after Begin; the locked state speaks for itself in Settings.
- **CA-5** Begin posts one campaign record `{world, seat, agents[], mode, rules, tone}`, the same record the turn loop's Setup step reads.
- **CA-6** *Loop.* Play / Author / Watch sits at the top right. In Author and Watch no card is "You".
- **CA-7** *Loop.* Every character except yours has a Thinks / Rules toggle (agent or Program), default from the world package.
- **CA-8** *Loop.* When a town has more leads than the agent cap, the grid holds you and your party (filled up to the cap) and a Bank row under it holds the rest. A small − on a party card sends them to the bank and a + on a bank card brings them in; tapping any portrait still plays as them. Whoever is in the bank at Begin lives in town as a background character.

### Play

- **PL-1** Three regions: the story in the centre, the cast list on the right, the composer at the bottom. On phones the cast list folds into a sheet opened from the header.
- **PL-2** The header is one line: place · time · condition, plus the mode control (*Loop*).
- **PL-3** The story holds the scene picture, prose in the reading font, the player's own line set off by an accent rule, and roll chips where rolls happened. No caption under the picture.
- **PL-4** The composer is one field and Send, with "Characters are AI and can make mistakes" under it. In Author its placeholder is "Nudge the story".
- **PL-5** The cast list replaces the Scene / Sheet / Pack / Journal / More tabs. Each row is a cast row; clicking your own portrait shows your condition and pack, clicking another shows what the mode allows.
- **PL-6** Shops and places appear in the cast list only while they are open ("The counter" when someone is behind it), not as closed notices.
- **PL-7** *Loop.* The round timeline sits above the cast list: five steps (Declare, React, Talk, Roll, Write) with the current one lit and named, plus a count while declaring ("Declaring · 2 of 3").
- **PL-8** *Loop.* Rows move through Thinking, Decided, Waiting for you. In Play a row never shows an intent or motive; in Author and Watch the intent shows on the row and the motive in the expanded row, in the warning tone.
- **PL-9** *Loop.* When a character addresses the player's character, the reply card replaces the composer, and the speaker's row shows "Waiting for you". If the tab is not focused, the title gets a badge.
- **PL-10** *Loop.* In Watch the composer becomes Play / Pause and Next. Pauses at big moments, the session cap or a dropped step use the banner, always with the reason.
- **PL-11** *Loop.* Leaving Play for Author or Watch asks once, in the banner, "Show the motives you missed?" with Keep hidden (default) and Show.
- **PL-12** *Loop.* Opening the GM view in Play asks first and marks the turns where it was open.
- **PL-13** Every visible state maps to a named state of the one turn state machine (`Idle → Gathering → Declaring → Reacting → Conversing ⇄ AwaitingUser → Resolving → Writing → Committing → Idle`). Components render from it; no widget fetches turn state on its own.
- **PL-14** Writer prose streams; with reduced motion it appears at once.

### Settings

- **SE-1** Each settings page is a title, labelled controls and values. No introductory paragraphs and no "This computer" report; a warning appears only when a chosen local model won't fit.
- **SE-2** *Loop.* Models opens with Pace: Quick, Balanced, Rich, each showing its time and call count per turn as data (for example "~25 s · 14 calls"). The agents preset that shipped as "Quick and cheap" and "Rich and slow" is renamed to match.
- **SE-3** Roles list one row per role in code, by its player-facing name: Writer, Characters (the `agents` role), Referee, Memory. Each row shows the model; "Add a model" sits under the list. The mapping from role key to name lives in one `*Text.ts` module, so agents and tests can use either.
- **SE-4** *Loop.* Advanced holds thinking characters at once, exchanges per turn and the session cap. One `pace` setting sets all of them and the role models together; changing one by hand makes Pace read "Custom".
- **SE-5** Sliders and toggles carry a label and their value, not a sentence of explanation.

## Checking a change

Before a UI PR is opened, check it against this list and say in the PR which requirement IDs it covers.

- [ ] No new tagline, helper sentence or secondary label; any new string lives in a `*Text.ts` module.
- [ ] Colors from tokens only; reads in Ink and Paper and under each world theme; one accent on screen.
- [ ] Sentence case, weights 400/500, sizes from the list, no italics in interface text, no trailing periods on short strings.
- [ ] Spacing on the 4px grid, radius by size, no new pills.
- [ ] lucide icons at 16/18px, stroke 1.5; no emoji or sparkles.
- [ ] Motion uses `--ease`, animates only color, opacity and transform, loops only for live states, and stops under reduced motion.
- [ ] Keyboard reachable with a visible focus ring; icon buttons labelled; contrast passes.
- [ ] No control without a working backend.
- [ ] Phone width: no sideways page scroll, 16px gutters.
- [ ] Screenshot of the change in Ink and Paper attached to the PR.
