import type { MixValues, TownsfolkMix } from '../../types'

/** Shares as the town would have them, in words, for Worlds > Townsfolk mix (dungeon/world/mix.py). */

export const BOLDER_LABELS: Record<string, string> = { '-2': 'Much tamer', '-1': 'Tamer', '0': 'As built', '1': 'Bolder', '2': 'Much bolder' }
export const DRIVE_LABELS: Record<string, string> = { '-2': 'Much lower', '-1': 'Lower', '0': 'As built', '1': 'Higher', '2': 'Much higher' }
export const LEVEL_NAMES: Record<string, string> = { reserved: 'reserved', conventional: 'conventional', curious: 'curious', adventurous: 'adventurous', wild: 'wild' }
const MOST_QUEER = 0.95

export function pct(value: number): string {
  const rounded = Math.round(value * 10) / 10
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}%`
}

/** Women, men and nonbinary people as shares of everyone, as generators.name draws them in a modern world. */
export function genderShares(mix: Pick<MixValues, 'nonbinary' | 'women'>) {
  const rest = 100 - mix.nonbinary
  return { woman: rest * mix.women / 100, man: rest * (100 - mix.women) / 100, nonbinary: mix.nonbinary }
}

/** Slender, in between and heavier as shares of the three together. */
export function buildShares(mix: Pick<MixValues, 'slender' | 'middle' | 'heavier'>) {
  const total = mix.slender + mix.middle + mix.heavier
  if (!total) return { slender: 0, middle: 0, heavier: 0 }
  return { slender: 100 * mix.slender / total, middle: 100 * mix.middle / total, heavier: 100 * mix.heavier / total }
}

/** Each age band's rates under the mix: the sliders scale every band alike (mix.orientation_band). */
export function bandRates(data: Pick<TownsfolkMix, 'bands' | 'defaults'>, mix: Pick<MixValues, 'gay' | 'bisexual'>) {
  return data.bands.map((band) => {
    const gay = Math.min(band.gay * mix.gay / data.defaults.gay, MOST_QUEER)
    const scale = mix.bisexual / data.defaults.bisexual
    const women = Math.min(band.bisexual_women * scale, MOST_QUEER - gay)
    const men = Math.min(band.bisexual_men * scale, MOST_QUEER - gay)
    return { ages: band.ages, gay: 100 * gay, bisexual: 100 * (women + men) / 2 }
  })
}

export function bandLine(rates: { ages: string; value: number }[]): string {
  return rates.map((rate) => `${rate.ages}: ${pct(rate.value)}`).join(', ')
}

export function sharesLine(shares: Record<string, number> | undefined, names: Record<string, string>): string {
  if (!shares) return ''
  return Object.entries(names).map(([key, name]) => `${pct(shares[key] ?? 0)} ${name}`).join(', ')
}

export function sameMix(a: MixValues, b: MixValues): boolean {
  return (Object.keys(b) as (keyof MixValues)[]).every((key) => Number(a[key]) === Number(b[key]))
}

export type BuildKey = 'slender' | 'middle' | 'heavier'
const BUILD_KEYS: BuildKey[] = ['slender', 'middle', 'heavier']

/** Moving one build slider gives the other two what is left, in the proportion they had, so the three always make
 * 100% (both at 0: shared evenly). Values land on the slider's half-percent steps. */
export function rebalanceBuilds(mix: MixValues, key: BuildKey, value: number): MixValues {
  const others = BUILD_KEYS.filter((other) => other !== key)
  const rest = 100 - value
  const before = others.reduce((sum, other) => sum + mix[other], 0)
  const first = Math.round((before ? rest * mix[others[0]] / before : rest / 2) * 2) / 2
  return { ...mix, [key]: value, [others[0]]: first, [others[1]]: rest - first }
}

const HEIGHT_KEYS = new Set(['height_woman', 'height_man'])

export function heightWords(cm: number): string {
  const inches = Math.round(cm / 2.54)
  return `${Math.floor(inches / 12)} foot ${inches % 12}, ${cm} cm`
}

/** What a screen reader says for a slider's value. */
export function valueText(key: keyof MixValues, value: number, steps?: Record<string, string>): string {
  if (steps) return steps[String(value)] ?? String(value)
  if (HEIGHT_KEYS.has(key)) return heightWords(value)
  const what: Partial<Record<keyof MixValues, string>> = {
    nonbinary: 'nonbinary', women: 'women', slender: 'slender', middle: 'in between', heavier: 'heavier',
    beard: 'of men with facial hair', gay: 'gay or lesbian', bisexual: 'bisexual',
  }
  return `${pct(value).replace('%', ' percent')} ${what[key] ?? ''}`.trim()
}

const CHANGE_WORDS: Record<keyof MixValues, [string, string]> = {
  nonbinary: ['fewer nonbinary people', 'more nonbinary people'], women: ['more men', 'more women'],
  height_woman: ['shorter women', 'taller women'], height_man: ['shorter men', 'taller men'],
  slender: ['fewer slender builds', 'more slender builds'], middle: ['fewer in-between builds', 'more in-between builds'],
  heavier: ['fewer heavier builds', 'more heavier builds'], beard: ['less facial hair', 'more facial hair'],
  gay: ['fewer gay and lesbian people', 'more gay and lesbian people'], bisexual: ['fewer bisexual people', 'more bisexual people'],
  bolder: ['a tamer adult side', 'a bolder adult side'], drive: ['lower drive', 'higher drive'],
}

/** "more heavier builds, taller men": what differs from the built-in mix, for the confirmation. */
export function changesLine(mix: MixValues, defaults: MixValues): string {
  return (Object.keys(CHANGE_WORDS) as (keyof MixValues)[])
    .filter((key) => Number(mix[key]) !== Number(defaults[key]))
    .map((key) => CHANGE_WORDS[key][Number(mix[key]) > Number(defaults[key]) ? 1 : 0]).join(', ')
}
