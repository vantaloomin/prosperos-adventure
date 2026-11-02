import type { KindChoices, KindShown } from '../../types'

/** "600 years", "1,000 years". */
export function yearsText(years: number) {
  return `${years.toLocaleString('en-US')} years`
}

/** Where the app's pick of a kind came from: their own words, their parents', or the app (a name, or nothing to read). */
export type KindSource = 'words' | 'parents' | 'app'

/** The Kind picker's first option, the app's pick, saying why: "As their description says (Elf)", "From their parents
 * (Half-elf)", "As the app picks (Human)". */
export function foundOption(foundLabel: string, source: KindSource, you = false) {
  if (source === 'words') return you ? `As About you says (${foundLabel})` : `As their description says (${foundLabel})`
  return source === 'parents' ? `From their parents (${foundLabel})` : `As the app picks (${foundLabel})`
}

/** How long they live's first option: "As their kind (about 600 years)", "As their kind (doesn't age)"; "your kind"
 * on the Persona page. */
export function asKindOption(kindYears: number | null, you = false) {
  const whose = you ? 'your' : 'their'
  return kindYears === null ? `As ${whose} kind (doesn't age)` : `As ${whose} kind (about ${yearsText(kindYears)})`
}

const HUMAN_YEARS = 80
const ADULT = 18
/** Past this, a kind is long-lived (dungeon/world/lifespans.py `LONG_LIVED`): an age past 120 can be theirs. */
export const LONG_LIVED = 150

/** Their age in human terms (dungeon/world/lifespans.py `life_age`): childhood at a human pace, then adulthood
 * stretched to their lifespan. Null lifespan: they don't age, so it is the age they are. */
export function lifeAge(real: number, lifespan: number | null) {
  if (lifespan === null || real <= ADULT || lifespan === HUMAN_YEARS) return real
  return Math.round(ADULT + (real - ADULT) * (HUMAN_YEARS - ADULT) / (lifespan - ADULT))
}

/** How long someone lives as the pickers stand: their own pick (0 doesn't age), else the picked kind's, else the
 * kind the app read. Null: they don't age. */
export function pickedLifespan(choices: KindChoices, picked: string, own: number | null, foundYears: number | null) {
  if (own === 0) return null
  if (own) return own
  const kind = choices.kinds.find((item) => item.id === picked)
  return kind ? kind.lifespan : foundYears
}

export function longLived(lifespan: number | null) {
  return lifespan === null || lifespan > LONG_LIVED
}

/** "About 48 in human terms": under the pickers, only when it differs from the age they are. */
export function humanTermsText(shown: KindShown | undefined, age: number | null | undefined) {
  if (!shown || shown.life_age === null || shown.life_age === undefined || shown.life_age === age) return ''
  return `About ${shown.life_age} in human terms.`
}

/** The lifespans offered, with the one already picked kept when it is not on the list (a city's own). */
export function spanChoices(choices: KindChoices | undefined, own: number | null) {
  const spans = choices?.spans ?? [80, 150, 300, 600, 1000]
  return own && !spans.includes(own) ? [...spans, own].sort((a, b) => a - b) : spans
}

/** The summary of a folded kind section on someone's card: "Kind: Elf · lives about 600 years", never read as an age. */
export function kindSummary(shown: KindShown) {
  if (shown.years === null) return shown.kind === 'ageless' ? `Kind: ${shown.label}` : `Kind: ${shown.label} · doesn't age`
  return `Kind: ${shown.label} · lives about ${yearsText(shown.years)}`
}
