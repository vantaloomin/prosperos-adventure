# The Sidebar Assistant

The **Sidebar Assistant** is an out-of-story chat beside the app, after the sidecar in Prospero's Companion (which came from the Collaborator in Prospero's Study). It can see the story, but it is never part of it: nothing said in it reaches the narrator, the record, recall or any character, and nothing in it is stored. It answers and explains, suggests, and proposes changes the user applies one at a time (`adventure/assistant.py`, `src/features/assistant/`).

## Opening it

**Assistant** in the navigation opens and closes the panel beside whatever view is showing, and the story's menu (⌘K) has **Sidebar Assistant** too. The choice is remembered in this browser (`adventure:assistant`). On wide screens it is docked on the right; at 720px and narrower it covers the page. Under each narration, **Ask the assistant** opens the panel pointed at that passage, so "make this tenser" knows which one. The conversation lasts while the app is open; the reset button starts a new one, and switching worlds reloads the page, which starts one too.

It uses the **Sidebar Assistant** job in Settings > Models, which falls back to the Default when no profile is chosen. Without any text model, sending says so and offers Open Settings. Like every message box, it has the line saying characters are AI and can make mistakes.

## What it sees

Each message is sent with the scene (place, town, local time and weather), the last 30 lines of the branch being played, the people met, the journal, the lore switched on for the town and the story's author's note. Lines, journal facts, people, arcs and beats are listed under short references (`m3`, `k2`, `p1`, `a1`, `b4`), and a proposal may only name what it was shown, by those references. The last five exchanges of the sidebar conversation go with it.

With the GM view off, it is shown only what the player may see: the journal without hidden truth, public lore only, the people met by name only. With the GM view on (the switch in the journal, the Table's `gm_view`), it also sees hidden facts and GM-only lore, how everyone met feels toward the character, and the director's arcs with their truths and planned beats. Privacy is kept by leaving things out of its context, never by asking the model to keep quiet.

## What it can change

Each proposal is a card with Apply and Dismiss, and Undo once applied. Several pending proposals in one answer also get Apply all. Every change goes through the app's own path:

- **Author's note**: the whole note, switched on when applied (`PUT /api/authors-notes/story`). Undo puts back the old note and whether it was on.
- **A narrator's passage in new words** (`POST /api/story/messages/{id}/reword`, `adventure/story.py` `replaced`). The dice and what happened stay; the record's facts are taken again from the new words, as after a Rewrite. It carries the wording it was proposed against, so a passage that changed since is left alone. Undo is Switch wording, which also stays under the passage. Only narrations on the branch being played can change, and never the user's own lines.
- **A journal fact added or corrected** (`POST` and `PATCH /api/story/journal`). A correction is logged like one made in the journal. Undo removes the new fact or puts back the old words.
- **A lore entry** (`POST /api/lore/entries`, `adventure/lore.py` `add_entry`): keyword or always-on, in a book of its own, "Written with the Sidebar Assistant", made the first time. With the GM view on it can be GM only. Undo deletes it (`DELETE /api/lore/entries/{id}`).

With the GM view on, it can also propose GM edits, marked GM on their cards:

- **How someone feels** toward the character: trust, affection and respect from -5 to 5, fear and desire from 0 to 5 (`PATCH /api/story/gm/people/{key}`). Undo puts back the values before.
- **A planned beat cut or brought back** (`PATCH /api/story/gm/beats/{id}`). Undo flips it again.
- **A new beat** at the end of an arc's plan for its stage (`POST /api/story/gm/beats`, kept with source `assistant`). Undo takes it out (`DELETE /api/story/gm/beats/{id}`), which works only for a beat the user added that the story has not used yet.

A GM edit is refused on the server whenever the GM view is off, whatever the panel shows.

## When the model misbehaves

The model answers one JSON object: a reply and a list of changes. An answer that is not JSON, has an empty reply, or has a change that cannot be used (an unknown kind, a reference it was not shown, a user's line to reword, a GM edit with the GM view off) is sent back once with the reason. On the second try, unusable changes are dropped, and an answer that is still not JSON is shown as plain words with nothing to apply.
