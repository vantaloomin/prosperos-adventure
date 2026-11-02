import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useFollowPcTimezone, type View } from './workspace'
import type { SettingsTab } from './features/settings/sections'
import { Loading } from './components/Feedback'
import { DebugBanner } from './features/settings/DebugBanner'
import { ReadyNotice } from './features/ready/ReadyNotice'
import { AiNotice } from './features/notice/AiNotice'
import { AppNav } from './features/nav/AppNav'
import { isView } from './features/nav/navText'
import { useAppColors } from './features/settings/useAppColors'
import { Story } from './features/story/Story'

// The story opens first, so it ships in the main bundle; the other views load the first time they are opened.
const Settings = lazy(() => import('./features/settings/Settings').then((m) => ({ default: m.Settings })))
const Worlds = lazy(() => import('./features/worlds/Worlds').then((m) => ({ default: m.Worlds })))

function viewFromHash(): View {
  const id = window.location.hash.slice(1)
  return isView(id) ? id as View : 'story'
}

export default function App() {
  const [view, setView] = useState<View>(viewFromHash)
  useFollowPcTimezone()
  useEffect(() => {
    const sync = () => setView(viewFromHash())
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])
  const go = useCallback((next: View) => { window.history.pushState(null, '', `#${next}`); setView(next) }, [])
  // Switching Settings tabs keeps the address deep-linkable without filling the back button with tabs.
  const openTab = useCallback((tab: SettingsTab) => { window.history.replaceState(null, '', `#settings/${tab}`); setView(`settings/${tab}`) }, [])
  useFocusOnViewChange(view)
  useAppColors()
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <AppNav view={view} go={go} />
      <main id="main" className="app-main" tabIndex={-1}>
        <DebugBanner onOpen={() => go('settings/developer')} />
        <ReadyNotice openModels={() => go('settings/models')} />
        <Suspense fallback={<Loading label="Opening" />}><CurrentView view={view} go={go} openTab={openTab} /></Suspense>
      </main>
      <AiNotice />
    </div>
  )
}

/**
 * A button inside a view that opens another view is gone once it renders, which leaves focus on the
 * page body. Start the new view from its top instead; focus on a nav button or set by the view stays.
 */
function useFocusOnViewChange(view: View) {
  const first = useRef(true)
  useEffect(() => {
    if (first.current) { first.current = false; return }
    if (document.activeElement === document.body) document.getElementById('main')?.focus({ preventScroll: true })
  }, [view])
}

interface CurrentViewProps { view: View; go: (view: View) => void; openTab: (tab: SettingsTab) => void }

function CurrentView({ view, go, openTab }: CurrentViewProps) {
  if (view === 'worlds') return <Worlds />
  if (view === 'settings' || view.startsWith('settings/')) return <Settings tab={view.split('/')[1]} onTab={openTab} go={go} />
  return <Story go={go} />
}
