import type { CSSProperties } from 'react'
import { paletteReadability, paletteStyle, type Palette } from '../settings/palette.ts'

/** The colors the story's world ships (dungeon/world_theme.py): Vallarith's ember, Havenbrooke's autumn quad. */
export interface WorldTheme { world: string | null; theme: { name: string; palette: Palette } | null }

/** The world's palette as the CSS variables the story screen sets on itself, or none: the player turned world colors
 *  off, the world ships none, or they would not read (text 4.5:1, accent 3:1, as a custom palette must). */
export function themeStyle(found: WorldTheme | undefined, on: boolean): CSSProperties | undefined {
  const palette = found?.theme?.palette
  if (!on || !palette || !paletteReadability(palette).valid) return undefined
  return paletteStyle(palette)
}
