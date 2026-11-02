import { useEffect } from 'react'
import { BookOpen, Settings as SettingsIcon } from 'lucide-react'
import type { View } from '../../workspace'
import { WorldButton } from '../worlds/WorldButton'
import { navCurrent } from './navText'
import { isActive, navLabel, percent, type ReadyView } from '../ready/readyText'
import { useReady, useReadyActions } from '../ready/useReady'

/** The views: the world (persona and worlds), the story and Settings. */
const VIEWS: { id: View; label: string; icon: typeof BookOpen }[] = [
  { id: 'story', label: 'Story', icon: BookOpen },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
]

export function AppNav({ view, go }: { view: View; go: (view: View) => void }) {
  const ready = useSettingsMark(view)
  return (
    <nav className="app-nav" aria-label="Views">
      <WorldButton current={view === 'worlds'} onOpen={() => go('worlds')} />
      {VIEWS.map(({ id, label, icon: Icon }) => (
        <button key={id} type="button" className={`nav-${id}`} aria-current={navCurrent(id, view) ? 'page' : undefined} onClick={() => go(id)}
          aria-label={id === 'settings' ? navLabel(ready) : undefined}>
          <Icon aria-hidden="true" />
          {id === 'settings' && <SettingsMark view={ready} />}
          <span>{label}</span>
        </button>
      ))}
    </nav>
  )
}

/** "Set it up for me" as the Settings tab shows it; opening Settings once clears the done dot. */
function useSettingsMark(view: View): ReadyView | undefined {
  const ready = useReady().data
  const { seen } = useReadyActions()
  const unseen = ready?.status === 'ready' && !ready.settings_seen
  useEffect(() => { if (unseen && view.startsWith('settings')) void seen('settings') }, [unseen, view, seen])
  return ready
}

/** A thin ring in the badge spot while the model downloads (static, so Less motion changes nothing), then a dot. */
function SettingsMark({ view }: { view?: ReadyView }) {
  if (view && isActive(view) && view.status !== 'cancelled') {
    const length = 2 * Math.PI * 7
    return <svg className="nav-ring" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="9" cy="9" r="7" className="nav-ring-track" />
      <circle cx="9" cy="9" r="7" className="nav-ring-fill" strokeDasharray={`${length * percent(view) / 100} ${length}`} />
    </svg>
  }
  return view?.status === 'ready' && !view.settings_seen ? <span className="nav-dot" aria-hidden="true" /> : null
}
