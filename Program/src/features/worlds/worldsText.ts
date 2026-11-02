import type { Persona, PersonaGender, World } from '../../types'

export const GENDERS: [PersonaGender, string][] = [['', 'Not said'], ['woman', 'A woman'], ['man', 'A man'], ['nonbinary', 'Nonbinary']]

/** A persona's own name, or '' when the user has not given one. The app never makes one up (Vanta, 2026-10-09). */
export function personaName(persona: Pick<Persona, 'name'> | null | undefined): string {
  return persona?.name.trim() ?? ''
}

/** How a persona is named on Worlds: their name, or a description of them while they have none (Iris). */
export function personaTitle(persona: Pick<Persona, 'name'>): string {
  return personaName(persona) || 'Your first persona'
}

/** A persona referred to inside a sentence or button: "New world for Sam", "New world for this persona". */
export function personaRef(persona: Pick<Persona, 'name'>): string {
  return personaName(persona) || 'this persona'
}

/** Where the persona lives in a world: "Ridge Road, Haddon Harbor", or the city alone. */
export function homeLine(world: Pick<World, 'home'>): string {
  const home = world.home
  if (!home) return 'No home yet'
  return home.neighbourhood_name ? `${home.neighbourhood_name}, ${home.city}` : home.city
}

/** The label under the nav button: who the user is and where. */
export function whereLine(persona: Pick<Persona, 'name'> | null | undefined, world: Pick<World, 'name'> | null | undefined): string {
  const name = personaName(persona)
  if (!world) return name
  return name ? `${name} · ${world.name}` : world.name
}

export function initial(persona: Pick<Persona, 'name'> | null | undefined): string {
  return personaName(persona).slice(0, 1).toUpperCase()
}

/** A persona's age: 18 to 120, and for a long-lived kind (an elf, a dwarf) on up to 5,000 in steps that get wider
 * (5s to 500, 10s to 1,000, 50s after). A saved age off the list stays listed, so nothing changes by itself. Never
 * free text. */
/** Under the age, when it can't be saved: why. Adults only, whole years, past 120 only for a long-lived kind. */
export function ageHint(age: number | null, longLived: boolean): string | undefined {
  if (age === null) return undefined
  if (!Number.isInteger(age)) return 'Give the age in whole years.'
  if (age < 18) return 'Everyone here is an adult: 18 or older.'
  if (age > 5000) return 'An age past 5,000 is not saved.'
  if (age > 120 && !longLived) return 'An age past 120 is only for a long-lived kind: pick one under Kind.'
  return undefined
}
