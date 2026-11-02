import { useSyncExternalStore } from 'react'

/** Text size, reading font and motion belong to this device, not the workspace: a phone and a 27" monitor want different
 * sizes (Iris, v09-appearance-first-launch.md). Kept in this browser; nothing breaks when storage is unavailable. */
export type ReadingFont = 'default' | 'atkinson' | 'opendyslexic'
export type Motion = 'system' | 'reduce' | 'full'
/** The story screen's layout (requirements "Play screen and widgets": presets as modes). Classic keeps the scene panel
 *  beside the story on a wide screen; Reader gives the story the width and folds the panel into its tabs; Custom is the
 *  free grid the player arranges (src/features/story/grid.ts), never the default; Visual novel puts the story's text box
 *  over the scene's picture with portraits of who is here (StoryArt.tsx StoryStage), and is Classic until pictures are
 *  made. */
export type Layout = 'classic' | 'reader' | 'custom' | 'novel'
export type Beside = Exclude<Layout, 'reader'>
/** `stageArt`: the place's picture behind the story and portraits of who is here, when they have been made.
 *  `lastBeside`: the layout with the panel beside the story that Reader goes back to. `worldColors`: the story screen
 *  wears the colors its world ships (dungeon/world_theme.py), when they read well. `panelWidth` and `gridWidth`: how wide
 *  the player dragged the panel beside the story, in Classic or Visual novel and in Custom (StoryPanel.tsx PanelResize). */
export interface DeviceLook { textScale: number; font: ReadingFont; fontEverywhere: boolean; motion: Motion; layout: Layout; lastBeside: Beside; stageArt: boolean; worldColors: boolean; panelWidth: number; gridWidth: number }

export const TEXT_SCALE = { min: 85, max: 200, step: 5 } as const
/** The panel beside the story, in pixels: the single column of widgets, and Custom's two-column grid. */
export const PANEL_WIDTH = { min: 280, max: 720, default: 360 } as const
export const GRID_WIDTH = { min: 440, max: 1000, default: 600 } as const
export const DEFAULT_LOOK: DeviceLook = { textScale: 100, font: 'default', fontEverywhere: false, motion: 'system', layout: 'classic', lastBeside: 'classic', stageArt: true, worldColors: true,
  panelWidth: PANEL_WIDTH.default, gridWidth: GRID_WIDTH.default }
const KEY = 'dungeon-device-look'
const FONTS: ReadingFont[] = ['default', 'atkinson', 'opendyslexic']
const MOTIONS: Motion[] = ['system', 'reduce', 'full']
const LAYOUTS: Layout[] = ['classic', 'reader', 'custom', 'novel']
const listeners = new Set<() => void>()

export function clampScale(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_LOOK.textScale
  return Math.min(TEXT_SCALE.max, Math.max(TEXT_SCALE.min, Math.round(value / TEXT_SCALE.step) * TEXT_SCALE.step))
}

/** A panel width kept within its bounds, whole pixels. */
export function clampWidth(value: number, bounds: { min: number; max: number; default: number }): number {
  if (!Number.isFinite(value)) return bounds.default
  return Math.min(bounds.max, Math.max(bounds.min, Math.round(value)))
}

/** A saved look with anything unknown or out of range put back to its default. */
export function cleanLook(value: unknown): DeviceLook {
  const saved = (value && typeof value === 'object' ? value : {}) as Partial<DeviceLook>
  return {
    textScale: clampScale(Number(saved.textScale ?? DEFAULT_LOOK.textScale)),
    font: FONTS.includes(saved.font as ReadingFont) ? saved.font as ReadingFont : DEFAULT_LOOK.font,
    fontEverywhere: saved.fontEverywhere === true,
    motion: MOTIONS.includes(saved.motion as Motion) ? saved.motion as Motion : DEFAULT_LOOK.motion,
    layout: LAYOUTS.includes(saved.layout as Layout) ? saved.layout as Layout : DEFAULT_LOOK.layout,
    lastBeside: saved.lastBeside === 'custom' || saved.lastBeside === 'novel' ? saved.lastBeside : 'classic',
    stageArt: saved.stageArt !== false,
    worldColors: saved.worldColors !== false,
    panelWidth: clampWidth(Number(saved.panelWidth), PANEL_WIDTH),
    gridWidth: clampWidth(Number(saved.gridWidth), GRID_WIDTH),
  }
}

let current: DeviceLook | null = null

export function readLook(): DeviceLook {
  if (current) return current
  try {
    current = cleanLook(JSON.parse(localStorage.getItem(KEY) ?? 'null'))
  } catch {
    current = DEFAULT_LOOK
  }
  return current
}

export function saveLook(change: Partial<DeviceLook>) {
  const beside = change.layout && change.layout !== 'reader' ? { lastBeside: change.layout } : {}
  current = cleanLook({ ...readLook(), ...change, ...beside })
  try { localStorage.setItem(KEY, JSON.stringify(current)) } catch { /* kept for this visit only */ }
  applyLook(current)
  listeners.forEach((listener) => listener())
}

/** The page root carries the look, so every screen and dialog follows it (styles.css: data-font, data-motion). */
export function applyLook(look: DeviceLook) {
  const root = document.documentElement
  root.style.fontSize = look.textScale === 100 ? '' : `${look.textScale}%`
  root.dataset.font = look.font
  root.dataset.fontEverywhere = String(look.fontEverywhere && look.font !== 'default')
  root.dataset.motion = look.motion
  root.dataset.layout = look.layout
  // From 150% the desktop nav rail shows icons only (their names stay for screen readers).
  root.dataset.textLarge = String(look.textScale >= 150)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function useDeviceLook(): DeviceLook {
  return useSyncExternalStore(subscribe, readLook, () => DEFAULT_LOOK)
}
