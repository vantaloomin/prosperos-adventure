import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Braces, Check, EyeOff, FileText, Link2, Plus, RotateCcw, Trash2, Undo2, X } from 'lucide-react'
import { api } from '../../api'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { Field, TextArea, TextInput, Toggle } from '../../components/Fields'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { blankEntry, changeLine, entryFrom, formFields, idFrom, linkName, listingQuery, parseEntry, type EditorChange, type EditorEntry, type EditorListing, type EntryLink, type FormField, type HiddenFilter } from './editorText'
import { sectionName, type PackageSummary } from './packagesText'

interface Opened { section: string; id: string }
type Run = (label: string, action: () => Promise<unknown>) => Promise<void>

function useRun(): [string, string, Run, (text: string) => void] {
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const run: Run = async (label, action) => {
    if (busy) return
    setBusy(label)
    setError('')
    try { await action() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work. Try again.') } finally { setBusy('') }
  }
  return [busy, error, run, setError]
}

function useRefresh(worldId: string) {
  const client = useQueryClient()
  return async () => {
    await client.invalidateQueries({ queryKey: ['package-entries', worldId] })
    await client.invalidateQueries({ queryKey: ['package-entry', worldId] })
    await client.invalidateQueries({ queryKey: ['package-history', worldId] })
    await client.invalidateQueries({ queryKey: ['packages'] })
  }
}

/** A world's entries, searched, opened, changed and undone (docs/packages.md "The editor"). */
export function WorldEditor({ item, onClose }: { item: PackageSummary; onClose: () => void }) {
  const [section, setSection] = useState('')
  const [query, setQuery] = useState('')
  const [hidden, setHidden] = useState<HiddenFilter>('all')
  const [opened, setOpened] = useState<Opened | null>(null)
  const listing = useQuery({ queryKey: ['package-entries', item.id, section, query, hidden], queryFn: () => api<EditorListing>(`/packages/${item.id}/entries${listingQuery(section, query, hidden)}`) })
  return (
    <div className="world-editor">
      <EditorFilters listing={listing.data} section={section} query={query} hidden={hidden} onSection={setSection} onQuery={setQuery} onHidden={setHidden} />
      {listing.isPending && <Loading label="Loading the entries" />}
      {listing.isError && <ErrorNotice error={listing.error} />}
      {listing.data && (opened
        ? <EntryLoader worldId={item.id} opened={opened} onOpen={setOpened} onClose={() => setOpened(null)} />
        : <EntryRows listing={listing.data} onOpen={setOpened} />)}
      <div className="form-actions">
        {!opened && <button type="button" className="button" onClick={() => setOpened({ section: section || 'lore', id: '' })}><Plus aria-hidden="true" />New {sectionName(section || 'lore').toLowerCase()} entry</button>}
        <button type="button" className="button" onClick={onClose}><X aria-hidden="true" />Close the editor</button>
      </div>
      <EditorHistory item={item} onUndone={() => setOpened(null)} />
    </div>
  )
}

interface FiltersProps { listing?: EditorListing; section: string; query: string; hidden: HiddenFilter; onSection: (value: string) => void; onQuery: (value: string) => void; onHidden: (value: HiddenFilter) => void }

function EditorFilters({ listing, section, query, hidden, onSection, onQuery, onHidden }: FiltersProps) {
  return (
    <div className="editor-filters">
      <Field label="Section">
        {(id) => <select id={id} value={section} onChange={(event) => onSection(event.target.value)}>
          <option value="">All sections</option>
          {listing?.sections.map((item) => <option key={item.id} value={item.id}>{sectionName(item.id)} ({item.entries})</option>)}
        </select>}
      </Field>
      <TextInput label="Search" value={query} onChange={onQuery} maxLength={120} placeholder="Words in an entry" />
      <Field label="Hidden truths">
        {(id) => <select id={id} value={hidden} onChange={(event) => onHidden(event.target.value as HiddenFilter)}>
          <option value="all">All entries</option>
          <option value="hidden">Only entries with a hidden truth</option>
          <option value="open">Only entries without one</option>
        </select>}
      </Field>
    </div>
  )
}

function EntryRows({ listing, onOpen }: { listing: EditorListing; onOpen: (opened: Opened) => void }) {
  if (!listing.entries.length) return <p className="subtle">No entries match.</p>
  return (
    <ul className="package-entries editor-rows">
      {listing.entries.map((row) => (
        <li key={`${row.section}/${row.id}`}>
          <button type="button" className="text-button" onClick={() => onOpen({ section: row.section, id: row.id })}>{row.name}</button>
          <span className="subtle"> {sectionName(row.section)}</span>
          {row.hidden && <span className="hidden-tag"><EyeOff aria-hidden="true" className="inline-icon" />hidden</span>}
        </li>
      ))}
    </ul>
  )
}

interface LoaderProps { worldId: string; opened: Opened; onOpen: (opened: Opened) => void; onClose: () => void }

function EntryLoader({ worldId, opened, onOpen, onClose }: LoaderProps) {
  const found = useQuery({ queryKey: ['package-entry', worldId, opened.section, opened.id], enabled: !!opened.id,
    queryFn: () => api<EditorEntry>(`/packages/${worldId}/entries/${opened.section}/${encodeURIComponent(opened.id)}`) })
  if (!opened.id) return <EntryForm key={`new/${opened.section}`} worldId={worldId} section={opened.section} onOpen={onOpen} onClose={onClose} />
  if (found.isPending) return <Loading label="Opening the entry" />
  if (found.isError) return <ErrorNotice error={found.error} />
  return <EntryForm key={`${opened.section}/${opened.id}`} worldId={worldId} section={opened.section} found={found.data} onOpen={onOpen} onClose={onClose} />
}

const withId = (entry: Record<string, unknown>) => ({ ...entry, id: String(entry.id || idFrom(String(entry.name ?? entry.title ?? ''))) })

interface FormProps { worldId: string; section: string; found?: EditorEntry; onOpen: (opened: Opened) => void; onClose: () => void }

function EntryForm({ worldId, section, found, onOpen, onClose }: FormProps) {
  const refresh = useRefresh(worldId)
  const [busy, error, run, setError] = useRun()
  const [fields, setFields] = useState<FormField[]>(() => formFields(found?.entry ?? blankEntry(section), section))
  const [raw, setRaw] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const oldId = found ? String(found.entry.id) : ''
  const path = `/packages/${worldId}/entries/${section}`
  const save = () => {
    const built = raw !== null ? parseEntry(raw) : entryFrom(fields)
    if ('error' in built) { setError(built.error); return }
    const entry = withId(built.entry)
    void run('save', async () => {
      const saved = await api<EditorEntry>(oldId ? `${path}/${encodeURIComponent(oldId)}` : path, { entry }, oldId ? 'PUT' : 'POST')
      await refresh()
      onOpen({ section, id: String(saved.entry.id) })
    })
  }
  const remove = () => void run('delete', async () => { await api(`${path}/${encodeURIComponent(oldId)}`, undefined, 'DELETE'); setDeleting(false); await refresh(); onClose() })
  const toRaw = () => { const built = entryFrom(fields); if ('error' in built) setError(built.error); else setRaw(JSON.stringify(built.entry, null, 1)) }
  const toForm = () => { const built = parseEntry(raw ?? ''); if ('error' in built) setError(built.error); else { setFields(formFields(built.entry, section)); setRaw(null) } }
  return (
    <div className="city-editor entry-editor">
      <EntryHeading section={section} found={found} />
      {raw !== null
        ? <textarea className="city-json" rows={16} value={raw} aria-label="The entry as JSON" onChange={(event) => setRaw(event.target.value)} />
        : fields.map((field, index) => <FieldInput key={field.key} field={field} onChange={(next) => setFields(fields.map((item, at) => at === index ? next : item))} />)}
      {found && <EntryLinks found={found} onOpen={onOpen} />}
      <EntryActions busy={busy} raw={raw !== null} canDelete={!!found} onSave={save} onView={raw !== null ? toForm : toRaw} onClose={onClose} onDelete={() => setDeleting(true)} />
      {error && <Notice tone="error">{error}</Notice>}
      {deleting && <ConfirmDialog title={`Delete ${oldId}?`} onClose={() => setDeleting(false)} actions={<>
        <button type="button" className="button" onClick={() => setDeleting(false)}>Keep it</button>
        <button type="button" className="button danger" disabled={!!busy} onClick={remove}>Delete</button>
      </>}>You can undo this from the editor's history.</ConfirmDialog>}
    </div>
  )
}

function EntryHeading({ section, found }: { section: string; found?: EditorEntry }) {
  const title = found ? String(found.entry.name ?? found.entry.title ?? found.entry.id) : `New ${sectionName(section).toLowerCase()} entry`
  const warning = section === 'hidden-truths' ? 'This whole entry is hidden from the player.' : `Hidden from the player: ${found?.hidden_fields.join(', ')}.`
  return <>
    <h4>{title}<span className="subtle">{sectionName(section)}</span></h4>
    {found?.hidden && <p className="hidden-warning"><EyeOff aria-hidden="true" className="inline-icon" /> {warning}</p>}
  </>
}

interface ActionsProps { busy: string; raw: boolean; canDelete: boolean; onSave: () => void; onView: () => void; onClose: () => void; onDelete: () => void }

function EntryActions({ busy, raw, canDelete, onSave, onView, onClose, onDelete }: ActionsProps) {
  return (
    <div className="form-actions">
      <button type="button" className="button primary" disabled={!!busy} onClick={onSave}><Check aria-hidden="true" />{busy === 'save' ? 'Saving…' : 'Save'}</button>
      <button type="button" className="button" onClick={onView}>{raw ? <><FileText aria-hidden="true" />Form view</> : <><Braces aria-hidden="true" />Raw view</>}</button>
      <button type="button" className="button" onClick={onClose}>Back to the list</button>
      {canDelete && <button type="button" className="button danger" onClick={onDelete}><Trash2 aria-hidden="true" />Delete</button>}
    </div>
  )
}

function FieldInput({ field, onChange }: { field: FormField; onChange: (field: FormField) => void }) {
  const label = field.hidden ? `${field.key} (hidden from the player)` : field.key
  const set = (text: string) => onChange({ ...field, text })
  if (field.kind === 'switch') return <Toggle label={label} checked={field.checked} onChange={(checked) => onChange({ ...field, checked })} />
  if (field.kind === 'number') return <TextInput label={label} type="number" value={field.text} onChange={set} />
  if (field.kind === 'line') return <TextInput label={label} value={field.text} onChange={set} hint={field.key === 'id' ? 'Lowercase words joined by hyphens. Left empty, it comes from the name.' : undefined} />
  return <TextArea label={label} value={field.text} onChange={set} rows={field.kind === 'json' ? 5 : 6} hint={field.kind === 'json' ? 'JSON' : undefined} />
}

function EntryLinks({ found, onOpen }: { found: EditorEntry; onOpen: (opened: Opened) => void }) {
  const row = (title: string, links: EntryLink[]) => links.length > 0 && (
    <p className="subtle"><Link2 aria-hidden="true" className="inline-icon" /> {title}: {links.map((link, index) => <span key={`${link.section}/${link.id}/${link.field}`}>
      {index > 0 && ', '}<button type="button" className="text-button" onClick={() => onOpen({ section: link.section, id: link.id })}>{linkName(link)}</button> ({link.field})
    </span>)}</p>
  )
  return <>{row('Names', found.names)}{row('Named by', found.named_by)}</>
}

function EditorHistory({ item, onUndone }: { item: PackageSummary; onUndone: () => void }) {
  const refresh = useRefresh(item.id)
  const history = useQuery({ queryKey: ['package-history', item.id], queryFn: () => api<{ history: EditorChange[] }>(`/packages/${item.id}/history`) })
  const [busy, error, run] = useRun()
  const [resetting, setResetting] = useState(false)
  const last = history.data?.history[0]
  const undo = () => void run('undo', async () => { await api(`/packages/${item.id}/undo`, {}); await refresh(); onUndone() })
  const reset = () => void run('reset', async () => { await api(`/packages/${item.id}/reset`, {}); setResetting(false); await refresh(); onUndone() })
  return (
    <div className="editor-history">
      {last && <p className="subtle">Last change: {changeLine(last)}.</p>}
      <div className="form-actions">
        {last && <button type="button" className="button" disabled={!!busy} onClick={undo}><Undo2 aria-hidden="true" />{busy === 'undo' ? 'Undoing…' : 'Undo it'}</button>}
        {item.builtin && item.edited && <button type="button" className="button danger" onClick={() => setResetting(true)}><RotateCcw aria-hidden="true" />Reset to how it shipped</button>}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {resetting && <ConfirmDialog title={`Reset ${item.name}?`} onClose={() => setResetting(false)} actions={<>
        <button type="button" className="button" onClick={() => setResetting(false)}>Keep my edits</button>
        <button type="button" className="button danger" disabled={!!busy} onClick={reset}>Reset</button>
      </>}>Every change made to this world here is lost, and it is rebuilt from the files it shipped with.</ConfirmDialog>}
    </div>
  )
}
