// Credits and usage a service reports for free (dungeon/providers/balance.py). Profiles whose service has no
// such lookup show nothing at all.
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../../api'
import type { ModelProfile } from './types'

export interface UsageItem { label: string; amount?: number; currency?: string; of?: number; percent_used?: number; resets_at?: string; count?: number; spent?: boolean }
export interface Usage { items: UsageItem[]; plan?: string | null; checked_at: string }

const usageKey = (profile: ModelProfile) => ['model-usage', profile.id, profile.revision]
const path = (profile: ModelProfile, fresh = false) => `/models/profiles/${profile.id}/usage${fresh ? '?fresh=true' : ''}`

/** Asked once when Settings > Models opens; the server keeps the answer a few minutes, so there is no polling. */
export function useModelUsage(profile: ModelProfile) {
  const client = useQueryClient()
  const query = useQuery({ queryKey: usageKey(profile), queryFn: () => api<Usage | null>(path(profile)), staleTime: 5 * 60_000, retry: false })
  /** Check connection asks the service again rather than showing the kept answer. */
  const refresh = async () => { try { client.setQueryData(usageKey(profile), await api<Usage | null>(path(profile, true))) } catch { /* nothing to show */ } }
  return { usage: query.data ?? null, refresh }
}

function money(amount: number, currency = 'USD') {
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount) } catch { return `${amount.toFixed(2)} ${currency}` }
}

function resets(iso: string) {
  const when = new Date(iso)
  const sameDay = when.toDateString() === new Date().toDateString()
  return sameDay ? when.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
    : when.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

export function valueText(item: UsageItem) {
  if (item.percent_used !== undefined) return `${item.percent_used}% used${item.resets_at ? `, resets ${resets(item.resets_at)}` : ''}`
  if (item.amount !== undefined) return item.of !== undefined ? `${money(item.amount, item.currency)} of ${money(item.of, item.currency)}` : money(item.amount, item.currency)
  return item.count !== undefined ? item.count.toLocaleString() : ''
}


/** Worth flagging: money left under a tenth of the total (or under 1 with no total), or a limit over 80% used. */
export function isLow(item: UsageItem) {
  if (item.percent_used !== undefined) return item.percent_used > 80
  if (item.amount === undefined || item.spent) return false
  return item.of ? item.amount < item.of * 0.1 : item.amount < 1
}
