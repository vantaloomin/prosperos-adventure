# Author's note

Hit List #48, built to Iris's mock. A short note of the user's that rides along with every narrator turn. It
steers the scene ("keep it light tonight", "they're still upset about the ferry") without becoming part of the
story.

## Behaviour

- **One note, for the story** (`story`). Nothing to set up first: a story starts with an empty note that is
  switched on.
- **Every turn while on.** No "every N turns" or depth settings. Up to 1,000 characters; the box counts them once
  past 800.
- **Last before the user's words.** The note goes right before the user's latest words, in the volatile tail, so
  the cached system prompt and story are untouched.
- **Never part of the story:** not shown in the story, not saved as a message, and the narrator never quotes it.
  An out-of-character message (`OOC:` or `((...))`) is answered without it.
- **Stays until changed:** cleared, edited or switched off by the user. Switching it off keeps the text. Starting a
  new story keeps the note (it is the user's own steering, not history); a world has its own note.

The wording in front of the note is an editable prompt (Settings > Developer > Prompts, "Author's note"):

    [Author's note from the user, for this reply. Follow it, but never mention or quote it:]

## In the app

A note button sits left of the message box. Empty, it is quiet grey; on, it is lit in the accent with a dot, and
hovering shows the note's first line; written but switched off, it has an accent outline and no dot. On a computer
the note pulls up from the message box as a tray, so nothing in the story moves; on a phone it is a bottom sheet
with a Done button. What is typed saves itself a moment after typing stops; the switch, Clear and closing save at
once.

## API

- `GET /api/authors-notes/story`: `{chat, text, enabled, updated_at}`; an empty, switched-on note when none is
  saved. 404 for any other name.
- `PUT /api/authors-notes/story` with `{text, enabled}`: saved as typed (a note of only spaces is saved empty).

Code: `dungeon/authors_note.py`, `src/features/story/AuthorsNote.tsx`.
