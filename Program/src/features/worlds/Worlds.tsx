import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Globe, Plus, Trash2, Upload, UserRound, UserRoundPlus } from 'lucide-react'
import { api, upload } from '../../api'
import type { Persona, World, Worlds as WorldsData } from '../../types'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { PersonaForm } from './PersonaForm'
import { Cities } from '../world/Cities'
import { WorldPackages } from './WorldPackages'
import { WorldLibrary, WorldLore } from './WorldLore'
import { AdultSideSettings } from '../settings/HiddenValues'
import { TownsfolkMix } from '../settings/TownsfolkMix'
import { CityPick, SOMEWHERE_NEW } from './CityPick'
import { enter, useWorlds, WORLDS_KEY } from './useWorlds'
import { homeLine, initial, personaName, personaRef, personaTitle } from './worldsText'

type Run = (action: () => Promise<unknown>) => Promise<void>

/** Worlds and personas: who the user is, the worlds each persona lives in, and switching between them. */
export function Worlds() {
  const worlds = useWorlds()
  const client = useQueryClient()
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [making, setMaking] = useState(false)
  const run: Run = async (action) => {
    if (busy) return
    setError('')
    try { await action() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work. Try again.') } finally { setBusy('') }
  }
  const switchTo = (path: string, label: string) => { setBusy(label); return run(async () => { await api(path, {}); enter() }) }
  const store = (data: WorldsData) => client.setQueryData(WORLDS_KEY, data)
  const loaded = !!worlds.data
  useEffect(() => { if (loaded && window.history.state?.focus === 'persona-home') toHomeCity() }, [loaded])
  if (worlds.isPending) return <Loading label="Loading your worlds" />
  if (worlds.isError) return <ErrorNotice error={worlds.error} />
  const data = worlds.data
  return (
    <section className="worlds" aria-labelledby="worlds-heading">
      <header className="worlds-header">
        <h1 id="worlds-heading">Worlds</h1>
        <p className="subtle">{personaName(data.persona) ? <>You are <strong>{personaName(data.persona)}</strong> in </> : <>You're in </>}<strong>{data.world.name}</strong>. Each persona lives in their own worlds, with their own town, people and history. Your settings and models come with you everywhere.</p>
        {busy && <Notice>Opening {busy}…</Notice>}
        {error && <Notice tone="error">{error}</Notice>}
      </header>
      <div className="worlds-list">
        {data.personas.map((persona) => (
          <PersonaWorlds key={persona.id} persona={persona} cityId={data.world.city_id} run={run} store={store}
            onSwitch={(world) => void switchTo(`/worlds/${world.id}/switch`, world.name)}
            onSwitchPersona={() => void switchTo(`/worlds/personas/${persona.id}/switch`, personaRef(persona))} />
        ))}
        {making
          ? <PersonaForm cityId={data.world.city_id} kinds={data.persona.kind_shown} onCancel={() => setMaking(false)} onSaved={() => { setMaking(false); void client.invalidateQueries({ queryKey: WORLDS_KEY }) }} />
          : <div className="form-actions">
              <button type="button" className="button" onClick={() => setMaking(true)}><UserRoundPlus aria-hidden="true" />New persona</button>
              <ImportCampaign run={run} store={store} />
            </div>}
        <div id="persona-edit"><PersonaForm key={`${data.persona.id}:${data.world.id}`} persona={data.persona} world={data.world} cityId={data.world.city_id} onSaved={(saved) => { if (saved) store(saved) }} /></div>
      </div>
      {/* What the world is made of: its cities and the people it generates. Settings keeps only what belongs to this
          computer and the user's accounts (src/features/settings/sections.ts). */}
      <section className="worlds-makeup" aria-labelledby="world-makeup-heading">
        <h2 id="world-makeup-heading">What {data.world.name} is made of</h2>
        <Cities />
        <WorldPackages />
        <WorldLore />
        <WorldLibrary />
        <AdultSideSettings />
        <TownsfolkMix />
      </section>
    </section>
  )
}

/** Where you live, on the persona form (opened from "Change your home city" on the Character page). */
function toHomeCity() {
  const field = document.querySelector<HTMLSelectElement>('#persona-edit .persona-home select')
  field?.scrollIntoView({ block: 'center' })
  field?.focus()
}

/** The edit form for the persona the user is now, at the end of the page: go there with its name box ready. */
function addName() {
  const field = document.querySelector<HTMLInputElement>('#persona-edit input')
  field?.scrollIntoView({ block: 'center' })
  field?.focus()
}

interface PersonaWorldsProps { persona: Persona; cityId: string; run: Run; store: (data: WorldsData) => void; onSwitch: (world: World) => void; onSwitchPersona: () => void }

function PersonaWorlds({ persona, cityId, run, store, onSwitch, onSwitchPersona }: PersonaWorldsProps) {
  const [deleting, setDeleting] = useState(false)
  const [adding, setAdding] = useState(false)
  const addLink = useRef<HTMLButtonElement>(null)
  // Closing the new-world form puts focus back on the link that opened it.
  const closeAdding = () => { setAdding(false); requestAnimationFrame(() => addLink.current?.focus()) }
  const removable = !persona.active && persona.worlds.every((world) => !world.first)
  return (
    <section className="persona-worlds" aria-label={personaTitle(persona)}>
      <PersonaRow persona={persona} onSwitchPersona={onSwitchPersona} onDelete={removable ? () => setDeleting(true) : undefined} />
      <ul className="world-rows">
        {persona.worlds.map((world) => <WorldRow key={world.id} world={world} run={run} store={store} onSwitch={() => onSwitch(world)} />)}
      </ul>
      {adding
        ? <NewWorld persona={persona} cityId={cityId} run={run} onDone={closeAdding} />
        : <button ref={addLink} type="button" className="text-button" onClick={() => setAdding(true)}><Plus aria-hidden="true" />New world for {personaRef(persona)}</button>}
      {deleting && <ConfirmDialog title={`Delete ${personaRef(persona)}?`} onClose={() => setDeleting(false)} actions={<>
        <button type="button" className="button" onClick={() => setDeleting(false)}>Keep</button>
        <button type="button" className="button danger" onClick={() => void run(async () => { store(await api<WorldsData>(`/worlds/personas/${persona.id}`, undefined, 'DELETE')); setDeleting(false) })}>Delete</button>
      </>}>
        <p>Their {persona.worlds.length === 1 ? 'world goes' : `${persona.worlds.length} worlds go`} with them, with everything that happened in it. A backup of each is kept in the data folder, under backups/deleted-worlds.</p>
      </ConfirmDialog>}
    </section>
  )
}

/** Where the persona's new world is: somewhere new the app picks unless the user picks a city. */
function NewWorld({ persona, cityId, run, onDone }: { persona: Persona; cityId: string; run: Run; onDone: () => void }) {
  const client = useQueryClient()
  const [city, setCity] = useState(SOMEWHERE_NEW)
  const [making, setMaking] = useState(false)
  const make = () => { setMaking(true); return run(async () => {
    await api('/worlds', { persona_id: persona.id, city_id: city })
    await client.invalidateQueries({ queryKey: WORLDS_KEY })
    onDone()
  }).finally(() => setMaking(false)) }
  return (
    <form className="new-world form-stack" aria-label={`New world for ${personaRef(persona)}`} onSubmit={(event) => { event.preventDefault(); void make() }}
      onKeyDown={(event) => { if (event.key === 'Escape' && !making) onDone() }}>
      <CityPick value={city} currentId={cityId} disabled={making} autoFocus onChange={setCity} />
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={making}>{making ? 'Making the world…' : 'Make this world'}</button>
        <button type="button" className="text-button" disabled={making} onClick={onDone}>Cancel</button>
      </div>
    </form>
  )
}

function PersonaRow({ persona, onSwitchPersona, onDelete }: { persona: Persona; onSwitchPersona: () => void; onDelete?: () => void }) {
  const name = personaName(persona)
  return (
    <div className="persona-row">
      <span className="portrait persona-initial" aria-hidden="true">{initial(persona) || <UserRound size={18} />}</span>
      <h2>{personaTitle(persona)}{persona.active && <span className="subtle"> (you, now)</span>}</h2>
      {persona.active && !name && <button type="button" className="text-button" onClick={addName}>Add a name</button>}
      {!persona.active && <button type="button" className="button" onClick={onSwitchPersona}>{name ? `Be ${name}` : 'Switch to this persona'}</button>}
      {onDelete && <button type="button" className="text-button" onClick={onDelete}><Trash2 aria-hidden="true" />Delete</button>}
    </div>
  )
}

function WorldRow({ world, run, store, onSwitch }: { world: World; run: Run; store: (data: WorldsData) => void; onSwitch: () => void }) {
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(world.name)
  const [deleting, setDeleting] = useState(false)
  const rename = () => run(async () => { store(await api<WorldsData>(`/worlds/${world.id}`, { name }, 'PATCH')); setRenaming(false) })
  return (
    <li className="world-row" aria-current={world.active ? 'true' : undefined}>
      <span className="portrait" aria-hidden="true"><Globe /></span>
      {renaming
        ? <form className="world-rename" onSubmit={(event) => { event.preventDefault(); void rename() }}>
            <label className="visually-hidden" htmlFor={`world-name-${world.id}`}>World name</label>
            <input id={`world-name-${world.id}`} value={name} maxLength={80} required onChange={(event) => setName(event.target.value)} />
            <button type="submit" className="button">Save</button>
            <button type="button" className="text-button" onClick={() => { setRenaming(false); setName(world.name) }}>Cancel</button>
          </form>
        : <span className="world-row-text"><strong>{world.name}</strong><span className="subtle">{homeLine(world)}</span></span>}
      <span className="world-row-actions">
        {world.active ? <span className="subtle">You are here</span> : <button type="button" className="button" onClick={onSwitch}>Go there</button>}
        {!renaming && <button type="button" className="text-button" onClick={() => setRenaming(true)}>Rename</button>}
        {!world.active && !world.first && <button type="button" className="text-button" aria-label={`Delete ${world.name}`} onClick={() => setDeleting(true)}><Trash2 aria-hidden="true" /></button>}
      </span>
      {deleting && <ConfirmDialog title={`Delete ${world.name}?`} onClose={() => setDeleting(false)} actions={<>
        <button type="button" className="button" onClick={() => setDeleting(false)}>Keep it</button>
        <button type="button" className="button danger" onClick={() => void run(async () => { store(await api<WorldsData>(`/worlds/${world.id}`, undefined, 'DELETE')); setDeleting(false) })}>Delete</button>
      </>}>
        <p>Everything that happened there goes with it. A backup is kept in the data folder, under backups/deleted-worlds.</p>
      </ConfirmDialog>}
    </li>
  )
}

/** A campaign file (Story > Export) from here or another machine, as a new world (dungeon/legacy.py). */
function ImportCampaign({ run, store }: { run: Run; store: (data: WorldsData) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const chosen = (file: File | undefined) => { if (file) void run(async () => { store(await upload<WorldsData>('/worlds/import', file)) }) }
  return <>
    <button type="button" className="button" onClick={() => input.current?.click()}><Upload aria-hidden="true" />Import a campaign file</button>
    <input ref={input} type="file" accept=".zip,application/zip" hidden aria-label="A campaign file"
      onChange={(event) => { chosen(event.target.files?.[0]); event.target.value = '' }} />
  </>
}
