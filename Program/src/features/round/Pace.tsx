import { useId, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { Notice } from '../../components/Feedback'
import { ROUND_KEY, useRoundTable } from './useRound'
import type { AgentPace, RoundTable } from './round'
import { estimateLine, LOYALTY, PACE_LABELS, PRESET_NAMES, SCHEMING, spendLine } from './roundText'

const PACE_KEY = ['agents']

/** Settings > Models: how the characters who think for themselves are paced in this campaign (adventure/agent_routes.py,
 *  adventure/round_routes.py). The preset with its estimate; under Advanced, how many think at once, how many exchanges
 *  a turn may hold, how much they scheme, how fast loyalties shift, and the session's cap. A change made during a turn
 *  counts from the next one. */
export function Pace() {
  const pace = useQuery({ queryKey: PACE_KEY, queryFn: () => api<AgentPace>('/agents') })
  const table = useRoundTable()
  const client = useQueryClient()
  const [error, setError] = useState('')
  const name = useId()
  if (!pace.data || !table.data) return null
  const save = (body: Partial<AgentPace>) => api<AgentPace>('/agents', body, 'PUT')
    .then((data) => { client.setQueryData(PACE_KEY, data); setError('') }, (failure: unknown) => setError(failure instanceof Error ? failure.message : 'Not changed.'))
  const saveTable = (body: { agent_cap?: number; converse_cap?: number }) => api<RoundTable>('/rounds/settings', body, 'PUT')
    .then((data) => { client.setQueryData(ROUND_KEY, data); setError(''); return client.invalidateQueries({ queryKey: PACE_KEY }) },
      (failure: unknown) => setError(failure instanceof Error ? failure.message : 'Not changed.'))
  return (
    <section className="settings-section form-stack" aria-labelledby="pace-heading">
      <h2 id="pace-heading">{PACE_LABELS.title}</h2>
      <fieldset className="pace-presets">
        <legend className="visually-hidden">{PACE_LABELS.title}</legend>
        {pace.data.presets.map((preset) => <label key={preset.key} className="pace-preset">
          <input type="radio" name={name} checked={pace.data.preset === preset.key} onChange={() => void save({ preset: preset.key })} />
          <span><span className="pace-name">{PRESET_NAMES[preset.key]}</span><small>{estimateLine(preset.estimate)}</small></span>
        </label>)}
      </fieldset>
      <details className="pace-advanced">
        <summary>{PACE_LABELS.advanced}</summary>
        <div className="form-stack">
          <NumberField label={PACE_LABELS.agentCap} value={table.data.settings.queued.agent_cap ?? table.data.settings.agent_cap} min={1} max={6} onSave={(value) => void saveTable({ agent_cap: value })} />
          <NumberField label={PACE_LABELS.converseCap} value={table.data.settings.queued.converse_cap ?? table.data.settings.converse_cap} min={1} max={12} onSave={(value) => void saveTable({ converse_cap: value })} />
          <Choice label={PACE_LABELS.scheming} value={String(pace.data.scheming)} options={SCHEMING.map((label, index) => ({ key: String(index), name: label }))} onSave={(value) => void save({ scheming: Number(value) })} />
          <Choice label={PACE_LABELS.loyalty} value={pace.data.loyalty} options={LOYALTY} onSave={(value) => void save({ loyalty: value as AgentPace['loyalty'] })} />
          <NumberField label={PACE_LABELS.sessionCap} value={pace.data.session_cap} min={0} max={100_000_000} step={10_000} placeholder={PACE_LABELS.none} onSave={(value) => void save({ session_cap: value })}
            after={<small className="subtle">{spendLine(pace.data.spend)}</small>} />
        </div>
      </details>
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}

interface NumberProps { label: string; value: number; min: number; max: number; step?: number; placeholder?: string; onSave: (value: number) => void; after?: ReactNode }

/** A number saved when the field is left, kept inside its range. */
function NumberField({ label, value, min, max, step, placeholder, onSave, after }: NumberProps) {
  const id = useId()
  const [text, setText] = useState<string | null>(null)
  const leave = () => {
    if (text === null) return
    const parsed = Math.min(max, Math.max(min, Math.round(Number(text) || 0)))
    setText(null)
    if (parsed !== value) onSave(parsed)
  }
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="number" inputMode="numeric" min={min} max={max} step={step} placeholder={placeholder}
        value={text ?? (placeholder && !value ? '' : String(value))} onChange={(event) => setText(event.target.value)} onBlur={leave}
        onKeyDown={(event) => { if (event.key === 'Enter') leave() }} />
      {after}
    </div>
  )
}

function Choice({ label, value, options, onSave }: { label: string; value: string; options: { key: string; name: string }[]; onSave: (value: string) => void }) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onSave(event.target.value)}>
        {options.map((option) => <option key={option.key} value={option.key}>{option.name}</option>)}
      </select>
    </div>
  )
}
