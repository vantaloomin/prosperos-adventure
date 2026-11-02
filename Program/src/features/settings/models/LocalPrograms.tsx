import { useState } from 'react'
import { Play } from 'lucide-react'
import { Notice } from '../../../components/Feedback'
import { TextInput, Toggle } from '../../../components/Fields'
import { shownPath } from '../../../paths'
import { STATE_TEXT, programFor, useLauncher, type LauncherView, type LocalProgram } from './launcher'

const failure = (error: unknown) => error instanceof Error ? error.message : 'That did not work.'
type Placeholders = Record<LocalProgram['program'] | 'model', string>
/** Example paths in the shape this computer uses. */
const PLACEHOLDERS: Record<LauncherView['system'], Placeholders> = {
  windows: {
    lmstudio: 'C:\\Users\\you\\.lmstudio\\bin\\lms.exe', ollama: 'C:\\Users\\you\\AppData\\Local\\Programs\\Ollama\\ollama.exe',
    kobold: 'C:\\koboldcpp\\koboldcpp.exe', comfyui: 'C:\\ComfyUI_windows_portable', model: 'C:\\Models\\model.gguf',
  },
  mac: {
    lmstudio: '~/.lmstudio/bin/lms', ollama: '/usr/local/bin/ollama', kobold: '~/koboldcpp/koboldcpp',
    comfyui: '~/ComfyUI', model: '~/Models/model.gguf',
  },
  linux: {
    lmstudio: '~/.lmstudio/bin/lms', ollama: '/usr/local/bin/ollama', kobold: '~/koboldcpp/koboldcpp',
    comfyui: '~/ComfyUI', model: '~/Models/model.gguf',
  },
}

/** Settings > Models: start LM Studio, Ollama, KoboldCpp or ComfyUI from here, and optionally with the Dungeon. */
export function LocalPrograms() {
  const launcher = useLauncher()
  const [error, setError] = useState('')
  const data = launcher.query.data
  if (!data || data.programs.length === 0) return null
  const act = async (work: () => Promise<unknown>) => { setError(''); try { await work() } catch (failed) { setError(failure(failed)) } }
  const order = data.programs.map(item => item.label).join(', then ')
  return <section className="settings-section form-stack" aria-labelledby="local-programs-heading">
    <div>
      <h2 id="local-programs-heading">Local programs</h2>
      <p className="subtle">Start the programs your local models run in, with the address, model and context size set above. They keep running after the Dungeon closes.</p>
    </div>
    <ul className="model-profiles">
      {data.programs.map(item => <ProgramRow key={item.program} item={item} act={act} launcher={launcher} examples={PLACEHOLDERS[data.system] ?? PLACEHOLDERS.windows} />)}
    </ul>
    {error && <Notice tone="error">{error}</Notice>}
    <Toggle label="Start these when the Dungeon starts" checked={data.auto_launch} onChange={(checked) => void act(() => launcher.setAuto(checked))}
      hint={`${order}, each once the one before answers. Off until you turn it on, since it opens other programs.`} />
  </section>
}

type Launcher = ReturnType<typeof useLauncher>

function ProgramRow({ item, act, launcher, examples }: { item: LocalProgram; act: (work: () => Promise<unknown>) => Promise<void>; launcher: Launcher; examples: Placeholders }) {
  const [editing, setEditing] = useState(false)
  const missing = !item.path
  const save = (body: { path: string; model_path?: string }) => act(async () => { await launcher.choose(item.program, body); setEditing(false) })
  return <li className="model-profile">
    <div>
      <h3>{item.label}</h3>
      <p className="subtle">For {item.used_by.map(use => use.name).join(', ')} · {item.address}</p>
      <StateLines item={item} />
      {!editing && !runsElsewhere(item) && <p className="subtle">{whereText(item)}</p>}
      {(editing || asksWhere(item)) && <WhereForm item={item} examples={examples} save={save} cancel={editing ? () => setEditing(false) : undefined} />}
    </div>
    <div className="form-actions">
      <LaunchButton item={item} onLaunch={() => void act(() => launcher.launch(item.program))} />
      {!editing && !missing && <button type="button" className="text-button" onClick={() => setEditing(true)}>Change where it is</button>}
    </div>
  </li>
}

/** How it is doing, and the system's own words under a failure so support can read them. */
function StateLines({ item }: { item: LocalProgram }) {
  return <>
    <p className="subtle" role="status">{item.message || STATE_TEXT[item.state]}</p>
    {item.detail && <p className="subtle"><small>{shownPath(item.detail)}</small></p>}
  </>
}

/** Running but not found here (started some other way): it runs, so there is nothing to ask for until it stops. */
const runsElsewhere = (item: LocalProgram) => item.state === 'running' && !item.path
const asksWhere = (item: LocalProgram) => (!item.path && !runsElsewhere(item)) || item.needs_model

function whereText(item: LocalProgram) {
  if (!item.path) return 'Not found on this PC.'
  return shownPath(item.path) + (item.model_path ? ` · ${shownPath(item.model_path)}` : '')
}

/** Where the program is, typed only when it was not found, and KoboldCpp's model file. */
function WhereForm({ item, examples, save, cancel }: { item: LocalProgram; examples: Placeholders; save: (body: { path: string; model_path?: string }) => void; cancel?: () => void }) {
  const [path, setPath] = useState(item.path)
  const [model, setModel] = useState(item.model_path)
  const kobold = item.program === 'kobold'
  return <div className="form-stack where-form">
    <TextInput label={item.program === 'comfyui' ? 'ComfyUI folder, app or launch script' : `Where ${item.label} is`} value={path} onChange={setPath} maxLength={1000} placeholder={examples[item.program]}
      hint={item.program === 'comfyui' ? 'A .bat, .cmd or .sh you start ComfyUI with runs as it is, with its own settings. Its port should match the address above.' : undefined} />
    {kobold && <TextInput label="Model file" value={model} onChange={setModel} maxLength={1000} placeholder={examples.model} hint="The .gguf file KoboldCpp loads, or a .kcpps settings file." />}
    <div className="form-actions">
      <button type="button" className="button primary" onClick={() => save(kobold ? { path, model_path: model } : { path })}>Save</button>
      {cancel && <button type="button" className="button" onClick={cancel}>Cancel</button>}
    </div>
  </div>
}

function LaunchButton({ item, onLaunch }: { item: LocalProgram; onLaunch: () => void }) {
  const unavailable = item.state === 'running' || item.state === 'starting' || !item.path || item.needs_model
  return <button type="button" className="button" aria-disabled={unavailable} onClick={() => { if (!unavailable) onLaunch() }}>
    <Play size={15} aria-hidden="true" />{item.state === 'starting' ? 'Starting…' : item.state === 'running' ? `${item.label} is running` : `Launch ${item.label}`}
  </button>
}

/** A launch button beside a profile or image backend that runs in a program the Dungeon can start. */
export function LaunchFor({ id }: { id: string }) {
  const launcher = useLauncher()
  const item = programFor(launcher.query.data, id)
  // Not found or still missing its model file: Local programs below says what it needs.
  if (!item || item.state === 'running' || !item.path || item.needs_model) return null
  return <LaunchButton item={item} onLaunch={() => void launcher.launch(item.program).catch(() => undefined)} />
}
