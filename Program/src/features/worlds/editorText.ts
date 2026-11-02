// The world editor (docs/packages.md "The editor"): the shapes it reads, and an entry turned into form fields and back.
import { SECTION_NAMES } from './packagesText.ts'

export interface EditorSection { id: string; name: string; entries: number; hidden: number }
export interface EditorRow { section: string; id: string; name: string; hidden: boolean }
export interface EditorListing { sections: EditorSection[]; entries: EditorRow[] }
export interface EntryLink { section: string; id: string; field: string }
export interface EditorEntry { section: string; entry: Record<string, unknown>; hidden: boolean; hidden_fields: string[]; names: EntryLink[]; named_by: EntryLink[] }
export interface EditorChange { id: number; at: string; section: string; entry_id: string; change: 'added' | 'changed' | 'deleted' }
export type HiddenFilter = 'all' | 'hidden' | 'open'

export const HIDDEN_FIELDS = ['secret', 'secrets', 'guise', 'mortal_life', 'truth', 'hidden']

/** How a field is edited on the form: short text, long text, a number, a switch, or JSON for lists and objects. */
export type FieldKind = 'line' | 'text' | 'number' | 'switch' | 'json'
export interface FormField { key: string; kind: FieldKind; text: string; checked: boolean; hidden: boolean }

export function kindOf(value: unknown): FieldKind {
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'switch'
  if (typeof value === 'string') return value.length > 80 || value.includes('\n') ? 'text' : 'line'
  return 'json'
}

/** The entry as form fields, id first, in the order the entry keeps them. */
export function formFields(entry: Record<string, unknown>, section = ''): FormField[] {
  const keys = ['id', ...Object.keys(entry).filter((key) => key !== 'id')]
  return keys.map((key) => {
    const value = entry[key] ?? ''
    const kind = kindOf(value)
    const text = kind === 'json' ? JSON.stringify(value, null, 1) : kind === 'switch' ? '' : String(value)
    return { key, kind, text, checked: value === true, hidden: section === 'hidden-truths' || HIDDEN_FIELDS.includes(key) }
  })
}

export type Built = { entry: Record<string, unknown> } | { error: string }

function valueOf(field: FormField): unknown {
  if (field.kind === 'switch') return field.checked
  if (field.kind === 'number') return Number(field.text)
  if (field.kind === 'json') return JSON.parse(field.text)
  return field.text
}

/** The form back into an entry; a field's JSON that will not read, or a number that is not one, is named. */
export function entryFrom(fields: FormField[]): Built {
  const entry: Record<string, unknown> = {}
  for (const field of fields) {
    try { entry[field.key] = valueOf(field) } catch { return { error: `${field.key} is not valid JSON: check its brackets and commas.` } }
    if (field.kind === 'number' && Number.isNaN(entry[field.key])) return { error: `${field.key} must be a number.` }
  }
  return { entry }
}

/** The raw view's text read back as one entry. */
export function parseEntry(text: string): Built {
  let value: unknown
  try { value = JSON.parse(text) } catch (failure) { return { error: `That is not valid JSON: ${failure instanceof Error ? failure.message : 'check the brackets and commas.'}` } }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return { error: 'An entry is one object, in { }.' }
  return { entry: value as Record<string, unknown> }
}

/** A kebab-case id from a name, for a new entry. */
export function idFrom(name: string): string {
  return name.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

/** A new entry's starting fields: the ones every entry of the section is likely to have. */
export function blankEntry(section: string): Record<string, unknown> {
  if (section === 'lore' || section === 'hidden-truths' || section === 'beats') return { id: '', title: '', text: '' }
  return { id: '', name: '', description: '' }
}

export const linkName = (link: EntryLink) => `${SECTION_NAMES[link.section] ?? link.section}: ${link.id}`

export function changeLine(change: EditorChange): string {
  const verb = change.change === 'added' ? 'Added' : change.change === 'deleted' ? 'Deleted' : 'Changed'
  return `${verb} ${change.entry_id} in ${SECTION_NAMES[change.section] ?? change.section}`
}

export function listingQuery(section: string, query: string, hidden: HiddenFilter): string {
  const params = new URLSearchParams()
  if (section) params.set('section', section)
  if (query.trim()) params.set('q', query.trim())
  if (hidden !== 'all') params.set('hidden', String(hidden === 'hidden'))
  const text = params.toString()
  return text ? `?${text}` : ''
}
