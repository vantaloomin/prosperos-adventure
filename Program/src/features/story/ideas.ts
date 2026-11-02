/** Ideas (dungeon/ideas.py): two or three things the character could do now. Used once: they live only here, in
 * the composer's memory, never in storage, and go when the player sends a line or the story moves on. */
export type Ideas = { ideas: string[]; turn: number }

/** A picked idea in the composer: in place of an empty draft, else after what is there. Nothing is sent. */
export function withIdea(draft: string, idea: string): string {
  return draft.trim() ? `${draft.trim()} ${idea}` : idea
}

/** The ideas still worth showing: none once the story has moved past the turn they were made for. */
export function freshIdeas(found: Ideas | null, turn: number): string[] {
  return found && found.turn === turn ? found.ideas : []
}
