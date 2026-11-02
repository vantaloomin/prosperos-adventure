import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { CitySummary } from '../../types'
import { Field } from '../../components/Fields'
import { CUSTOM_WORLD, homeWorlds, type FeaturedCities } from '../world/cityText'
import { CitiesUnavailable } from '../world/CitiesUnavailable'

interface CityPickProps { value: string; onChange: (cityId: string) => void; currentId: string; disabled?: boolean; autoFocus?: boolean }

/** The picker's first option: the app picks a town of this world other than this one (dungeon/worlds.py
 * SOMEWHERE_NEW); with `:<world>` after it, a town of that world. The form starts on it. */
export const SOMEWHERE_NEW = 'somewhere-new'

const somewhereIn = (world: string) => `${SOMEWHERE_NEW}:${world}`

/** Where a new world is, in two steps: the world (Vallarith, Havenbrooke, BABEL or Custom), then a town of that world
 * or somewhere new there the app picks. It starts in the world of the city the user is in now. */
export function CityPick({ value, onChange, currentId, disabled, autoFocus }: CityPickProps) {
  const cities = useQuery({ queryKey: ['cities'], queryFn: () => api<CitySummary[]>('/world/cities'), staleTime: Infinity })
  const featured = useQuery({ queryKey: ['featured-cities'], queryFn: () => api<FeaturedCities<CitySummary>>('/world/featured'), staleTime: Infinity })
  // The current city is always there to pick, even before the list arrives or when it can't be read.
  const listed = cities.data?.some((city) => city.id === currentId) ? cities.data : [...(cities.data ?? []), { id: currentId, name: 'The city you are in now' }]
  const worlds = homeWorlds(listed, featured.data?.cities)
  const worldOf = (cityId: string) => {
    const city: Partial<CitySummary> | undefined = listed.find((item) => item.id === cityId)
    return city && (city.world || CUSTOM_WORLD)
  }
  const picked = value.startsWith(`${SOMEWHERE_NEW}:`) ? value.slice(SOMEWHERE_NEW.length + 1) : worldOf(value)
  const worldId = picked ?? worldOf(currentId) ?? CUSTOM_WORLD
  const world = worlds.find((item) => item.id === worldId)
  const towns = world?.towns ?? []
  // A world with one town has nothing to pick for you; a world with several starts on "somewhere new" there.
  const opening = (id: string) => {
    const found = worlds.find((item) => item.id === id)?.towns ?? []
    return found.length === 1 ? found[0].id : somewhereIn(id)
  }
  const label = (city: { name: string; region?: string }) => city.region ? `${city.name}, ${city.region}` : city.name
  return (<>
    <Field label="Which world" hint="Pick the world first, then a town in it.">
      {(id, hint) => (
        <select id={id} aria-describedby={hint} value={worldId} disabled={disabled} autoFocus={autoFocus} onChange={(event) => onChange(opening(event.target.value))}>
          {worlds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          {!world && <option value={worldId}>{worldId === CUSTOM_WORLD ? 'Custom' : worldId}</option>}
        </select>
      )}
    </Field>
    <Field label="Where they live" hint="A new town with new people in it. Days there follow its places and its era.">
      {(id, hint) => (
        // Plain "somewhere new" is somewhere new in the world the user is in now (the server reads it so too).
        <select id={id} aria-describedby={hint} value={value === SOMEWHERE_NEW ? opening(worldId) : value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
          {towns.length !== 1 && <option value={somewhereIn(worldId)}>Somewhere new in {world?.name ?? 'this world'} (picked for you)</option>}
          {towns.map((city) => <option key={city.id} value={city.id}>{label(city)}</option>)}
        </select>
      )}
    </Field>
    <CitiesUnavailable cities={cities} />
  </>)
}
