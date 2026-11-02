import { Fragment, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, Bookmark, Lightbulb, MapPin, RotateCcw, Send, Timer, Undo2 } from 'lucide-react'
import { api, newId, streamApi } from '../../api'
import type { View } from '../../workspace'
import type { BandStep, CitySummary, Story as StoryData, StoryBack, StoryMap as TravelMap, StoryMessage, StoryScene, TurnEvent, TurnSoFar } from '../../types'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { InfoTip } from '../../components/InfoTip'
import { LifeCard } from './StoryLifeCard'
import { AiFooter, CrisisNote } from '../../components/Safety'
import { aroundText, foesText, NO_TURN, otherTowns, paceText, placeGroups, receiptsByReply, spotsText, turnAfter, whereText } from './storyText'
import { TurnReceipt } from './StoryReceipt'
import { StatusStrip } from './StoryStatus'
import { RollCard, TurnLive } from './StoryTurn'
import { StoryTown } from './StoryTown'
import { StoryMap } from './StoryMap'
import { AuthorsNote } from './AuthorsNote'
import { StoryStart } from './StoryStart'
import { TitleScreen } from './TitleScreen'
import { StoryNarration } from './StoryNarration'
import { StoryPanel } from './StoryPanel'
import { StoryStage } from './StoryArt'
import { useWorldTheme } from './useWorldTheme'
import { EntityHost } from './EntityCard'
import { STORY_KEY } from './table'
import { freshIdeas, withIdea, type Ideas } from './ideas'

const OUT_OF_STORY = 'To step out of the story, start a message with OOC: or wrap it in ((double parentheses)).'

/** The story: the user's own story around the cities, told by a narrator. */
export function Story({ go }: { go: (view: View) => void }) {
  const story = useQuery({ queryKey: STORY_KEY, queryFn: () => api<StoryData>('/story') })
  const client = useQueryClient()
  const [pending, setPending] = useState<string | null>(null)
  // The narration so far while it streams in (dungeon/pace.py).
  const [streamed, setStreamed] = useState('')
  // The turn's stages and rolls so far, before and around the narration (dungeon/story.py answer).
  const [turn, setTurn] = useState<TurnSoFar>(NO_TURN)
  const [error, setError] = useState('')
  // How many lines the story had when the turn began: once the saved story has more, the turn is in it.
  const [since, setSince] = useState(0)
  const [draft, setDraft] = useState({ text: '', at: 0 })
  // Past the title screen (./TitleScreen.tsx), which shows before a campaign starts.
  const [begun, setBegun] = useState(false)
  const look = useWorldTheme(story.data)
  if (story.isPending) return <Loading label="Opening your story" />
  if (story.isError) return <ErrorNotice error={story.error} />
  const update = (data: StoryData) => client.setQueryData(STORY_KEY, data)
  // The turn stays on screen as streamed until the saved story has come back, so the narration never blinks out;
  // `streamed` is kept after the turn, as the draft the saved text is compared with (StoryNarration `draft`).
  const run = async (text: string | null, request: () => Promise<unknown>) => {
    setSince(story.data.messages.length)
    setPending(text)
    setStreamed('')
    setTurn(NO_TURN)
    setError('')
    try { await request() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work. Try again.') }
    finally {
      await Promise.all([client.invalidateQueries({ queryKey: STORY_KEY }), client.invalidateQueries({ queryKey: ['story-journal'] }), client.invalidateQueries({ queryKey: ['story-gear'] }), client.invalidateQueries({ queryKey: ['story-sheet'] }), client.invalidateQueries({ queryKey: ['story-dice-log'] })])
        .finally(() => setPending(null))
    }
  }
  const grow = (piece: string) => setStreamed((before) => before + piece)
  const note = (event: unknown) => setTurn((before) => turnAfter(before, event as TurnEvent))
  const send = (text: string) => run(text, () => streamApi('/story/messages/stream', { text, client_id: newId() }, grow, note))
  const change = (request: () => Promise<StoryData>) => run(null, () => request().then(update))
  const draftLine = (text: string) => setDraft({ text, at: Date.now() })
  const opening = openingOf(story.data, pending, begun)
  return (
    <EntityHost story={story.data} onDraft={draftLine} onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))}>
    <section className={look.className} style={look.style} aria-labelledby="story-heading">
      <div className="story-main">
        <StoryHeader story={story.data} change={change} onDraft={(text) => setDraft({ text, at: Date.now() })} />
        {!story.data.ready && <NoModel go={go} />}
        {opening === 'title' ? <TitleScreen onBegin={() => setBegun(true)} />
          : opening === 'start' ? <StoryStart onStarted={update} intensity={story.data.intensity} /> : <>
          <StoryStage turn={`${story.data.scene.city.id}/${story.data.scene.place.id}/${story.data.messages.length}`} />
          <StoryLog messages={story.data.messages} pending={story.data.messages.length > since ? null : pending} streamed={streamed} turn={turn} bands={story.data.bands}
            onRetry={() => void run('', () => streamApi('/story/retry/stream', {}, grow, note))}
            onRewrite={(id, passage, note) => change(() => api<StoryData>(`/story/messages/${id}/rewrite`, { passage, note }))}
            onSwitch={(id) => change(() => api<StoryData>(`/story/messages/${id}/switch`, {}))}
            onBack={story.data.campaign?.ironman ? undefined : (id) => void run(null, () => api<StoryBack>('/story/back', { message_id: id }).then((data) => { update(data); setDraft({ text: data.draft, at: Date.now() }) }))}
            onBookmark={(id, name) => change(() => api<StoryData>('/story/bookmarks', { message_id: id, name }))} />
          {error && <div className="story-notice"><Notice tone="error">{error}</Notice></div>}
          <StoryComposer key={draft.at} busy={pending !== null} draft={draft.text} turn={story.data.messages.length} onSend={(text) => void send(text)} />
        </>}
        <NewStory empty={!story.data.messages.length} onClear={() => run(null, () => api<StoryData>('/story', undefined, 'DELETE').then((data) => { update(data); setBegun(false) }))} />
      </div>
      <StoryPanel story={story.data} change={change} onTravel={(name) => setDraft({ text: `I set out for ${name}.`, at: Date.now() })}
        onLine={(text) => setDraft({ text, at: Date.now() })}
        onBack={(data) => setDraft({ text: data.draft, at: Date.now() })} />
    </section>
    </EntityHost>
  )
}

/** Before a campaign starts: the title screen (./TitleScreen.tsx) until the player begins, then the start form. */
function openingOf(story: StoryData, pending: string | null, begun: boolean): 'title' | 'start' | null {
  if (story.messages.length || pending !== null) return null
  return begun ? 'start' : 'title'
}

function NoModel({ go }: { go: (view: View) => void }) {
  return <div className="story-notice"><Notice action={<button type="button" className="text-button" onClick={() => go('settings/models')}>Open Models</button>}>
    Add a text model in Settings &gt; Models to tell the story.</Notice></div>
}

/** Where and when the story is, and the fight. The scene line is the header; the title is for screen readers. */
interface HeaderProps { story: StoryData; change: (request: () => Promise<StoryData>) => Promise<void>; onDraft: (text: string) => void }

function StoryHeader({ story, change, onDraft }: HeaderProps) {
  const fight = foesText(story.fight)
  return (
    <header className="story-header">
      <h1 id="story-heading" className="visually-hidden">Story</h1>
      <SceneBar scene={story.scene} map={story.map ?? null} onDraft={onDraft}
        onMove={(body) => change(() => api<StoryData>('/story/scene', body, 'PUT'))} status={<StatusStrip story={story} />} />
      {fight && <p className="story-fight" role="status">{fight}</p>}
    </header>
  )
}

interface SceneProps { scene: StoryScene; map: TravelMap | null; onDraft: (text: string) => void; onMove: (body: { city_id: string; place_id?: string }) => Promise<void>; status?: ReactNode }

function SceneBar({ scene, map, onDraft, onMove, status }: SceneProps) {
  const [moving, setMoving] = useState(false)
  return (
    <div className="story-scene">
      <div className="story-where">
        <p><MapPin aria-hidden="true" /> <strong>{whereText(scene)}</strong></p>
        <button type="button" className="text-button" aria-expanded={moving} onClick={() => setMoving(!moving)}>
          {moving ? 'Stay here' : 'Go somewhere else…'}</button>
      </div>
      {status}
      {!!scene.place.spots?.length && <p className="subtle">{spotsText(scene.place.spots)}</p>}
      <p>{aroundText(scene.around)}</p>
      {moving && <GoElsewhere scene={scene} map={map} onDone={() => setMoving(false)} onDraft={onDraft} onMove={onMove} />}
    </div>
  )
}

interface GoProps extends Omit<SceneProps, 'scene' | 'status'> { scene: StoryScene; onDone: () => void }

/** Going somewhere else, on the maps. A place across town is picked on the street map (./StoryTown.tsx) and is a cut.
 *  Another town, a keep or a hex is picked on the travel map (./StoryMap.tsx) and is a journey: it writes "I set out
 *  for…" into the composer, so the road takes its hours and can bring trouble (dungeon/travel.py). A town of this
 *  world that no travel map shows is a cut too; towns of other worlds and the roads between towns are not offered. */
function GoElsewhere({ scene, map, onDone, onDraft, onMove }: GoProps) {
  const cities = useQuery({ queryKey: ['world-cities'], queryFn: () => api<CitySummary[]>('/world/cities') })
  const journeys = map?.places.filter((place) => !place.here).map((place) => place.name) ?? []
  const towns = otherTowns(cities.data ?? [], scene.city.id, journeys)
  const move = (body: { city_id: string; place_id?: string }) => void onMove(body).then(onDone)
  const draft = (text: string) => { onDraft(text); onDone() }
  const places = scene.places.filter((place) => place.id !== scene.place.id)
  return (
    <div className="story-go">
      <StoryTown where={`${scene.city.id}/${scene.place.id}`} open onGo={(thing) => move({ city_id: scene.city.id, place_id: thing.id })}
        empty={!!places.length && <PlaceList places={places} onGo={(id) => move({ city_id: scene.city.id, place_id: id })} />} />
      <StoryMap map={map} open onTravel={(name) => draft(`I set out for ${name}.`)} onLine={draft} />
      {!!towns.length && <div className="story-go-towns">
        <p className="subtle">Other towns</p>
        <ul className="map-places">
          {towns.map((town) => <li key={town.id}><span>{town.name}</span>
            <button type="button" className="text-button" onClick={() => move({ city_id: town.id })}>Go</button></li>)}
        </ul>
      </div>}
    </div>
  )
}

/** The places here by neighborhood, where there is no street map to pick them on. */
function PlaceList({ places, onGo }: { places: StoryScene['places']; onGo: (id: string) => void }) {
  return (
    <details className="story-people" open>
      <summary>Places here</summary>
      {placeGroups(places).map(([hood, items]) => <Fragment key={hood}>
        <p className="subtle">{hood}</p>
        <ul className="map-places">
          {items.map((item) => <li key={item.id}><span>{item.name} <span className="subtle">({item.kind})</span></span>
            <button type="button" className="text-button" onClick={() => onGo(item.id)}>Go</button></li>)}
        </ul>
      </Fragment>)}
    </details>
  )
}

interface Rewrites { onRewrite: (id: string, passage: string, note: string) => Promise<void>; onSwitch: (id: string) => Promise<void> }
interface LogProps extends Rewrites {
  messages: StoryMessage[]; pending: string | null; streamed: string; turn: TurnSoFar; bands?: BandStep[] | null
  onRetry: () => void; onBack?: (id: string) => void; onBookmark: (id: string, name: string) => Promise<void>
}

/** How near the bottom (px) still counts as reading the newest text, so the log keeps following it. */
const FOLLOW = 80

/** Follows new text only while the reader is at the bottom; scrolled up to reread, they keep their place, and
 *  `behind` says there is newer text than what they last read to. Sending a line jumps to it wherever they were. */
function useFollow(shown: string, pending: string | null) {
  const log = useRef<HTMLDivElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const [atEnd, setAtEnd] = useState(true)
  const [readTo, setReadTo] = useState(shown)
  // At the bottom the reader has read everything shown (set while rendering, React's pattern for derived state).
  if (atEnd && readTo !== shown) setReadTo(shown)
  const toEnd = () => end.current?.scrollIntoView?.({ block: 'end' })
  const onScroll = () => {
    const box = log.current
    if (box) setAtEnd(box.scrollHeight - box.scrollTop - box.clientHeight < FOLLOW)
  }
  useEffect(() => { if (atEnd) end.current?.scrollIntoView?.({ block: 'end' }) }, [shown, atEnd])
  useEffect(() => { if (pending !== null) end.current?.scrollIntoView?.({ block: 'end' }) }, [pending])
  return { log, end, onScroll, toEnd, behind: !atEnd && readTo !== shown }
}

function StoryLog({ messages, pending, streamed, turn, bands, onRetry, onBack, onBookmark, onRewrite, onSwitch }: LogProps) {
  const { log, end, onScroll, toEnd, behind } = useFollow(`${messages.length}:${streamed.length}`, pending)
  const last = messages[messages.length - 1]
  const receipts = receiptsByReply(messages)
  return (
    <div className="story-log" aria-live="polite" ref={log} onScroll={onScroll}>
      {messages.map((message) => <Fragment key={message.id}>
        <StoryLine message={message} bands={bands} onBack={pending ? undefined : onBack} onBookmark={pending ? undefined : onBookmark}
          rewrites={pending === null ? { onRewrite, onSwitch } : undefined} draft={pending === null && message === last ? streamed : undefined} />
        <TurnReceipt chips={receipts.get(message.id)} />
      </Fragment>)}
      {pending && <p className="story-user">{pending}</p>}
      {pending !== null && <TurnLive turn={turn} writing={!!streamed} />}
      {pending !== null && !!streamed && <div className="story-narration">{streamed.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}</div>}
      {last?.status === 'failed' && !pending && <button type="button" className="text-button" onClick={onRetry}><RotateCcw aria-hidden="true" />Try again</button>}
      <div ref={end} />
      {behind && <button type="button" className="button story-newer" onClick={toEnd}><ArrowDown aria-hidden="true" />New text below</button>}
    </div>
  )
}

/** `onBack` goes back to before a line of the player's, to send it again with new dice; `rewrites` rewords a
 *  narration (none while a turn is being told). */
interface LineProps { message: StoryMessage; bands?: BandStep[] | null; onBack?: (id: string) => void; onBookmark?: (id: string, name: string) => Promise<void>; rewrites?: Rewrites; draft?: string }

function StoryLine({ message, bands, onBack, onBookmark, rewrites, draft }: LineProps) {
  if (message.role === 'scene') return <p className="story-move">{message.text}</p>
  if (message.role === 'user') return <>
    <p className="story-user" id={`line-${message.id}`}>{message.text}</p>
    <div className="story-turn">
      {message.cards?.map((card, index) => <LifeCard key={index} card={card} />)}
      {message.rolls?.map((roll, index) => <RollCard key={index} roll={roll} bands={bands} />)}
      <div className="story-turn-actions">
        {/* How long the turn took is for tuning, not the story: it waits in a tooltip until the dice log ships. */}
        {message.pace && <span className="story-pace" title={paceText(message.pace)}><Timer aria-hidden="true" /><span className="visually-hidden">{paceText(message.pace)}</span></span>}
        {onBack && <button type="button" className="text-button story-back" onClick={() => onBack(message.id)}
          title="Go back to before this line and send it again, with new dice. The story from here is kept as a branch."><Undo2 aria-hidden="true" />Go back here</button>}
        {onBookmark && <BookmarkButton onSave={(name) => onBookmark(message.id, name)} />}
      </div>
    </div>
    {message.crisis_help && <CrisisNote />}
  </>
  if (message.status === 'failed') return <Notice tone="error">The narrator could not go on: {message.error}</Notice>
  return <StoryNarration message={message} draft={draft} {...rewrites} />
}

/** Names this moment to find it again (dungeon/chapters.py bookmarks). */
function BookmarkButton({ onSave }: { onSave: (name: string) => Promise<void> }) {
  const [name, setName] = useState<string | null>(null)
  if (name === null) return <button type="button" className="text-button" onClick={() => setName('')}><Bookmark aria-hidden="true" />Bookmark</button>
  return (
    <form className="story-bookmark" onSubmit={(event) => { event.preventDefault(); if (name.trim()) void onSave(name.trim()).then(() => setName(null)) }}>
      <input aria-label="Name this moment" placeholder="Name this moment" maxLength={80} value={name} onChange={(event) => setName(event.target.value)} autoFocus />
      <button type="submit" className="text-button" disabled={!name.trim()}>Save</button>
      <button type="button" className="text-button" onClick={() => setName(null)}>Cancel</button>
    </form>
  )
}

/** `draft` is a line taken back to send again; a new draft remounts the composer with it, which also drops any
 * ideas (./ideas.ts), as sending a line does. */
function StoryComposer({ busy, draft, turn, onSend }: { busy: boolean; draft: string; turn: number; onSend: (text: string) => void }) {
  const [text, setText] = useState(draft)
  const [found, setFound] = useState<Ideas | null>(null)
  const [thinking, setThinking] = useState(false)
  const shown = freshIdeas(found, turn)
  const submit = () => { if (text.trim() && !busy) { onSend(text.trim()); setText(''); setFound(null) } }
  const askIdeas = () => {
    setThinking(true)
    api<Ideas>('/story/ideas', {}).then(setFound, () => setFound(null)).finally(() => setThinking(false))
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit() }
  }
  return (<>
    {shown.length > 0 && <div className="story-ideas" role="group" aria-label="Ideas">
      {shown.map((idea) => <button key={idea} type="button" className="receipt-chip" onClick={() => { setText((before) => withIdea(before, idea)); setFound(null) }}>{idea}</button>)}
    </div>}
    <form className="composer story-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
      <AuthorsNote chat="story" name="The narrator" story />
      <label className="visually-hidden" htmlFor="story-text">What you do or say</label>
      <textarea id="story-text" rows={2} value={text} maxLength={40000} placeholder="What do you do or say?"
        onChange={(event) => setText(event.target.value)} onKeyDown={onKeyDown} />
      <InfoTip id="story-tip" label="the story" above text={`Enter sends, Shift+Enter adds a new line. ${OUT_OF_STORY}`} />
      <button type="button" className="button story-ideas-button" disabled={busy || thinking} onClick={askIdeas} aria-label="Ideas" title="Two or three things you could do now. They are not kept."><Lightbulb aria-hidden="true" /><span className="label">{thinking ? 'Thinking…' : 'Ideas'}</span></button>
      <button type="submit" className="button primary" disabled={busy || !text.trim()}><Send aria-hidden="true" />Send</button>
    </form>
    <AiFooter />
  </>)
}

function NewStory({ empty, onClear }: { empty: boolean; onClear: () => Promise<void> }) {
  const [asking, setAsking] = useState(false)
  if (empty) return null
  return (
    <div className="story-footer">
      <button type="button" className="text-button" onClick={() => setAsking(true)}>Start a new story…</button>
      {asking && <ConfirmDialog title="Start a new story?" onClose={() => setAsking(false)} actions={<>
        <button type="button" className="button" onClick={() => setAsking(false)}>Cancel</button>
        <button type="button" className="button primary" onClick={() => void onClear().then(() => setAsking(false))}>Start a new story</button>
      </>}>
        <p>The story so far and the people you&apos;ve met in it are cleared for good. You stay where you are.</p>
      </ConfirmDialog>}
    </div>
  )
}
