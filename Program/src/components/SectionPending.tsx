import type { UseQueryResult } from '@tanstack/react-query'
import { Loading } from './Feedback'
import { ErrorNotice } from './ErrorNotice'

/**
 * Stands in for a settings section whose data has not arrived: a loading line, or what failed with Try again.
 * A section that failed to load is never left blank, where it reads as having nothing to set.
 */
export function SectionPending({ queries, heading, title }: { queries: UseQueryResult<unknown>[]; heading: string; title: string }) {
  const failed = queries.find((query) => query.isError)
  return (
    <section className="settings-section form-stack" aria-labelledby={heading}>
      <h2 id={heading}>{title}</h2>
      {failed?.error ? <ErrorNotice error={failed.error}
        action={<button type="button" className="text-button" onClick={() => void Promise.all(queries.map((query) => query.refetch()))}>Try again</button>} />
        : <Loading label={`Loading ${title.toLowerCase()}`} />}
    </section>
  )
}
