import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FolderOpen, Gauge, RefreshCw } from 'lucide-react'
import { api } from '../../../api'
import { shownPath, useRefetchOnFocus } from '../../../paths'
import { Notice } from '../../../components/Feedback'
import { Field, TextInput, Toggle } from '../../../components/Fields'

interface FoundModel { path: string; name: string; source: string; size_mb: number }
interface SuggestedModel { name: string; file: string; size_mb: number; memory_mb: number; page: string; licence: string; note: string }
interface BuiltinRecallView {
  enabled: boolean
  model_path: string
  state: 'off' | 'starting' | 'ready' | 'failed'
  message: string
  runtime: { version: string; installed: boolean; available: boolean; download_mb: number | null; downloading: boolean }
  models: FoundModel[]
  models_folder: string
  suggested: SuggestedModel[]
}
interface RecallTest { model: string; dimensions: number; scores: number[]; milliseconds: number; found_related: boolean }

const KEY = ['builtin-recall']
const OTHER = '__other__'
const failure = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback
const STATES = { off: 'Off.', starting: 'Loading the model…', ready: 'Running on this PC.', failed: 'Stopped.' }

type Run = (label: string, work: () => Promise<void>) => Promise<void>

/** Settings > Models: an embedding model the Dungeon runs itself with llama.cpp (dungeon/providers/builtin_recall.py). */
export function BuiltinRecall() {
  const client = useQueryClient()
  const query = useQuery({ queryKey: KEY, queryFn: () => api<BuiltinRecallView>('/models/builtin-recall'), refetchInterval: (state) => state.state.data?.state === 'starting' ? 1500 : false, staleTime: 0 })
  // A model file dropped in the folder shows up when the user comes back to the app.
  useRefetchOnFocus(query.refetch)
  const [path, setPath] = useState<string | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const data = query.data
  if (!data) return null
  // Until one is saved, the first model found on this PC is the choice, so the switch can turn on.
  const chosen = path ?? (data.model_path || data.models[0]?.path || '')
  const run: Run = async (label, work) => {
    setBusy(label); setError('')
    try { await work() } catch (failed) { setError(failure(failed, 'That did not work.')) } finally { setBusy('') }
  }
  const update = (view: BuiltinRecallView) => client.setQueryData(KEY, view)
  return <section className="settings-section form-stack" aria-labelledby="recall-heading">
    <div>
      <h2 id="recall-heading">Built-in recall</h2>
      <p className="subtle">Recall finds related parts of the story even when the words differ. The Dungeon can run a small embedding model for this itself, on this PC's processor, apart from LM Studio, Kobold or Ollama. You download the model file, so you accept its license. While this is on, it does Semantic recall instead of the profile chosen above.</p>
    </div>
    <RuntimeStep data={data} busy={busy} run={run} onChange={update} />
    <ModelStep data={data} chosen={chosen} busy={busy} run={run} setPath={setPath} checking={query.isFetching} refresh={() => void query.refetch()} />
    <RecallSwitch data={data} chosen={chosen} busy={busy} run={run} onChange={update} />
    {error && <Notice tone="error">{error}</Notice>}
    <TestRecall busy={busy} run={run} refresh={() => void query.refetch()} />
  </section>
}

interface StepProps { data: BuiltinRecallView; busy: string; run: Run }

function RuntimeStep({ data, busy, run, onChange }: StepProps & { onChange: (view: BuiltinRecallView) => void }) {
  const install = () => run('install', async () => { onChange(await api<BuiltinRecallView>('/models/builtin-recall/runtime', {})) })
  const { runtime } = data
  return <div className="form-stack">
    <h3>1. llama.cpp</h3>
    {runtime.installed && <p className="subtle">llama.cpp {runtime.version} is ready.</p>}
    {!runtime.installed && runtime.available && <div className="form-actions"><button type="button" className="button" onClick={() => void install()} disabled={!!busy}><Download size={15} aria-hidden="true" />{busy === 'install' ? 'Downloading…' : `Download llama.cpp (${runtime.download_mb} MB)`}</button><small>From llama.cpp's official releases, checked against a pinned checksum. MIT license.</small></div>}
    {!runtime.installed && !runtime.available && <p className="subtle">There is no llama.cpp download for this computer. Set DUNGEON_LLAMA_SERVER to a llama-server you installed.</p>}
  </div>
}

function ModelStep({ data, chosen, busy, run, setPath, checking, refresh }: StepProps & { chosen: string; setPath: (path: string) => void; checking: boolean; refresh: () => void }) {
  const listed = data.models.some(model => model.path === chosen)
  const openFolder = () => run('folder', async () => { await api('/models/builtin-recall/open-folder', {}); refresh() })
  return <div className="form-stack">
    <h3>2. A model file</h3>
    <ul className="form-stack">
      {data.suggested.map(model => <li key={model.file}>
        <strong>{model.name}</strong> · {model.size_mb} MB download, about {model.memory_mb} MB of memory while running · {model.licence}
        <br /><span className="subtle">{model.note}</span> <a className="text-button" href={model.page} target="_blank" rel="noreferrer">Get {model.file}</a>
      </li>)}
    </ul>
    <p className="subtle">Put the file in the Dungeon's models folder, or use one LM Studio already downloaded.</p>
    <div className="form-actions"><button type="button" className="button" onClick={() => void openFolder()} disabled={!!busy}><FolderOpen size={15} aria-hidden="true" />Open models folder</button><small>{shownPath(data.models_folder)}</small></div>
    <Field label="Model file" hint={data.models.length ? 'Embedding models found on this PC.' : 'No embedding model found yet. Choose Another file to type its path.'}>{(id, hint) => (
      <select id={id} aria-describedby={hint} value={listed ? chosen : OTHER} onChange={event => setPath(event.target.value === OTHER ? '' : event.target.value)}>
        {data.models.map(model => <option key={model.path} value={model.path}>{model.name} ({model.source}, {model.size_mb} MB)</option>)}
        <option value={OTHER}>Another file…</option>
      </select>
    )}</Field>
    <div className="form-actions"><button type="button" className="text-button" aria-disabled={checking} onClick={() => { if (!checking) refresh() }}><RefreshCw size={15} aria-hidden="true" />{checking ? 'Checking…' : 'Check for models'}</button></div>
    {!listed && <TextInput label="Path to the model file" value={chosen} onChange={setPath} maxLength={1000} placeholder="C:\Models\embeddinggemma-2-Q8_0.gguf" hint="The full path of a .gguf embedding model." />}
  </div>
}

function RecallSwitch({ data, chosen, busy, run, onChange }: StepProps & { chosen: string; onChange: (view: BuiltinRecallView) => void }) {
  const save = (enabled: boolean) => run('save', async () => { onChange(await api<BuiltinRecallView>('/models/builtin-recall', { enabled, model_path: chosen }, 'PUT')) })
  const cannotStart = !data.enabled && (!data.runtime.installed || !chosen)
  return <>
    <Toggle label="Use built-in recall" checked={data.enabled} disabled={!!busy || cannotStart} onChange={enabled => void save(enabled)}
      hint={data.enabled ? STATES[data.state] : cannotStart ? 'Needs llama.cpp and a model file.' : STATES.off} />
    {data.enabled && chosen !== data.model_path && <div className="form-actions"><button type="button" className="button" onClick={() => void save(true)} disabled={!!busy}>Use this model</button><small>Memories are re-read with the new model in the background.</small></div>}
    {data.state === 'failed' && data.message && <Notice tone="error">{data.message}</Notice>}
  </>
}

function TestRecall({ busy, run, refresh }: { busy: string; run: Run; refresh: () => void }) {
  const [test, setTest] = useState<RecallTest | null>(null)
  const check = () => run('test', async () => { setTest(null); setTest(await api<RecallTest>('/models/recall-test', {})); refresh() })
  return <>
    <div className="form-actions">
      <button type="button" className="button" onClick={() => void check()} disabled={!!busy}><Gauge size={15} aria-hidden="true" />{busy === 'test' ? 'Testing…' : 'Test recall'}</button>
      <small>Asks whatever does recall now to match a question with two memories.</small>
    </div>
    {test && <Notice tone={test.found_related ? 'info' : 'error'}>{test.found_related ? 'Recall works: it matched the question with the right memory.' : 'Recall answered, but matched the wrong memory. Try another model.'} {test.model}, {test.dimensions} numbers per text, {test.milliseconds} ms.</Notice>}
  </>
}
