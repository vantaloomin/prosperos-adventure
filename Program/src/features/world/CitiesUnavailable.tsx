import type { UseQueryResult } from '@tanstack/react-query'
import { Notice } from '../../components/Feedback'

/** Said under a city picker when the city list did not load, so an empty list is never mistaken for "no cities". */
export function CitiesUnavailable({ cities }: { cities: UseQueryResult<unknown> }) {
  if (!cities.isError) return null
  return (
    <Notice tone="error" action={<button type="button" className="text-button" onClick={() => void cities.refetch()}>Try again</button>}>
      The cities did not load: {cities.error.message} Settings &gt; Cities says more.
    </Notice>
  )
}
