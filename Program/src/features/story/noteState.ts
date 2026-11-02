/** The one author's note of a chat (dungeon/authors_note.py): `story`. */
export interface AuthorsNoteState { chat: string; text: string; enabled: boolean; updated_at: string | null }
export const NOTE_LIMIT = 1000
/** The switch's label says what it does, like every other switch in the app, so it reads true when on or off. */
export const NOTE_SWITCH = 'Use this note'

export const noteKey = (chat: string) => ['authors-note', chat]

export type Look = 'off' | 'on' | 'paused'
export function noteLook(text: string, enabled: boolean): Look {
  return !text.trim() ? 'off' : enabled ? 'on' : 'paused'
}
