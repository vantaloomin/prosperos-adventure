import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import type { WorkspaceSettings } from '../../types'

/** Shown once, before anything else: the characters are AI, and the app is for adults (docs/safety.md). It can't be
 * closed without confirming; afterwards the line under every message box keeps saying it. */
export function AiNotice() {
  const settings = useWorkspaceSettings()
  if (!settings.data || settings.data.ai_notice_confirmed !== false) return null
  return <AiNoticeDialog />
}

function AiNoticeDialog() {
  const client = useQueryClient()
  const dialog = useRef<HTMLDialogElement>(null)
  const checkbox = useRef<HTMLInputElement>(null)
  const [adult, setAdult] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    checkbox.current?.focus()  // Not the safety link, which would start out outlined.
    return () => element?.close()
  }, [])
  const confirm = async () => {
    try {
      client.setQueryData(SETTINGS_KEY, await api<WorkspaceSettings>('/settings', { ai_notice_confirmed: true }, 'PUT'))
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved. Please try again.') }
  }
  return (
    <dialog ref={dialog} className="dialog ai-notice" aria-labelledby="ai-notice-title" onCancel={(event) => event.preventDefault()}>
      <h2 id="ai-notice-title">Before you start</h2>
      <div className="dialog-body">
        <p>The narrator and everyone in Prospero&apos;s Dungeon are AI. Everything they say is written by an AI model, not a person, and it can be wrong. They stay in the story, so a line under the message box reminds you.</p>
        <p>If you ever mention hurting yourself, the app shows a note with places to get help. It never stops the story and nothing is sent anywhere. <a href="https://github.com/vantaloomin/prosperos-dungeon/blob/main/Program/docs/safety.md" target="_blank" rel="noreferrer">How the app handles safety</a></p>
        <label className="ai-notice-adult"><input ref={checkbox} type="checkbox" checked={adult} onChange={(event) => setAdult(event.target.checked)} /> I&apos;m 18 or older</label>
        {error && <p className="error-text" role="alert">{error}</p>}
      </div>
      <div className="dialog-actions">
        <button type="button" className="button primary" disabled={!adult} onClick={() => void confirm()}>Continue</button>
      </div>
    </dialog>
  )
}
