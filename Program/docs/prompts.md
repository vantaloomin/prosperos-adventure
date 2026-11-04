# Editable prompts

Power users can reword the core prompts Adventure sends to their models, in Settings > Developer > Prompts. Searching Settings for "prompt" finds the section.

The section lists each prompt in its group with what it is for, an edit box, the placeholders it must keep, and **Reset to default**. Once a prompt is reworded, its default wording is shown under it for comparison.

### Story

| Prompt | Used for | Default lives in |
| --- | --- | --- |
| The Story narrator | Every narrator turn: who the narrator is, what wins when instructions disagree, its contract with the game and the content rules ([story.md](story.md)) | `CORE` in `adventure/narration/prompt.py` |
| The narrator's writing rules | After the Story narrator and the round Writer: the hard rules (em dashes, the dialogue rules), then how to write; small-context models get `CRAFT_COMPACT` instead | `CRAFT` in `adventure/narration/prompt.py` |
| The round Writer | Every round told when other characters think for themselves (a party in Play, Author and Watch), in place of the Story narrator | `ROUND` in `adventure/rounds/writer.py` |
| Author's note | The line in front of the user's note ([authors-note.md](authors-note.md)) | `HEADER` in `adventure/authors_note.py` |

### Characters

Every call to a character who thinks for themselves (an agent) is laid out by **A character's prompt, laid out**: the rules every character shares (their mind, the fence rule, the answer's shape and **Turning on someone**), the story's intensity and scheming dial, then the character's own parts, the scene, this turn, and last the line for the moment the call is for. See [Layouts and caching](#layouts-and-caching).

| Prompt | Used for | Default lives in |
| --- | --- | --- |
| A character's mind | Opens every agent call: deciding only from inside their own head, the sheet as canon, how they speak, the content rules. It names nobody, so every character in a story shares it; the name comes with the sheet | `MIND` in `adventure/rounds/agents.py` |
| Deciding a move | Everyone declares at once at the start of a round | `PURPOSES['declare']` |
| Reacting to the others | After everyone declared, the one chance to change a move | `PURPOSES['react']` |
| Speaking up | The talk inside a round: a character says something to someone | `PURPOSES['ask']` |
| Answering | The talk inside a round: a character answers a line said to them | `PURPOSES['answer']` |
| Off the page | A few lines a character said away from the main scene | `PURPOSES['offpage']` |
| Being asked along | The player asks them to come along and their feelings leave it to them: they say yes or no | `PURPOSES['invite']` |
| Turning on someone | What a character may do once they turn on someone, and what turns them | `TURNING` in `adventure/rounds/agents.py` |
| A character's prompt, laid out | Where each part of a character call goes, as slots | `LAYOUT` in `adventure/rounds/agents.py` |

These stay code: the fence rule that keeps story text from reading as instructions, the answer's JSON shape (`CONTRACT`, `REACT_CONTRACT` for a reaction and `INVITE_CONTRACT` for being asked along), the intensity, the scheming dial (`SCHEMING`), and how the character stands with each person present (`siding`). What a character may know is built by the context builder (`adventure/rounds/context.py` `agent_slots`), so no rewording or layout can show a character someone else's secrets. Code still validates every answer (claims cut back to attempts, audiences kept to who is present, the intensity kept in every field).

A mind reworded before the name moved to the sheet keeps working: its `{{character}}` is still filled with the name. Saving a mind with `{{character}}` in it is refused with a note to take it out, because a name there stops the characters sharing the cached start.

### Genres

The Table's Genre (Story, More, Tone and rules) adds one of these after the intensity in the narrator's and the round Writer's prompt, or none. How explicit or how violent the page gets stays with the intensity settings.

| Prompt | Used for | Default lives in |
| --- | --- | --- |
| Dark romantasy | Romance as the spine, fantasy as the pressure on it, power that shifts | `GENRES['dark-romantasy']` in `adventure/narration/prompt.py` |
| Adventure | Something always moving, competence through technique, travel that costs | `GENRES['adventure']` |
| Graphic violence | Violence with physical specificity and consequence, never a how-to | `GENRES['graphic-violence']` |

`adventure/prompt_library.py` is the list, in the order shown. Defaults are read from the constants above when needed, so changing one in code is the new default at once. The constants are written for `str.format`; the library shows and fills them in the `{{placeholder}}` form.

## Storage and updates

A rewording is kept in `prompt_overrides` (name, text, the default it replaced, time), so it travels with backups and survives updates. Saving the default wording unchanged removes the row. When an update changes a default the user had reworded, their wording stays in use and the prompt is marked **New default** with a note, until they reset or save again.

## What a rewording cannot break

Saving is refused, with a message naming the problem, when the wording:

- drops a placeholder the app fills in,
- uses a `{{placeholder}}` the app does not fill in (a typo such as `{{nmae}}`),
- writes a placeholder with single braces, such as `{name}`, or
- puts a layout's slots out of tier order (see [Layouts and caching](#layouts-and-caching)).

Only the wording is editable. These stay code and run whatever a prompt says: the in-character sentence filter and retry (`adventure/in_character.py`), OOC handling, the prose checks (`adventure/narration/prose.py`), the round's draft scan (`adventure/rounds/scan.py`), the agents' context builder and answer checks, and the NSFW check before image generation. The in-character retry reminder is not editable, and nor is the Reviewer's prompt yet (`adventure/rounds/reviewer.py`).

## Layouts and caching

Claude, OpenAI, Gemini and llama.cpp all reuse the work of reading a prompt for as long as its start is unchanged, which saves time and, on hosted models, money. So a layout puts what changes least first (`adventure/prompt_layout.py`). Each piece of live content is a slot, and each slot belongs to a tier:

| Tier | Changes when | Character slots |
| --- | --- | --- |
| Rules | The app updates, or a prompt is reworded | `{{RULES}}` |
| Story | The story's settings change | `{{STORY}}` |
| Character | Their sheet or notes change | `{{CHARACTER}}`, `{{SHEET}}`, `{{NOTES}}`, `{{SHOWN}}`, `{{FACTIONS}}` |
| Scene | A scene starts, or who is in it changes | `{{HERE}}`, `{{LORE}}` (lore and facts that are always there) |
| Turn | Every turn | `{{MENTIONED}}` (lore what was just said brings up), `{{MEM}}`, `{{FEELINGS}}` (with where they stand with each person), `{{TURN}}` |
| Call | Every call | `{{DECLARED}}`, `{{MOMENT}}`, `{{CUE}}` |

The rules, story, character and scene tiers make the system prompt; the turn and call tiers make the user message. So every call for one character in one scene starts with the same system prompt, byte for byte, whatever the turn or the moment, and every character in a story shares the rules and story at its start.

- **Claude** gets the system prompt as three blocks with a cache mark at the end of each: rules and story (shared by every character), the character, and the scene. A retry's conversation takes the fourth mark. Claude caches a start of 1,024 tokens or more (2,048 on Haiku), so a character with a thin sheet may not be cached.
- **OpenAI** caches on its own from 1,024 tokens; each request also carries `prompt_cache_key`, a digest of the rules, story and character, so calls for the same character go to the same cache.
- **Gemini** caches the same stable start on its own.
- **llama.cpp** with `--slot-save-path` keeps one saved prompt start per character, keyed by the whole system prompt, so each character's file survives from one turn to the next (`adventure/providers/prompt_cache.py`).

Nothing in the first four tiers may carry a timestamp, a turn number or anything in a changing order; a test renders a character's prompt across turns, moments and focus and checks the system prompt does not change (`tests/test_prompt_layout.py`).

Editing a layout, in Settings > Developer > Prompts:

- **Order.** Saving is refused when a slot comes before one from a slower tier, with a note saying which to move: memories change every turn, so `{{MEM}}` above `{{SHEET}}` would mean the sheet is never cached.
- **Only the reader's slots.** A layout is offered only the slots its reader's context builder fills, and an unknown slot is refused. A slot is a position, never a permission: a character layout has no slot for anyone else's motives, whispers or the GM's notes.
- **Fences stay.** Slot content is always fenced by code under a label code chooses. A layout can put a heading over a slot, but cannot remove its fence.
- **Left-out slots come back** at the end of their tier, so content never silently disappears. Each slot may appear once.
- **Paragraphs.** A layout is read in paragraphs split by blank lines. A paragraph whose slots are all empty this call is left out, so keep a heading in the same paragraph as its slot. A paragraph with no slot stays with the tier of the paragraph before it.

The **round Writer** follows the same order without slots: its system prompt holds only its rules (the round Writer prompt, the writing rules, the fence rule) and the story's settings (length, intensity, house rules, whose eyes), as two cache blocks. The story so far follows, word for word, and what the Writer may know this round comes last, in the closing message with the ask. So each round's request starts with all of the last one's except its closing message, and Claude's mark on the last message of the story so far lets the next round read it back. The **Referee**'s system prompt was already the same every call, with the scene and intents in its message. The Story narrator is not laid out this way yet.

**Cache use in the turn report.** Each agent and Writer call adds what its model service said about caching to the turn (`draft.extra['cache']`, adventure/pace.py `count_cache`), from each service's own usage fields: Claude's cache reads and writes, OpenAI's, OpenRouter's and Gemini's cached tokens, and llama.cpp's reused tokens (`timings.cache_n`). The turn report shows it as **Model cache**: the share of prompt tokens read from cache, the calls, and what was written, or that the service did not say.

## How the defaults are written

The narrator, round Writer and character defaults follow one shape, from a red-team review of the adult fiction prompts:

- **One order of authority.** Content first and never overridden, then the facts the game decided and the hard rules (never weighed), then the player's words, then canon, then everything else as guidance.
- **One content scope.** Every character in a sexual or romantic context is an adult and written as one, with no childlike trait or framing whatever the setting says about age; real, living people are never shown in sexual content or as victims of violence. Within that, difficult material gets full craft with no softening, moralizing or disclaimers.
- **Hard rules are few and checkable**: em dashes, echoed phrases, reported speech, a verbal habit once a scene. Everything else is a tendency, not a quota, because a quota is met the same way every time and becomes a tell.
- **No blocklist in the generation prompt.** A list of phrases never to write puts them in front of the model every turn. The stock phrases and tells are found after the draft instead: by `prose.py` for the narrator, and by the draft scan and the Reviewer for a round. The Reviewer reads a tell as a place to look, not an automatic cut.
- **No rule the model can't check.** New names follow "a name a real person of that age, place and culture would ordinarily carry, never one picked for how it sounds"; the outlawed names list is checked in code.
