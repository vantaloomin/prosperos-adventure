import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Image, MapPin, RefreshCw, User, Users } from 'lucide-react'
import { api } from '../../api'
import { Notice } from '../../components/Feedback'
import type { ArtKind, ArtStage, StoryArt as Picture, StoryPerson } from '../../types'
import { useDeviceLook } from '../settings/deviceLook'
import { artLabel, artStatus, making, pictureChoices } from './artText'
import { askForDrawer } from './scene'

const ART_KEY = ['story-art']
// Passive art finishes after the turn, so the stage looks again now and then.
const STAGE_REFRESH = 20_000
// A default backdrop is a daytime picture: dawn and dusk warm it, and night darkens one with no night picture of its own.
const TINTS: Record<string, string> = {
  day: '',
  dawn: 'linear-gradient(rgba(255, 170, 140, 0.18), rgba(90, 70, 120, 0.22))',
  dusk: 'linear-gradient(rgba(255, 140, 60, 0.2), rgba(60, 30, 80, 0.32))',
  night: 'linear-gradient(rgba(8, 14, 40, 0.58), rgba(8, 14, 40, 0.66))',
}

/** Pictures on request (dungeon/art.py): you, someone you met, this place, or the whole scene. Each is built from what
 *  the game tracks and made by the image backends in Settings; one goes out of date when what it shows changes. */
export function StoryArt({ people, present = [], place, open }: { people: StoryPerson[]; present?: { key: string; label: string }[]; place: { key: string; name: string }; open?: boolean }) {
  const client = useQueryClient()
  const gallery = useQuery({ queryKey: ART_KEY, queryFn: () => api<{ art: Picture[] }>('/story/art'),
    refetchInterval: (query) => making(query.state.data?.art ?? []) ? 2000 : false })
  const [who, setWho] = useState('')
  const [error, setError] = useState('')
  const ask = async (kind: ArtKind, subject = '') => {
    setError('')
    try { client.setQueryData(ART_KEY, await api<{ art: Picture[] }>('/story/art', { kind, subject })) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That picture was not asked for.') }
  }
  const items = gallery.data?.art ?? []
  const choices = pictureChoices(people, present)
  return (
    <details className="story-people story-art" open={open}>
      <summary>Pictures ({items.filter((item) => item.url).length})</summary>
      <div className="form-actions">
        <button type="button" className="button" onClick={() => void ask('portrait', 'player')}><User aria-hidden="true" />Picture me</button>
        <button type="button" className="button" onClick={() => void ask('place')}><MapPin aria-hidden="true" />This place</button>
        <button type="button" className="button" onClick={() => void ask('scene')}><Image aria-hidden="true" />The scene</button>
      </div>
      {choices.length > 0 && <div className="form-actions">
        <select aria-label="Someone here or someone you met" value={who} onChange={(event) => setWho(event.target.value)}>
          <option value="">Someone here or someone you met…</option>
          {choices.map((choice) => <option key={choice.key} value={choice.key}>{choice.label}</option>)}
        </select>
        <button type="button" className="button" disabled={!who} onClick={() => void ask('portrait', who)}><Users aria-hidden="true" />Picture them</button>
      </div>}
      {error && <Notice tone="error">{error}</Notice>}
      <ul className="art-gallery">
        {items.map((item) => <ArtCard key={item.id} item={item} label={artLabel(item, people, item.subject === place.key ? place.name : '')}
          onAgain={() => void ask(item.kind, item.kind === 'portrait' || item.kind === 'passage' ? item.subject : '')} />)}
      </ul>
    </details>
  )
}

function ArtCard({ item, label, onAgain }: { item: Picture; label: string; onAgain: () => void }) {
  const status = artStatus(item)
  return (
    <li className="art-card">
      {item.url && <img src={item.url} alt={label} loading="lazy" width={item.width ?? undefined} height={item.height ?? undefined} />}
      <p><strong>{label}</strong>{item.reference && <span className="subtle"> · their likeness</span>}</p>
      {status && <p className={item.status === 'failed' || item.status === 'refused' ? 'hidden-warning' : 'subtle'}>{status}</p>}
      {(item.stale || item.status === 'failed') && <button type="button" className="text-button" onClick={onAgain}><RefreshCw aria-hidden="true" />Make it again</button>}
    </li>
  )
}

/** Pictures a passage of the story, then opens Pictures to show it. */
export function IllustrateButton({ messageId }: { messageId: string }) {
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const illustrate = async () => {
    setBusy(true)
    try { client.setQueryData(ART_KEY, await api<{ art: Picture[] }>('/story/art', { kind: 'passage', subject: messageId })) }
    finally { setBusy(false); askForDrawer('art') }
  }
  return <button type="button" className="text-button story-back" disabled={busy} onClick={() => void illustrate()}
    title="Make a picture of this passage with your image backend."><Image aria-hidden="true" />{busy ? 'Picturing…' : 'Picture this'}</button>
}

/** The stage over the story (VN style): the place's picture behind (a made one, else the world's default backdrop),
 *  the portraits of who is here in front. Shown only when there is a picture, and only when this device has "Show
 *  pictures on the story" on. In the Visual novel layout the picture fills the story column and the portraits stand on its own row above the text box
 *  (styles.css `data-layout='novel'`), so they come apart. */
export function StoryStage({ turn }: { turn: string }) {
  const look = useDeviceLook()
  const stage = useQuery({ queryKey: [...ART_KEY, 'stage', turn], queryFn: () => api<ArtStage>('/story/art/stage'),
    enabled: look.stageArt, refetchInterval: STAGE_REFRESH })
  const shown = look.stageArt ? stage.data : undefined
  if (!shown || (!shown.background && !shown.portraits.length)) return null
  const portraits = <StagePortraits portraits={shown.portraits} />
  return <>
    <figure className="story-stage" style={shown.background ? { backgroundImage: [TINTS[shown.background.light ?? 'day'], `url(${shown.background.url})`].filter(Boolean).join(', ') } : undefined}>
      {look.layout !== 'novel' && portraits}
      {shown.background && <figcaption className="visually-hidden">A picture of this place</figcaption>}
    </figure>
    {look.layout === 'novel' && portraits}
  </>
}

function StagePortraits({ portraits }: { portraits: ArtStage['portraits'] }) {
  return (
    <ul className="stage-portraits" aria-label="Who is here">
      {portraits.map((item) => <li key={item.key}>
        <img src={item.url} alt={`Portrait of ${item.name}`} width={item.width ?? undefined} height={item.height ?? undefined} />
        <span>{item.name}</span>
      </li>)}
    </ul>
  )
}
