import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, RefreshCw, Trash2 } from 'lucide-react'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import { useRefetchOnFocus } from '../../paths'
import type { WorkspaceSettings, BackendCheck, BackendFiles, BackendKind, HostedProvider, ImageBackend, ImageFamily, ModelFiles, ModelLink, SamplerSettings, StyleLora } from '../../types'
import { Notice } from '../../components/Feedback'
import { useReturnFocus } from '../../components/returnFocus'
import { Field, TextArea, TextInput, Toggle } from '../../components/Fields'
import { BACKEND_KINDS, NSFW_PROVIDERS, PROVIDERS, disclosureFor } from '../images/imageState'
import { HardwareWarnings } from './models/HardwareCheck'
import { HARDWARE_KEY, useHardware, type HardwareReport } from './models/hardware'
import { FAMILIES, FAMILY_KEYS, MAX_STYLE_LORAS, MISSING, PRESET_FILES, missingFrom, NEW_STYLE_LORA, TURBO, familyOf, fileChoices, filesBody, filesLabel, hasMatching, isChosen, isTuned, linksByRole, noChoice, serverFiles, shownFiles, shownSampler, stylesBody, fitLine, type FileSlot } from './modelFiles'
import { SectionPending } from '../../components/SectionPending'
import { ImageModelField } from './ImageModelField'
import { LaunchFor } from './models/LocalPrograms'
import { imageKeyFrom } from './models/discovery'
import type { ModelsOverview } from './models/types'
import { SliderNumber } from '../../components/NumberFields'

const BACKENDS_KEY = ['image-backends']
type Result = { tone: 'info' | 'error'; text: string } | null
const failure = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback

/** Image backends (PRD F3). Everything is off until set up here. The story's pictures (Story, More, Pictures) are made
 *  on request; Passive art adds a few on its own (dungeon/art.py). */
export function ImageSettings() {
  const client = useQueryClient()
  const backends = useQuery({ queryKey: BACKENDS_KEY, queryFn: () => api<{ backends: ImageBackend[] }>('/images/backends') })
  const [result, setResult] = useState<Result>(null)
  const refresh = () => Promise.all([client.invalidateQueries({ queryKey: BACKENDS_KEY }), client.invalidateQueries({ queryKey: HARDWARE_KEY })])
  if (!backends.data) return <SectionPending queries={[backends]} heading="images-heading" title="Images" />
  const list = backends.data.backends
  const hasLocal = list.some((backend) => backend.enabled && backend.accepts_nsfw)
  return (
    <section className="settings-section form-stack" aria-labelledby="images-heading">
      <div>
        <h2 id="images-heading">Images</h2>
        <p className="subtle">Set up where pictures are made. Every request is checked on this computer first. NSFW requests only go to a ComfyUI server on this computer, or to an image API you switched to take NSFW; Codex, Google and the OpenAI API only ever receive safe requests, and some things are never made anywhere.</p>
      </div>
      {list.length === 0 && <p className="subtle">No image backend is set up yet.</p>}
      {list.length > 0 && !hasLocal && <p className="subtle">No enabled backend takes NSFW requests, so they will be refused.</p>}
      <Backends list={list} refresh={refresh} setResult={setResult} />
      <PassiveArt />
      {result && <Notice tone={result.tone}>{result.text}</Notice>}
    </section>
  )
}

/** Passive art: a few pictures made on their own from what happens in the story, off by default. */
function PassiveArt() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const [error, setError] = useState('')
  const save = async (passive_art: boolean) => {
    setError('')
    try { client.setQueryData(SETTINGS_KEY, await api<WorkspaceSettings>('/settings', { passive_art }, 'PUT')) }
    catch (failed) { setError(failure(failed, 'That setting was not saved.')) }
  }
  return <>
    <Toggle label="Passive art" hint="Pictures made on their own as you play: someone new in the scene, a new place, a chapter's end. At most one a turn and six a session; the story never waits for them."
      checked={Boolean(settings.data?.passive_art)} disabled={!settings.data} onChange={(checked) => void save(checked)} />
    {error && <Notice tone="error">{error}</Notice>}
  </>
}

/** The backends in the order they are tried, each with its controls, and adding another. */
function Backends({ list, refresh, setResult }: { list: ImageBackend[]; refresh: () => Promise<unknown>; setResult: (result: Result) => void }) {
  const [adding, setAdding] = useState(false)
  const addButton = useReturnFocus<HTMLButtonElement>(adding)
  const hardware = useHardware()
  return <>
    <ol className="backend-list">
      {list.map((backend, index) => <BackendRow key={backend.id} backend={backend} index={index} count={list.length} refresh={refresh} setResult={setResult} />)}
    </ol>
    {hardware.data && <HardwareWarnings warnings={hardware.data.warnings} area="images" />}
    {adding ? <AddBackend onDone={() => { setAdding(false); void refresh() }} setResult={setResult} />
      : <div className="form-actions"><button ref={addButton} type="button" className="button" onClick={() => setAdding(true)}>Add an image backend</button></div>}
  </>
}



/** Where a backend connects and how it draws. */
function BackendSetup({ backend, put, putWorkflow }: { backend: ImageBackend; put: (body: object) => Promise<boolean>; putWorkflow: (body: object) => Promise<string> }) {
  return <>
    <BackendConnection backend={backend} save={put} />
    <BackendStyle backend={backend} save={(style) => put({ style })} />
    <ComfyFiles backend={backend} put={put} />
    {backend.kind === 'comfyui' && <>
      <WorkflowEditor backend={backend} field="workflow" save={(value) => putWorkflow({ workflow: value })} />
      <WorkflowEditor backend={backend} field="reference_workflow" save={(value) => putWorkflow({ reference_workflow: value })} />
    </>}
  </>
}

function BackendRow({ backend, index, count, refresh, setResult }: { backend: ImageBackend; index: number; count: number; refresh: () => Promise<unknown>; setResult: (result: Result) => void }) {
  const [check, setCheck] = useState<BackendCheck | null>(null)
  const [busy, setBusy] = useState(false)
  // Busy controls are marked, not disabled: disabling the focused control would drop keyboard focus.
  const act = async (action: () => Promise<unknown>) => {
    if (busy) return false
    setBusy(true)
    try { await action(); await refresh(); setResult(null); return true } catch (error) { setResult({ tone: 'error', text: failure(error, 'That did not work.') }); return false } finally { setBusy(false) }
  }
  const pending = Boolean(backend.disclosure && !backend.disclosure_accepted)
  return (
    <li className="backend-row">
      <BackendSummary backend={backend} />
      {backend.blocked_reason && (
        <Notice tone="error" action={<button type="button" className="button" aria-disabled={busy} onClick={() => void act(() => api(`/images/backends/${backend.id}/unblock`, {}))}>{backend.kind === 'codex' ? 'Signed in again' : 'Try again'}</button>}>
          {backend.blocked_reason}
        </Notice>
      )}
      {pending && <p className="subtle">{backend.disclosure}</p>}
      <Toggle label="Enabled" checked={backend.enabled}
        onChange={(value) => void act(() => api(`/images/backends/${backend.id}`, { enabled: value, accept_disclosure: value && pending ? true : undefined }, 'PUT'))}
        hint={pending ? 'Turning it on accepts what it receives, described above.' : undefined} />
      {backend.nsfw_switch && <Toggle label="Also take NSFW requests" checked={backend.allows_nsfw}
        onChange={(value) => void act(() => api(`/images/backends/${backend.id}`, { allows_nsfw: value, accept_disclosure: value || undefined }, 'PUT'))}
        hint={backend.allows_nsfw ? 'NSFW requests go to this provider under its terms. Prohibited requests are never sent.' : 'Only for a provider whose terms allow NSFW images. Turning it on accepts that NSFW requests go to this provider and its terms decide what it makes and keeps. Every request is still checked on this computer first, and prohibited ones are never sent.'} />}
      {backend.kind === 'comfyui' && <FamilyPicker backend={backend} save={(body) => act(() => api(`/images/backends/${backend.id}`, body, 'PUT'))} />}
      <BackendSetup backend={backend} put={(body) => act(() => api(`/images/backends/${backend.id}`, body, 'PUT'))}
        putWorkflow={async (body) => {
          // A refused workflow says why beside its own box, not at the foot of the section.
          try { await api(`/images/backends/${backend.id}`, body, 'PUT'); await refresh(); return '' } catch (error) { return failure(error, 'That workflow could not be saved.') }
        }} />
      {check && <CheckResult key={JSON.stringify(check)} backend={backend} check={check} />}
      <div className="post-actions backend-actions">
        <button type="button" className="text-button" aria-disabled={busy} onClick={() => void act(async () => setCheck(await api<BackendCheck>(`/images/backends/${backend.id}/check`, {})))}>Check</button>
        <button type="button" className="text-button" aria-disabled={busy} disabled={index === 0} aria-label={`Move ${backend.label} up`} onClick={() => void act(() => api(`/images/backends/${backend.id}/move`, { position: index - 1 }))}><ArrowUp aria-hidden="true" />Up</button>
        <button type="button" className="text-button" aria-disabled={busy} disabled={index === count - 1} aria-label={`Move ${backend.label} down`} onClick={() => void act(() => api(`/images/backends/${backend.id}/move`, { position: index + 1 }))}><ArrowDown aria-hidden="true" />Down</button>
        <button type="button" className="text-button danger-text" aria-disabled={busy} onClick={() => void act(() => api(`/images/backends/${backend.id}`, undefined, 'DELETE'))}><Trash2 aria-hidden="true" />Remove</button>
        <LaunchFor id={backend.id} />
      </div>
    </li>
  )
}

/** What Check found. Notes that do not stop the backend sit under Details; a node pack the app can
 * install gets a button (Vanta approved one-press installs, 2026-10-13; wording and states per Iris). */
function CheckResult({ backend, check }: { backend: ImageBackend; check: BackendCheck }) {
  const [installing, setInstalling] = useState('')
  const [installed, setInstalled] = useState('')
  const [problem, setProblem] = useState('')
  const install = async (pack: { id: string; label: string }) => {
    if (installing) return
    setInstalling(pack.id); setProblem('')
    try {
      await api(`/images/backends/${backend.id}/install-nodes/${pack.id}`, {})
      setInstalled(pack.label)
    } catch (error) { setProblem(failure(error, `Couldn't install the ${pack.label} nodes. Try again.`)) } finally { setInstalling('') }
  }
  if (installed) return <Notice tone="success">{installed} nodes installed. Restart ComfyUI to load them, then press Check again.</Notice>
  const lines = <ul>{check.details.map((line) => <li key={line}>{line}</li>)}</ul>
  return (
    <Notice tone={check.ok ? 'info' : 'error'}>
      {check.summary}
      {check.details.length > 0 && (check.ok ? <details className="check-details"><summary>Details</summary>{lines}</details> : lines)}
      {(check.install ?? []).map((pack) => <div key={pack.id} className="node-install">
        {problem && <p className="node-install-problem" role="alert">{problem}</p>}
        <button type="button" className="button node-install-button" disabled={Boolean(installing)} onClick={() => void install(pack)}>
          {installing === pack.id ? 'Installing…' : `Install the ${pack.label} nodes`}
        </button>
        <p className="subtle node-install-note">Adds one folder to ComfyUI's custom_nodes. No Python packages.</p>
      </div>)}
    </Notice>
  )
}

interface ConnectionDraft { label: string; model: string; baseUrl: string; apiKey: string; cliPath: string }

const connectionDraft = (backend: ImageBackend): ConnectionDraft => ({ label: backend.label, model: backend.model, baseUrl: backend.base_url, apiKey: '', cliPath: backend.cli_path })
const editsAddress = (backend: ImageBackend) => backend.kind === 'comfyui' || (backend.kind === 'hosted' && backend.provider === 'other')
const movesAddress = (backend: ImageBackend, draft: ConnectionDraft) => editsAddress(backend) && draft.baseUrl.trim() !== backend.base_url

function connectionChanged(backend: ImageBackend, draft: ConnectionDraft): boolean {
  const saved = connectionDraft(backend)
  return movesAddress(backend, draft) || draft.apiKey !== '' || (['label', 'model', 'cliPath'] as const).some((key) => draft[key].trim() !== saved[key])
}

/** Only the fields this kind of backend uses; a new address is accepted on save, as its hint says. */
function connectionBody(backend: ImageBackend, draft: ConnectionDraft): Record<string, unknown> {
  const body: Record<string, unknown> = { label: draft.label.trim() || undefined }
  if (backend.kind === 'hosted') Object.assign(body, { model: draft.model.trim(), api_key: draft.apiKey || undefined })
  if (editsAddress(backend)) Object.assign(body, { base_url: draft.baseUrl.trim(), accept_disclosure: movesAddress(backend, draft) && backend.disclosure ? true : undefined })
  if (backend.kind === 'codex') body.cli_path = draft.cliPath.trim()
  return body
}

/** The backend's name and where it connects, edited in place: an image API's model, key and (for another
 * API) address, a ComfyUI server's address or the Codex CLI's location. */
function BackendConnection({ backend, save }: { backend: ImageBackend; save: (body: Record<string, unknown>) => Promise<boolean> }) {
  const [draft, setDraft] = useState(() => connectionDraft(backend))
  const set = (key: keyof ConnectionDraft) => (value: string) => setDraft((current) => ({ ...current, [key]: value }))
  const hosted = backend.kind === 'hosted'
  const store = async () => { if (await save(connectionBody(backend, draft))) setDraft((current) => ({ ...current, apiKey: '' })) }
  return (
    <details>
      <summary className="subtle">Connection</summary>
      <div className="form-stack">
        <TextInput label="Name" value={draft.label} onChange={set('label')} />
        {hosted && <TextInput label={backend.provider === 'novelai' ? 'API token' : 'API key'} type="password" value={draft.apiKey} onChange={set('apiKey')} placeholder={backend.has_key ? 'Saved; type a new one to replace it' : backend.key_from ? `Using the key saved with ${backend.key_from}` : ''} hint={backend.key_from ? 'Type a key only to use a different one here.' : keyHint(backend.provider)} />}
        <AddressField backend={backend} draft={draft} onChange={set('baseUrl')} />
        {hosted && <ImageModelField provider={backend.provider} baseUrl={draft.baseUrl} apiKey={draft.apiKey} backendId={backend.id} value={draft.model} onChange={set('model')} />}
        {backend.kind === 'codex' && <TextInput label="Codex CLI location (optional)" value={draft.cliPath} onChange={set('cliPath')} hint="Found on PATH when empty." />}
        {connectionChanged(backend, draft) && <div className="form-actions">
          <button type="button" className="button primary" onClick={() => void store()}>Save connection</button>
          <button type="button" className="button" onClick={() => setDraft(connectionDraft(backend))}>Cancel</button>
        </div>}
      </div>
    </details>
  )
}

/** A ComfyUI server's address, or another image API's base URL; the providers named in the list keep their own. */
function AddressField({ backend, draft, onChange }: { backend: ImageBackend; draft: ConnectionDraft; onChange: (value: string) => void }) {
  if (!editsAddress(backend)) return null
  const moveHint = movesAddress(backend, draft) && backend.disclosure ? `Saving sends requests to the new address. ${backend.disclosure}` : undefined
  return <TextInput label={backend.kind === 'hosted' ? 'API base URL' : 'ComfyUI address'} value={draft.baseUrl} required onChange={onChange} hint={moveHint} />
}

/** What an empty Prompt style falls back to, and the hint that says so. */
function styleFallback(backend: ImageBackend) {
  const fallback = backend.family_style ? "the model's own" : "the world's own"
  const hint = `Starts every prompt this backend makes, in place of the world's look. Leave empty to use ${fallback}.${
    backend.tag_prompts && !backend.family_style ? ' Prompts go out as booru tags.' : ''}`
  return { fallback, hint, reset: backend.family_style ? "Use the model's own style" : "Use the world's look" }
}

/** The style line that starts this backend's prompts, since each model wants its own (a photo line for
 * Krea 2, quality tags for a Booru model). Empty uses the model family's own line, else the world's look. */
function BackendStyle({ backend, save }: { backend: ImageBackend; save: (style: string) => Promise<boolean> }) {
  const [draft, setDraft] = useState<string | null>(null)
  const store = async (value: string) => { if (await save(value)) setDraft(null) }
  const { fallback, hint, reset } = styleFallback(backend)
  return (
    <details>
      <summary className="subtle">Prompt style {backend.style ? '(its own)' : `(${fallback})`}</summary>
      <div className="form-stack">
        <TextArea grows label="Style for this backend" value={draft ?? backend.style} maxLength={500}
          placeholder={backend.family_style || "The world's own look"} hint={hint} onChange={setDraft} />
        <div className="form-actions">
          {draft !== null && <>
            <button type="button" className="button primary" onClick={() => void store(draft)}>Save style</button>
            <button type="button" className="button" onClick={() => setDraft(null)}>Cancel</button>
          </>}
          {backend.style && draft === null && <button type="button" className="text-button" onClick={() => void store('')}>{reset}</button>}
        </div>
      </div>
    </details>
  )
}

/** Which kind of model this server runs, so the built-in workflow, its files, sampling and prompt style suit it
 * (Vanta, 2026-10-13). Krea 2 until changed; saved on change. A workflow of the user's own runs whatever it says. */
function FamilyPicker({ backend, save }: { backend: ImageBackend; save: (body: object) => Promise<boolean> }) {
  const hardware = useHardware()
  // What a switch replaced, so it can be undone (undo over confirm); only when the user had made choices.
  const [undo, setUndo] = useState<{ to: string; body: object; before: string; after: string | null } | null>(null)
  const family = familyOf(backend.family)
  const current = JSON.stringify([backend.family, backend.model_files, backend.sampler])
  // Offered only until this backend changes again, so it never undoes something stale (Iris): the state the
  // switch left is noted once it arrives, and any later change hides the notice.
  if (undo && undo.after === null && current !== undo.before) setUndo({ ...undo, after: current })
  const shown = undo && (undo.after ?? current) === current ? undo : null
  const choose = async (next: ImageFamily) => {
    const before = previous(backend)
    const was = current
    if (!(await save({ family: next })) || !before) return setUndo(null)
    setUndo({ to: FAMILIES[next].sampling, body: before, before: was, after: null })
  }
  return <div className="form-stack family-picker">
    <Field label="Model family" hint={familyHint(family, backend.custom_workflow, fitLine(backend.model_fit, backend.model_files, biggestCard(hardware.data)))}>{(id, describedBy) => (
      <select id={id} aria-describedby={describedBy} value={backend.family ?? 'krea2'} onChange={(event) => void choose(event.target.value as ImageFamily)}>
        {FAMILY_KEYS.map((key) => <option key={key} value={key}>{FAMILIES[key].label}</option>)}
      </select>
    )}</Field>
    {/* Its own muted line, so the sentence above reads the same for every family (Iris). */}
    {family.reference && !backend.reference_workflow && <p className="subtle family-reference">{family.reference}</p>}
    {shown && <div className="family-undo"><Notice action={<button type="button" className="text-button" onClick={() => void save(shown.body).then(() => setUndo(null))}>Undo</button>}>Switched to {shown.to} defaults.</Notice></div>}
  </div>
}

/** The memory of this computer's biggest graphics card, which the app picks model files for. */
const biggestCard = (report: HardwareReport | undefined) =>
  report?.computer.gpus.reduce<number | null>((most, gpu) => Math.max(most ?? 0, gpu.memory_gb), null) ?? null

/** The dropdown's hint (Iris's wording). */
function familyHint(family: ReturnType<typeof familyOf>, custom: boolean, fitted: string | null): string {
  if (custom) return 'Your own workflow is used for pictures; the family still sets the reference workflow.'
  const lines = [`Sets the built-in workflow, model files and sampling to ${family.sampling}'s. You can change any of them below.`]
  if (fitted) lines.push(fitted)
  if (family.note) lines.push(family.note)
  return lines.join(' ')
}

/** The family and the file and sampling choices a switch would replace, or null when nothing was chosen. */
function previous(backend: ImageBackend): object | null {
  const files = Object.fromEntries(Object.entries(backend.model_files ?? {}).filter(([, value]) => value))
  const sampler = Object.fromEntries(Object.entries(backend.sampler ?? {}).filter(([, value]) => value !== null))
  if (!Object.keys(files).length && !Object.keys(sampler).length) return null
  return { family: backend.family ?? 'krea2', ...files, ...sampler }
}

/** The built-in workflow's model, text encoder and VAE, picked from the files the ComfyUI server
 * lists. The server is only asked once this is opened; a server that cannot be asked takes typed names. */
function ModelFilePicker({ backend, saved, save }: { backend: ImageBackend; saved: ModelFiles; save: (files: ModelFiles) => Promise<boolean> }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<ModelFiles>({})
  const [familyOnly, setFamilyOnly] = useState(true)
  const family = familyOf(backend.family)
  const files = useBackendFiles(backend, open)
  const links = useQuery({ queryKey: ['image-model-links'], queryFn: () => api<{ links: ModelLink[] }>('/images/model-links'), enabled: open, staleTime: Infinity })
  const server = serverFiles(files.data, files.isError ? failure(files.error, 'The server could not be asked.') : null, saved)
  const shown = shownFiles(family.slots, draft, saved, server.defaults)
  const store = async (body: ModelFiles) => { if (await save(body)) setDraft({}) }
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="subtle">Model files for the built-in workflow {filesLabel(saved, backend.model_fit)}</summary>
      <div className="form-stack">
        <p className="subtle">Pick the files your ComfyUI server has. The lists come from the server at this backend's address; nothing is downloaded or installed.</p>
        {open && !server.answered && <p className="subtle">Asking ComfyUI for its files…</p>}
        {server.error && <Notice tone="error">{server.error} Type the file names instead.</Notice>}
        {hasMatching(server.matching) && <Toggle label={`Only ${family.short} files`} checked={familyOnly} onChange={setFamilyOnly}
          hint={`Files whose name or folder says ${family.looks}. Turn off to see every file.`} />}
        {server.answered && <FileSlots slots={family.slots} server={server} familyOnly={familyOnly} shown={shown} onChange={(key, value) => setDraft({ ...draft, [key]: value })} />}
        <FileActions changed={Object.keys(draft).length > 0} chosen={isChosen(saved)} busy={files.isFetching}
          save={() => void store(filesBody(family.slots, shown, server.defaults))} cancel={() => setDraft({})} reset={() => void store(noChoice(family.slots))} refresh={() => void files.refetch()} />
        <ModelLinks links={links.data?.links ?? []} family={backend.family} />
      </div>
    </details>
  )
}

type ServerFiles = ReturnType<typeof serverFiles>

function FileSlots({ slots, server, familyOnly, shown, onChange }: { slots: FileSlot[]; server: ServerFiles; familyOnly: boolean; shown: ModelFiles; onChange: (key: FileSlot['key'], value: string) => void }) {
  return <div className="form-grid">
    {slots.map((slot) => <FileField key={slot.key} slot={slot} options={server.options[slot.key]} matching={familyOnly ? server.matching[slot.key] : []}
      value={shown[slot.key] ?? ''} fallback={server.defaults[slot.key] ?? ''} onChange={(value) => onChange(slot.key, value)} />)}
  </div>
}

interface FileActionProps { changed: boolean; chosen: boolean; busy: boolean; save: () => void; cancel: () => void; reset: () => void; refresh: () => void }

function FileActions({ changed, chosen, busy, save, cancel, reset, refresh }: FileActionProps) {
  return <div className="form-actions">
    {changed && <>
      <button type="button" className="button primary" onClick={save}>Save files</button>
      <button type="button" className="button" onClick={cancel}>Cancel</button>
    </>}
    {chosen && <button type="button" className="text-button" onClick={reset}>Use the defaults</button>}
    {/* Marked busy, not disabled, so keyboard focus stays on it. */}
    <button type="button" className="text-button" aria-disabled={busy} onClick={() => { if (!busy) refresh() }}><RefreshCw aria-hidden="true" />Refresh list</button>
  </div>
}

/** A ComfyUI server's model files (built-in workflow only) and style LoRAs (any workflow). */
function ComfyFiles({ backend, put }: { backend: ImageBackend; put: (body: object) => Promise<boolean> }) {
  return <>
    {backend.model_files && !backend.custom_workflow && <ModelFilePicker backend={backend} saved={backend.model_files} save={put} />}
    {backend.sampler && !backend.custom_workflow && <SamplerPicker backend={backend} saved={backend.sampler} save={put} />}
    {backend.style_loras && <StyleLoraPicker backend={backend} saved={backend.style_loras} save={(rows) => put(stylesBody(rows))} />}
  </>
}

/** The built-in workflow's steps, CFG, sampler and scheduler, for a model that wants other settings
 * than Krea 2 Turbo's. The sampler and scheduler lists come from the server's KSampler. A custom
 * workflow keeps its own settings, so this is not shown for one. */
function SamplerPicker({ backend, saved, save }: { backend: ImageBackend; saved: SamplerSettings; save: (body: object) => Promise<boolean> }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<Partial<SamplerSettings>>({})
  const files = useBackendFiles(backend, open)
  const server = serverFiles(files.data, files.isError ? failure(files.error, 'The server could not be asked.') : null, {})
  const defaults = files.data?.sampler_defaults ?? TURBO
  const family = familyOf(backend.family)
  const shown = shownSampler(draft, saved, defaults)
  const store = async (body: object) => { if (await save(body)) setDraft({}) }
  const slot = (label: string, hint: string): FileSlot => ({ key: 'unet_name', label, role: null, hint })
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="subtle">Sampling {isTuned(saved) ? '(your settings)' : `(${family.sampling} defaults)`}</summary>
      <div className="form-stack">
        <p className="subtle">Starts on {family.sampling}'s settings: {defaults.steps} steps, CFG {defaults.cfg}, {defaults.sampler_name} and {defaults.scheduler}. Change them when your model's page recommends others.</p>
        <div className="form-grid">
          <SliderNumber label="Steps" value={shown.steps} min={1} max={100} step={1} hint={family.steps} onChange={(steps) => setDraft({ ...draft, steps })} />
          <SliderNumber label="CFG" value={shown.cfg} min={0} max={30} step={0.5} hint="At 1 the negative prompt is ignored." onChange={(cfg) => setDraft({ ...draft, cfg })} />
          <FileField slot={slot('Sampler', 'From ComfyUI\'s KSampler.')} options={server.options.sampler_name} matching={[]} value={shown.sampler_name} fallback={defaults.sampler_name ?? ''} onChange={(value) => setDraft({ ...draft, sampler_name: value })} />
          <FileField slot={slot('Scheduler', 'From ComfyUI\'s KSampler.')} options={server.options.scheduler} matching={[]} value={shown.scheduler} fallback={defaults.scheduler ?? ''} onChange={(value) => setDraft({ ...draft, scheduler: value })} />
        </div>
        <FileActions changed={Object.keys(draft).length > 0} chosen={isTuned(saved)} busy={files.isFetching}
          save={() => void store(shown)} cancel={() => setDraft({})} reset={() => void store(defaults)} refresh={() => void files.refetch()} />
      </div>
    </details>
  )
}

/** The server's file lists, asked once the panel is opened and shared by the file and LoRA pickers. */
function useBackendFiles(backend: ImageBackend, open: boolean) {
  // Each family lists its own loaders, so a new family asks the server again.
  const files = useQuery({ queryKey: ['image-backend-files', backend.id, backend.family], queryFn: () => api<BackendFiles>(`/images/backends/${backend.id}/files`), enabled: open, staleTime: Infinity, retry: false })
  // A model dropped in ComfyUI's folders shows up when the user comes back to the app.
  useRefetchOnFocus(files.refetch, open)
  return files
}

/** A dropdown of the server's files (only `matching` when given), or a text box when it listed none. */
function FileField({ slot, options, matching, value, fallback, onChange }: { slot: FileSlot; options: string[]; matching: string[]; value: string; fallback: string; onChange: (value: string) => void }) {
  const { label, hint, tip, same } = slot
  if (options.length === 0) return <TextInput label={label} value={value} maxLength={300} placeholder={fallback || same} hint={hint} tip={tip} onChange={onChange} />
  return <Field label={label} hint={hint} tip={tip}>{(id, describedBy) => <>
    <select id={id} aria-describedby={describedBy} value={value} onChange={(event) => onChange(event.target.value)}>
      {fileChoices(options, value, matching, matching.length > 0, same).map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
    </select>
    {/* On its own line, so the file name in the box is never cut short by it (Iris). */}
    {missingFrom(options, value) && <p className="subtle field-missing">{MISSING}</p>}
  </>}</Field>
}

/** Up to three LoRAs from the server's loras folder, applied after the character's own LoRA (which is
 * never offered here), each with a strength and the trigger words it needs. Any workflow takes them. */
function StyleLoraPicker({ backend, saved, save }: { backend: ImageBackend; saved: StyleLora[]; save: (rows: StyleLora[]) => Promise<boolean> }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<StyleLora[] | null>(null)
  const files = useBackendFiles(backend, open)
  const server = serverFiles(files.data, files.isError ? failure(files.error, 'The server could not be asked.') : null, {})
  const store = async (body: StyleLora[]) => { if (await save(body)) setDraft(null) }
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="subtle">Style LoRAs {saved.length ? `(${saved.length})` : '(none)'}</summary>
      <div className="form-stack">
        <p className="subtle">Extra LoRAs for the look of every picture from this server, such as a phone-photo or realism LoRA. They apply in this order.</p>
        {open && !server.answered && <p className="subtle">Asking ComfyUI for its LoRAs…</p>}
        {server.error && <Notice tone="error">{server.error} Type the file names instead.</Notice>}
        {server.answered && <StyleLoraRows rows={draft ?? saved} options={server.options.lora} matching={server.matching.lora} short={familyOf(backend.family).short} looks={familyOf(backend.family).looks} setRows={setDraft} />}
        {draft && <FileActions changed chosen={false} busy={files.isFetching} save={() => void store(draft)} cancel={() => setDraft(null)} reset={() => undefined} refresh={() => void files.refetch()} />}
      </div>
    </details>
  )
}

const LORA_SLOT: FileSlot = { key: 'unet_name', label: 'LoRA', role: null, hint: 'From ComfyUI\'s models/loras folder.' }

function StyleLoraRows({ rows, options, matching, short, looks, setRows }: { rows: StyleLora[]; options: string[]; matching: string[]; short: string; looks: string; setRows: (rows: StyleLora[]) => void }) {
  const [familyOnly, setFamilyOnly] = useState(true)
  const edit = (index: number, change: Partial<StyleLora>) => setRows(rows.map((row, at) => at === index ? { ...row, ...change } : row))
  return <>
    {matching.length > 0 && <Toggle label={`Only ${short} LoRAs`} checked={familyOnly} onChange={setFamilyOnly} hint={`LoRAs whose name or folder says ${looks}. Turn off to see every LoRA.`} />}
    {rows.map((row, index) => <div key={index} className="form-grid">
      <FileField slot={{ ...LORA_SLOT, label: `LoRA ${index + 1}` }} options={options} matching={familyOnly ? matching : []} value={row.name} fallback="" onChange={(name) => edit(index, { name })} />
      <SliderNumber label="Strength" value={row.strength} min={-2} max={2} step={0.05} hint="0.6 to 0.8 suits most style LoRAs." onChange={(strength) => edit(index, { strength })} />
      <TextInput label="Trigger words" value={row.trigger} maxLength={200} hint="Put in front of the prompt when the LoRA needs them." onChange={(trigger) => edit(index, { trigger })} />
      <button type="button" className="text-button" onClick={() => setRows(rows.filter((_, at) => at !== index))}><Trash2 aria-hidden="true" />Remove</button>
    </div>)}
    {rows.length < MAX_STYLE_LORAS && <div className="form-actions">
      <button type="button" className="button" onClick={() => setRows([...rows, { ...NEW_STYLE_LORA, name: (familyOnly && matching[0]) || options[0] || '' }])}>Add a LoRA</button>
    </div>}
  </>
}

/** Official pages for the built-in workflow's files. Pages only, never a direct download. */
function ModelLinks({ links, family }: { links: ModelLink[]; family: ImageFamily | null }) {
  const groups = linksByRole(links, family ?? 'krea2')
  const { pack } = familyOf(family)
  if (groups.length === 0) return null
  return <div>
    <p className="subtle"><strong>Where to get models.</strong> Put each file in the ComfyUI folder named, then refresh the list.{pack && <> Pictures made from a reference also need the {pack.label} <a className="text-button" href={pack.url} target="_blank" rel="noreferrer">node pack</a> in ComfyUI's custom_nodes folder{pack.install ? '; Check offers to install it' : ''}.</>}{family === 'anima' && <> They also need the Anima Edit LoRA, <code>AnimeEditV2.safetensors</code>, in models/loras.</>} Check the license on each page before downloading.</p>
    <ul className="plain-list">
      {groups.flatMap(({ slot, links: items }) => items.map(link => <li key={link.name}>
        {slot.label}: <a className="text-button" href={link.url} target="_blank" rel="noreferrer">{link.name}</a>{link.file && <> · {link.file}</>}
        <br /><span className="subtle">{link.licence}</span>
      </li>))}
    </ul>
  </div>
}

type WorkflowField = 'workflow' | 'reference_workflow'
type SavedWorkflows = Record<WorkflowField | 'built_in' | 'built_in_reference', string>

const tokens = (...names: string[]) => names.map((name, index) => <span key={name}>{index ? (index === names.length - 1 ? ' and ' : ', ') : ''}<code>{`{{${name}}}`}</code></span>)

// Both boxes start with the family's built-in workflow filled in; editing and saving makes it yours.
const WORKFLOWS: Record<WorkflowField, { title: string; label: string; builtIn: 'built_in' | 'built_in_reference'; hint: ReactNode; shown: (family: string) => string }> = {
  workflow: {
    title: 'Workflow', label: 'Workflow', builtIn: 'built_in',
    hint: <>ComfyUI's API format ("Save (API format)") with <code>{'{{prompt}}'}</code>, plus any of {tokens('negative', 'seed', 'width', 'height')}.</>,
    shown: (family) => `Shown is the built-in ${family} workflow; paste or edit one and save it to use your own.`,
  },
  reference_workflow: {
    title: 'Workflow for pictures made from a reference', label: 'Reference workflow', builtIn: 'built_in_reference',
    hint: <>Used for the profile pictures, where pictures 2 and 3 are made from picture 1. ComfyUI's API format with <code>{'{{prompt}}'}</code> and <code>{'{{reference_image}}'}</code> as a LoadImage node's image, plus any of {tokens('negative', 'seed', 'width', 'height')}.</>,
    shown: (family) => `Shown is the built-in ${family} reference workflow; paste or edit one and save it to use your own.`,
  },
}
const USE_BUILT_IN = 'Use the built-in one'
const BACK_TO_BUILT_IN = 'Back to the built-in workflow.'

/** The files a built-in workflow loads, for its hint, on a line of their own (Iris). */
function needs(workflow: string): ReactNode {
  type Node = { class_type?: string; inputs?: Record<string, unknown> }
  let nodes: Node[]
  try { nodes = Object.values(JSON.parse(workflow) as Record<string, Node>) } catch { return null }
  const files = [...nodes.flatMap(({ inputs = {} }) => ['unet_name', 'ckpt_name', 'clip_name', 'vae_name', 'lora_name'].map((key) => inputs[key])),
    ...nodes.flatMap(({ class_type: type = '' }) => PRESET_FILES[type] ?? [])]
    .filter((name): name is string => typeof name === 'string' && name.endsWith('.safetensors'))
  if (!files.length) return null
  return <span className="workflow-needs">It needs, in ComfyUI's models folders: {files.map((file, index) => <span key={file}>{index ? ', ' : ''}<code>{file}</code></span>)}</span>
}

/** Saved workflows come back indented so they can be read and edited; anything else is shown as saved. */
const readable = (text: string) => { try { return JSON.stringify(JSON.parse(text), null, 2) } catch { return text } }

/** Why a workflow is not JSON, with the line it broke on when the browser says where. */
function jsonProblem(text: string): string {
  try { JSON.parse(text); return '' } catch (error) {
    const message = error instanceof Error ? error.message : ''
    const line = /line (\d+)/.exec(message)?.[1] ?? (/position (\d+)/.exec(message) ? String(text.slice(0, Number(/position (\d+)/.exec(message)?.[1])).split('\n').length) : '')
    return `This is not valid JSON${line ? ` (near line ${line})` : ''}. Check for a missing comma, quote or bracket. Nothing was saved.`
  }
}

/** The saved text (empty for the built-in one), the box and what was just cleared, read when the
 * section first opens. The box shows the built-in workflow while nothing of the user's is saved. */
function useWorkflow(backend: ImageBackend, field: WorkflowField, save: (value: string) => Promise<string>) {
  const [saved, setSaved] = useState<string | null>(null)
  const [builtIn, setBuiltIn] = useState('')
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [removed, setRemoved] = useState('')
  const load = async () => {
    try {
      const found = await api<SavedWorkflows>(`/images/backends/${backend.id}/workflows`)
      const fallback = readable(found[WORKFLOWS[field].builtIn])
      setSaved(readable(found[field])); setText(readable(found[field]) || fallback); setBuiltIn(fallback); setError('')
    } catch (failed) { setError(failure(failed, 'The saved workflow could not be read.')) }
  }
  const store = async (value: string) => {
    // The built-in one saved unchanged stays the built-in one, so its model file and sampler choices keep applying.
    const own = value && readable(value) !== builtIn ? value : ''
    const problem = (own ? jsonProblem(own) : '') || await save(own)
    setError(problem)
    if (problem) return
    setRemoved(own || !saved ? '' : saved); setSaved(readable(own)); setText(readable(own) || builtIn)
  }
  const edit = (value: string) => { setText(value); setError(''); setRemoved('') }
  return { saved, builtIn, text, error, removed, load, store, edit, shown: saved || builtIn }
}

/** A ComfyUI backend's own workflow, or the one for pictures that follow another (the profile pictures). */
function WorkflowEditor({ backend, field, save }: { backend: ImageBackend; field: WorkflowField; save: (value: string) => Promise<string> }) {
  const copy = WORKFLOWS[field]
  const set = field === 'workflow' ? backend.custom_workflow : backend.reference_workflow
  const flow = useWorkflow(backend, field, save)
  // A built-in one starts closed and the user's own starts open (Iris); saving or resetting never folds it away.
  const [startOpen] = useState(set)
  // The built-in one shows the family's workflow with the chosen model files and sampler; once they change, an
  // untouched box follows.
  const picks = JSON.stringify([backend.family, backend.model_files, backend.sampler])
  const family = familyOf(backend.family)
  const shownNote = copy.shown(family.sampling)
  const shownPicks = useRef(picks)
  const { saved, text, builtIn, load } = flow
  useEffect(() => {
    if (picks === shownPicks.current) return
    shownPicks.current = picks
    if (saved !== null && !saved && text === builtIn) void load()
  }, [picks, saved, text, builtIn, load])
  return (
    <details open={startOpen} onToggle={(event) => { if (event.currentTarget.open && flow.saved === null) void flow.load() }}>
      <summary className="subtle">{copy.title} {set ? '(yours)' : '(built-in)'}</summary>
      <div className="form-stack workflow-editor">
        <Field label={copy.label} hint={<>{copy.hint}{!set && <> {shownNote}{needs(flow.builtIn)}</>}</>}>{(id, describedBy) =>
          <>
            <textarea id={id} rows={12} value={flow.text} placeholder="Paste a workflow" spellCheck={false} aria-describedby={describedBy}
              aria-invalid={Boolean(flow.error)} onChange={(event) => flow.edit(event.target.value)} />
            {/* Right under the box it is about, above the hint (Iris). */}
            {flow.error && <Notice tone="error">{flow.error}</Notice>}
          </>}</Field>
        <WorkflowActions flow={flow} set={set} />
      </div>
    </details>
  )
}

type Workflow = ReturnType<typeof useWorkflow>

/** Save and undo first; resetting sits at the far end, muted, and can be undone right after. */
function WorkflowActions({ flow, set }: { flow: Workflow; set: boolean }) {
  const edited = flow.saved !== null && flow.text !== flow.shown
  return <>
    {flow.removed && <Notice action={<button type="button" className="text-button" onClick={() => void flow.store(flow.removed)}>Undo</button>}>{BACK_TO_BUILT_IN}</Notice>}
    {(edited || set) && <div className="form-actions">
      {/* Shown only once something changed, like Undo changes (Iris). */}
      {edited && <button type="button" className="button primary" disabled={!flow.text.trim()} onClick={() => void flow.store(flow.text.trim())}>Save workflow</button>}
      {edited && <button type="button" className="button" onClick={() => flow.edit(flow.shown)}>Undo changes</button>}
      {set && <button type="button" className="text-button subtle workflow-reset" onClick={() => void flow.store('')}>{USE_BUILT_IN}</button>}
    </div>}
  </>
}

function summaryLine(backend: ImageBackend) {
  const where = backend.kind === 'codex' ? 'Codex CLI' : backend.local ? 'This computer' : backend.base_url
  const missingKey = backend.kind === 'hosted' && !backend.has_key && !backend.key_from
  return [where, backend.model, missingKey ? (backend.provider === 'novelai' ? 'no API token' : 'no API key') : '', backend.key_from ? `key from ${backend.key_from}` : '', backend.takes_reference ? 'can follow a reference picture' : ''].filter(Boolean).join(' · ')
}

function BackendSummary({ backend }: { backend: ImageBackend }) {
  return <>
    <div className="backend-title">
      <strong>{backend.label}</strong>
      <span className="badge">{backend.accepts_nsfw ? (backend.local ? 'Local · safe and NSFW' : 'Safe and NSFW') : 'Safe only'}</span>
      {backend.experimental && <span className="badge">Experimental</span>}
    </div>
    <p className="subtle">{summaryLine(backend)}</p>
  </>
}

interface Draft { kind: BackendKind; provider: HostedProvider; baseUrl: string; model: string; apiKey: string; cliPath: string; workflow: string; controlled: boolean; nsfw: boolean }

/** The request body for a new backend; only the fields its kind uses. */
function backendBody(draft: Draft, disclosure: string | null, accepted: boolean): Record<string, unknown> {
  const body: Record<string, unknown> = { kind: draft.kind, accept_disclosure: disclosure ? accepted : undefined, enabled: !disclosure || accepted }
  if (draft.kind === 'comfyui') return { ...body, base_url: draft.baseUrl, controlled_machine: draft.controlled, workflow: draft.workflow.trim() || undefined }
  if (draft.kind === 'codex') return { ...body, cli_path: draft.cliPath.trim() || undefined }
  return { ...body, provider: draft.provider, model: draft.model, api_key: draft.apiKey || undefined, base_url: draft.baseUrl.trim() || undefined,
    allows_nsfw: NSFW_PROVIDERS.includes(draft.provider) ? draft.nsfw : undefined }
}

const MODEL_EXAMPLES: Record<HostedProvider, string> = {
  openrouter: 'google/gemini-2.5-flash-image', google: 'imagen-4.0-generate-001', openai: 'gpt-image-1', nanogpt: 'hidream-o1-image', novelai: 'nai-diffusion-4-5-full', other: 'gpt-image-1',
}

/** The NSFW switch for a new image API backend; Google and the OpenAI API only say they stay safe-only. */
function NsfwChoice({ provider, checked, onChange }: { provider: HostedProvider; checked: boolean; onChange: (value: boolean) => void }) {
  if (!NSFW_PROVIDERS.includes(provider)) return <p className="subtle">{PROVIDERS.find((item) => item.id === provider)?.label} only receives safe requests.</p>
  return <Toggle label="Also take NSFW requests" checked={checked} onChange={onChange}
    hint="Off: safe images only. On: NSFW requests can go to this provider too, so only turn it on if its terms allow them. Every request is still checked on this computer first, and prohibited ones are never sent." />
}

function AddBackend({ onDone, setResult }: { onDone: () => void; setResult: (result: Result) => void }) {
  const [kind, setKind] = useState<BackendKind>('comfyui')
  const [provider, setProvider] = useState<HostedProvider>('openrouter')
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:8188')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [cliPath, setCliPath] = useState('')
  const [workflow, setWorkflow] = useState('')
  const [controlled, setControlled] = useState(false)
  const [nsfw, setNsfw] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false)
  const disclosure = disclosureFor(kind, provider, baseUrl, controlled, nsfw)
  const chooseKind = (next: BackendKind) => {
    setKind(next)
    setBaseUrl(next === 'comfyui' ? 'http://127.0.0.1:8188' : '')
    setAccepted(false)
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api('/images/backends', backendBody({ kind, provider, baseUrl, model, apiKey, cliPath, workflow, controlled, nsfw }, disclosure, accepted))
      const leftOff = disclosure && !accepted
      setResult({ tone: 'info', text: leftOff ? 'Added, but left off until you accept what it receives.' : 'Backend added. Use Check to confirm it can run.' })
      onDone()
    } catch (error) { setResult({ tone: 'error', text: failure(error, 'Not added.') }) } finally { setBusy(false) }
  }
  return (
    <form className="form-stack backend-form" onSubmit={submit}>
      <Field label="Kind" hint={BACKEND_KINDS.find((item) => item.id === kind)?.hint}>{(id, describedBy) => (
        <select id={id} aria-describedby={describedBy} value={kind} autoFocus onChange={(event) => chooseKind(event.target.value as BackendKind)}>
          {BACKEND_KINDS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      )}</Field>
      {kind === 'comfyui' && <>
        <TextInput label="ComfyUI address" value={baseUrl} required onChange={setBaseUrl} hint="The app connects to this server only. It never starts or stops ComfyUI." />
        <Toggle label="This address is a machine I control" checked={controlled} onChange={setControlled} hint="Only for your own computer on your network. A rented or shared GPU service is not." />
        <TextArea label="Custom workflow (optional)" value={workflow} rows={3} onChange={setWorkflow}
          hint="Leave empty for the built-in workflow (Krea 2 Turbo; another model family and its files can be picked once the backend is added). A custom one is ComfyUI's API format with {{prompt}}, {{negative}}, {{seed}}, {{width}} and {{height}}." />
      </>}
      {kind === 'codex' && <TextInput label="Codex CLI location (optional)" value={cliPath} onChange={setCliPath} hint="Found on PATH when empty. Sign in once with codex login in a terminal; the app never sees your password or token." />}
      {kind === 'hosted' && <>
        <Field label="Provider" hint="The image service you are adding.">{(id, hint) => (
          <select id={id} aria-describedby={hint} value={provider} onChange={(event) => { setProvider(event.target.value as HostedProvider); setAccepted(false) }}>
            {PROVIDERS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        )}</Field>
        <HostedKey provider={provider} baseUrl={baseUrl} value={apiKey} onChange={setApiKey} />
        {provider === 'other' && <TextInput label="API base URL" value={baseUrl} required onChange={setBaseUrl} hint="For an OpenAI-compatible image service, usually ending in /v1." />}
        <ImageModelField provider={provider} baseUrl={baseUrl} apiKey={apiKey} value={model} placeholder={MODEL_EXAMPLES[provider]} onChange={setModel} />
        <NsfwChoice provider={provider} checked={nsfw} onChange={(value) => { setNsfw(value); setAccepted(false) }} />
      </>}
      {disclosure && <Toggle label="I understand what it receives" checked={accepted} onChange={setAccepted} hint={disclosure} />}
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={busy}>Add backend</button>
        <button type="button" className="button" onClick={onDone}>Cancel</button>
      </div>
    </form>
  )
}

/** Where a hosted provider's key comes from: NovelAI calls it a persistent API token. */
function keyHint(provider: string | null | undefined): string {
  return provider === 'novelai'
    ? "Your persistent API token, from Account Settings on novelai.net. Saved in your system's credential store."
    : "Saved in your system's credential store."
}

/** The key for a new image API: the one saved with a text profile on the same service is used as it is, as in
 * Settings > Models, and "Use a different key" opens the field. */
function HostedKey({ provider, baseUrl, value, onChange }: { provider: HostedProvider; baseUrl: string; value: string; onChange: (value: string) => void }) {
  const profiles = useQuery({ queryKey: ['models'], queryFn: () => api<ModelsOverview>('/models') }).data?.profiles ?? []
  const [typing, setTyping] = useState(false)
  const from = imageKeyFrom(profiles, provider, baseUrl)
  if (from && !typing) return <div className="token-entry"><p>Uses the API key saved with <strong>{from.name}</strong>.</p><button type="button" className="button" onClick={() => setTyping(true)}>Use a different key</button></div>
  return <div className="token-entry"><TextInput label={provider === 'novelai' ? 'API token' : 'API key'} type="password" value={value} onChange={onChange} hint={keyHint(provider)} />
    {from && <button type="button" className="text-button" onClick={() => { onChange(''); setTyping(false) }}>Use the {from.name} key</button>}</div>
}
