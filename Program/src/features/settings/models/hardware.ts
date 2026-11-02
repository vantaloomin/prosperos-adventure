import { useQuery } from '@tanstack/react-query'
import { api } from '../../../api'

export interface Gpu { index: number; name: string; memory_gb: number; usable_gb: number; used_gb: number | null; shared: boolean }
export type Area = 'computer' | 'text' | 'images'
export interface HardwareWarning {
  area: Area; tone: 'warning' | 'tip'; text: string
  // A one-press fix: put a ComfyUI backend on a model file it has that fits the card (dungeon/hardware.py too_big).
  action?: { label: string; backend_id: string; unet_name: string }
  // A last line after the fix, such as the hosted service to fall back on.
  after?: string
}
export interface HardwareReport {
  computer: { system: string; cores: number; memory_gb: number | null; gpus: Gpu[]; gpu_note: string | null }
  can_run: string[]
  warnings: HardwareWarning[]
}

export const HARDWARE_KEY = ['hardware']
export const gb = (value: number) => value >= 10 ? `${Math.round(value)} GB` : `${value.toFixed(1)} GB`

/** The server scans this computer (dungeon/hardware.py) and checks the models set up against it. */
export function useHardware() {
  return useQuery({ queryKey: HARDWARE_KEY, queryFn: () => api<HardwareReport>('/hardware') })
}
