import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { WorkspaceSettings } from './types'
import type { SettingsTab } from './features/settings/sections'

/** A view, as named in the address after #. Settings can name a tab too: #settings/models. */
export type View = 'story' | 'worlds' | 'settings' | `settings/${SettingsTab}`

export const SETTINGS_KEY = ['settings']

export function useWorkspaceSettings() {
  return useQuery({ queryKey: SETTINGS_KEY, queryFn: () => api<WorkspaceSettings>('/settings') })
}

/** This PC's timezone as the browser resolves it, with the backend's own reading as the fallback. */
export function pcTimezone(settings?: Pick<WorkspaceSettings, 'system_timezone'>): string | null {
  const browser = guessTimezone()
  return browser !== 'UTC' || !settings?.system_timezone ? browser : settings.system_timezone
}

/** On open, a workspace that follows the PC (or is still on the UTC default) takes the browser's zone. */
export function useFollowPcTimezone() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const sent = useRef(false)
  useEffect(() => {
    const data = settings.data
    if (!data || sent.current || data.user_timezone_source === 'chosen') return
    const zone = pcTimezone(data)
    if (!zone || zone === data.user_timezone) return
    sent.current = true
    // The backend ignores this if the user picked a zone meanwhile; a refusal just leaves the setting alone.
    api<WorkspaceSettings>('/settings', { user_timezone: zone, user_timezone_source: 'detected' }, 'PUT')
      .then((saved) => client.setQueryData(SETTINGS_KEY, saved))
      .catch(() => undefined)
  }, [client, settings.data])
}

/** The zone the browser resolves, or UTC when it gives none. */
export function guessTimezone(): string {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' } catch { return 'UTC' }
}

/** Every IANA zone the browser knows, for the timezone field. */
export function timezones(): string[] {
  try { return Intl.supportedValuesOf('timeZone') } catch { return ['UTC'] }
}
