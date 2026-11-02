import type { ReactNode } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle2, Info, LoaderCircle } from 'lucide-react'

export function Loading({ label }: { label: string }) {
  return <div className="loading" role="status"><LoaderCircle aria-hidden="true" /><span>{label}</span></div>
}

/** Errors are announced assertively; other notices politely. A warning is advice, not a failure. */
export function Notice({ tone = 'info', children, action }: { tone?: 'info' | 'error' | 'warning' | 'success'; children: ReactNode; action?: ReactNode }) {
  const Icon = tone === 'error' ? AlertCircle : tone === 'warning' ? AlertTriangle : tone === 'success' ? CheckCircle2 : Info
  return (
    <div className={`notice notice-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon aria-hidden="true" /><span>{children}</span>{action}
    </div>
  )
}
