import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../../api'
import { Notice } from '../../../components/Feedback'
import { HARDWARE_KEY, useHardware, type HardwareWarning } from './hardware'

/** Settings > Models: nothing about the computer unless a chosen local model won't fit or will run badly; then the
 *  warning, with a fix when there is one. */
export function HardwareCheck() {
  const data = useHardware().data
  if (!data?.warnings.length) return null
  return <section className="settings-section form-stack" aria-label="This computer"><HardwareWarnings warnings={data.warnings} /></section>
}

/** Warnings for the setup in use; `area` keeps only those about one part, such as pictures. */
export function HardwareWarnings({ warnings, area }: { warnings: HardwareWarning[]; area?: HardwareWarning['area'] }) {
  const shown = area ? warnings.filter(warning => warning.area === area) : warnings
  return <>{shown.map(warning => <Notice key={warning.text} tone={warning.tone === 'warning' ? 'warning' : 'info'}>
    {warning.text}
    {warning.action && <UseFile action={warning.action} />}
    {warning.after && <span className="hardware-after">{warning.after}</span>}
  </Notice>)}</>
}

/** One press puts the backend on the model file that fits (Iris, 2026-10-28); the warning then clears. */
function UseFile({ action }: { action: NonNullable<HardwareWarning['action']> }) {
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const use = async () => {
    setBusy(true)
    try {
      await api(`/images/backends/${action.backend_id}`, { unet_name: action.unet_name }, 'PUT')
      await Promise.all([client.invalidateQueries({ queryKey: ['image-backends'] }), client.invalidateQueries({ queryKey: HARDWARE_KEY })])
    } finally { setBusy(false) }
  }
  return <span className="hardware-fix"><button type="button" className="button" aria-disabled={busy} onClick={() => { if (!busy) void use() }}>{action.label}</button></span>
}
