import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import type { WorkspaceSettings } from '../../types'
import { Field, Toggle } from '../../components/Fields'
import { Notice } from '../../components/Feedback'

const BUDGETS: [number, string][] = [[0, 'Automatic (90 seconds on this PC, 30 for an online model)'], [15, '15 seconds'],
  [30, '30 seconds'], [60, '1 minute'], [90, '90 seconds'], [120, '2 minutes'], [180, '3 minutes']]

const CAPS: [number, string][] = [[0, "The model's whole window"], [4000, '4,000 tokens'], [8000, '8,000 tokens'],
  [16000, '16,000 tokens'], [32000, '32,000 tokens'], [64000, '64,000 tokens']]

/** Models > Turn speed (dungeon/pace.py): how long a story turn may take before its optional steps give way, whether a
 * narration that clashes with the record is rewritten, and how much a turn may send (dungeon/remembering.py). */
export function TurnSpeed() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const [error, setError] = useState('')
  const save = async (change: Partial<Pick<WorkspaceSettings, 'turn_budget' | 'contradiction_check' | 'context_cap'>>) => {
    setError('')
    try { client.setQueryData(SETTINGS_KEY, await api<WorkspaceSettings>('/settings', change, 'PUT')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (
    <section className="settings-section form-stack" aria-labelledby="turn-speed-heading">
      <div>
        <h2 id="turn-speed-heading">Turn speed</h2>
        <p className="subtle">The story streams as it is written, and the facts are noted after you can read it.</p>
      </div>
      <Field label="Time for each turn" hint="Past it, the polishing steps give way: the prose rewrite first, then the check against the record. Dice and the record are never skipped.">
        {(id, describedBy) => <select id={id} value={settings.data?.turn_budget ?? 0} disabled={!settings.data} aria-describedby={describedBy}
          onChange={(event) => void save({ turn_budget: Number(event.target.value) })}>
          {BUDGETS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>}
      </Field>
      <Toggle label="Check each narration against the record" hint="A passage that has the dead acting is rewritten before you read it. Off is faster on slow local models; such a passage is then marked for you to rewrite."
        checked={settings.data?.contradiction_check ?? true} disabled={!settings.data} onChange={(checked) => void save({ contradiction_check: checked })} />
      <Field label="Most a turn may send" hint="Caps the tokens each turn sends, to keep paid models cheap and fast. The summary and older facts give way first; the latest turns are kept.">
        {(id, describedBy) => <select id={id} value={settings.data?.context_cap ?? 0} disabled={!settings.data} aria-describedby={describedBy}
          onChange={(event) => void save({ context_cap: Number(event.target.value) })}>
          {CAPS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>}
      </Field>
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}
