import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { TitleWorlds, TitleWorld } from '../../types'
import { Notice } from '../../components/Feedback'
import { enter } from '../worlds/useWorlds'
import { worldAction } from './titleText'

/** Remembers, for this tab, which world the player went to from the title screen, so arriving there skips it once. */
const PICKED = 'dungeon-title-picked'

function picked(): string | null {
  try { return window.sessionStorage.getItem(PICKED) } catch { return null }
}

function remember(world: string | null) {
  try {
    if (world) window.sessionStorage.setItem(PICKED, world)
    else window.sessionStorage.removeItem(PICKED)
  } catch { /* the title screen shows once more after the switch */ }
}

/** The title screen before a campaign starts (dungeon/world_select.py): the game's key art, then a card for each
 * world. The world the story is in begins here; another world switches to the persona's world there, made when
 * they have none, and the page starts afresh in it. With no worlds to show, it steps aside for the start form. */
export function TitleScreen({ onBegin }: { onBegin: () => void }) {
  const worlds = useQuery({ queryKey: ['title-worlds'], queryFn: () => api<TitleWorlds>('/story/worlds') })
  const [going, setGoing] = useState('')
  const [error, setError] = useState('')
  const data = worlds.data
  const skip = worlds.isError || (!!data && !data.worlds.length) || (!!data?.here && picked() === data.here)
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
    <section className="title-screen" aria-labelledby="title-heading">
      <div className="title-hero">
        <img src="/title.webp" alt="" width={1536} height={1024} />
        <div className="title-words">
          <h2 id="title-heading">Prospero&apos;s Dungeon</h2>
          <p>Choose a world. The dice decide the rest.</p>
        </div>
      </div>
      {going && <Notice>Opening {going}…</Notice>}
      {error && <Notice tone="error">{error}</Notice>}
      <ul className="title-worlds" aria-label="Worlds" aria-busy={!data}>
        {data?.worlds.map((world) => (
          <li key={world.id} className={world.here ? 'title-world here' : 'title-world'}>
            {world.art ? <img src={world.art} alt="" loading="lazy" width={1536} height={1024} /> : <span className="title-world-blank" aria-hidden="true" />}
            <div className="title-world-text">
              <h3>{world.name}</h3>
              {world.genre && <p className="title-world-genre">{world.genre}</p>}
              <p className="title-world-pitch" title={world.pitch}>{world.pitch}</p>
              <button type="button" className={world.here ? 'button primary' : 'button'} disabled={!!going} onClick={() => void go(world)}>
                {worldAction(world)}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
