import { useEffect, useState, type DragEvent, type ReactNode } from 'react'
import { ArrowDown, ArrowUp, LayoutGrid, Plus, Trash2, Undo2, X } from 'lucide-react'
import type { Story as StoryData } from '../../types'
import {
  addable, addTile, dropTile, moveTile, onGrid, removeTile, resizeTile, SIZES, tileName, withGrid, withoutGrid,
  type Flash, type GridLayout, type Grids, type SavedGrids, type Tile, type TileSize, type TileWidget,
} from './grid'
import { hasWidget, WIDGET_NAMES, type Widget } from './scene'

interface GridProps {
  story: StoryData; grids: Grids; picked: Widget[]; flash: Flash | null
  render: (widget: Widget) => ReactNode
}

/** The Custom layout (deviceLook.ts): the scene panel as a grid of tiles the player arranges. Arranging is a mode
 *  behind a button, with buttons and a size choice on each tile, so dragging is never the only way. */
export function StoryGrid({ story, grids, picked, flash, render }: GridProps) {
  const [arranging, setArranging] = useState(false)
  const [dragged, setDragged] = useState<TileWidget | null>(null)
  const { grid, saved, keep } = grids
  const change = (next: GridLayout) => keep(withGrid(saved, next))
  useEffect(() => {
    if (flash) document.getElementById(tileId(flash.widget))?.scrollIntoView({ block: 'nearest' })
  }, [flash])
  const own = picked.filter((widget) => !onGrid(grid, widget))
  // This scene's tile stays out of the way when all it needs is already on the grid, except while arranging.
  const tiles = grid.tiles.filter((tile) => tile.widget === 'scene' ? own.length || arranging : hasWidget(story, tile.widget))
  const drop = (onto: TileWidget) => { if (dragged) change(dropTile(grid, dragged, onto)); setDragged(null) }
  return (<>
    <GridBar grids={grids} arranging={arranging} onArrange={() => setArranging(!arranging)} />
    {arranging && <GridAdd story={story} grid={grid} onAdd={(widget) => change(addTile(grid, widget))} />}
    <div className={arranging ? 'story-grid arranging' : 'story-grid'}>
      {tiles.map((tile, index) => <GridTile key={tile.widget} tile={tile} arranging={arranging} first={index === 0} last={index === tiles.length - 1}
        flashing={flash?.widget === tile.widget} grid={grid} change={change}
        drag={{ onDragStart: () => setDragged(tile.widget), onDragEnd: () => setDragged(null), onDrop: () => drop(tile.widget) }}>
        {tile.widget === 'scene' ? <SceneTile own={own} render={render} /> : render(tile.widget)}
      </GridTile>)}
    </div>
    {!tiles.length && <p className="subtle">Nothing on this layout yet. Arrange it to add widgets.</p>}
  </>)
}

function tileId(widget: TileWidget) {
  return `story-tile-${widget}`
}

function SceneTile({ own, render }: { own: Widget[]; render: (widget: Widget) => ReactNode }) {
  if (!own.length) return <p className="subtle">Shows what the scene needs when it is not already on your layout.</p>
  return <>{own.map((widget) => <div key={widget}>{render(widget)}</div>)}</>
}

/** Which saved layout is in use, and the Arrange button. */
function GridBar({ grids, arranging, onArrange }: { grids: Grids; arranging: boolean; onArrange: () => void }) {
  const { saved, keep } = grids
  const names = Object.keys(saved.layouts)
  return (
    <div className="story-grid-bar">
      <label className="story-grid-pick">
        <span className="visually-hidden">Layout</span>
        <select value={saved.current} onChange={(event) => keep({ ...saved, current: event.target.value })}>
          {names.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </label>
      <button type="button" className="text-button" aria-pressed={arranging} onClick={onArrange}>
        {arranging ? <><X aria-hidden="true" />Done</> : <><LayoutGrid aria-hidden="true" />Arrange</>}
      </button>
      {arranging && <GridSave grids={grids} />}
    </div>
  )
}

/** Keep the arrangement under a new name, or let go of this one (one layout always stays). */
function GridSave({ grids }: { grids: Grids }) {
  const { saved, grid, keep } = grids
  const [name, setName] = useState('')
  return (
    <form className="story-grid-save" onSubmit={(event) => { event.preventDefault(); if (name.trim()) { keep(withGrid(saved, grid, name)); setName('') } }}>
      <label><span className="visually-hidden">New layout name</span>
        <input value={name} maxLength={40} placeholder="Save as…" onChange={(event) => setName(event.target.value)} /></label>
      <button type="submit" className="text-button" disabled={!name.trim()}>Save as new</button>
      <GridDelete grids={grids} />
    </form>
  )
}

/** Delete this layout (one always stays), with an Undo until the next change. */
function GridDelete({ grids }: { grids: Grids }) {
  const { saved, keep } = grids
  const [before, setBefore] = useState<{ saved: SavedGrids; name: string } | null>(null)
  if (before && before.saved.layouts[before.name] && !saved.layouts[before.name]) {
    return <button type="button" className="text-button" onClick={() => { keep(before.saved); setBefore(null) }}>
      <Undo2 aria-hidden="true" />Undo deleting “{before.name}”</button>
  }
  if (Object.keys(saved.layouts).length < 2) return null
  return <button type="button" className="text-button" onClick={() => { setBefore({ saved, name: saved.current }); keep(withoutGrid(saved, saved.current)) }}>
    <Trash2 aria-hidden="true" />Delete “{saved.current}”</button>
}

function GridAdd({ story, grid, onAdd }: { story: StoryData; grid: GridLayout; onAdd: (widget: TileWidget) => void }) {
  const choices = addable(grid, (Object.keys(WIDGET_NAMES) as Widget[]).filter((widget) => hasWidget(story, widget)))
  if (!choices.length) return null
  return (
    <label className="story-grid-add">
      <Plus aria-hidden="true" /><span className="visually-hidden">Add a widget</span>
      <select value="" onChange={(event) => { if (event.target.value) onAdd(event.target.value as TileWidget) }}>
        <option value="">Add a widget…</option>
        {choices.map((widget) => <option key={widget} value={widget}>{tileName(widget)}</option>)}
      </select>
    </label>
  )
}

interface TileProps {
  tile: Tile; arranging: boolean; first: boolean; last: boolean; flashing: boolean
  grid: GridLayout; change: (next: GridLayout) => void; children: ReactNode
  drag: { onDragStart: () => void; onDragEnd: () => void; onDrop: () => void }
}

/** One tile: its heading, and while arranging, the buttons that move, size and remove it (and dragging, as well). */
function GridTile({ tile, arranging, first, last, flashing, grid, change, children, drag }: TileProps) {
  const name = tileName(tile.widget)
  const titled = arranging || tile.widget === 'scene' || tile.widget === 'rules'
  const over = (event: DragEvent) => { if (arranging) event.preventDefault() }
  return (
    <section id={tileId(tile.widget)} className={`story-tile ${tile.size}${flashing ? ' flash' : ''}`}
      aria-label={name} draggable={arranging} onDragStart={arranging ? drag.onDragStart : undefined} onDragEnd={drag.onDragEnd}
      onDragOver={over} onDrop={(event) => { event.preventDefault(); if (arranging) drag.onDrop() }}>
      {titled && <div className="story-tile-tools">
        <h2 className="story-panel-heading" id={tile.widget === 'rules' ? 'story-dials-heading' : undefined}>{name}</h2>
        {arranging && <TileTools tile={tile} first={first} last={last} grid={grid} change={change} />}
      </div>}
      <div className="story-tile-body">{children}</div>
    </section>
  )
}

function TileTools({ tile, first, last, grid, change }: Pick<TileProps, 'tile' | 'first' | 'last' | 'grid' | 'change'>) {
  const name = tileName(tile.widget)
  return (<>
    <button type="button" className="icon-button" aria-label={`Move ${name} earlier`} disabled={first} onClick={() => change(moveTile(grid, tile.widget, -1))}><ArrowUp aria-hidden="true" /></button>
    <button type="button" className="icon-button" aria-label={`Move ${name} later`} disabled={last} onClick={() => change(moveTile(grid, tile.widget, 1))}><ArrowDown aria-hidden="true" /></button>
    <label><span className="visually-hidden">Size of {name}</span>
      <select value={tile.size} onChange={(event) => change(resizeTile(grid, tile.widget, event.target.value as TileSize))}>
        {SIZES.map((size) => <option key={size.id} value={size.id}>{size.label}</option>)}
      </select>
    </label>
    <button type="button" className="icon-button" aria-label={`Remove ${name}`} onClick={() => change(removeTile(grid, tile.widget))}><X aria-hidden="true" /></button>
  </>)
}
