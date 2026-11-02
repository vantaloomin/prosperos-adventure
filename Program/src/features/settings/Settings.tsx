import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Search } from 'lucide-react'
import { TurnSpeed } from './TurnSpeed'
import { AppearanceSettings } from './AppearanceSettings'
import { ModelCalls } from './ModelCalls'
import { Backups } from './Backups'
import { DataFolder } from './DataFolder'
import { DebugSettings } from './DebugSettings'
import { ImageSettings } from './ImageSettings'
import { PromptSettings } from './PromptSettings'
import { TimezoneSettings } from './WorkspaceSettings'
import { BuiltinRecall } from './models/BuiltinRecall'
import { HardwareCheck } from './models/HardwareCheck'
import { LocalPrograms } from './models/LocalPrograms'
import { ModelSettings } from './models/ModelSettings'
import type { View } from '../../workspace'
import { askForDrawer } from '../story/scene'
import { availableTabs, pickTab, searchSettings, type SettingsMatch, type SettingsTab } from './sections'

interface Props {
  /** The tab named in the address (#settings/models); an unknown one opens the first tab. */
  tab?: string
  onTab: (tab: SettingsTab) => void
  /** Opens another view, for a search result that lives outside Settings. */
  go: (view: View) => void
}

export function Settings({ tab, onTab, go }: Props) {
  const current = pickTab(tab)
  const landing = useLanding()
  const land = (match: SettingsMatch) => {
    // The Story screen's sections are all its tone and rules, in the drawer, which opens to them.
    if (match.elsewhere && match.section.view === 'story') askForDrawer('rules')
    if (match.elsewhere) { go(match.section.view); landOn(match.section.heading, away); return }
    onTab(match.tab.id)
    landing(match.section.heading)
  }
  return (
    <section className="page settings">
      <header className="page-header"><h1>Settings</h1></header>
      <SettingsSearch onPick={land} />
      <div className="settings-layout">
        <div className="settings-nav">
          <SettingsTabs current={current} onTab={onTab} />
        </div>
        <div className="settings-panel" role="tabpanel" id={`settings-panel-${current}`} aria-labelledby={`settings-tab-${current}`}>
          <TabContent tab={current} />
        </div>
      </div>
    </section>
  )
}

/**
 * Moves focus to a section heading, for a search result or a finished review. The heading only exists once its tab
 * (or another view) and that section's data have rendered, and a view that loads in steps can draw it again, so it
 * keeps the heading in focus until it has stayed put for a moment. Within Settings, leaving the page stops it.
 */
function useLanding() {
  const frame = useRef({ id: 0 })
  useEffect(() => () => cancelAnimationFrame(frame.current.id), [])
  return (id: string) => landOn(id, frame.current)
}

/** The landing for a section on another view, which outlives the Settings page that started it. */
const away = { id: 0 }

function landOn(id: string, frame: { id: number }) {
  cancelAnimationFrame(frame.id)
  const until = performance.now() + 3000
  let settled = 0
  const attempt = () => {
    const heading = document.getElementById(id)
    if (heading && document.activeElement === heading) settled += 1
    else if (heading) { settled = 0; focusOn(heading) }
    if (settled < STEADY_FRAMES && performance.now() < until) frame.id = requestAnimationFrame(attempt)
  }
  frame.id = requestAnimationFrame(attempt)
}

const STEADY_FRAMES = 20

function focusOn(heading: HTMLElement) {
  // A section folded away on the Story screen opens to show it.
  const fold = heading.closest('details')
  if (fold && !fold.open) fold.open = true
  if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1')
  heading.focus()
}

function TabContent({ tab }: { tab: SettingsTab }) {
  const content: Record<SettingsTab, ReactNode> = {
    general: <><TimezoneSettings /><AppearanceSettings /></>,
    models: <><HardwareCheck /><ModelSettings /><TurnSpeed /><LocalPrograms /><BuiltinRecall /></>,
    images: <ImageSettings />,
    data: <><DataFolder /><Backups /></>,
    developer: <><ModelCalls /><DebugSettings /><PromptSettings /></>,
  }
  return content[tab]
}

const NEXT_KEYS: Record<string, number> = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }

/** Vertical tabs beside the panel on wide windows, a scrolling row above it on narrow ones. */
function SettingsTabs({ current, onTab }: { current: SettingsTab; onTab: (tab: SettingsTab) => void }) {
  const tabs = availableTabs()
  const narrow = useNarrow()
  const list = useRef<HTMLDivElement>(null)
  // On a narrow window the row scrolls; keep the open tab in sight, as after a deep link.
  useEffect(() => { list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' }) }, [current])
  // Arrow keys move between tabs and open them, Home and End jump to the ends (the WAI-ARIA tabs pattern).
  const onKeyDown = (event: KeyboardEvent) => {
    const index = tabs.findIndex((item) => item.id === current)
    const target = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
      : event.key in NEXT_KEYS ? (index + NEXT_KEYS[event.key] + tabs.length) % tabs.length : null
    if (target === null) return
    event.preventDefault()
    onTab(tabs[target].id)
    list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[target]?.focus()
  }
  return (
    <div className="settings-tabs" role="tablist" aria-label="Settings" aria-orientation={narrow ? 'horizontal' : 'vertical'} ref={list} onKeyDown={onKeyDown}>
      {tabs.map((item) => (
        <button key={item.id} type="button" role="tab" id={`settings-tab-${item.id}`} aria-selected={item.id === current}
          aria-controls={item.id === current ? `settings-panel-${item.id}` : undefined} tabIndex={item.id === current ? 0 : -1} onClick={() => onTab(item.id)}>
          {item.label}
        </button>
      ))}
    </div>
  )
}

const NARROW = '(max-width: 720px)'

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia(NARROW).matches)
  useEffect(() => {
    const query = window.matchMedia(NARROW)
    const sync = () => setNarrow(query.matches)
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])
  return narrow
}

function SettingsSearch({ onPick }: { onPick: (match: SettingsMatch) => void }) {
  const [query, setQuery] = useState('')
  const matches = searchSettings(query)
  const searching = query.trim().length > 0
  return (
    <div className="settings-search">
      <label className="visually-hidden" htmlFor="settings-search">Find a setting</label>
      <div className="search-field">
        <Search aria-hidden="true" />
        <input id="settings-search" type="search" placeholder="Find a setting" value={query} onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Escape') setQuery('') }} aria-describedby="settings-search-count" />
      </div>
      <p id="settings-search-count" className="visually-hidden" aria-live="polite">{searching ? `${matches.length} ${matches.length === 1 ? 'setting' : 'settings'} found` : ''}</p>
      {searching && (matches.length ? (
        <ul className="settings-results">
          {matches.map((match) => (
            <li key={match.section.heading}>
              <button type="button" className="text-button" onClick={() => { setQuery(''); onPick(match) }}>
                {match.section.title}{match.elsewhere ? <span className="subtle"> on {match.section.where}</span>
                  : match.section.title !== match.tab.label && <span className="subtle"> in {match.tab.label}</span>}
              </button>
            </li>
          ))}
        </ul>
      ) : <p className="subtle settings-results">No settings match “{query.trim()}”.</p>)}
    </div>
  )
}
