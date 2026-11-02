import { useState } from 'react'
import { api } from '../../api'
import type { World, Worlds } from '../../types'

/** Where the user lives, as the form holds it: a blank neighbourhood is the app's to pick. */
export interface HomeDraft { city_id: string; neighbourhood: string }

export function homeDraft(world: World): HomeDraft {
  return { city_id: world.home?.city_id ?? world.city_id, neighbourhood: world.home?.neighbourhood ?? '' }
}

export function homeChanged(world: World, draft: HomeDraft): boolean {
  const saved = homeDraft(world)
  return saved.city_id !== draft.city_id || saved.neighbourhood !== draft.neighbourhood
}

export function saveHome(world: World, draft: HomeDraft) {
  return api<Worlds>(`/worlds/${world.id}/home`, draft, 'PUT')
}

/** The form's "Where you live": the draft for the world the persona is in (none on a new persona's form), and
 * `settle` to show what was saved, such as the neighbourhood the app picked for a blank one. */
export function useHomeDraft(world?: World) {
  const [home, setHome] = useState<HomeDraft | null>(() => world ? homeDraft(world) : null)
  const moving = world && home ? { world, home } : null
  const settle = (saved?: Worlds) => { if (saved && home) setHome(homeDraft(saved.world)) }
  return { moving, setHome, settle }
}
