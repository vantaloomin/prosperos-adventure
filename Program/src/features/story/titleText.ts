import type { TitleWorld } from '../../types'

/** What a title-screen card's button does: begin in the world the story is in, go back to one the persona has, or
 * go to a new one (dungeon/world_select.py enter). */
export function worldAction(world: Pick<TitleWorld, 'name' | 'here' | 'yours'>): string {
  if (world.here) return `Begin in ${world.name}`
  return world.yours ? `Return to ${world.name}` : `Go to ${world.name}`
}
