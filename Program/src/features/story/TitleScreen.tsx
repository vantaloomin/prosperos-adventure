import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { api } from '../../api'
import type { TitleWorlds, TitleWorld } from '../../types'
import { Notice } from '../../components/Feedback'
import { enter } from '../worlds/useWorlds'
import { nextTile, rowEdges } from './titleText'

/** Remembers, for this tab, which world the player went to from the title screen, so arriving there skips it once. */
const PICKED = 'adventure-title-picked'

function picked(): string | null {
  try { return window.sessionStorage.getItem(PICKED) } catch { return null }
}

function remember(world: string | null) {
  try {
    if (world) window.sessionStorage.setItem(PICKED, world)
    else window.sessionStorage.removeItem(PICKED)
  } catch { /* the title screen shows once more after the switch */ }
}

/** The title screen before a campaign starts (adventure/world_select.py): one row of worlds, most recently played
 * first, each tile its key art and name; the tile is the button. The world the story is in begins here; another
 * world switches to the persona's world there, made when they have none, and the page starts afresh in it. The +
 * tile at the end opens the world packages on the Worlds page. With no worlds to show, it steps aside for the start
 * form. */
export function TitleScreen({ onBegin, onNew }: { onBegin: () => void; onNew: () => void }) {
  const worlds = useQuery({ queryKey: ['title-worlds'], queryFn: () => api<TitleWorlds>('/story/worlds') })
  const [going, setGoing] = useState('')
  const [error, setError] = useState('')
  const data = worlds.data
  const skip = worlds.isError || skipped(data)
  useEffect(() => { if (skip) { remember(null); onBegin() } }, [skip, onBegin])
  if (skip) return null
  const go = async (world: TitleWorld) => {
    if (world.here) { onBegin(); return }
    setGoing(world.name)
    setError('')
    try {
      await api(`/story/worlds/${world.id}/enter`, {})
      remember(world.id)
      enter()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That world did not open. Try again.')
      setGoing('')
    }
  }
  return (
    <section className="title-screen" aria-labelledby="title-heading" aria-busy={!data || !!going}>
      <h2 id="title-heading" className="visually-hidden">Choose a world</h2>
      <p className="visually-hidden" role="status">{going && `Opening ${going}…`}</p>
      {error && <Notice tone="error">{error}</Notice>}
      {/* Not before the worlds arrive: scroll snap would hold on to the + tile as they are put in front of it. */}
      {data && <WorldRow worlds={data.worlds} going={going} onGo={(world) => void go(world)} onNew={onNew} />}
    </section>
  )
}

/** Nothing to pick from, or the player just picked the world the story is now in. */
function skipped(data: TitleWorlds | undefined): boolean {
  return !!data && (!data.worlds.length || (!!data.here && picked() === data.here))
}

interface RowProps { worlds: TitleWorld[]; going: string; onGo: (world: TitleWorld) => void; onNew: () => void }

/** One sideways row with scroll snap. The fade and an arrow show only on a side with more; arrow keys move between
 * tiles; on a phone the next tile peeks in. */
function WorldRow({ worlds, going, onGo, onNew }: RowProps) {
  const row = useRef<HTMLUListElement>(null)
  const [edges, setEdges] = useState({ before: false, after: false })
  const sync = useCallback(() => {
    const box = row.current
    if (box) setEdges(rowEdges(box.scrollLeft, box.clientWidth, box.scrollWidth))
  }, [])
  useEffect(() => {
    const box = row.current
    if (!box) return
    sync()
    const watch = new ResizeObserver(sync)
    watch.observe(box)
    return () => watch.disconnect()
  }, [sync, worlds.length])
  const step = (direction: number) => row.current?.scrollBy({ left: direction * row.current.clientWidth * 0.8, behavior: 'smooth' })
  const onKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const tiles = [...(row.current?.querySelectorAll<HTMLButtonElement>('button') ?? [])]
    const index = tiles.indexOf(document.activeElement as HTMLButtonElement)
    if (index < 0) return
    const next = nextTile(index, event.key, tiles.length)
    if (next === index) return
    event.preventDefault()
    tiles[next].focus()
    tiles[next].scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
  }
  const fade = `title-row${edges.before ? ' more-before' : ''}${edges.after ? ' more-after' : ''}`
  return (
    <div className="title-worlds">
      {edges.before && <button type="button" className="title-step before" tabIndex={-1} aria-label="Earlier worlds" onClick={() => step(-1)}><ChevronLeft /></button>}
      <ul ref={row} className={fade} aria-label="Worlds" onScroll={sync} onKeyDown={onKeyDown}>
        {worlds.map((world) => (
          <li key={world.id}>
            <button type="button" className={world.here ? 'title-world here' : 'title-world'} disabled={!!going} aria-busy={going === world.name} onClick={() => onGo(world)}>
              {world.art ? <img src={world.art} alt="" loading="lazy" width={1536} height={1024} /> : <span className="title-world-blank" aria-hidden="true" />}
              <span className="title-world-name">{world.name}</span>
            </button>
          </li>
        ))}
        <li><button type="button" className="title-world title-new" aria-label="New world" disabled={!!going} onClick={onNew}><Plus aria-hidden="true" /></button></li>
      </ul>
      {edges.after && <button type="button" className="title-step after" tabIndex={-1} aria-label="More worlds" onClick={() => step(1)}><ChevronRight /></button>}
    </div>
  )
}
