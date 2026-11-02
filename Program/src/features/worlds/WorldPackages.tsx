import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, EyeOff, FolderOutput, Pencil, Sparkles, Trash2, Upload, X } from 'lucide-react'
import { api } from '../../api'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { TextInput, Toggle } from '../../components/Fields'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { shownPath } from '../../paths'
import { WorldEditor } from './WorldEditor'
import { hiddenLine, hiddenTotal, IMPORT_TYPES, nameFromFiles, packageLine, parseEntries, sectionName, statusLine, type Draft, type DraftListing, type DraftSection, type PackageSummary } from './packagesText'

const PACKAGES_KEY = ['packages']
const DRAFTS_KEY = ['package-drafts']
const draftKey = (id: string) => ['package-draft', id]
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

/** The world packages on this computer and the world importer (docs/packages.md). */
export function WorldPackages() {
  const packages = useQuery({ queryKey: PACKAGES_KEY, queryFn: () => api<{ packages: PackageSummary[] }>('/packages') })
  const drafts = useQuery({ queryKey: DRAFTS_KEY, queryFn: () => api<{ drafts: DraftListing[] }>('/packages/drafts') })
  const [open, setOpen] = useState('')
  const [importing, setImporting] = useState(false)
  if (packages.isPending || drafts.isPending) return <Loading label="Loading world packages" />
  if (packages.isError) return <ErrorNotice error={packages.error} />
  if (drafts.isError) return <ErrorNotice error={drafts.error} />
  return (
    <section className="world-packages" aria-labelledby="world-packages-heading">
      <h3 id="world-packages-heading">World packages</h3>
      <p className="subtle">Each world is one file you can share. Import an existing world from its documents and lorebook: a model drafts each part for you to read, change and approve before it is used.</p>
      <ul className="city-list">
        {packages.data.packages.map((item) => <PackageCard key={item.id} item={item} />)}
      </ul>
      {drafts.data.drafts.length > 0 && <>
        <h4>Imports to review</h4>
        <ul className="city-list">
          {drafts.data.drafts.map((item) => (
            <li key={item.id} className="city-card">
              <h4>{item.name}</h4>
              {open === item.id
                ? <DraftReview id={item.id} onClose={() => setOpen('')} />
                : <div className="form-actions"><button type="button" className="button" onClick={() => setOpen(item.id)}><Pencil aria-hidden="true" />Review</button></div>}
            </li>
          ))}
        </ul>
      </>}
      {importing
        ? <ImportWorld onCancel={() => setImporting(false)} onStarted={(id) => { setImporting(false); setOpen(id) }} />
        : <div className="form-actions"><button type="button" className="button" onClick={() => setImporting(true)}><Upload aria-hidden="true" />Import a world</button></div>}
    </section>
  )
}

function PackageCard({ item }: { item: PackageSummary }) {
  const [busy, error, run] = useRun()
  const [folder, setFolder] = useState('')
  const [editing, setEditing] = useState(false)
  const hidden = hiddenTotal(item)
  return (
    <li className="city-card">
      <h4>{item.name}{item.builtin && <span className="subtle">{item.edited ? 'Built in, edited' : 'Built in'}</span>}</h4>
      <p className="subtle">{packageLine(item)}</p>
      {hidden > 0 && <p className="subtle"><EyeOff aria-hidden="true" className="inline-icon" /> {hidden} hidden {hidden === 1 ? 'truth' : 'truths'}, kept from the player</p>}
      {editing && <WorldEditor item={item} onClose={() => setEditing(false)} />}
      <div className="form-actions">
        {!editing && <button type="button" className="button" onClick={() => setEditing(true)}><Pencil aria-hidden="true" />Edit the world</button>}
        <button type="button" className="button" disabled={!!busy} onClick={() => void run('export', async () => {
          setFolder((await api<{ folder: string }>(`/packages/${item.id}/export`, {})).folder)
        })}><FolderOutput aria-hidden="true" />{busy ? 'Exporting…' : 'Export as a folder'}</button>
      </div>
      {folder && <Notice tone="success">Written to {shownPath(folder)}. Edit the Markdown and JSON there for bulk changes.</Notice>}
      {error && <Notice tone="error">{error}</Notice>}
    </li>
  )
}

function ImportWorld({ onCancel, onStarted }: { onCancel: () => void; onStarted: (id: string) => void }) {
  const client = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [name, setName] = useState('')
  const [busy, error, run] = useRun()
  const start = () => void run('start', async () => {
    const read = await Promise.all(files.map(async (file) => ({ name: file.name, text: await file.text() })))
    const draft = await api<Draft>('/packages/drafts', { name: name.trim() || nameFromFiles(files.map((file) => file.name)), files: read })
    client.setQueryData(draftKey(draft.id), draft)
    await client.invalidateQueries({ queryKey: DRAFTS_KEY })
    onStarted(draft.id)
  })
  return (
    <div className="city-editor">
      <h4>Import a world</h4>
      <p className="subtle">Add the world's documents (Markdown or text) and its lorebook (JSON from the Lore screen's formats). Documents are kept as written.</p>
      <TextInput label="World name" value={name} onChange={setName} maxLength={120} placeholder={nameFromFiles(files.map((file) => file.name))} />
      <div className="form-actions">
        <button type="button" className="button" onClick={() => input.current?.click()}><Upload aria-hidden="true" />{files.length ? `${files.length} ${files.length === 1 ? 'file' : 'files'} chosen` : 'Choose files'}</button>
        <input ref={input} type="file" multiple accept={IMPORT_TYPES} hidden aria-label="The world's files"
          onChange={(event) => { setFiles(Array.from(event.target.files ?? [])); event.target.value = '' }} />
        <button type="button" className="button primary" disabled={!files.length || !!busy} onClick={start}>{busy ? 'Reading…' : 'Start the import'}</button>
        <button type="button" className="button" onClick={onCancel}>Cancel</button>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
    </div>
  )
}

function DraftReview({ id, onClose }: { id: string; onClose: () => void }) {
  const client = useQueryClient()
  const draft = useQuery({ queryKey: draftKey(id), queryFn: () => api<Draft>(`/packages/drafts/${id}`) })
  const [busy, error, run] = useRun()
  const [replace, setReplace] = useState(false)
  const [discarding, setDiscarding] = useState(false)
  if (draft.isPending) return <Loading label="Opening the import" />
  if (draft.isError) return <ErrorNotice error={draft.error} />
  const data = draft.data
  const store = (next: Draft) => client.setQueryData(draftKey(id), next)
  const done = async () => { await client.invalidateQueries({ queryKey: DRAFTS_KEY }); await client.invalidateQueries({ queryKey: PACKAGES_KEY }); onClose() }
  return (
    <div className="package-review">
      <p className="subtle">{data.documents.length} {data.documents.length === 1 ? 'document' : 'documents'} kept as written. Draft each part you want, read it, then approve it. Parts you leave empty stay out.</p>
      {data.notes.map((note) => <p key={note} className="subtle">{note}</p>)}
      <ul className="city-list">
        {data.sections.map((section) => <SectionCard key={section.id} draftId={id} section={section} canDraft={data.documents.length > 0} store={store} />)}
      </ul>
      <Problems problems={data.problems} />
      <Toggle label="Replace a package with the same name" checked={replace} onChange={setReplace} />
      <div className="form-actions">
        <button type="button" className="button primary" disabled={!data.ready || !!busy} onClick={() => void run('finish', async () => { await api(`/packages/drafts/${id}/finish`, { replace }); await done() })}><Check aria-hidden="true" />{busy === 'finish' ? 'Writing…' : 'Write the package'}</button>
        <button type="button" className="button" onClick={onClose}>Close</button>
        <button type="button" className="button danger" onClick={() => setDiscarding(true)}><Trash2 aria-hidden="true" />Discard the import</button>
      </div>
      {data.waiting.length > 0 && <p className="subtle">Still to read: {data.waiting.map(sectionName).join(', ')}.</p>}
      {error && <Notice tone="error">{error}</Notice>}
      {discarding && <ConfirmDialog title={`Discard the ${data.name} import?`} onClose={() => setDiscarding(false)} actions={<>
        <button type="button" className="button" onClick={() => setDiscarding(false)}>Keep it</button>
        <button type="button" className="button danger" onClick={() => void run('discard', async () => { await api(`/packages/drafts/${id}`, undefined, 'DELETE'); setDiscarding(false); await done() })}>Discard</button>
      </>}>Everything drafted and approved here is lost. Your own files are not touched.</ConfirmDialog>}
    </div>
  )
}

function Problems({ problems }: { problems: string[] }) {
  if (!problems.length) return null
  const more = problems.length > 6 ? ` (and ${problems.length - 6} more)` : ''
  return <Notice tone="warning">Fix these before the package is written: {problems.slice(0, 6).join('; ')}{more}.</Notice>
}

interface SectionCardProps { draftId: string; section: DraftSection; canDraft: boolean; store: (draft: Draft) => void }

function SectionCard({ draftId, section, canDraft, store }: SectionCardProps) {
  const [busy, error, run, setError] = useRun()
  const [editing, setEditing] = useState<string | null>(null)
  const path = `/packages/drafts/${draftId}/sections/${section.id}`
  const put = (status: string, entries?: Record<string, unknown>[]) => run(status, async () => { store(await api<Draft>(path, { status, entries }, 'PUT')); setEditing(null) })
  const save = () => {
    const parsed = parseEntries(editing ?? '')
    if ('error' in parsed) setError(parsed.error)
    else void put('approved', parsed.entries)
  }
  const warning = hiddenLine(section)
  return (
    <li className="city-card package-section">
      <h4>{sectionName(section.id)}</h4>
      <p className="subtle">{statusLine(section)}</p>
      {warning && <p className="hidden-warning"><EyeOff aria-hidden="true" className="inline-icon" /> {warning}</p>}
      {editing !== null
        ? <textarea className="city-json" rows={14} value={editing} aria-label={`${sectionName(section.id)} entries`} onChange={(event) => setEditing(event.target.value)} />
        : section.entries.length > 0 && <EntryList section={section} />}
      <div className="form-actions">
        {editing !== null
          ? <>
              <button type="button" className="button primary" disabled={!!busy} onClick={save}><Check aria-hidden="true" />Save and approve</button>
              <button type="button" className="button" onClick={() => { setEditing(null); setError('') }}>Cancel</button>
            </>
          : <SectionActions section={section} canDraft={canDraft} busy={busy}
              onDraft={() => void run('draft', async () => { store(await api<Draft>(`${path}/draft`, {})) })}
              onEdit={() => setEditing(JSON.stringify(section.entries, null, 1))}
              onApprove={() => void put('approved')} onClear={() => void put('empty')} />}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
    </li>
  )
}

interface SectionActionsProps { section: DraftSection; canDraft: boolean; busy: string; onDraft: () => void; onEdit: () => void; onApprove: () => void; onClear: () => void }

function SectionActions({ section, canDraft, busy, onDraft, onEdit, onApprove, onClear }: SectionActionsProps) {
  const has = section.entries.length > 0
  return <>
    {canDraft && <button type="button" className="button" disabled={!!busy} onClick={onDraft}><Sparkles aria-hidden="true" />{busy === 'draft' ? 'Drafting…' : has ? 'Draft again' : 'Draft with the model'}</button>}
    <button type="button" className="button" disabled={!!busy} onClick={onEdit}><Pencil aria-hidden="true" />{has ? 'Edit' : 'Write it yourself'}</button>
    {section.status === 'drafted' && <button type="button" className="button primary" disabled={!!busy} onClick={onApprove}><Check aria-hidden="true" />Approve</button>}
    {has && <button type="button" className="button" disabled={!!busy} onClick={onClear}><X aria-hidden="true" />Clear</button>}
  </>
}

/** The section's entries by name, the ones with a hidden truth marked. */
function EntryList({ section }: { section: DraftSection }) {
  return (
    <details>
      <summary>{section.entries.length} {section.entries.length === 1 ? 'entry' : 'entries'}</summary>
      <ul className="package-entries">
        {section.entries.map((entry) => {
          const label = String(entry.name ?? entry.title ?? entry.id)
          const secret = section.id === 'hidden-truths' || ['secret', 'secrets', 'guise', 'mortal_life', 'truth', 'hidden'].some((field) => entry[field])
          return <li key={String(entry.id)}>{label}{secret && <span className="hidden-tag"><EyeOff aria-hidden="true" className="inline-icon" />hidden</span>}</li>
        })}
      </ul>
    </details>
  )
}
