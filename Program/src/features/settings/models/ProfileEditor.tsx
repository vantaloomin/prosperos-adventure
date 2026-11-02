// The profile form adapted from prosperos-study src/features/models/ProfileEditor.tsx, ModelDiscovery.tsx and
// useModelDiscovery.ts at bbcbde4. It opens in place in Settings rather than in a dialog.
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Check, PlugZap } from 'lucide-react'
import { api } from '../../../api'
import { Notice } from '../../../components/Feedback'
import { TextInput } from '../../../components/Fields'
import { GenerationSettings } from './GenerationSettings'
import { ModelCombobox } from './ModelCombobox'
import { applyDiscovered, decisionsReady, discoveredSettings, profileReady, recallReady, reusableKey, savedKeyApplies, typedModelSettings, type Discovery } from './discovery'
import { shownPath } from '../../../paths'
import { cliProviders, configFor, decisionProviders, decisionsConfigFor, embeddingProviders, isDecisions, isRecall, isText, providerOrder, providers, recallConfigFor, type ModelProfile, type ProfileConfig, type Provider } from './types'

const failure = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback

function useDiscovery(profile?: ModelProfile) {
  const [result, setResult] = useState<Discovery | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const sequence = useRef(0)
  useEffect(() => () => { sequence.current++ }, [])
  const reset = () => { sequence.current++; setResult(null); setError(''); setBusy(false) }
  const connect = async (config: ProfileConfig, key: string, onResult: (value: Discovery) => void) => {
    const request = ++sequence.current
    setBusy(true); setError(''); setResult(null)
    try {
      const value = await api<Discovery>('/models/discover', { config, api_key: key || null, profile_id: profile?.id ?? null })
      if (request !== sequence.current) return
      setResult(value); onResult(value)
    } catch (problem) {
      if (request === sequence.current) setError(failure(problem, 'The connection test failed.'))
    } finally { if (request === sequence.current) setBusy(false) }
  }
  return { result, busy, error, reset, connect }
}

type Patch = (change: Partial<ProfileConfig>) => void
type Discovered = ReturnType<typeof useDiscovery>

function useSave(profile: ModelProfile | undefined, onDone: (saved?: ModelProfile) => void) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const save = async (body: { name: string; config: ProfileConfig; api_key: string | null; share_key?: boolean }) => {
    if (saving) return
    setSaving(true); setError('')
    try {
      onDone(profile
        ? await api<ModelProfile>(`/models/profiles/${profile.id}`, { ...body, expected_revision: profile.revision }, 'PUT')
        : await api<ModelProfile>('/models/profiles', body))
    } catch (problem) { setError(failure(problem, 'The profile was not saved.')) } finally { setSaving(false) }
  }
  return { saving, error, save }
}

export type ProfileKind = 'text' | 'recall' | 'decisions'
const kindOf = (config: ProfileConfig): ProfileKind => isRecall(config) ? 'recall' : isDecisions(config) ? 'decisions' : 'text'
const FRESH: Record<ProfileKind, (provider: Provider) => ProfileConfig> = { text: configFor, recall: recallConfigFor, decisions: decisionsConfigFor }
const CHOICES: Record<ProfileKind, Provider[]> = { text: providerOrder, recall: embeddingProviders, decisions: decisionProviders }

function useProfileForm(profile: ModelProfile | undefined, kind: ProfileKind, others: ModelProfile[]) {
  const fresh = FRESH[kind]
  const [name, setName] = useState(profile?.name ?? '')
  const [config, setConfig] = useState<ProfileConfig>(profile?.config ?? fresh('local'))
  const [key, setKey] = useState('')
  const [shareKey, setShareKey] = useState(true)
  const discovery = useDiscovery(profile)
  const patch: Patch = (change) => { if (change.base_url !== undefined) discovery.reset(); setConfig(current => ({ ...current, ...change })) }
  const changeProvider = (provider: Provider) => { discovery.reset(); setConfig(fresh(provider)); setKey('') }
  const changeKey = (value: string) => { discovery.reset(); setKey(value) }
  const test = () => { void discovery.connect(config, key, result => setConfig(current => isText(current) ? applyDiscovered(result, current) : current)) }
  return { name, setName, config, key, discovery, found: discovery.result?.location, patch, changeProvider, changeKey, test, ...readiness(profile, config, key, others),
    shareKey, setShareKey, body: { name: name.trim(), config, api_key: key || null, share_key: shareKey } }
}

function keyState(profile: ModelProfile | undefined, config: ProfileConfig, others: ModelProfile[]) {
  const savedKey = savedKeyApplies(profile?.config, profile?.has_saved_key ?? false, config)
  return { savedKey, reused: savedKey ? undefined : reusableKey(others, config, profile?.id), sharedWith: savedKey ? profile?.key_shared_with ?? [] : [] }
}

function readiness(profile: ModelProfile | undefined, config: ProfileConfig, key: string, others: ModelProfile[]) {
  const { savedKey, reused, sharedWith } = keyState(profile, config, others)
  const ready = isRecall(config) ? recallReady(config) : isDecisions(config) ? decisionsReady(config) : profileReady(config)
  return { savedKey, reused: reused?.name, sharedWith, ready, canSave: ready || !!key.trim() || savedKey || !!reused, keyless: cliProviders.includes(config.provider) }
}

const LABELS: Record<ProfileKind, string> = { text: 'New model profile', recall: 'New recall profile', decisions: 'New decisions profile' }
const PLACEHOLDERS: Record<ProfileKind, string> = { text: 'Everyday chat, careful drafting…', recall: 'Ollama embeddings…', decisions: 'Jev, local Qwen scoring…' }

/** A text profile writes; a recall profile only makes embeddings, so recall can use a different service; a decisions
 * profile only answers the Referee's questions with probabilities. */
export function ProfileEditor({ profile, kind = 'text', others, onDone }: { profile?: ModelProfile; kind?: ProfileKind; others: ModelProfile[]; onDone: (saved?: ModelProfile) => void }) {
  const form = useProfileForm(profile, profile ? kindOf(profile.config) : kind, others)
  const saving = useSave(profile, onDone)
  const { config, patch, discovery } = form
  const shown = kindOf(config)
  const submit = (event: FormEvent) => { event.preventDefault(); if (form.canSave) void saving.save(form.body) }
  return <form className="model-profile-editor form-stack" onSubmit={submit} aria-label={profile ? `Edit ${profile.name}` : LABELS[shown]}>
    <ProviderPicker selected={config.provider} choices={CHOICES[shown]} onChange={form.changeProvider} decisions={shown === 'decisions'} />
    <TextInput label="Profile name" value={form.name} onChange={form.setName} maxLength={120} placeholder={PLACEHOLDERS[shown]} hint={`Leave empty to name it after the provider and ${shown === 'recall' ? 'embedding ' : ''}model.`} />
    <ConnectionFields config={config} patch={patch} keyEntry={{ saved: form.savedKey, reused: form.reused, sharedWith: form.sharedWith, value: form.key, onChange: form.changeKey, share: form.shareKey, onShare: form.setShareKey }} found={form.found} />
    <ModelDiscovery config={config} discovery={discovery} onTest={form.test} patch={patch} />
    {shown === 'recall' ? <EmbeddingFields config={config} patch={patch} discovery={discovery} />
      : shown === 'decisions' ? <DecisionFields config={config} patch={patch} discovery={discovery} />
        : <ModelFields config={config} patch={patch} discovery={discovery} />}
    <SaveActions ready={form.ready} recall={shown === 'recall'} keyless={form.keyless} typed={!!form.key.trim()} canSave={form.canSave} saving={saving.saving} error={saving.error} onCancel={() => onDone()} />
  </form>
}

/** "the key" only once one is typed: a borrowed or already saved key is not what Save stores. */
function SaveActions({ ready, recall, keyless, typed, canSave, saving, error, onCancel }: { ready: boolean; recall: boolean; keyless: boolean; typed: boolean; canSave: boolean; saving: boolean; error: string; onCancel: () => void }) {
  const what = typed && !keyless ? 'the key' : 'it'
  return <>
    {!ready && <p className="subtle">{recall ? `You can save ${what} now and choose an embedding model later. A recall profile needs one before it can do recall.` : `You can save ${what} now and choose a model later. A profile needs a model before it can do a job.`}</p>}
    {error && <Notice tone="error">{error}</Notice>}
    <div className="form-actions"><button type="submit" className="button primary" disabled={!canSave} aria-disabled={saving}>{saving ? 'Saving…' : 'Save profile'}</button><button type="button" className="button" onClick={onCancel}>Cancel</button>{!keyless && <span className="subtle keychain-note">Keys are kept in your system keychain, never in the workspace or its backups.</span>}</div>
  </>
}

/** What each provider does as a decisions profile. */
const DECIDES: Partial<Record<Provider, string>> = {
  openrouter: 'Jev, TypeSafe’s decision model, through your OpenRouter account. Turn text goes to TypeSafe under its content policy.',
  openai: 'OpenAI’s Decisions API (in beta). Turn text goes to OpenAI under its content policy.',
  local: 'A model on this computer, such as Qwen3.5 4B in LM Studio, Ollama or llama.cpp. The Dungeon reads the odds of each answer, so the server must return log probabilities.',
  compatible: 'A model on an OpenAI-compatible service that returns log probabilities. The Dungeon reads the odds of each answer.',
}

function ProviderPicker({ selected, choices, onChange, decisions = false }: { selected: Provider; choices: Provider[]; onChange: (provider: Provider) => void; decisions?: boolean }) {
  return <><fieldset className="provider-picker"><legend>Provider</legend>
    {choices.map(provider => <button key={provider} type="button" className={`button${selected === provider ? ' selected' : ''}`} aria-pressed={selected === provider} onClick={() => onChange(provider)}>{providers[provider].name}</button>)}
  </fieldset><p className="subtle">{selected === 'claude_code'
    ? <>Uses the Claude plan your Claude Code is signed in to. No key is entered here, and the app never sees your password or token. To sign in, run <code>claude</code> once in a terminal.</>
    : (decisions && DECIDES[selected]) || providers[selected].description}</p></>
}

type KeyEntry = { saved: boolean; reused?: string; sharedWith: string[]; value: string; onChange: (value: string) => void; share: boolean; onShare: (value: boolean) => void }

function ConnectionFields({ config, patch, keyEntry, found }: { config: ProfileConfig; patch: Patch; keyEntry: KeyEntry; found?: string }) {
  const local = config.provider === 'local' || config.provider === 'kobold'
  if (config.provider === 'codex') return <p className="subtle">Uses the Codex CLI’s own login; no key is entered here. Codex runs in an empty temporary folder with its shell, plugins, web search and tools turned off.</p>
  if (config.provider === 'claude_code') return <ClaudeCodeFields config={config} patch={patch} found={found} />
  return <>
    {(local || config.provider === 'compatible') && <TextInput label="Server address" value={config.base_url} onChange={value => patch({ base_url: value })} maxLength={500} hint={local ? 'An address on this computer. LM Studio and Ollama usually end in /v1.' : 'The API base URL, without /models or /chat/completions.'} />}
    <TokenEntry key={config.provider} {...keyEntry} local={local || config.provider === 'compatible'} />
  </>
}

function ClaudeCodeFields({ config, patch, found }: { config: ProfileConfig; patch: Patch; found?: string }) {
  return <>
    <Notice>Claude follows Anthropic’s usage policy, so it won’t write the adult side of life. Use it for everyday chat and the other non-explicit jobs, and give adult scenes a different profile.</Notice>
    <TextInput label="Claude Code location (optional)" value={config.cli_path ?? ''} onChange={value => patch({ cli_path: value })} maxLength={500} placeholder={found ? shownPath(found) : undefined} hint="Leave empty to use the Claude Code found on this computer." />
    <TextInput label="Claude account folder (optional)" value={config.cli_account_dir ?? ''} onChange={value => patch({ cli_account_dir: value })} maxLength={500} placeholder="C:\Users\you\.claude-second"
      hint="For a second Claude account: a folder of its own that keeps that account's sign-in. Test connection says how to sign in to it. Leave empty for the account Claude Code usually uses." />
  </>
}

function ModelDiscovery({ config, discovery, onTest, patch }: { config: ProfileConfig; discovery: Discovered; onTest: () => void; patch: Patch }) {
  const models = discovery.result?.model_details ?? []
  const choose = (id: string) => { const model = models.find(item => item.id === id); if (model) patch(discoveredSettings(model, config)) }
  return <section className="model-discovery form-stack" aria-label="Connection and models">
    <TestButton blocked={config.provider === 'compatible' && !config.base_url.trim()} busy={discovery.busy} connected={!!discovery.result} onTest={onTest} />
    {discovery.error && <Notice tone="error">{discovery.error}</Notice>}
    {discovery.result?.note && <p className="subtle">{discovery.result.note}</p>}
    {models.length > 0 && isText(config) && <ModelCombobox models={models} value={models.some(model => model.id === config.model) ? config.model : ''} onChange={choose} />}
  </section>
}

function TestButton({ blocked, busy, connected, onTest }: { blocked: boolean; busy: boolean; connected: boolean; onTest: () => void }) {
  return <div className="form-actions"><button type="button" className="button" disabled={busy || blocked} onClick={onTest}><PlugZap size={16} aria-hidden="true" />{busy ? 'Testing…' : 'Test connection'}</button>{connected && <span className="connection-success" role="status"><Check size={15} aria-hidden="true" />Connected</span>}</div>
}

function ModelFields({ config, patch, discovery }: { config: ProfileConfig; patch: Patch; discovery: Discovered }) {
  const models = discovery.result?.model_details ?? []
  return <>
    <TextInput label="Model ID" value={config.model} onChange={value => patch(typedModelSettings(value.trim(), config, models))} maxLength={200} placeholder="Pick from the list or type an ID"
      hint="Test connection lists the models this service offers. Picking one fills in its settings." tip="The exact name the service uses for the model, such as gpt-4o-mini or llama3.1:8b." />
    <details className="advanced-settings"><summary>Generation settings</summary><GenerationSettings config={config} patch={patch} model={models.find(model => model.id === config.model)} /></details>
  </>
}

function DecisionFields({ config, patch, discovery }: { config: ProfileConfig; patch: Patch; discovery: Discovered }) {
  const models = discovery.result?.model_details ?? []
  const scored = config.provider === 'local' || config.provider === 'compatible'
  return <>
    {scored && models.length > 0 && <ModelCombobox models={models} value={models.some(model => model.id === config.model) ? config.model : ''} onChange={id => patch({ model: id })} />}
    <TextInput label="Model ID" value={config.model} onChange={value => patch({ model: value.trim() })} maxLength={200} placeholder={scored ? 'Pick from the list or type an ID' : undefined}
      hint={scored ? 'A small instruct model is plenty: Qwen3.5 4B, or 0.8B on a computer without a graphics card.' : 'The decision model to ask. The newest one is filled in for you.'} />
  </>
}

function EmbeddingFields({ config, patch, discovery }: { config: ProfileConfig; patch: Patch; discovery: Discovered }) {
  const models = discovery.result?.model_details ?? []
  const value = config.embedding_model ?? ''
  return <>
    {models.length > 0 && <ModelCombobox models={models} value={models.some(model => model.id === value) ? value : ''} onChange={id => patch({ embedding_model: id })} />}
    <TextInput label="Embedding model" value={value} onChange={text => patch({ embedding_model: text.trim() })} maxLength={200} placeholder="Choose from the list, or type the model's ID"
      hint="Turns memories into embeddings so recall finds related ones even when the words differ. EmbeddingGemma 2, Qwen3 Embedding 0.6B or nomic-embed-text work well." />
  </>
}

function TokenEntry(entry: KeyEntry & { local: boolean }) {
  const [editing, setEditing] = useState(false)
  if (editing) return <KeyField {...entry} onDone={() => setEditing(false)} />
  // A key another profile saved for this service is used as it is; typing one is only for a different key.
  if (entry.reused && !entry.saved) return <div className="token-entry"><p>Uses the API key saved with <strong>{entry.reused}</strong>.</p><button type="button" className="button" onClick={() => setEditing(true)}>Use a different key</button></div>
  return <div className="token-entry"><p><KeyStatus saved={entry.saved} others={entry.sharedWith.join(', ')} /></p><button type="button" className="button" onClick={() => setEditing(true)}>{entry.saved ? 'Replace key' : 'Add API key'}</button>{entry.local && <small>Local servers can leave this empty, and an environment variable such as OPENAI_API_KEY also works.</small>}</div>
}

function KeyStatus({ saved, others }: { saved: boolean; others: string }) {
  if (saved && others) return <>Shares its API key with <strong>{others}</strong>.</>
  return <>{saved ? 'An API key is saved for this profile.' : 'No API key saved for this profile.'}</>
}

function KeyField({ saved, reused, sharedWith, value, onChange, share, onShare, onDone }: KeyEntry & { onDone: () => void }) {
  const others = sharedWith.join(', ')
  return <div className="token-entry"><TextInput label="API key" type="password" value={value} onChange={onChange} maxLength={4000} hint="Saved in your system keychain. It is never shown again." />
    {/* A replaced key does every job that shared it, so a rotated key keeps recall working; unticked, only this profile changes. */}
    {saved && others && <label className="checkbox-row"><input type="checkbox" checked={share} onChange={(event) => onShare(event.target.checked)} />Also use it for {others}</label>}
    <button type="button" className="text-button" onClick={() => { onChange(''); onShare(true); onDone() }}>{reused && !saved ? `Use the ${reused} key` : 'Cancel key entry'}</button></div>
}
