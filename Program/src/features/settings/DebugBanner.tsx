import { Clock } from 'lucide-react'
import { useDebugTime } from '../../appClock'
import { useWorkspaceSettings } from '../../workspace'
import { bannerText } from './debugText'

/** Shown above every view while debug time is on, so a moved clock is never mistaken for the real one. */
export function DebugBanner({ onOpen }: { onOpen: () => void }) {
  const status = useDebugTime()
  const workspace = useWorkspaceSettings()
  if (!status.data?.active) return null
  return (
    <div className="debug-banner" role="status">
      <Clock aria-hidden="true" />
      <span>{bannerText(status.data, workspace.data?.user_timezone)}</span>
      <button type="button" className="text-button" onClick={onOpen}>Open Debug</button>
    </div>
  )
}
