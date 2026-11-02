import { Fragment, useEffect, useRef, useState, useSyncExternalStore, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpenText, Ellipsis, PanelRight, Pin, PinOff, Swords, X } from 'lucide-react'
import { api } from '../../api'
import type { Gear, Story as StoryData, StoryBack, StoryFight } from '../../types'
import { HiddenValues } from '../settings/HiddenValues'
import { clampWidth, GRID_WIDTH, PANEL_WIDTH, readLook, saveLook, useDeviceLook } from '../settings/deviceLook'
import { StoryBranches } from './StoryBranches'
import { StoryChapters } from './StoryChapters'
import { StoryExport } from './StoryExport'
import { StoryGear } from './StoryGear'
import { StoryInjuries } from './StoryInjuries'
import { StoryIntensity } from './StoryIntensity'
import { StoryJournal } from './StoryJournal'
import { StoryMap } from './StoryMap'
import { StoryTown } from './StoryTown'
import { StoryInterior } from './StoryInterior'
import { StoryArt } from './StoryArt'
import { StoryNotebook } from './StoryNotebook'
import { StoryDiceLog } from './StoryDiceLog'
import { StoryPeople } from './StoryPeople'
import { StoryPolitics } from './StoryPolitics'
import { StoryPowers } from './StoryPowers'
import { StorySheet } from './StorySheet'
import { loadGrids, onGrid, useGrids, type Flash } from './grid'
import { StoryGrid } from './StoryGrid'
import { foeNumbers, zoneText } from './storyText'
import { BattleMap } from './BattleMap'
import { ASK_EVENT, hasWidget, loadPins, MORE, partyOf, peopleHere, savePins, sceneWidgets, TABS, takeAsked, WIDGET_NAMES, type Widget } from './scene'
import { STORY_KEY } from './table'

/** Matches the stylesheet's breakpoint for the side panel. */
const WIDE = '(min-width: 1100px)'

/** The media query's change, and a resize as well: some embedded or emulated windows resize without firing it. */
function subscribe(change: () => void) {
  const query = window.matchMedia?.(WIDE)
  query?.addEventListener('change', change)
  window.addEventListener('resize', change)
  return () => { query?.removeEventListener('change', change); window.removeEventListener('resize', change) }
}

function useWide() {
  return useSyncExternalStore(subscribe, () => window.matchMedia?.(WIDE).matches ?? false, () => false)
}

/** Whether the panel sits beside the story (a wide screen, in Classic or Custom; Reader keeps it in tabs), and whether
 *  it is the player's own grid. */
function useBeside() {
  const wide = useWide()
  const { layout } = useDeviceLook()
  return { wide: wide && layout !== 'reader', custom: wide && layout === 'custom' }
}

/** Whether a widget is a tile of the Custom grid on screen now (read fresh, since it is asked for from elsewhere). */
function tiledNow(widget: Widget): boolean {
  if (readLook().layout !== 'custom' || !window.matchMedia?.(WIDE).matches) return false
  const saved = loadGrids()
  return onGrid(saved.layouts[saved.current], widget)
}

interface PanelProps { story: StoryData; change: (request: () => Promise<StoryData>) => Promise<void>; onTravel: (name: string) => void; onLine?: (text: string) => void; onBack: (data: StoryBack) => void }
type PanelView = 'scene' | 'more' | Widget

/** Beside the story (requirements "Play screen and widgets"): the scene panel, which shows what the scene needs and
 *  what the player pinned, and the drawer's tabs for everything else. On a wide screen it is a column beside the
 *  story; on a narrow one the tabs sit under the composer and open it as a sheet, and the Scene tab gets a dot when
 *  the scene changes (a fight starts), so nothing opens over the reading. */
export function StoryPanel(props: PanelProps) {
  const panel = usePanel(props.story)
  const width = usePanelWidth(panel.custom)
  if (!props.story.messages.length) return <BeforeTheStory {...props} />
  return (
    <aside className={`story-panel${panel.open ? ' open' : ''}${panel.custom ? ' custom' : ''}`} aria-label="The scene and your character"
      style={panel.wide ? { '--story-panel-width': `${width.shown}px` } as CSSProperties : undefined}>
      {panel.showing && <PanelBody {...props} panel={panel} />}
      <PanelTabs story={props.story} panel={panel} />
      {panel.wide && <PanelResize width={width} />}
    </aside>
  )
}

type Panel = ReturnType<typeof usePanel>

/** How wide the panel beside the story is: Classic and Visual novel share one width, Custom's grid keeps its own. While
 *  the handle is dragged the width lives here, and it is saved for this device when the drag ends. */
function usePanelWidth(custom: boolean) {
  const look = useDeviceLook()
  const bounds = custom ? GRID_WIDTH : PANEL_WIDTH
  const saved = custom ? look.gridWidth : look.panelWidth
  const [dragging, setDragging] = useState<number | null>(null)
  const clamp = (value: number) => clampWidth(value, bounds)
  return {
    shown: dragging ?? saved,
    bounds,
    drag: (value: number) => setDragging(clamp(value)),
    save: (value: number) => { setDragging(null); saveLook(custom ? { gridWidth: clamp(value) } : { panelWidth: clamp(value) }) },
  }
}

/** The handle on the panel's inner edge: drag it to widen or narrow the panel, use the arrow keys when it has focus,
 *  or double-click it to go back to the usual width. */
function PanelResize({ width }: { width: ReturnType<typeof usePanelWidth> }) {
  const start = useRef<{ x: number; width: number } | null>(null)
  const down = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    // From the width on screen, which the stylesheet can hold below the saved one on a smaller window.
    const panel = event.currentTarget.parentElement?.getBoundingClientRect().width
    start.current = { x: event.clientX, width: panel ? Math.round(panel) : width.shown }
  }
  // The panel is on the right, so moving left makes it wider.
  const at = (event: PointerEvent<HTMLDivElement>) => start.current ? start.current.width + start.current.x - event.clientX : width.shown
  const move = (event: PointerEvent<HTMLDivElement>) => { if (start.current) width.drag(at(event)) }
  const up = (event: PointerEvent<HTMLDivElement>) => {
    if (!start.current) return
    width.save(at(event))
    start.current = null
  }
  const key = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 80 : 20
    const next = event.key === 'ArrowLeft' ? width.shown + step : event.key === 'ArrowRight' ? width.shown - step
      : event.key === 'Home' ? width.bounds.min : event.key === 'End' ? width.bounds.max : null
    if (next === null) return
    event.preventDefault()
    width.save(next)
  }
  return <div className="story-panel-resize" role="separator" aria-orientation="vertical" aria-label="Panel width" tabIndex={0}
    aria-valuemin={width.bounds.min} aria-valuemax={width.bounds.max} aria-valuenow={width.shown}
    title="Drag to resize the panel; double-click for the usual width"
    onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onKeyDown={key}
    onDoubleClick={() => width.save(width.bounds.default)} />
}

function usePanel(story: StoryData) {
  const { wide, custom } = useBeside()
  const roomy = useWide()
  const grids = useGrids()
  const gear = useQuery({ queryKey: ['story-gear'], queryFn: () => api<Gear>('/story/gear'), enabled: story.messages.length > 0 })
  const [view, setView] = useState<PanelView>('scene')
  const [open, setOpen] = useState(false)
  const [flash, setFlash] = useState<Flash | null>(null)
  // Opened to a widget asked for from elsewhere: before this screen was shown, or while it is. In Custom, a widget
  // already on the grid is shown where it is, for a moment, rather than opened in the drawer.
  useEffect(() => {
    const take = () => {
      const widget = takeAsked()
      if (!widget) return
      if (tiledNow(widget)) { setView('scene'); setFlash({ widget, at: Date.now() }) } else { setView(widget); setOpen(true) }
    }
    take()
    window.addEventListener(ASK_EVENT, take)
    return () => window.removeEventListener(ASK_EVENT, take)
  }, [])
  useEffect(() => {
    if (!flash) return
    const timer = window.setTimeout(() => setFlash(null), 1600)
    return () => window.clearTimeout(timer)
  }, [flash])
  const [pins, setPins] = useState(loadPins)
  const picked = sceneWidgets(story, !!gear.data?.shop)
  const showing = wide || open
  // The scene the player last looked at; a different one since puts the dot on the Scene tab.
  const [seen, setSeen] = useState(picked.join())
  if (showing && view === 'scene' && seen !== picked.join()) setSeen(picked.join())
  const pick = (next: PanelView) => {
    if (!wide && open && view === next) setOpen(false)
    else { setView(next); setOpen(true) }
  }
  const pin = (widget: Widget) => {
    const next = pins.includes(widget) ? pins.filter((item) => item !== widget) : [...pins, widget]
    setPins(next)
    savePins(next)
  }
  return { wide, custom, grids, flash, roomy, view, open, close: () => setOpen(false), pins, picked, showing, changed: seen !== picked.join(), pick, pin }
}

function PanelBody({ panel, ...props }: PanelProps & { panel: Panel }) {
  const { story } = props
  const { view, pins, picked, pin } = panel
  return (
    <div className="story-panel-body">
      {!panel.wide && <button type="button" className="icon-button story-panel-close" aria-label="Close" onClick={panel.close}><X aria-hidden="true" /></button>}
      {view === 'scene' && panel.custom && <StoryGrid story={story} grids={panel.grids} picked={picked} flash={panel.flash}
        render={(widget) => <PanelWidget widget={widget} {...props} />} />}
      {view === 'scene' && !panel.custom && <SceneView {...props} picked={picked} pins={pins.filter((item) => !picked.includes(item) && hasWidget(story, item))} onUnpin={pin} />}
      {view === 'more' && <MoreList story={story} onPick={panel.pick} />}
      {view !== 'scene' && view !== 'more' && <DrawerView {...props} widget={view} pinned={pins.includes(view)} onPin={() => pin(view)} />}
    </div>
  )
}

function PanelTabs({ story, panel }: { story: StoryData; panel: Panel }) {
  const tab = (name: PanelView, label: ReactNode) => (
    <button type="button" className="story-tab" aria-pressed={panel.showing && panel.view === name} onClick={() => panel.pick(name)}>{label}</button>)
  return (
    <nav className="story-tabs" aria-label="Scene and drawer">
      {tab('scene', <>{panel.changed && <span className="story-dot" aria-label="The scene changed" />}{panel.picked.includes('fight') && <Swords aria-hidden="true" />}Scene</>)}
      {TABS.filter((item) => hasWidget(story, item)).map((item) => <Fragment key={item}>{tab(item, WIDGET_NAMES[item])}</Fragment>)}
      {tab('more', <><Ellipsis aria-hidden="true" />More</>)}
      {panel.roomy && <LayoutSwitch reader={!panel.wide} />}
    </nav>
  )
}

/** Reader, or back to the layout with the panel beside the story (Classic, Custom or Visual novel), from the tabs on a wide screen
 *  (Settings > General > Appearance keeps it too). */
function LayoutSwitch({ reader }: { reader: boolean }) {
  const { lastBeside } = useDeviceLook()
  const label = reader ? 'Show the scene panel beside the story' : 'Reader layout: give the story the room'
  return <button type="button" className="icon-button story-layout" aria-label={label} title={label}
    onClick={() => saveLook({ layout: reader ? lastBeside : 'reader' })}>{reader ? <PanelRight aria-hidden="true" /> : <BookOpenText aria-hidden="true" />}</button>
}

/** Before the first line there is no scene yet; only the ways back into other stories are worth showing. */
function BeforeTheStory({ story, change }: PanelProps) {
  const others = !story.campaign?.ironman && story.branches.some((branch) => !branch.playing)
  if (!others && !story.people.length) return null
  return (
    <aside className="story-panel story-panel-before" aria-label="Your other stories">
      <div className="story-panel-body">
        <StoryPeople people={story.people} onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))} />
        {others && <StoryBranches branches={story.branches} onSwitch={(id) => void change(() => api<StoryData>(`/story/branches/${encodeURIComponent(id)}/switch`, {}))} />}
      </div>
    </aside>
  )
}

interface SceneProps extends PanelProps { picked: Widget[]; pins: Widget[]; onUnpin: (widget: Widget) => void }

function SceneView({ picked, pins, onUnpin, ...props }: SceneProps) {
  return (<>
    <h2 className="story-panel-heading">This scene</h2>
    {picked.map((widget) => <PanelWidget key={widget} widget={widget} {...props} />)}
    {!!pins.length && <h2 className="story-panel-heading">Pinned</h2>}
    {pins.map((widget) => <div key={widget} className="story-pinned">
      <PanelWidget widget={widget} {...props} />
      <button type="button" className="text-button" onClick={() => onUnpin(widget)}><PinOff aria-hidden="true" />Unpin {WIDGET_NAMES[widget].toLowerCase()}</button>
    </div>)}
  </>)
}

function MoreList({ story, onPick }: { story: StoryData; onPick: (widget: Widget) => void }) {
  return (<>
    <h2 className="story-panel-heading">More</h2>
    <ul className="story-more">
      {MORE.filter((widget) => hasWidget(story, widget)).map((widget) => <li key={widget}>
        <button type="button" className="text-button" onClick={() => onPick(widget)}>{WIDGET_NAMES[widget]}</button>
      </li>)}
    </ul>
  </>)
}

interface DrawerProps extends PanelProps { widget: Widget; pinned: boolean; onPin: () => void }

/** One widget out of the drawer, with a pin to keep it in the scene panel (a pin wins over what the scene picks). */
function DrawerView({ widget, pinned, onPin, ...props }: DrawerProps) {
  return (<>
    <div className="story-panel-title">
      <h2 className="story-panel-heading" id={widget === 'rules' ? 'story-dials-heading' : undefined}>{WIDGET_NAMES[widget]}</h2>
      <button type="button" className="text-button" aria-pressed={pinned} onClick={onPin}
        title={pinned ? 'Take it out of the scene panel' : 'Keep it in the scene panel, whatever the scene'}>
        {pinned ? <><PinOff aria-hidden="true" />Unpin</> : <><Pin aria-hidden="true" />Pin to the scene</>}
      </button>
    </div>
    <PanelWidget widget={widget} {...props} />
  </>)
}

/** Each widget as the panel shows it: unfolded, since it was asked for. */
const WIDGETS: Record<Widget, (props: PanelProps, refresh: () => void) => ReactNode> = {
  fight: ({ story }) => <FightCard fight={story.fight} />,
  here: ({ story, change }) => <StoryPeople people={peopleHere(story)} title="Here with you" open onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))} />,
  sheet: () => <StorySheet open />,
  pack: (_, refresh) => <StoryGear open onTrade={refresh} />,
  journal: () => <StoryJournal open />,
  map: ({ story, onTravel, onLine }) => <StoryMap map={story.map} open onTravel={onTravel} onLine={onLine} />,
  inside: ({ story, onLine }) => <StoryInterior interior={story.interior} open onLine={onLine} />,
  town: ({ story, onLine }) => <StoryTown where={`${story.scene.city.id}/${story.scene.place.id}`} open onLine={onLine} />,
  people: ({ story, change }) => <StoryPeople people={story.people} open onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))} />,
  party: ({ story, change }) => <StoryPeople people={partyOf(story)} title="Your party" open onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))} />,
  powers: ({ story }) => <StoryPowers factions={story.factions ?? []} tier={story.tier} open />,
  talk: ({ story }) => <StoryPolitics where={`${story.scene.city.id}/${story.scene.local_time.slice(0, 10)}/${story.table?.politics ?? ''}/${story.dice_shown}`} gm={!!story.table?.gm_view} open />,
  chapters: ({ story, change, onBack }) => story.campaign && <StoryChapters campaign={story.campaign} change={change} onBack={onBack} open />,
  branches: ({ story, change }) => <StoryBranches branches={story.branches} open
    onSwitch={(id) => void change(() => api<StoryData>(`/story/branches/${encodeURIComponent(id)}/switch`, {}))} />,
  notebook: () => <StoryNotebook open />,
  dice: () => <StoryDiceLog open />,
  art: ({ story }) => <StoryArt people={story.people} present={story.scene.present} place={{ key: `${story.scene.city.id}/${story.scene.place.id}`, name: story.scene.place.name }} open />,
  export: () => <StoryExport open />,
  rules: ({ story }, refresh) => <ToneAndRules story={story} refresh={refresh} />,
}

function PanelWidget({ widget, ...props }: PanelProps & { widget: Widget }) {
  const client = useQueryClient()
  return <>{WIDGETS[widget](props, () => void client.invalidateQueries({ queryKey: STORY_KEY }))}</>
}

/** Tone and rules are set once and changed now and then. They are this campaign's rules, so they live here rather
 *  than in Settings (src/features/settings/sections.ts ELSEWHERE). */
function ToneAndRules({ story, refresh }: { story: StoryData; refresh: () => void }) {
  return (
    <div className="story-dials">
      <p className="subtle">This campaign's rules. Another world keeps its own, and a new story starts in the world's tone with what you last chose to see.</p>
      <StoryIntensity intensity={story.intensity} onSaved={refresh} />
      <StoryInjuries persistence={story.injury_persistence ?? 'permanent'} onSaved={refresh} />
      <HiddenValues />
    </div>
  )
}

/** Who the character is fighting and how each foe stands; the numbers only with the dice shown (the story sends
 *  them only then). */
function FightCard({ fight }: { fight: StoryFight }) {
  if (!fight.fight) return null
  return (
    <details className="story-people story-fight-card" open>
      <summary>The fight · round {fight.fight.round}{fight.fight.area ? ` · at ${fight.fight.area}` : ''}</summary>
      <ul aria-label="Foes">
        {fight.fight.foes.map((foe, index) => <li key={`${foe.name}-${index}`}>
          <p><strong>{foe.name}</strong> <span className="subtle">{foe.state}{foeNumbers(foe)}{zoneText(foe.zone)}</span></p>
        </li>)}
      </ul>
      {!!fight.fight.allies?.length && <ul aria-label="Beside you">
        {fight.fight.allies.map((ally) => <li key={ally.name}>
          <p><strong>{ally.name}</strong> <span className="subtle">beside you, {ally.state}</span></p>
        </li>)}
      </ul>}
      {fight.fight.grid && <BattleMap grid={fight.fight.grid} />}
    </details>
  )
}
