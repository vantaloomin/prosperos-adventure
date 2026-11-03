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

Every call to a character who thinks for themselves (an agent) opens with **A character's mind**, then the line for the moment the call is for, then **Turning on someone**.

| Prompt | Used for | Default lives in |
| --- | --- | --- |
| A character's mind | Opens every agent call: whom they play (`{{character}}`, their name), deciding only from inside their own head, the sheet as canon, how they speak, the content rules | `MIND` in `adventure/rounds/agents.py` |
| Deciding a move | Everyone declares at once at the start of a round | `PURPOSES['declare']` |
| Reacting to the others | After everyone declared, the one chance to change a move | `PURPOSES['react']` |
| Speaking up | The talk inside a round: a character says something to someone | `PURPOSES['ask']` |
| Answering | The talk inside a round: a character answers a line said to them | `PURPOSES['answer']` |
| Off the page | A few lines a character said away from the main scene | `PURPOSES['offpage']` |
| Turning on someone | What a character may do once they turn on someone, and what turns them | `TURNING` in `adventure/rounds/agents.py` |

These stay code, between and after the editable parts: the fence rule that keeps story text from reading as instructions, the answer's JSON shape (`CONTRACT`, and `REACT_CONTRACT` for a reaction), the intensity, the scheming dial (`SCHEMING`), and how the character stands with each person present. What a character may know is built by the context builder (`adventure/rounds/context.py`), so no rewording can show a character someone else's secrets. Code still validates every answer (claims cut back to attempts, audiences kept to who is present, the intensity kept in every field).

`adventure/prompt_library.py` is the list, in the order shown. Defaults are read from the constants above when needed, so changing one in code is the new default at once. The constants are written for `str.format`; the library shows and fills them in the `{{placeholder}}` form.

## Storage and updates

A rewording is kept in `prompt_overrides` (name, text, the default it replaced, time), so it travels with backups and survives updates. Saving the default wording unchanged removes the row. When an update changes a default the user had reworded, their wording stays in use and the prompt is marked **New default** with a note, until they reset or save again.

## What a rewording cannot break

Saving is refused, with a message naming the problem, when the wording:

- drops a placeholder the app fills in,
- uses a `{{placeholder}}` the app does not fill in (a typo such as `{{nmae}}`), or
- writes a placeholder with single braces, such as `{name}`.

Only the wording is editable. These stay code and run whatever a prompt says: the in-character sentence filter and retry (`adventure/in_character.py`), OOC handling, the prose checks (`adventure/narration/prose.py`), the round's draft scan (`adventure/rounds/scan.py`), the agents' context builder and answer checks, and the NSFW check before image generation. The in-character retry reminder is not editable, and nor is the Reviewer's prompt yet (`adventure/rounds/reviewer.py`).

## How the defaults are written

The narrator, round Writer and character defaults follow one shape, from a red-team review of the adult fiction prompts:

- **One order of authority.** Content first and never overridden, then the facts the game decided and the hard rules (never weighed), then the player's words, then canon, then everything else as guidance.
- **One content scope.** Every character in a sexual or romantic context is an adult and written as one, with no childlike trait or framing whatever the setting says about age; real, living people are never shown in sexual content or as victims of violence. Within that, difficult material gets full craft with no softening, moralizing or disclaimers.
- **Hard rules are few and checkable**: em dashes, echoed phrases, reported speech, a verbal habit once a scene. Everything else is a tendency, not a quota, because a quota is met the same way every time and becomes a tell.
- **No blocklist in the generation prompt.** A list of phrases never to write puts them in front of the model every turn. The stock phrases and tells are found after the draft instead: by `prose.py` for the narrator, and by the draft scan and the Reviewer for a round. The Reviewer reads a tell as a place to look, not an automatic cut.
- **No rule the model can't check.** New names follow "a name a real person of that age, place and culture would ordinarily carry, never one picked for how it sounds"; the outlawed names list is checked in code.
