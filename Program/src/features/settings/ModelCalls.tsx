import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Trash2 } from 'lucide-react'
import { api } from '../../api'
import type { ModelCallLog } from '../../types'
import { Notice } from '../../components/Feedback'
import { Toggle } from '../../components/Fields'

const KEY = ['model-calls']

function size(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** Settings > Developer: write every model request and response down in full, to find out why a reply came out
 * strange (dungeon/model_calls.py). Off by default; the files hold the chats word for word. PC only. */
export function ModelCalls() {
  const client = useQueryClient()
  const log = useQuery({ queryKey: KEY, queryFn: () => api<ModelCallLog>('/model-calls') })
  const [error, setError] = useState('')
  const change = async (body?: { recording: boolean }) => {
    setError('')
    try { client.setQueryData(KEY, await api<ModelCallLog>('/model-calls', body ?? {}, body ? 'PUT' : 'DELETE')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work.') }
  }
  const data = log.data
  return (
    <section className="settings-section form-stack" aria-labelledby="model-calls-heading">
      <div>
        <h2 id="model-calls-heading">Record model calls</h2>
        <p className="subtle">For tracking down a strange reply: every request the app sends to your model, in full, and exactly what came back, one file a day in the logs folder. Keys are never written. Kept 7 days.</p>
      </div>
      <Toggle label="Record model calls" checked={data?.recording === true} disabled={!data} onChange={(checked) => void change({ recording: checked })}
        hint="The files hold your story and the narrator's prompts word for word. Turn this off once you have what you need, and only share the files with someone you trust." />
      {data && data.files > 0 && (
        <div className="form-actions">
          <a className="button" href="/api/model-calls/download" download><Download aria-hidden="true" />Save for support ({size(data.bytes)})</a>
          <button type="button" className="button" onClick={() => void change()}><Trash2 aria-hidden="true" />Delete recorded calls</button>
        </div>
      )}
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}
