import { createContext, useContext } from 'react'
import type { EntityRef, NameLink } from './entity'

export interface Entities { open: (entity: EntityRef) => void; links: NameLink[] }

/** The story screen's entity cards (EntityCard.tsx EntityHost): null outside it, where names stay plain text. */
export const EntityContext = createContext<Entities | null>(null)

/** The names the story's prose links to their cards (none outside the story screen). */
export function useNameLinks(): NameLink[] {
  return useContext(EntityContext)?.links ?? []
}
