import { useState } from 'react'
import { loadPins, TABS, WIDGET_NAMES, type Widget } from './scene.ts'

/** The Custom layout's free grid (requirements "Play screen and widgets": "a free snapping grid with saved layouts,
 *  an optional Customize layout mode, never the default"). The scene panel becomes a grid of tiles the player
 *  arranges: which widgets, in what order, and how big (small, wide across both columns, or tall). `scene` is the scene panel's
 *  own picks (the fight, the shop, the people here), so the game can still put what matters in front. Layouts are a
 *  convenience of this device, kept in this browser under names; nothing breaks without storage. */
export type TileWidget = Widget | 'scene'
export type TileSize = 'small' | 'wide' | 'tall'
export interface Tile { widget: TileWidget; size: TileSize }
export interface GridLayout { tiles: Tile[] }
export interface SavedGrids { current: string; layouts: Record<string, GridLayout> }

export const SCENE_TILE = 'This scene'
export const DEFAULT_NAME = 'My layout'
export const MOST_TILES = 12
export const SIZES: { id: TileSize; label: string }[] = [{ id: 'small', label: 'Small' }, { id: 'wide', label: 'Wide' }, { id: 'tall', label: 'Tall' }]
const KEY = 'dungeon.story.grids'
const objectOr = (value: unknown): object => value && typeof value === 'object' ? value : {}

export function tileName(widget: TileWidget): string {
  return widget === 'scene' ? SCENE_TILE : WIDGET_NAMES[widget]
}

/** A first grid: this scene across the top, then what the player pinned, then the drawer's own tabs. */
export function seedGrid(pins: Widget[] = []): GridLayout {
  const widgets: TileWidget[] = ['scene', ...pins, ...TABS]
  return cleanGrid({ tiles: widgets.map((widget) => ({ widget, size: widget === 'scene' ? 'wide' : 'small' })) })
}

const known = (widget: unknown): widget is TileWidget => widget === 'scene' || (typeof widget === 'string' && widget in WIDGET_NAMES)

/** A saved grid with anything unknown dropped: each widget once, at most MOST_TILES. */
export function cleanGrid(value: unknown): GridLayout {
  const saved = objectOr(value) as Partial<GridLayout>
  if (!Array.isArray(saved.tiles)) return seedGrid()
  const seen = new Set<TileWidget>()
  const tiles: Tile[] = []
  for (const item of saved.tiles as Partial<Tile>[]) {
    if (!item || !known(item.widget) || seen.has(item.widget) || tiles.length >= MOST_TILES) continue
    seen.add(item.widget)
    tiles.push({ widget: item.widget, size: SIZES.some((size) => size.id === item.size) ? item.size as TileSize : 'small' })
  }
  return { tiles }
}

export function addTile(grid: GridLayout, widget: TileWidget): GridLayout {
  if (grid.tiles.some((tile) => tile.widget === widget) || grid.tiles.length >= MOST_TILES) return grid
  return { ...grid, tiles: [...grid.tiles, { widget, size: 'small' }] }
}

export function removeTile(grid: GridLayout, widget: TileWidget): GridLayout {
  return { ...grid, tiles: grid.tiles.filter((tile) => tile.widget !== widget) }
}

/** The tile moved `by` places (−1 earlier, +1 later), kept inside the grid. */
export function moveTile(grid: GridLayout, widget: TileWidget, by: number): GridLayout {
  const from = grid.tiles.findIndex((tile) => tile.widget === widget)
  const to = Math.max(0, Math.min(grid.tiles.length - 1, from + by))
  if (from < 0 || from === to) return grid
  return { ...grid, tiles: placed(grid.tiles, from, to) }
}

/** The dragged tile dropped where another one is: it takes that place and the rest close up. */
export function dropTile(grid: GridLayout, dragged: TileWidget, onto: TileWidget): GridLayout {
  const from = grid.tiles.findIndex((tile) => tile.widget === dragged)
  const to = grid.tiles.findIndex((tile) => tile.widget === onto)
  if (from < 0 || to < 0 || from === to) return grid
  return { ...grid, tiles: placed(grid.tiles, from, to) }
}

function placed(tiles: Tile[], from: number, to: number): Tile[] {
  const next = [...tiles]
  const [tile] = next.splice(from, 1)
  next.splice(to, 0, tile)
  return next
}

export function resizeTile(grid: GridLayout, widget: TileWidget, size: TileSize): GridLayout {
  return { ...grid, tiles: grid.tiles.map((tile) => tile.widget === widget ? { ...tile, size } : tile) }
}

/** The widgets not yet in the grid, for "Add a widget". */
export function addable(grid: GridLayout, widgets: Widget[]): TileWidget[] {
  const used = new Set(grid.tiles.map((tile) => tile.widget))
  return (['scene', ...widgets] as TileWidget[]).filter((widget) => !used.has(widget))
}

/** Saved layouts, cleaned; with none yet, one seeded from `pins` (the scene panel's pins carry over). */
export function cleanSaved(value: unknown, pins: Widget[] = []): SavedGrids {
  const saved = objectOr(value) as Partial<SavedGrids>
  const layouts: Record<string, GridLayout> = {}
  for (const [name, grid] of Object.entries(objectOr(saved.layouts))) {
    const trimmed = name.trim().slice(0, 40)
    if (trimmed) layouts[trimmed] = cleanGrid(grid)
  }
  if (!Object.keys(layouts).length) layouts[DEFAULT_NAME] = seedGrid(pins)
  const current = typeof saved.current === 'string' && saved.current in layouts ? saved.current : Object.keys(layouts)[0]
  return { current, layouts }
}

/** The current layout changed, or kept as a new name (which becomes the current one). */
export function withGrid(saved: SavedGrids, grid: GridLayout, name = saved.current): SavedGrids {
  const trimmed = name.trim().slice(0, 40) || saved.current
  return { current: trimmed, layouts: { ...saved.layouts, [trimmed]: grid } }
}

export function withoutGrid(saved: SavedGrids, name: string): SavedGrids {
  const layouts = { ...saved.layouts }
  delete layouts[name]
  return cleanSaved({ current: saved.current === name ? undefined : saved.current, layouts })
}

export function loadGrids(): SavedGrids {
  try { return cleanSaved(JSON.parse(localStorage.getItem(KEY) ?? 'null'), loadPins()) } catch { return cleanSaved(null, loadPins()) }
}

export function saveGrids(saved: SavedGrids) {
  try { localStorage.setItem(KEY, JSON.stringify(saved)) } catch { /* kept for this visit only */ }
}

/** The saved layouts and the one in use, kept in this browser as they change. */
export function useGrids() {
  const [saved, setSaved] = useState<SavedGrids>(loadGrids)
  const keep = (next: SavedGrids) => { setSaved(next); saveGrids(next) }
  return { saved, grid: saved.layouts[saved.current], keep }
}

export type Grids = ReturnType<typeof useGrids>

export function onGrid(grid: GridLayout, widget: Widget): boolean {
  return grid.tiles.some((tile) => tile.widget === widget)
}

/** A widget asked for from elsewhere that is already a tile: shown where it is, for a moment. */
export interface Flash { widget: Widget; at: number }
