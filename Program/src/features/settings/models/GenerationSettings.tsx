// Per-provider generation controls adapted from prosperos-study src/features/models/GenerationSettings.tsx
// at bbcbde4: no LM Studio native protocol and no context safety margin.
import { useId } from 'react'
import { Field } from '../../../components/Fields'
import { bounded } from '../../../components/numberBounds'
import type { DiscoveredModel } from './discovery'
import type { ProfileConfig } from './types'

type Props = { config: ProfileConfig; patch: (next: Partial<ProfileConfig>) => void; model?: DiscoveredModel }
type Sampler = 'temperature' | 'top_p' | 'top_k' | 'min_p' | 'frequency_penalty' | 'presence_penalty' | 'repetition_penalty' | 'seed'
const samplerFields: [Sampler, string, number, number, number][] = [
  ['temperature', 'Temperature', 0, 2, .05], ['top_p', 'Top-p', 0, 1, .01], ['top_k', 'Top-k', 0, 1000, 1],
  ['min_p', 'Min-p', 0, 1, .01], ['frequency_penalty', 'Frequency penalty', -2, 2, .1],
  ['presence_penalty', 'Presence penalty', -2, 2, .1], ['repetition_penalty', 'Repetition penalty', .01, 3, .05], ['seed', 'Seed', 0, 2147483647, 1],
]
const samplerTips: Record<Sampler, string> = {
  temperature: 'Higher gives more varied, surprising wording; lower gives steadier, more predictable replies.',
  top_p: 'Only words within this share of likelihood are considered. Lower is more focused.',
  top_k: 'Only this many of the likeliest next words are considered. 0 turns it off.',
  min_p: 'Drops words much less likely than the likeliest one. Small values like 0.05 trim nonsense.',
  frequency_penalty: 'Above 0 discourages repeating the same words; below 0 encourages it.',
  presence_penalty: 'Above 0 nudges toward words and topics not used yet.',
  repetition_penalty: 'Above 1 discourages repeating words and phrases. 1 turns it off.',
  seed: 'The same seed with the same settings can repeat a reply. Most people leave it blank.',
}

function samplingFields(config: ProfileConfig) {
  const { provider } = config
  if (provider === 'codex' || provider === 'claude_code') return []
  if (provider === 'openai') return samplerFields.slice(0, 2)
  if (provider === 'anthropic' || provider === 'google') return samplerFields.slice(0, 3)
  if (provider === 'kobold') return samplerFields.filter(item => ['temperature', 'top_p', 'top_k', 'repetition_penalty'].includes(item[0]))
  return samplerFields
}

export function GenerationSettings(props: Props) {
  const { config, patch } = props
  return <div className="form-stack">
    <BudgetControls {...props} />
    <ThinkingControls {...props} />
    {config.provider === 'openai' && <Choice label="Response verbosity" value={config.response_verbosity} options={['low', 'medium', 'high']} onChange={value => patch({ response_verbosity: value as ProfileConfig['response_verbosity'] })} hint="How much the model tends to say. The longest reply still caps it." />}
    <SamplingControls {...props} />
    <NumberInput label="Shared inference slot (optional)" type="text" value={config.resource_group ?? ''} onChange={value => patch({ resource_group: value })} hint="Profiles with the same name take turns on one slot. Leave blank and all local profiles share one; use different names only for separate hardware." />
    <NumberInput label="Time limit (seconds)" value={config.timeout_seconds} min={10} max={1800} onChange={value => patch({ timeout_seconds: Number(value) })} hint="How long to wait for a reply before giving up. Slow local models may need more." />
  </div>
}

function BudgetControls({ config, patch, model }: Props) {
  const cli = config.provider === 'codex' || config.provider === 'claude_code'
  const input = config.context_tokens - config.max_output_tokens
  return <div className="form-grid">
    <NumberInput label="Context size (tokens)" value={config.context_tokens} min={1024} max={2000000} onChange={value => patch({ context_tokens: Number(value) })} hint={model?.context_tokens ? `The service reports ${model.context_tokens.toLocaleString()} tokens. This can be lower.` : 'What the model can read at once. Not reported, so set it to the model’s context size.'} />
    <NumberInput label={cli ? 'Reply budget (tokens)' : 'Longest reply (tokens)'} value={config.max_output_tokens} min={64} max={128000} onChange={value => patch({ max_output_tokens: Number(value) })} hint={cli ? 'Used for planning what fits. The CLI sets its own hard limit.' : 'Includes thinking where the provider counts it.'} />
    <p className="subtle" role="status">{Math.max(0, input).toLocaleString()} tokens left for the character, memories and conversation.</p>
    {input <= 0 && <p role="alert">Raise the context size or lower the longest reply.</p>}
    {!!model?.max_output_tokens && config.max_output_tokens > model.max_output_tokens && <p role="alert">The longest reply is above the reported maximum of {model.max_output_tokens.toLocaleString()} tokens.</p>}
  </div>
}

function ThinkingControls(props: Props) {
  const { config } = props, provider = config.provider
  const compatible = provider === 'compatible' || provider === 'local'
  if (thinksNot(config)) return <p className="subtle">This model does not report thinking controls, so none are sent.</p>
  return <>
    {provider !== 'kobold' && <EffortControl {...props} />}
    {['anthropic', 'google', 'openrouter'].includes(provider) && <ModeControl {...props} />}
    {config.thinking_mode === 'budget' && <ThinkingBudget {...props} />}
    {compatible && <CompatibleControls {...props} />}
  </>
}

/** OpenRouter lists each model's parameters: one without reasoning gets no thinking controls (a saved one still shows,
 * so it can be cleared). */
function thinksNot(config: ProfileConfig): boolean {
  const listed = config.reported_capabilities?.supported_parameters
  if (config.provider !== 'openrouter' || !listed || config.reasoning_effort || config.thinking_mode) return false
  return !listed.includes('reasoning') && !listed.includes('reasoning_effort')
}

function EffortControl({ config, patch, model }: Props) {
  const efforts = config.provider === 'google' ? ['minimal', 'low', 'medium', 'high'] : config.provider === 'anthropic' || config.provider === 'claude_code' ? ['low', 'medium', 'high', 'xhigh', 'max'] : ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
  const reported = model?.supported_efforts ?? config.reported_capabilities?.supported_efforts
  const available = reported ? efforts.filter(value => reported.includes(value)) : efforts
  return <Choice label="Reasoning effort" value={config.reasoning_effort} options={available} onChange={value => patch({ reasoning_effort: value, ...(config.provider === 'google' ? { thinking_mode: null, thinking_budget_tokens: null } : {}) })} capitalised hint={reported ? 'Only the levels this model takes.' : 'This model doesn’t list its levels. If it turns one down, the app switches to the nearest one it takes.'} />
}

function ModeControl({ config, patch }: Props) {
  const provider = config.provider
  const change = (value: string | null) => patch({
    thinking_mode: value as ProfileConfig['thinking_mode'],
    thinking_budget_tokens: value === 'budget' ? (provider === 'anthropic' ? 1024 : 512) : null,
    ...((provider === 'google' || value === 'off') ? { reasoning_effort: null } : {}),
  })
  return <Choice label="Thinking mode" value={config.thinking_mode} options={provider === 'google' ? ['off', 'budget'] : ['off', 'budget', 'adaptive']} onChange={change} hint={provider === 'anthropic' ? 'Adaptive suits models that support it; older thinking models use a budget. Clear temperature and top-k when thinking is on.' : 'Leave at the default when support is unknown.'} />
}

function ThinkingBudget({ config, patch }: Props) {
  const budget = config.thinking_budget_tokens ?? -1
  const reserve = config.response_reserve_tokens ?? 256
  const left = budget >= 0 ? config.max_output_tokens - budget : null
  return <div className="form-grid">
    <NumberInput label="Thinking budget (tokens)" value={config.thinking_budget_tokens ?? ''} min={config.provider === 'anthropic' ? 1024 : config.provider === 'google' ? -1 : 0} max={128000} onChange={value => patch({ thinking_budget_tokens: value === '' ? null : Number(value) })} hint={config.provider === 'google' ? 'Use -1 for a dynamic budget, or 0 to turn thinking off where supported.' : 'Leave enough of the longest reply for the answer.'} />
    <NumberInput label="Reply space after thinking (tokens)" value={reserve} min={64} max={128000} onChange={value => patch({ response_reserve_tokens: Number(value) })} hint="The thinking budget plus this must fit the longest reply." />
    {left !== null && left < reserve && <p role="alert">The thinking budget leaves too little room for a reply.</p>}
  </div>
}

function CompatibleControls({ config, patch }: Props) {
  const thinking = config.compatible_thinking == null ? null : config.compatible_thinking ? 'on' : 'off'
  return <>
    <Choice label="Chat-template thinking" value={thinking} options={['off', 'on']} onChange={value => patch({ compatible_thinking: value === null ? null : value === 'on' })} hint="For servers and models that read enable_thinking. The default sends no switch." />
    <Choice label="Output-limit parameter" value={config.output_token_parameter ?? 'max_tokens'} options={['max_tokens', 'max_completion_tokens']} noDefault onChange={value => patch({ output_token_parameter: (value ?? 'max_tokens') as ProfileConfig['output_token_parameter'] })} hint="Use max_completion_tokens only when the model requires it." />
  </>
}

function SamplingControls({ config, patch }: Props) {
  const fields = samplingFields(config)
  if (!fields.length) return null
  const supported = config.reported_capabilities?.supported_parameters
  return <details className="advanced-settings"><summary>Sampling</summary><div className="form-stack"><p className="subtle">Blank sends nothing, so the service you connect to picks its own value. That can differ between hosts of the same model. Some thinking models reject sampling settings.</p>
    <div className="form-grid">{fields.map(([key, label, min, max, step]) => <NumberInput key={key} label={label} value={config[key] ?? ''} min={min} max={key === 'temperature' && config.provider === 'anthropic' ? 1 : max} step={step} placeholder="Service default" onChange={value => patch({ [key]: value === '' ? null : Number(value) })} tip={samplerTips[key]} hint={supported && !supported.includes(key) ? 'Not reported as supported by this model. Leave blank.' : undefined} />)}</div>
    <div className="form-actions"><button type="button" className="button" onClick={() => patch(Object.fromEntries(samplerFields.map(([key]) => [key, null])))}>Clear sampling settings</button></div></div></details>
}

function NumberInput({ label, value, onChange, hint, tip, min, max, step, placeholder, type = 'number' }: { label: string; value: number | string; onChange: (value: string) => void; hint?: string; tip?: string; min?: number; max?: number; step?: number; placeholder?: string; type?: string }) {
  const leave = () => { const fixed = bounded(String(value), min, max, true); if (fixed !== String(value)) onChange(fixed) }
  return <Field label={label} hint={hint} tip={tip}>{(id, describedBy) => <input id={id} type={type} value={value} min={min} max={max} step={step} placeholder={placeholder} aria-describedby={describedBy} onChange={event => onChange(type === 'number' ? bounded(event.target.value, min, max) : event.target.value)} onBlur={type === 'number' ? leave : undefined} />}</Field>
}

function Choice({ label, value, options, onChange, hint, noDefault, capitalised }: { label: string; value?: string | null; options: string[]; onChange: (value: string | null) => void; hint?: string; noDefault?: boolean; capitalised?: boolean }) {
  const id = useId()
  const shown = (option: string) => capitalised ? option.charAt(0).toUpperCase() + option.slice(1) : option
  return <div className="field"><label htmlFor={id}>{label}</label><select id={id} value={value ?? ''} aria-describedby={hint ? `${id}-hint` : undefined} onChange={event => onChange(event.target.value || null)}>{!noDefault && <option value="">Service default</option>}{value && !options.includes(value) && <option value={value}>{shown(value)} · saved, not reported</option>}{options.map(option => <option key={option} value={option}>{shown(option)}</option>)}</select>{hint && <small id={`${id}-hint`}>{hint}</small>}</div>
}
