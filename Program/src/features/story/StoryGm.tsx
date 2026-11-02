import { type ReactNode, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { FeelingAxis, GmView } from '../../types'
import { Notice } from '../../components/Feedback'

const GM_KEY = ['story-gm']
const AXES: FeelingAxis[] = ['trust', 'affection', 'respect', 'fear', 'desire']
const RANGE: Record<FeelingAxis, [number, number]> = { trust: [-5, 5], affection: [-5, 5], respect: [-5, 5], fear: [0, 5], desire: [0, 5] }

function Section({ label, title, shown, children }: { label: string; title: string; shown: boolean; children: ReactNode }) {
  if (!shown) return null
  return <section aria-label={label}><h3>{title}</h3><ul>{children}</ul></section>
}

const SEED_STATES: Record<string, string> = { planted: 'planted, not yet on the page', reached: 'on the page', asked: 'asked to come back', paid: 'paid off', retired: 'retired' }

interface PlanningProps { seeds: GmView['seeds']; plans: GmView['plans']; arcs: GmView['arcs']; change: (request: () => Promise<GmView>) => Promise<void> }

/** Planning with the director (dungeon/plotting.py): the seeds planted and where each stands, to cash in or retire,
 * and each arc's planned beats for its stage, to cut or move up. */
function Planning({ seeds, plans, arcs, change }: PlanningProps) {
  const title = (arcId: string | null) => arcs.find((arc) => arc.id === arcId)?.title ?? 'No arc'
  return <>
    <Section label="Seeds" title="Seeds and payoffs" shown={!!seeds.length}>
      {seeds.map((seed) => <li key={seed.id}>
        <p><strong>{seed.text}</strong> <span className="subtle">{title(seed.arc_id)} · {SEED_STATES[seed.status]}</span></p>
        <p className="story-note">{seed.truth}</p>
        {seed.status !== 'paid' && <div className="form-actions">
          <button type="button" className="text-button" onClick={() => void change(() => api<GmView>(`/story/gm/seeds/${seed.id}/cash-in`, {}))}>Bring it back next</button>
          {seed.status !== 'retired' && <button type="button" className="text-button" onClick={() => void change(() => api<GmView>(`/story/gm/seeds/${seed.id}/retire`, {}))}>Retire</button>}
        </div>}
      </li>)}
    </Section>
    <Section label="Planned beats" title="Planned beats" shown={plans.some((plan) => plan.beats.length)}>
      {plans.filter((plan) => plan.beats.length).map((plan) => <li key={plan.arc_id}>
        <p><strong>{title(plan.arc_id)}</strong> <span className="subtle">stage {plan.stage + 1}</span></p>
        <ol>{plan.beats.map((beat, index) => <li key={beat.id}>
          <span className={beat.cut ? 'subtle' : undefined}>{beat.cut ? <s>{beat.text}</s> : beat.text}</span>{beat.used && <span className="subtle"> · used</span>}
          <div className="form-actions">
            <button type="button" className="text-button" onClick={() => void change(() => api<GmView>(`/story/gm/beats/${beat.id}`, { cut: !beat.cut }, 'PATCH'))}>{beat.cut ? 'Bring back' : 'Cut'}</button>
            {index > 0 && <button type="button" className="text-button" onClick={() => void change(() => api<GmView>(`/story/gm/beats/${beat.id}`, { position: index - 1 }, 'PATCH'))}>Move up</button>}
          </div>
        </li>)}</ol>
      </li>)}
    </Section>
  </>
}

/** Behind the story (dungeon/gm.py), while the GM view is on: quests and their truths, how people feel, the
 * director's arcs, threads and nemeses, the factions, the dark tracks, and every correction made to the record. */
export function StoryGm() {
  const client = useQueryClient()
  const gm = useQuery({ queryKey: GM_KEY, queryFn: () => api<GmView>('/story/gm') })
  const [error, setError] = useState('')
  const change = async (request: () => Promise<GmView>) => {
    setError('')
    try { client.setQueryData(GM_KEY, await request()) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  if (gm.isError) return <Notice tone="error">{gm.error instanceof Error ? gm.error.message : 'The GM view did not load.'}</Notice>
  if (!gm.data) return null
  const { quests, people, arcs, threads, nemeses, factions, dark, corrections, seeds = [], plans = [] } = gm.data
  return (
    <details className="story-gm">
      <summary>Behind the story</summary>
      <Section label="Quests and their truths" title="Quests" shown={!!quests.length}>
        {quests.map((quest) => <li key={quest.id}><p><strong>{quest.title}</strong> <span className="subtle">{quest.status}{quest.known ? '' : ' · not yet known'}</span></p>
          {quest.truth && <p className="story-note">{quest.truth}</p>}</li>)}
      </Section>
      <Section label="The director's arcs" title="Arcs" shown={!!arcs.length}>
        {arcs.map((arc) => <li key={arc.id}><p><strong>{arc.title}</strong> <span className="subtle">stage {arc.stage + 1} of {arc.stages}{arc.antagonist && ` · ${arc.antagonist}`}</span></p>
          {arc.truth && <p className="story-note">{arc.truth}</p>}</li>)}
      </Section>
      <Section label="Threads" title="Threads" shown={!!threads.length}>
        {threads.map((thread) => <li key={thread.id}><p><strong>{thread.title}</strong> <span className="subtle">{thread.kind} · heat {thread.heat}{thread.known ? '' : ' · unseen'}</span></p>
          {thread.truth && <p className="story-note">{thread.truth}</p>}</li>)}
      </Section>
      <Section label="Nemeses" title="Nemeses" shown={!!nemeses.length}>
        {nemeses.map((nemesis) => <li key={nemesis.name}><p><strong>{nemesis.name}</strong> <span className="subtle">{nemesis.status} · remembers your {nemesis.remembers}</span></p><p className="story-note">{nemesis.grudge}</p></li>)}
      </Section>
      <Section label="How people feel" title="How people feel" shown={!!people.length}>
        {people.map((person) => <li key={person.key}>
          <p><strong>{person.name}</strong></p>
          <div className="story-gm-axes">
            {AXES.map((axis) => <label key={axis}>{axis}
              <input type="number" min={RANGE[axis][0]} max={RANGE[axis][1]} value={person.feelings[axis]}
                onChange={(event) => void change(() => api<GmView>(`/story/gm/people/${encodeURIComponent(person.key)}`, { [axis]: Number(event.target.value) }, 'PATCH'))} />
            </label>)}
          </div>
          {!!person.impressions.length && <p className="story-note">{person.impressions.join(' · ')}</p>}
        </li>)}
      </Section>
      <Section label="Factions" title="Factions" shown={!!factions.length}>
        {factions.map((faction) => <li key={faction.faction_id}><label>{faction.faction_id}{' '}
          <input type="number" min={-5} max={5} value={faction.value}
            onChange={(event) => void change(() => api<GmView>(`/story/gm/factions/${encodeURIComponent(faction.faction_id)}`, { value: Number(event.target.value) }, 'PUT'))} />
        </label></li>)}
      </Section>
      <Section label="Dark tracks" title="Dark tracks" shown={!!dark.length}>
        {dark.map((track) => <li key={track.id}>{track.name}: {track.word}{track.points !== undefined && ` (${track.points} of ${track.top})`}</li>)}
      </Section>
      <Section label="Corrections to the record" title="Corrections" shown={!!corrections.length}>
        {corrections.map((item, index) => <li key={index}><p className="subtle">{item.subject ?? 'A fact'}</p>
          <p><s>{item.before}</s> {item.after ?? '(removed)'}</p></li>)}
      </Section>
      <Planning seeds={seeds} plans={plans} arcs={arcs} change={change} />
      {error && <Notice tone="error">{error}</Notice>}
    </details>
  )
}
