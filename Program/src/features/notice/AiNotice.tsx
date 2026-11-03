import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import type { WorkspaceSettings } from '../../types'

/** Shown once, before anything else: the characters are AI, and the app is for adults. It can't be closed without
 * confirming; afterwards the line under every message box keeps saying it. What the app does about safety is on the
 * Safety page (docs/safety.md), so the notice itself is one fact, one check and one button. */
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
      <form method="dialog" onSubmit={(event) => { event.preventDefault(); if (adult) void confirm() }}>
        <h2 id="ai-notice-title">Everyone here is AI</h2>
        <label className="ai-notice-adult"><input ref={checkbox} type="checkbox" checked={adult} onChange={(event) => setAdult(event.target.checked)} /> I&apos;m 18 or older</label>
        {error && <p className="error-text" role="alert">{error}</p>}
        <div className="ai-notice-actions">
          <a href={SAFETY} target="_blank" rel="noreferrer">Safety</a>
          <button type="submit" className="button primary" disabled={!adult}>Enter</button>
        </div>
      </form>
    </dialog>
  )
}

const SAFETY = 'https://github.com/vantaloomin/prosperos-adventure/blob/main/Program/docs/safety.md'
