import { Fragment, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, Bookmark, RotateCcw, Send, Timer, Undo2 } from 'lucide-react'
import { api, newId, streamApi } from '../../api'
import type { View } from '../../workspace'
import type { BandStep, CitySummary, Story as StoryData, StoryBack, StoryMap as TravelMap, StoryMessage, StoryScene, TurnEvent, TurnSoFar } from '../../types'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { LifeCard } from './StoryLifeCard'
import { AiFooter, CrisisNote } from '../../components/Safety'
import { foesText, NO_TURN, otherTowns, paceText, placeGroups, receiptsByReply, sceneLine, turnAfter, whereText } from './storyText'
import { TurnReceipt } from './StoryReceipt'
import { RollCard, TurnLive } from './StoryTurn'
import { StoryTown } from './StoryTown'
import { StoryMap } from './StoryMap'
import { AuthorsNote } from './AuthorsNote'
import { openAuthorsNote } from './noteState'
import { StoryMenu } from './StoryMenu'
import { menuCommands, OUT_OF_STORY, type MenuCommand } from './menuText'
import { askForDrawer } from './scene'
import { StoryStart } from './StoryStart'
import { TitleScreen } from './TitleScreen'
import { StoryNarration } from './StoryNarration'
import { StoryPanel } from './StoryPanel'
import { StoryStage } from './StoryArt'
import { useWorldTheme } from './useWorldTheme'
import { EntityHost } from './EntityCard'
import { STORY_KEY } from './table'
import { freshIdeas, withIdea, type Ideas } from './ideas'
import { ReplyCard } from '../round/ReplyCard'
import { PACE_KEY, ROUND_KEY, useRoundPlay } from '../round/useRound'
import { useLineMarks, useMode, useWatch } from '../round/useModes'
import { ModeSwitch } from '../round/ModeSwitch'
import { WatchBar } from '../round/WatchBar'
import { MissedBanner } from '../round/MissedBanner'
import { AuthorNotes } from '../round/AuthorNotes'
import { LineTools } from '../round/LineTools'
import { openingKind, type LineMarks, type Mode } from '../round/round'
import { composerText, NUDGE } from '../round/roundText'

/** The story: the user's own story around the cities, told by a narrator. */
export function Story({ go }: { go: (view: View) => void }) {
  const story = useQuery({ queryKey: STORY_KEY, queryFn: () => api<StoryData>('/story') })
  const client = useQueryClient()
  const [pending, setPending] = useState<string | null>(null)
  // The narration so far while it streams in (adventure/pace.py).
  const [streamed, setStreamed] = useState('')
  // The turn's stages and rolls so far, before and around the narration (adventure/story.py answer).
  const [turn, setTurn] = useState<TurnSoFar>(NO_TURN)
  const [error, setError] = useState('')
  // How many lines the story had when the turn began: once the saved story has more, the turn is in it.
  const [since, setSince] = useState(0)
  const [draft, setDraft] = useState({ text: '', at: 0 })
  // Past the title screen (./TitleScreen.tsx), which shows before a campaign starts.
  const [begun, setBegun] = useState(false)
  // "Start a new story…" from the menu, waiting to be confirmed.
  const [clearing, setClearing] = useState(false)
  const look = useWorldTheme(story.data)
  // The round loop (src/features/round/): the timeline, the cast list's minds and the reply card.
  const round = useRoundPlay(setError)
  const update = (data: StoryData) => client.setQueryData(STORY_KEY, data)
  // The turn stays on screen as streamed until the saved story has come back, so the narration never blinks out;
  // `streamed` is kept after the turn, as the draft the saved text is compared with (StoryNarration `draft`).
  const run = async (text: string | null, request: () => Promise<unknown>) => {
    setSince(story.data?.messages.length ?? 0)
    setPending(text)
    setStreamed('')
    setTurn(NO_TURN)
    round.start()
    setError('')
    try { await request() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work. Try again.') }
    finally {
      await Promise.all([client.invalidateQueries({ queryKey: STORY_KEY }), client.invalidateQueries({ queryKey: ['story-journal'] }), client.invalidateQueries({ queryKey: ['story-gear'] }), client.invalidateQueries({ queryKey: ['story-sheet'] }), client.invalidateQueries({ queryKey: ['story-dice-log'] }), client.invalidateQueries({ queryKey: ROUND_KEY }), client.invalidateQueries({ queryKey: PACE_KEY })])
        .finally(() => setPending(null))
    }
  }
  const grow = (piece: string) => setStreamed((before) => before + piece)
  const note = (event: unknown) => { setTurn((before) => turnAfter(before, event as TurnEvent)); round.hear(event) }
  const send = (text: string) => run(text, () => streamApi('/story/messages/stream', { text, client_id: newId() }, grow, note))
  const change = (request: () => Promise<StoryData>) => run(null, () => request().then(update))
  const mode = useMode(round.cast.table, setError)
  // Author and Watch turns (POST /api/rounds/turns/stream): Next with the author's nudge, or with none in Watch.
  const nextTurn = (nudge: string) => run(nudge, () => streamApi('/rounds/turns/stream', { nudge, against: mode.head }, grow, note))
  const watch = useWatch({ on: mode.active === 'watch', busy: pending !== null, waiting: !!round.waiting, error, head: mode.head,
    next: () => void run('', () => streamApi('/rounds/watch/next/stream', { against: mode.head }, grow, note)), clear: () => setError(''), onError: setError })
  const marks = useLineMarks(round.cast.table)
  if (story.isPending) return <Loading label="Opening your story" />
  if (story.isError) return <ErrorNotice error={story.error} />
  const draftLine = (text: string) => setDraft({ text, at: Date.now() })
  const opening = openingOf(story.data, pending, begun)
  return (
    <EntityHost story={story.data} onDraft={draftLine} onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))}>
    <section className={look.className} style={look.style} aria-labelledby="story-heading">
      <div className="story-main">
        <StoryHeader story={story.data} change={change} onDraft={(text) => setDraft({ text, at: Date.now() })}
          extra={<ModeSwitch shown={mode.shown} mode={mode.mode} onChange={mode.change} />} />
        {opening === 'title' ? <TitleScreen onBegin={() => setBegun(true)} onNew={toPackages} />
          : opening === 'start' ? <StoryStart onStarted={update} place={story.data.scene.city.name} /> : <>
          <StoryStage turn={`${story.data.scene.city.id}/${story.data.scene.place.id}/${story.data.messages.length}`} />
          <StoryLog marks={marks} messages={story.data.messages} pending={story.data.messages.length > since ? null : pending} streamed={streamed} turn={turn} bands={story.data.bands}
            onRetry={() => void run('', () => streamApi('/story/retry/stream', {}, grow, note))}
            onRewrite={(id, passage, note) => change(() => api<StoryData>(`/story/messages/${id}/rewrite`, { passage, note }))}
            onSwitch={(id) => change(() => api<StoryData>(`/story/messages/${id}/switch`, {}))}
            onBack={story.data.campaign?.ironman ? undefined : (id) => void run(null, () => api<StoryBack>('/story/back', { message_id: id }).then((data) => { update(data); setDraft({ text: data.draft, at: Date.now() }) }))}
            onBookmark={(id, name) => change(() => api<StoryData>('/story/bookmarks', { message_id: id, name }))} />
          <StoryError error={watch.hides(round.shownError(error))} />
          <MissedBanner asking={mode.asking} onAnswer={mode.answer} />
          <StoryFoot waiting={!!round.waiting} active={mode.active}
            reply={() => round.waiting && <ReplyCard waiting={round.waiting.awaiting} speaker={round.speaker} you={round.you} busy={pending !== null}
              onAnswer={(kind, text) => void run(kind === 'reply' ? text.trim() : '', () => round.answer(kind, text, grow, note))} />}
            watch={() => <WatchBar playing={watch.playing} busy={pending !== null} pause={watch.pause} seconds={watch.seconds}
              onPlay={watch.play} onPause={watch.stop} onNext={() => void nextTurn('')} onEvery={watch.every} onGoOn={watch.goOn}
              onAuthor={() => mode.change('author')} onRaise={() => go('settings/models')} onStop={watch.stop} />}
            compose={() => <StoryComposer key={draft.at} busy={pending !== null} draft={draft.text} turn={story.data.messages.length}
              nudge={mode.active === 'author'} below={mode.active === 'author' && <AuthorNotes />} onSend={(text) => void (mode.active === 'author' ? nextTurn(text) : send(text))}
              commands={menuCommands(story.data)} onNewStory={() => setClearing(true)}
              onAddModel={story.data.ready ? undefined : () => go('settings/models')} />} />
        </>}
        <NewStory open={clearing} onClose={() => setClearing(false)} onClear={() => run(null, () => api<StoryData>('/story', undefined, 'DELETE').then((data) => { update(data); setBegun(false) }))} />
      </div>
      <StoryPanel story={story.data} change={change} round={round.cast} onTravel={(name) => setDraft({ text: `I set out for ${name}.`, at: Date.now() })}
        onLine={(text) => setDraft({ text, at: Date.now() })}
        onBack={(data) => setDraft({ text: data.draft, at: Date.now() })} />
    </section>
    </EntityHost>
  )
}

/** Under the story: the reply card while a character waits on the user, Watch's Play / Pause and Next in Watch, and
 *  otherwise the composer. */
interface FootProps { waiting: boolean; active: Mode; reply: () => ReactNode; watch: () => ReactNode; compose: () => ReactNode }

function StoryFoot({ waiting, active, reply, watch, compose }: FootProps) {
  if (waiting) return reply()
  return active === 'watch' ? watch() : compose()
}

function StoryError({ error }: { error: string }) {
  return error ? <div className="story-notice"><Notice tone="error">{error}</Notice></div> : null
}

/** Before a campaign starts: the title screen (./TitleScreen.tsx) until the player begins, then the start form. */
function openingOf(story: StoryData, pending: string | null, begun: boolean): 'title' | 'start' | null {
  if (story.messages.length || pending !== null) return null
  return begun ? 'start' : 'title'
}

/** The + tile on the title screen: the Worlds page, at its world packages, where a new world is added. */
function toPackages() {
  window.history.pushState({ focus: 'world-packages' }, '', '#worlds')
  window.dispatchEvent(new PopStateEvent('popstate'))
}

/** Where and when the story is, and the fight, in one line: the place (which opens the maps to go somewhere else),
 *  the time, and how the character is. The title is for screen readers. */
interface HeaderProps { story: StoryData; change: (request: () => Promise<StoryData>) => Promise<void>; onDraft: (text: string) => void; extra?: ReactNode }

function StoryHeader({ story, change, onDraft, extra }: HeaderProps) {
  const fight = foesText(story.fight)
  return (
    <header className="story-header">
      <h1 id="story-heading" className="visually-hidden">Story</h1>
      <SceneBar scene={story.scene} map={story.map ?? null} line={sceneLine(story.scene, story.fight)} onDraft={onDraft} extra={extra}
        onMove={(body) => change(() => api<StoryData>('/story/scene', body, 'PUT'))} />
      {fight && <p className="story-fight" role="status">{fight}</p>}
    </header>
  )
}

interface SceneProps { scene: StoryScene; map: TravelMap | null; onDraft: (text: string) => void; onMove: (body: { city_id: string; place_id?: string }) => Promise<void>; line?: string[]; extra?: ReactNode }

function SceneBar({ scene, map, onDraft, onMove, line = [], extra }: SceneProps) {
  const [moving, setMoving] = useState(false)
  return (
    <div className="story-scene">
      <div className="story-scene-line">
      <p className="story-where">
        <button type="button" className="story-place" aria-expanded={moving} title={whereText(scene)} onClick={() => setMoving(!moving)}>
          <span className="visually-hidden">{moving ? 'Stay at ' : 'Go somewhere else from '}</span>{capitalized(scene.place.name)}</button>
        {line.map((item) => <span key={item}> · {item}</span>)}
      </p>
      {extra}
      </div>
      {moving && <GoElsewhere scene={scene} map={map} onDone={() => setMoving(false)} onDraft={onDraft} onMove={onMove} />}
    </div>
  )
}

/** "the Felled Oak" leads the line as "The Felled Oak". */
function capitalized(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

interface GoProps extends Omit<SceneProps, 'scene' | 'line' | 'extra'> { scene: StoryScene; onDone: () => void }

/** Going somewhere else, on the maps. A place across town is picked on the street map (./StoryTown.tsx) and is a cut.
 *  Another town, a keep or a hex is picked on the travel map (./StoryMap.tsx) and is a journey: it writes "I set out
 *  for…" into the composer, so the road takes its hours and can bring trouble (adventure/travel.py). A town of this
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
  marks: LineMarks | null; onRetry: () => void; onBack?: (id: string) => void; onBookmark: (id: string, name: string) => Promise<void>
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

function StoryLog({ messages, pending, streamed, turn, bands, marks, onRetry, onBack, onBookmark, onRewrite, onSwitch }: LogProps) {
  const { log, end, onScroll, toEnd, behind } = useFollow(`${messages.length}:${streamed.length}`, pending)
  const last = messages[messages.length - 1]
  const receipts = receiptsByReply(messages)
  return (
    <div className="story-log" aria-live="polite" ref={log} onScroll={onScroll}>
      {messages.map((message) => <Fragment key={message.id}>
        <StoryLine message={message} bands={bands} marks={marks} onBack={pending ? undefined : onBack} onBookmark={pending ? undefined : onBookmark}
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
interface LineProps { message: StoryMessage; bands?: BandStep[] | null; marks?: LineMarks | null; onBack?: (id: string) => void; onBookmark?: (id: string, name: string) => Promise<void>; rewrites?: Rewrites; draft?: string }

function StoryLine({ message, bands, marks, onBack, onBookmark, rewrites, draft }: LineProps) {
  if (message.role === 'scene') return <p className="story-move">{message.text}</p>
  if (message.role === 'user') return <>
    <OpeningLine message={message} />
    <div className="story-turn">
      {message.cards?.map((card, index) => <LifeCard key={index} card={card} />)}
      {message.rolls?.map((roll, index) => <RollCard key={index} roll={roll} bands={bands} />)}
      <div className="story-turn-actions">
        {/* How long the turn took is for tuning, not the story: it waits in a tooltip until the dice log ships. */}
        {message.pace && <span className="story-pace" title={paceText(message.pace)}><Timer aria-hidden="true" /><span className="visually-hidden">{paceText(message.pace)}</span></span>}
        {onBack && <button type="button" className="text-button story-back" onClick={() => onBack(message.id)}
          title="Go back to before this line and send it again, with new dice. The story from here is kept as a branch."><Undo2 aria-hidden="true" />Go back here</button>}
        {onBookmark && <BookmarkButton onSave={(name) => onBookmark(message.id, name)} />}
        <LineTools turnId={message.turn_id} marks={marks} />
      </div>
    </div>
    {message.crisis_help && <CrisisNote />}
  </>
  if (message.status === 'failed') return <Notice tone="error">The narrator could not go on: {message.error}</Notice>
  return <StoryNarration message={message} draft={draft} {...rewrites} />
}

/** A round turn's opening line: the player's own line, the author's nudge, or nothing for a Watch turn. */
function OpeningLine({ message }: { message: StoryMessage }) {
  const kind = openingKind(message)
  if (kind === 'none') return <span id={`line-${message.id}`} />
  return <p className={kind === 'nudge' ? 'story-user story-nudge' : 'story-user'} id={`line-${message.id}`}>
    {kind === 'nudge' && <span className="visually-hidden">{NUDGE.label}: </span>}{message.text}</p>
}

/** Names this moment to find it again (adventure/chapters.py bookmarks). */
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
 * ideas (./ideas.ts), as sending a line does. One box and Send; the rest is in the menu (./StoryMenu.tsx, ⌘K). With no
 * text model yet, Send is `onAddModel`: it opens Settings > Models. */
interface ComposerProps {
  busy: boolean; draft: string; turn: number; onSend: (text: string) => void; onAddModel?: () => void
  /** In Author the line is a nudge to the story (PL-4), and Next with none plays the next turn as it comes; `below`
   *  says under the box whether the last nudge took. */
  nudge?: boolean; below?: ReactNode
  commands: MenuCommand[]; onNewStory: () => void
}

function StoryComposer({ busy, draft, turn, onSend, onAddModel, commands, onNewStory, nudge = false, below }: ComposerProps) {
  const [text, setText] = useState(draft)
  const [found, setFound] = useState<Ideas | null>(null)
  const box = useRef<HTMLTextAreaElement>(null)
  const shown = freshIdeas(found, turn)
  const ready = !busy && (nudge || !!text.trim())
  const words = composerText(nudge, !text.trim())
  const submit = () => { if (ready && !onAddModel) { onSend(text.trim()); setText(''); setFound(null) } }
  const askIdeas = () => { if (!busy) api<Ideas>('/story/ideas', {}).then(setFound, () => setFound(null)) }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit() }
  }
  const run = (command: MenuCommand) => {
    if (command.id === 'ideas') askIdeas()
    else if (command.id === 'note') openAuthorsNote('story')
    else if (command.id === 'step-out') { setText((before) => before.startsWith(OUT_OF_STORY) ? before : OUT_OF_STORY + before); box.current?.focus() }
    else if (command.id === 'new-story') onNewStory()
    else askForDrawer(command.id)
  }
  return (<>
    {shown.length > 0 && <div className="story-ideas" role="group" aria-label="Ideas">
      {shown.map((idea) => <button key={idea} type="button" className="receipt-chip" onClick={() => { setText((before) => withIdea(before, idea)); setFound(null) }}>{idea}</button>)}
    </div>}
    <form className="composer story-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
      <StoryMenu commands={commands} onRun={run} />
      <AuthorsNote chat="story" name="The narrator" story quiet />
      <label className="visually-hidden" htmlFor="story-text">{words.label}</label>
      <textarea ref={box} id="story-text" rows={2} value={text} maxLength={words.max} placeholder={words.placeholder}
        onChange={(event) => setText(event.target.value)} onKeyDown={onKeyDown} />
      {onAddModel
        ? <button type="button" className="button primary" onClick={onAddModel}>Add a model</button>
        : <button type="submit" className="button primary" disabled={!ready}><Send aria-hidden="true" />{words.send}</button>}
    </form>
    {below}
    <AiFooter />
  </>)
}

function NewStory({ open, onClose, onClear }: { open: boolean; onClose: () => void; onClear: () => Promise<void> }) {
  if (!open) return null
  return (
    <ConfirmDialog title="Start a new story?" onClose={onClose} actions={<>
      <button type="button" className="button" onClick={onClose}>Cancel</button>
      <button type="button" className="button primary" onClick={() => void onClear().then(onClose)}>Start a new story</button>
    </>}>
      <p>The story so far and the people you&apos;ve met in it are cleared for good. You stay where you are.</p>
    </ConfirmDialog>
  )
}
