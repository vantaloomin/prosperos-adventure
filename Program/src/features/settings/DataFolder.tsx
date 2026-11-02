import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FolderInput, FolderOpen } from 'lucide-react'
import { api } from '../../api'
import type { DataFolderStatus } from '../../types'
import { Notice } from '../../components/Feedback'
import { shownPath } from '../../paths'

const DATA_FOLDER_KEY = ['data-folder']

// Where the workspace lives, and moving it into the app's own folder (dungeon/data_folder.py).
export function DataFolder() {
  const client = useQueryClient()
  const status = useQuery({ queryKey: DATA_FOLDER_KEY, queryFn: () => api<DataFolderStatus>('/backups/data-folder') })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  // Busy controls are marked, not disabled: disabling the focused control would drop keyboard focus.
  const run = async (action: () => Promise<unknown>, fallback: string) => {
    if (busy) return
    setBusy(true)
    setError(null)
    try { await action() } catch (failure) {
      setError(failure instanceof Error ? failure.message : fallback)
    } finally { setBusy(false) }
  }
  const open = () => run(() => api('/backups/data-folder/open', {}), 'The folder could not be opened.')
  const move = () => run(async () => {
    client.setQueryData(DATA_FOLDER_KEY, await api<DataFolderStatus>('/backups/data-folder/move', {}))
    setConfirming(false)
  }, 'The move could not be set up.')
  const cancel = () => run(async () => {
    client.setQueryData(DATA_FOLDER_KEY, await api<DataFolderStatus>('/backups/data-folder/move', undefined, 'DELETE'))
  }, 'The move was not cancelled.')
  const data = status.data
  return (
    <section className="settings-section form-stack" aria-labelledby="data-folder-heading">
      <div>
        <h2 id="data-folder-heading">Data folder</h2>
        <p className="subtle">Everything the Dungeon keeps (your conversations, memories, life, images, logs and backups) is in this folder.</p>
      </div>
      {status.isError && <Notice tone="error">{status.error.message}</Notice>}
      {error && <Notice tone="error">{error}</Notice>}
      {data && (
        <>
          <div className="form-actions">
            <button type="button" className="button" aria-disabled={busy} onClick={() => void open()}><FolderOpen size={15} aria-hidden="true" />Open data folder</button>
            <small>{shownPath(data.path)}</small>
          </div>
          {data.portable && <p className="subtle">Your data is inside the app folder, so it goes wherever the app folder goes. Copy or move the whole app folder together, and keep its Data folder with it.</p>}
          {data.notes.map((note) => <Notice key={note}>{note}</Notice>)}
          {data.pending && (
            <Notice action={<button type="button" className="text-button" aria-disabled={busy} onClick={() => void cancel()}>Cancel</button>}>
              Your data will move to {shownPath(data.target)} the next time the Dungeon starts. Close it and start it again to finish.
            </Notice>
          )}
          {!data.portable && !data.pending && (
            <div className="form-stack">
              <h3>Keep data with the app</h3>
              <p className="subtle">Moving your data into the app folder keeps everything together, for example on an external drive. The Dungeon copies it when it next starts, checks the copy, and leaves the old folder as it was until you delete it.</p>
              {data.reason
                ? <p className="subtle">{data.reason}</p>
                : confirming
                  ? <div className="form-actions">
                      <button type="button" className="button" aria-disabled={busy} onClick={() => void move()}>Move on next start</button>
                      <button type="button" className="text-button" onClick={() => setConfirming(false)}>Keep it here</button>
                    </div>
                  : <div className="form-actions"><button type="button" className="button" onClick={() => setConfirming(true)}><FolderInput size={15} aria-hidden="true" />Move into the app folder…</button><small>{shownPath(data.target)}</small></div>}
            </div>
          )}
        </>
      )}
    </section>
  )
}
