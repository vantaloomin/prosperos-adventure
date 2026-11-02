import { useQuery } from '@tanstack/react-query'
import type { CSSProperties } from 'react'
import { api } from '../../api'
import type { Story } from '../../types'
import { useDeviceLook } from '../settings/deviceLook'
import { themeStyle, type WorldTheme } from './worldTheme'

/** The story screen's class and colors: its world's, when it ships some and this device uses them (Settings >
 *  Appearance). */
export function useWorldTheme(story: Story | undefined): { className: string; style?: CSSProperties } {
  const { worldColors } = useDeviceLook()
  const city = story?.scene.city.id ?? ''
  // Asked again only when the story moves to another city (a new campaign may be in another world).
  const found = useQuery({ queryKey: ['story-theme', city], queryFn: () => api<WorldTheme>('/story/theme'), staleTime: Infinity, enabled: worldColors && !!city })
  const style = themeStyle(found.data, worldColors)
  return style ? { className: 'story world-colors', style } : { className: 'story' }
}
