import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, RotateCcw } from 'lucide-react'
import { api } from '../../api'
import type { AutoBackups, BackupList, BackupResult } from '../../types'
import { Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { backupLabel } from './backupText'
import { shownPath } from '../../paths'

const BACKUPS_KEY = ['backups']
const formatDate = (iso: string) => new Date(iso).toLocaleString()

export function Backups() {
  const client = useQueryClient()
  const list = useQuery({ queryKey: BACKUPS_KEY, queryFn: () => api<BackupList>('/backups') })
  const [result, setResult] = useState<{ tone: 'info' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState<string | null>(null)
  // Busy controls are marked, not disabled: disabling the focused control would drop keyboard focus.
  const run = async (action: () => Promise<unknown>, fallback: string) => {
    if (busy) return
    setBusy(true)
    try { await action() } catch (error) {
      setResult({ tone: 'error', text: error instanceof Error ? error.message : fallback })
    } finally { setBusy(false) }
  }
  const backup = () => run(async () => {
    const created = await api<BackupResult>('/backups', {})
    setResult({ tone: 'info', text: `Backup saved to ${shownPath(created.path)}.` })
    await client.invalidateQueries({ queryKey: BACKUPS_KEY })
  }, 'The backup failed.')
  const choose = (name: string) => run(async () => {
    client.setQueryData(BACKUPS_KEY, await api<BackupList>(`/backups/${encodeURIComponent(name)}/restore`, {}))
    setConfirming(null)
    setResult(null)
  }, 'That backup cannot be restored.')
  const cancel = () => run(async () => {
    client.setQueryData(BACKUPS_KEY, await api<BackupList>('/backups/restore', undefined, 'DELETE'))
  }, 'The restore was not cancelled.')
  const pending = list.data?.pending
  return (
    <section className="settings-section form-stack" aria-labelledby="backup-heading">
      <div>
        <h2 id="backup-heading">Backups</h2>
        <p className="subtle">A backup is a copy of the world you are in, saved beside it: your story, its people and its town. Your API keys are not included. Anything you delete later stays in backups made before.</p>
      </div>
      {<AutoBackupsSetting list={list.data} onSaved={() => void client.invalidateQueries({ queryKey: BACKUPS_KEY })} />}
      {result && <Notice tone={result.tone}>{result.text}</Notice>}
      {pending && (
        <Notice action={<button type="button" className="text-button" aria-disabled={busy} onClick={() => void cancel()}>Cancel</button>}>
          {pending.name} will be restored the next time the Dungeon starts. Close it and start it again to finish.
        </Notice>
      )}
      <div className="form-actions"><button type="button" className="button" aria-disabled={busy} onClick={() => void backup()}><Archive aria-hidden="true" />Back up now</button></div>
      {list.isError && <ErrorNotice error={list.error} />}
      {list.data && list.data.backups.length > 0 && (
        <div className="form-stack">
          <h3>Restore a backup</h3>
          <p className="subtle">Restoring replaces this workspace when the Dungeon next starts. The current one is moved aside, not deleted, and anything you deleted since the backup stays deleted. Your current settings and connections stay as they are.</p>
          <ul className="plain-list">
            {list.data.backups.map((entry) => (
              <li key={entry.name}>
                {backupLabel(entry, formatDate)}{' '}
                {entry.readable && pending?.name !== entry.name && (confirming === entry.name
                  ? <>
                      <button type="button" className="text-button" aria-disabled={busy} onClick={() => void choose(entry.name)}>Restore on next start</button>{' '}
                      <button type="button" className="text-button" onClick={() => setConfirming(null)}>Keep current</button>
                    </>
                  : <button type="button" className="text-button" onClick={() => setConfirming(entry.name)}><RotateCcw aria-hidden="true" />Restore…</button>)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

const EVERY: [AutoBackups, string][] = [['daily', 'Every day'], ['weekly', 'Every week'], ['off', 'Off']]

/** Automatic backups cover every world, on their own, while the app runs; this sets how often. */
function AutoBackupsSetting({ list, onSaved }: { list: BackupList | undefined; onSaved: () => void }) {
  const [error, setError] = useState('')
  if (!list) return null
  const save = async (auto_backups: AutoBackups) => {
    setError('')
    try { await api('/settings', { auto_backups }, 'PUT'); onSaved() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  const last = list.last_auto_backup ? `Last one here: ${formatDate(`${list.last_auto_backup}Z`)}.` : 'The first one is made a few minutes after the app starts.'
  return (
    <div className="field">
      <label htmlFor="auto-backups">Automatic backups</label>
      <select id="auto-backups" value={list.auto_backups} aria-describedby="auto-backups-hint" onChange={(event) => void save(event.target.value as AutoBackups)}>
        {EVERY.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <small id="auto-backups-hint">Every world is backed up on its own while the Dungeon runs. The last 7 days and one a week for 4 weeks before are kept. {list.auto_backups !== 'off' && last}</small>
      {error && <Notice tone="error">{error}</Notice>}
    </div>
  )
}
