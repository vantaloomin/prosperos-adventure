import { Notice } from '../../components/Feedback'
import type { ReactNode } from 'react'
import { modelOf, type ReadyView } from './readyText'
import { useReady, useReadyActions } from './useReady'

/** Once, on whatever screen they are on: the model is ready.
 * It stays until dismissed, so it is never gone before it is read (Iris). */
export function ReadyNotice({ openModels }: { openModels: () => void }) {
  const view = useReady().data
  const actions = useReadyActions()
  if (view?.status !== 'ready' || view.announced) return null
  return <Done view={view} dismiss={<button type="button" className="text-button" onClick={() => void actions.seen('notice')}>Dismiss</button>} openModels={openModels} />
}

function Done({ view, dismiss, openModels }: { view: ReadyView; dismiss: ReactNode; openModels: () => void }) {
  const name = modelOf(view).name
  if (!view.in_use) {
    return <Notice action={<><button type="button" className="text-button" onClick={openModels}>Open Models</button>{dismiss}</>}>
      {name} is ready. Your story model is still the one you picked.</Notice>
  }
  return <Notice action={dismiss}>{name} is ready. It's now your story model.</Notice>
}
