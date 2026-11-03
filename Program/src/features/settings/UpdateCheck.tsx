import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { api } from '../../api'
import type { UpdateCheck as Found } from '../../types'
import { Notice } from '../../components/Feedback'
import { howToUpdate, linkLabel, releasedOn } from './updateText'

// Asks GitHub for the newest release only when pressed (adventure/updates.py); nothing checks in the background.
export function UpdateCheck() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<{ version: string }>('/health'), staleTime: Infinity })
  const [found, setFound] = useState<Found | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Busy controls are marked, not disabled: disabling the focused control would drop keyboard focus.
  const check = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try { setFound(await api<Found>('/updates/check', {})) } catch (failure) {
      setFound(null)
      setError(failure instanceof Error ? failure.message : 'The check did not finish.')
    } finally { setBusy(false) }
  }
  const current = found?.current ?? health.data?.version
  return (
    <section className="settings-section form-stack update-check" aria-labelledby="updates-heading">
      <div>
        <h2 id="updates-heading">Updates</h2>
        <p className="subtle">{current && `You’re on version ${current}. `}Checking asks GitHub for the newest release. Nothing about you is sent.</p>
      </div>
      <div className="form-actions">
        <button type="button" className="button" aria-disabled={busy} onClick={() => void check()}>
          <RefreshCw size={15} aria-hidden="true" className={busy ? 'spin' : undefined} />{busy ? 'Checking…' : 'Check for updates'}
        </button>
      </div>
      <div aria-live="polite">
        {error && <Notice tone="error">{error}</Notice>}
        {found && <UpdateResult found={found} />}
      </div>
    </section>
  )
}

function UpdateResult({ found }: { found: Found }) {
  const link = (
    <a className="text-button" href={found.page} target="_blank" rel="noreferrer noopener">
      {linkLabel(found)}<span className="visually-hidden"> (GitHub, opens in a new tab)</span>
    </a>
  )
  if (found.status === 'current') return <Notice tone="success" action={link}>You have the latest version.</Notice>
  if (found.status === 'unavailable') {
    return <Notice tone="warning" action={link}>GitHub could not be reached just now. Try again later, or look at the releases page yourself.</Notice>
  }
  return <Notice action={link}>Version {found.latest} is out{releasedOn(found.published)}. {howToUpdate(found)}</Notice>
}
