import { useState } from 'react'
import { ConfirmDownload } from './ConfirmDownload'
import { DownloadProgress } from './DownloadProgress'
import { isActive, modelOf, size, type ReadyView } from './readyText'
import { useReady, useReadyActions } from './useReady'

/** Top of Settings > Models: the built-in model while it downloads (titled as the profile it becomes), and, with
 * nothing set up yet, the same "Set it up for me" as the welcome. Once it is ready its own profile card takes over. */
export function ReadyCard({ hasProfiles }: { hasProfiles: boolean }) {
  const view = useReady().data
  if (!view) return null
  if (isActive(view)) {
    return <div className="model-profile ready-card"><div><span className="eyebrow">Local / Built-in</span><h3>Built-in · {modelOf(view).name}</h3>
      <DownloadProgress view={view} titled={false} /></div></div>
  }
  if (view.status === 'idle' && !hasProfiles && view.pick.fits) return <Offer view={view} />
  return null
}

/** On the built-in profile's own card when the user picked another chat model during the download: theirs stays,
 * and this is the one place to switch (Iris). */
export function UseBuiltin({ profileId }: { profileId: string }) {
  const view = useReady().data
  const actions = useReadyActions()
  if (view?.status !== 'ready' || view.in_use || view.profile_id !== profileId) return null
  return <p className="subtle">Ready. <button type="button" className="text-button use-it" onClick={() => void actions.use()}>Use it for conversation</button></p>
}

function Offer({ view }: { view: ReadyView }) {
  const [asking, setAsking] = useState(false)
  return <div className="model-profile ready-card"><div><span className="eyebrow">On this computer</span><h3>A free model on your graphics card</h3>
    <p className="subtle">{view.pick.name} ({size(view.pick.bytes)}) runs here, so your chats stay on this computer.</p>
    <div className="form-actions"><button type="button" className="button primary" onClick={() => setAsking(true)}>Set it up for me</button></div>
    {asking && <ConfirmDownload view={view} onClose={() => setAsking(false)} />}</div></div>
}
