# Editable prompts

Power users can reword the core prompts the Dungeon sends to their models. In Settings, the
**Show advanced settings** switch under the tab list adds an **Advanced** tab. It is off by default
and remembered by the browser. Searching Settings for "prompt" finds the tab and turns the switch on.

The Advanced tab lists each prompt with what it is for, an edit box, the placeholders it must
keep, and **Reset to default**. Once a prompt is reworded, its default wording is shown under it
for comparison.

| Prompt | Used for | Default lives in |
| --- | --- | --- |
| The Story narrator | Every narrator turn: who the narrator is and its contract with the game ([story.md](story.md)) | `CORE` in `dungeon/narration/prompt.py` |
| The narrator's writing rules | After the Story narrator: craft, dialogue rules, phrases never to use; small-context models get `CRAFT_COMPACT` instead | `CRAFT` in `dungeon/narration/prompt.py` |
| Author's note | The line in front of the user's note ([authors-note.md](authors-note.md)) | `HEADER` in `dungeon/authors_note.py` |

`dungeon/prompt_library.py` is the list. Defaults are read from the constants above when needed,
so changing one in code is the new default at once. The constants are written for `str.format`;
the library shows and fills them in the `{{placeholder}}` form.

## Storage and updates

A rewording is kept in `prompt_overrides` (name, text, the default it replaced, time), so it
travels with backups and survives updates. Saving the default wording unchanged removes the row.
When an update changes a default the user had reworded, their wording stays in use and the prompt
is marked **New default** with a note, until they reset or save again.

## What a rewording cannot break

Saving is refused, with a message naming the problem, when the wording:

- drops a placeholder the app fills in,
- uses a `{{placeholder}}` the app does not fill in (a typo such as `{{nmae}}`), or
- writes a placeholder with single braces, such as `{name}`.

Only the wording is editable. These stay code and run whatever a prompt says: the in-character
sentence filter and retry (`dungeon/in_character.py`), OOC handling, the prose checks
(`dungeon/narration/prose.py`) and the NSFW check before image generation. The in-character retry
reminder is not editable.
