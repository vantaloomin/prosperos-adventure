// World packages and the world importer (docs/packages.md): words and checks for the Worlds screen.

export interface SectionCount { entries: number; hidden: number }
export interface PackageSummary { id: string; name: string; builtin: boolean; sections: Record<string, SectionCount>; documents: number; engine: number; assets: number; edited?: boolean }
export type SectionStatus = 'empty' | 'drafted' | 'approved'
export interface DraftSection { id: string; status: SectionStatus; from: '' | 'lorebook' | 'model'; entries: Record<string, unknown>[]; hidden: number }
export interface Draft { id: string; name: string; created_at: string; documents: string[]; notes: string[]; sections: DraftSection[]; waiting: string[]; problems: string[]; ready: boolean }
export interface DraftListing { id: string; name: string; created_at: string }

export const SECTION_NAMES: Record<string, string> = {
  lore: 'Lore', regions: 'Regions', settlements: 'Settlements', factions: 'Factions', deities: 'Powers',
  cast: 'Cast', personas: 'Personas', 'hidden-truths': 'Hidden truths', beats: 'Planned beats',
}

export const sectionName = (id: string) => SECTION_NAMES[id] ?? id

const plural = (count: number, one: string, many = `${one}s`) => `${count} ${count === 1 ? one : many}`

/** What a package holds, in one line: its biggest sections first. */
export function packageLine(summary: PackageSummary): string {
  const parts = Object.entries(summary.sections)
    .filter(([, count]) => count.entries > 0)
    .sort(([, a], [, b]) => b.entries - a.entries)
    .map(([id, count]) => `${sectionName(id)} ${count.entries}`)
  if (summary.documents) parts.push(plural(summary.documents, 'document'))
  return parts.join(' · ') || 'Empty'
}

export function hiddenTotal(summary: PackageSummary): number {
  return Object.values(summary.sections).reduce((total, count) => total + count.hidden, 0)
}

export function statusLine(section: DraftSection): string {
  if (section.status === 'approved') return `Approved · ${plural(section.entries.length, 'entry', 'entries')}`
  if (section.status === 'empty') return 'Not drafted'
  const from = section.from === 'lorebook' ? 'from your lorebook' : 'by the model'
  return `Drafted ${from}, ready for you to read · ${plural(section.entries.length, 'entry', 'entries')}`
}

/** The warning on a section whose entries hold a truth the player must not see. */
export function hiddenLine(section: Pick<DraftSection, 'id' | 'hidden' | 'entries'>): string {
  if (!section.hidden) return ''
  if (section.id === 'hidden-truths') return 'Every entry here is hidden from the player.'
  return `${plural(section.hidden, 'entry holds', 'entries hold')} a hidden truth (a secret field). The player never sees it.`
}

export type Parsed = { entries: Record<string, unknown>[] } | { error: string }

/** A section's entries as the author typed them: a JSON list of objects. */
export function parseEntries(text: string): Parsed {
  let value: unknown
  try { value = JSON.parse(text) } catch (failure) { return { error: `That is not valid JSON: ${failure instanceof Error ? failure.message : 'check the brackets and commas.'}` } }
  if (!Array.isArray(value)) return { error: 'A section is a list of entries: start with [ and end with ].' }
  const bad = value.findIndex((item) => typeof item !== 'object' || item === null || Array.isArray(item))
  if (bad >= 0) return { error: `Entry ${bad + 1} is not an object: each entry goes in { }.` }
  return { entries: value as Record<string, unknown>[] }
}

/** The world's name from the files when the author has not typed one: the first file's name, tidied. */
export function nameFromFiles(names: string[]): string {
  const first = names[0]?.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim() ?? ''
  return first ? first[0].toUpperCase() + first.slice(1) : ''
}

export const IMPORT_TYPES = '.md,.markdown,.txt,.json,text/markdown,text/plain,application/json'
