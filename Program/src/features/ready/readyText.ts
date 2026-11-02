// Words and numbers for "Set it up for me" (dungeon/ready.py; Iris, v09-appearance-first-launch.md).

export type ReadyStatus = 'idle' | 'downloading' | 'checking' | 'paused' | 'cancelled' | 'failed' | 'ready'
export interface ReadyModel { key: string; name: string; quant: string; bits: string; bytes: number; file: string; licence: string; page: string; fits: boolean }
export interface ReadyView {
  pick: ReadyModel; reason: string; models: ReadyModel[]; runtime: { installed: boolean }; runtime_bytes: number
  card: { name: string; memory_gb: number } | null
  status: ReadyStatus; model: string | null; received: number; total: number; message: string; waiting: boolean
  seconds_left: number | null; free_bytes: number | null; drive: string; in_use: boolean; profile_id: string | null
  announced: boolean; settings_seen: boolean
}

/** Under way or waiting on the user: the progress row shows instead of the offer. */
export const ACTIVE: ReadyStatus[] = ['downloading', 'checking', 'paused', 'cancelled', 'failed']
export const isActive = (view?: ReadyView | null) => !!view && ACTIVE.includes(view.status)
export const isRunning = (view?: ReadyView | null) => !!view && (view.status === 'downloading' || view.status === 'checking')

/** "10.5 GB", or "25 MB" for the small runtime. */
export function size(bytes: number): string {
  if (bytes < 1e9) return `${Math.max(1, Math.round(bytes / 1e6))} MB`
  return bytes >= 100e9 ? `${Math.round(bytes / 1e9)} GB` : `${(bytes / 1e9).toFixed(1)} GB`
}

/** Rounded so it never flickers: "about 2 minutes", "about 40 minutes", "about 1 hour". */
export function timeLeft(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return ''
  const minutes = seconds / 60
  if (minutes < 1.5) return 'about a minute'
  if (minutes < 10) return `about ${Math.round(minutes)} minutes`
  if (minutes < 55) return `about ${Math.round(minutes / 5) * 5} minutes`
  const hours = Math.round(minutes / 30) / 2
  return hours <= 1 ? 'about 1 hour' : `about ${hours} hours`
}

/** The quant code stays for those who know it (Vanta); the words are what most people read. */
export function quality(quant: string): string {
  if (/^Q8|^F16|^BF16/i.test(quant)) return 'high quality'
  if (/^Q[56]/i.test(quant)) return 'high quality'
  if (/^Q4/i.test(quant)) return 'balanced'
  return 'smaller and faster'
}

export const percent = (view: ReadyView) => view.total ? Math.min(100, Math.floor(view.received / view.total * 100)) : 0

/** The last quarter passed, for the polite announcement (25, 50, 75, 100), or 0. */
export const milestone = (value: number) => Math.floor(value / 25) * 25

export const modelOf = (view: ReadyView) => view.models.find(model => model.key === view.model) ?? view.pick

/** "3.2 of 10.5 GB · about 12 minutes left", or why it is not moving. */
export function progressLine(view: ReadyView): string {
  const amount = `${(view.received / 1e9).toFixed(1)} of ${size(view.total)}`
  if (view.status === 'checking') return `Checking the download · ${size(view.total)}`
  if (view.waiting) return `Waiting for the connection… ${amount}`
  if (view.status === 'paused') return `Paused · ${amount}`
  if (view.status === 'failed') return view.message || `Stopped · ${amount}`
  const left = timeLeft(view.seconds_left)
  return left ? `${amount} · ${left} left` : amount
}

/** Under a card already titled with the model: "Downloading · 5.4 of 17.6 GB · about 15 minutes left". */
export const cardLine = (view: ReadyView) => view.status === 'downloading' && !view.waiting ? `Downloading · ${progressLine(view)}` : progressLine(view)

export function heading(view: ReadyView): string {
  const name = modelOf(view).name
  if (view.status === 'cancelled') return 'Download cancelled.'
  if (view.status === 'checking') return `Checking ${name}`
  if (view.status === 'failed') return `${name} stopped downloading`
  if (view.status === 'paused') return `${name} is paused`
  return `Downloading ${name}`
}

/** The download needs the model, the runtime if this computer lacks it, and a little room to spare. */
export const needed = (view: ReadyView, model: ReadyModel = view.pick) => model.bytes + view.runtime_bytes
export const roomy = (view: ReadyView, model: ReadyModel = view.pick) => view.free_bytes === null || view.free_bytes >= needed(view, model) + 2e9

export function navLabel(view: ReadyView | undefined): string | undefined {
  if (view && isActive(view) && view.status !== 'cancelled') return `Settings, model downloading, ${percent(view)}%`
  return view?.status === 'ready' && !view.settings_seen ? 'Settings, model ready' : undefined
}
