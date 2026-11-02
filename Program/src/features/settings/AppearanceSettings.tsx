import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import type { WorkspaceSettings } from '../../types'
import { Notice } from '../../components/Feedback'
import { ColorSchemeSettings } from './ColorSchemeSettings'
import { DeviceLookSettings } from './DeviceLookSettings'
import type { ColorScheme, Palette } from './palette'

type Change = { color_scheme?: ColorScheme; custom_palette?: Palette; theme?: WorkspaceSettings['theme'] }

/** General > Appearance: the app's colors, and this device's text size, reading font and motion. */
export function AppearanceSettings() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const [error, setError] = useState<string | null>(null)
  if (!settings.data) return null
  const save = async (change: Change) => {
    setError(null)
    try { client.setQueryData(SETTINGS_KEY, await api<WorkspaceSettings>('/settings', change, 'PUT')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (
    <section className="settings-section form-stack" aria-labelledby="appearance-heading">
      <div><h2 id="appearance-heading">Appearance</h2></div>
      {error && <Notice tone="error">{error}</Notice>}
      <ColorSchemeSettings theme={settings.data.theme ?? 'scheme'} scheme={settings.data.color_scheme ?? 'ink'}
        palette={settings.data.custom_palette ?? null} save={save} />
      <DeviceLookSettings />
    </section>
  )
}
