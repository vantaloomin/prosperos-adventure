import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { HomeChoices, World } from '../../types'
import { Field } from '../../components/Fields'
import { CityOptions } from '../world/CityOptions'
import type { HomeDraft } from './personaHomeText'

interface PersonaHomeProps { moving: { world: World; home: HomeDraft } | null; disabled?: boolean; onChange: (draft: HomeDraft) => void }

/** Where you live in this world (dungeon/life/where.py): the app picked it, and it is the user's to change. Cities
 * are the world's own and those a trip from it could reach. */
export function PersonaHome({ moving, disabled, onChange }: PersonaHomeProps) {
  // Only on the form of the persona the user is now, in the world they are in.
  return moving && <HomeFields world={moving.world} draft={moving.home} disabled={disabled} onChange={onChange} />
}

function HomeFields({ world, draft, disabled, onChange }: { world: World; draft: HomeDraft; disabled?: boolean; onChange: (draft: HomeDraft) => void }) {
  const choices = useQuery({
    queryKey: ['world-home', world.id, draft.city_id],
    queryFn: () => api<HomeChoices>(`/worlds/${world.id}/home?city_id=${encodeURIComponent(draft.city_id)}`),
    placeholderData: keepPreviousData,
  })
  const cities = choices.data?.cities ?? (world.home ? [{ id: world.home.city_id, name: world.home.city, region: world.home.region }] : [])
  const hoods = choices.data?.city_id === draft.city_id ? choices.data.neighbourhoods : []
  return (
    <fieldset className="persona-home">
      <legend>Where you live</legend>
      <Field label="City" hint="Where your story starts.">
        {(id, hint) => (
          <select id={id} aria-describedby={hint} value={draft.city_id} disabled={disabled}
            onChange={(event) => onChange({ city_id: event.target.value, neighbourhood: '' })}>
            <CityOptions cities={cities} withRegion />
          </select>
        )}
      </Field>
      {(hoods.length > 0 || draft.neighbourhood) && <Field label="Neighborhood">
        {(id) => (
          <select id={id} value={draft.neighbourhood} disabled={disabled}
            onChange={(event) => onChange({ ...draft, neighbourhood: event.target.value })}>
            <option value="">Picked for you</option>
            {hoods.map((hood) => <option key={hood.id} value={hood.id}>{hood.name}</option>)}
          </select>
        )}
      </Field>}
    </fieldset>
  )
}
