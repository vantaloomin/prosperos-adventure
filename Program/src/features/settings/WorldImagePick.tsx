import { useState } from 'react'
import { api } from '../../api'
import type { ImageBackend, WorldImageBackends } from '../../types'
import { Toggle } from '../../components/Fields'
import { useWorlds } from '../worlds/useWorlds'

type Result = { tone: 'info' | 'error'; text: string } | null
const failure = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback

/** Which backends this world draws with (adventure/images/world_choice.py), such as an anime model for one world and
 * photographs for another. Every world uses all of them until the user picks; shown once there is a choice to make. */
export function WorldImagePick({ list, world, refresh, setResult }: { list: ImageBackend[]; world: WorldImageBackends; refresh: () => Promise<unknown>; setResult: (result: Result) => void }) {
  const name = useShownFor(list, world)
  const [busy, setBusy] = useState(false)
  if (!name) return null
  const save = async (ids: string[] | null) => {
    if (busy) return
    setBusy(true)
    try { await api('/images/world', { backend_ids: ids }, 'PUT'); await refresh(); setResult(null) } catch (error) { setResult({ tone: 'error', text: failure(error, 'Not saved.') }) } finally { setBusy(false) }
  }
  const on = list.filter((backend) => backend.enabled)
  return (
    <div className="world-image-divider"><fieldset className="plain-fieldset world-image-pick">
      <legend id="world-image-legend">Pictures in {name}</legend>
      <select aria-labelledby="world-image-legend" aria-describedby="world-image-hint" aria-disabled={busy} value={world.own ? 'own' : 'all'}
        onChange={(event) => void save(event.target.value === 'own' ? (on.length ? on : list).map((backend) => backend.id) : null)}>
        <option value="all">All of them, in the order above</option>
        <option value="own">Only the ones I pick</option>
      </select>
      <small id="world-image-hint" className="subtle">{world.own ? 'Only the ones switched on below, in the order above. Your other worlds keep their own.' : 'Pick some for this world alone, say an anime model here and photographs elsewhere.'}</small>
      {world.own && <Picks list={list} picked={world.picked} save={save} />}
      {world.falls_back && <p className="subtle">None of the backends picked here is on, so {name} uses all of them for now.</p>}
    </fieldset></div>
  )
}

/** The world's name, when there is a pick to make here: two backends or more, and more than one world (or a pick
 * already made in this one). */
function useShownFor(list: ImageBackend[], world: WorldImageBackends) {
  const worlds = useWorlds()
  const count = worlds.data?.personas.reduce((total, persona) => total + persona.worlds.length, 0) ?? 0
  return list.length >= 2 && (count >= 2 || world.own) ? worlds.data?.world.name : undefined
}

function Picks({ list, picked, save }: { list: ImageBackend[]; picked: string[]; save: (ids: string[]) => Promise<void> }) {
  return <div className="world-image-list">
    {list.map((backend) => <Toggle key={backend.id} label={`Use ${backend.label}`} checked={picked.includes(backend.id)}
      onChange={(value) => void save(value ? [...picked, backend.id] : picked.filter((id) => id !== backend.id))}
      hint={backend.enabled ? undefined : 'Switched off above, so not used anywhere until it is on again.'} />)}
  </div>
}
