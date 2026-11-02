import { useState, type ReactNode } from 'react'
import { FolderOpen } from 'lucide-react'
import { ApiError, api } from '../api'
import { Notice } from './Feedback'

/**
 * A request that failed. When the Dungeon itself hit a bug, its message names the log file, and on the PC
 * a button opens the folder holding it, so the user does not have to find the data folder themself.
 */
export function ErrorNotice({ error, children, action }: { error: Error; children?: ReactNode; action?: ReactNode }) {
  const bug = error instanceof ApiError && error.code === 'server_error'
  const { message, details } = splitDetails(error.message)
  return <Notice tone="error" action={<>{action}{bug && <LogFolderButton />}</>}>
    {children}{message}{details && <small className="error-details">Details: {details}</small>}
  </Notice>
}

/** The Dungeon ends an unexpected failure's message with "Details: …" for a bug report (dungeon/troubleshoot.py),
 * shown on its own smaller line so the plain explanation reads first. */
function splitDetails(text: string): { message: string; details: string } {
  const at = text.lastIndexOf(' Details: ')
  return at < 0 ? { message: text, details: '' } : { message: text.slice(0, at), details: text.slice(at + ' Details: '.length) }
}

function LogFolderButton() {
  const [failed, setFailed] = useState(false)
  const open = () => api('/logs/open-folder', {}).then(() => setFailed(false), () => setFailed(true))
  return (
    <button type="button" className="text-button" onClick={() => void open()}>
      <FolderOpen aria-hidden="true" size={14} />{failed ? 'Could not open it; try again' : 'Open the log folder'}
    </button>
  )
}
