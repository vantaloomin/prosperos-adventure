import { api } from '../../../api'
import { Field } from '../../../components/Fields'
import { useWorlds } from '../../worlds/useWorlds'
import type { ModelsOverview } from './types'

/** Whether this world has job assignments of its own (adventure/world_models.py), such as a different narrator in
 * one world. Every world uses the usual ones until the user says otherwise; shown once there is another world. */
export function WorldModelPick({ overview, onChanged, onError }: { overview: ModelsOverview; onChanged: (data?: ModelsOverview) => void; onError: (text: string) => void }) {
  const worlds = useWorlds()
  const count = worlds.data?.personas.reduce((total, persona) => total + persona.worlds.length, 0) ?? 0
  const own = !!overview.world?.own
  const name = worlds.data?.world.name
  if (!name || (count < 2 && !own)) return null
  const change = async (value: boolean) => {
    try { onChanged(await api<ModelsOverview>('/models/world', { own: value }, 'PUT')) } catch (error) { onError(error instanceof Error ? error.message : 'Not changed.') }
  }
  return <div className="world-model-pick"><Field label={`Models in ${name}`} hint={own ? `Only in ${name}; your other worlds keep theirs. The Story narrator Mix works only with the usual models.` : `Uses the same models as your other worlds. Pick This world's own to give ${name} its own, starting from these.`}>{(id, hint) => (
    <select id={id} aria-describedby={hint} value={own ? 'own' : 'usual'} onChange={(event) => void change(event.target.value === 'own')}>
      <option value="usual">Same as your other worlds</option>
      <option value="own">This world's own</option>
    </select>
  )}</Field></div>
}
