import { reducedMotion } from '../../motion'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Download, FilePlus2, FolderSync, Pencil, Search, Trash2, Upload } from 'lucide-react'
import { api } from '../../api'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { TextInput } from '../../components/Fields'
import { shownPath } from '../../paths'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { isWorldMap, readWorldMap } from './worldMap'
import { useWorlds } from '../worlds/useWorlds'
import { citiesOfWorld, cityFacts, definitionOf, exportName, groupNotes, matchesCity, parseDefinition, shelveCities, slugify, type BrokenCity, type CityCategory, type CityListing, type FeaturedCities, type PackReport } from './cityText'

const CITIES_KEY = ['cities']
const BROKEN_KEY = ['broken-cities']
// `notes` lists what the server mended or added when it loaded a city (dungeon/world/mend.py).
type Feedback = { tone: 'info' | 'error'; text: string; notes?: string[] } | null
// What the editor is working on: a new city (from the template, a file or a copy) or one of the user's own.
type Editing = { mode: 'create'; text: string } | { mode: 'update'; id: string; revision: number; text: string }

const pretty = (value: unknown) => JSON.stringify(value, null, 1)

function FeedbackNotice({ feedback }: { feedback: NonNullable<Feedback> }) {
  return (
    <Notice tone={feedback.tone}>
      {feedback.text}
      {feedback.notes && feedback.notes.length > 0 && <>
        {' '}Along the way:
        <CityNotes notes={feedback.notes} />
      </>}
    </Notice>
  )
}

/** A long list scrolls in its own box, so its bottom edge fades while more is below, like the city chips' right edge. */
function CityNotes({ notes }: { notes: string[] }) {
  const box = useRef<HTMLUListElement>(null)
  const [more, setMore] = useState(false)
  const check = useCallback(() => {
    const list = box.current
    if (list) setMore(list.scrollTop + list.clientHeight < list.scrollHeight - 2)
  }, [])
  useEffect(() => {
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [check, notes])
  return <ul ref={box} className={`city-notes${more ? ' more-below' : ''}`} onScroll={check}>{groupNotes(notes).map((note) => <li key={note}>{note}</li>)}</ul>
}

function saveFile(id: string, definition: unknown) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([pretty(definition)], { type: 'application/json' }))
  link.download = exportName(id)
  link.click()
  URL.revokeObjectURL(link.href)
}

/** Build, import, copy, edit and export cities (PRD W5). Built-in and pack cities are read-only here. */
export function Cities() {
  const client = useQueryClient()
  const cities = useQuery({ queryKey: CITIES_KEY, queryFn: () => api<CityListing[]>('/world/cities') })
  const featured = useQuery({ queryKey: ['featured-cities'], queryFn: () => api<FeaturedCities>('/world/featured') })
  const worlds = useWorlds()
  const broken = useQuery({ queryKey: BROKEN_KEY, queryFn: () => api<BrokenCity[]>('/world/broken-cities') })
  const [feedback, setFeedback] = useState<Feedback>(null)
  const [editing, setEditing] = useState<Editing | null>(null)
  const [copying, setCopying] = useState<CityListing | null>(null)
  const [deleting, setDeleting] = useState<Pick<CityListing, 'id' | 'name'> | null>(null)
  const file = useRef<HTMLInputElement>(null)
  const refresh = () => Promise.all([client.invalidateQueries({ queryKey: CITIES_KEY }), client.invalidateQueries({ queryKey: BROKEN_KEY })])
  const fail = (error: unknown) => setFeedback({ tone: 'error', text: error instanceof Error ? error.message : 'That did not work.' })

  const startNew = async () => {
    try { setEditing({ mode: 'create', text: pretty(await api('/world/template')) }); setFeedback(null) } catch (error) { fail(error) }
  }
  const startEdit = async (city: CityListing) => {
    try {
      const data = await api<Record<string, unknown> & { revision: number }>(`/world/cities/${city.id}`)
      setEditing({ mode: 'update', id: city.id, revision: data.revision, text: pretty(definitionOf(data)) })
      setFeedback(null)
    } catch (error) { fail(error) }
  }
  const importFile = async (chosen: File | undefined) => {
    if (!chosen) return
    if (isWorldMap(chosen.name, await chosen.slice(0, 4096).text())) { await importWorldMap(chosen); return }
    setEditing({ mode: 'create', text: await chosen.text() })
    setFeedback({ tone: 'info', text: `Opened ${chosen.name}. Check it, change the id if you need to, then save it as one of your cities.` })
    if (file.current) file.current.value = ''
  }
  // A Marinara world map becomes a city and world lore straight away, with no editor step (dungeon/world/marinara.py).
  const importWorldMap = async (chosen: File) => {
    setEditing(null)
    setFeedback({ tone: 'info', text: `Reading the world map ${chosen.name}…` })
    if (file.current) file.current.value = ''
    try {
      const made = await api<CityListing & { book: { name: string; entries: number } | null }>('/world/import/marinara', await readWorldMap(chosen))
      const lore = made.book ? ` Its places' notes are world lore in "${made.book.name}".` : ''
      setFeedback({ tone: 'info', text: `${made.name} is here, under Custom.${lore}`, notes: made.import_notes })
      void client.invalidateQueries({ queryKey: ['lore'] })
    } catch (error) { fail(error) } finally { void refresh() }
  }
  const exportCity = async (city: CityListing) => {
    try { saveFile(city.id, definitionOf(await api<Record<string, unknown>>(`/world/cities/${city.id}`))) } catch (error) { fail(error) }
  }
  const remove = async (city: Pick<CityListing, 'id' | 'name'>) => {
    setDeleting(null)
    try {
      await api(`/world/cities/${city.id}`, undefined, 'DELETE')
      setFeedback({ tone: 'info', text: `Deleted ${city.name}.` })
    } catch (error) { fail(error) } finally { void refresh() }
  }

  return (
    <section className="settings-section form-stack" aria-labelledby="cities-heading">
      <div>
        <h2 id="cities-heading">Cities</h2>
        <p className="subtle">A story's town is built from its city: its neighborhoods, places, work and weather. Start a city of your own, copy one to change it, or open a city file someone shared. A Marinara world map opens as a city straight away, with its places' notes as world lore.</p>
      </div>
      <div className="form-actions">
        <button type="button" className="button" onClick={() => void startNew()}><FilePlus2 aria-hidden="true" />New city</button>
        <button type="button" className="button" onClick={() => file.current?.click()}><Upload aria-hidden="true" />Open a city file</button>
        <input ref={file} type="file" accept=".json,application/json" hidden onChange={(event) => void importFile(event.target.files?.[0])} />
      </div>
      <div aria-live="polite">{feedback && <FeedbackNotice feedback={feedback} />}</div>
      {editing && <CityEditor editing={editing} onClose={() => setEditing(null)}
        onSaved={(saved) => { setEditing(null); setFeedback({ tone: 'info', text: `Saved ${saved.name}.`, notes: saved.import_notes }); void refresh() }} />}
      {cities.isPending && <Loading label="Loading cities" />}
      {cities.isError && <ErrorNotice error={cities.error} />}
      {broken.data?.map((city) => (
        <Notice key={city.id} tone="error" action={<span className="person-actions">
          <button type="button" className="text-button" onClick={() => saveFile(city.id, city.definition)}><Download aria-hidden="true" />Save as file</button>
          <button type="button" className="text-button" onClick={() => setDeleting(city)}><Trash2 aria-hidden="true" />Delete</button>
        </span>}>
          Your city {city.name} no longer loads, so it is left out of every list. {city.error} Save it as a file, fix it, delete it here, then open the fixed file.
        </Notice>
      ))}
      {cities.data && <CityShelves cities={cities.data} home={worlds.data?.world.city_id} featured={featured.data} actions={(city) => <>
        {city.origin === 'user' && <button type="button" className="text-button" onClick={() => void startEdit(city)}><Pencil aria-hidden="true" />Edit</button>}
        <button type="button" className="text-button" onClick={() => setCopying(city)}><Copy aria-hidden="true" />Copy</button>
        {city.distribution === 'public' && <button type="button" className="text-button" onClick={() => void exportCity(city)}><Download aria-hidden="true" />Save as file</button>}
        {city.origin === 'user' && <button type="button" className="text-button" onClick={() => setDeleting(city)}><Trash2 aria-hidden="true" />Delete</button>}
      </>} />}
      <Packs onReloaded={() => void refresh()} />
      {copying && <CopyDialog city={copying} onClose={() => setCopying(null)}
        onCopied={(name) => { setCopying(null); setFeedback({ tone: 'info', text: `Copied as ${name}. It is under Custom.` }); void refresh() }} />}
      {deleting && (
        <ConfirmDialog title={`Delete ${deleting.name}?`} onClose={() => setDeleting(null)} actions={<>
          <button type="button" className="button" onClick={() => setDeleting(null)}>Cancel</button>
          <button type="button" className="button danger" onClick={() => void remove(deleting)}>Delete</button>
        </>}>
          <p>The city is removed from this workspace. Events that already happened there keep their wording, and backups made before keep the city. If you live there, move first.</p>
        </ConfirmDialog>
      )}
    </section>
  )
}

interface ShelvesProps { cities: CityListing[]; home?: string; featured?: FeaturedCities; actions: (city: CityListing) => ReactNode }

/** The city list: the open world's cities (every world's on request), a filter chip per shelf with its count, a
 * search box, then a headed section per shelf (PRD W5). */
function CityShelves({ cities: every, home, featured, actions }: ShelvesProps) {
  const [shown, setShown] = useState<CityCategory | 'all'>('all')
  const [query, setQuery] = useState('')
  const [everywhere, setEverywhere] = useState(false)
  const own = citiesOfWorld(every, home)
  const cities = everywhere ? every : own
  const shelves = shelveCities(cities)
  const found = shelves.map((shelf) => ({ ...shelf, cities: shelf.cities.filter((city) => matchesCity(city, query)) }))
    .filter((shelf) => shown === 'all' || shelf.id === shown)
  const searching = query.trim().length > 0
  const total = found.reduce((sum, shelf) => sum + shelf.cities.length, 0)
  const chip = (id: CityCategory | 'all', title: string, count: number) => (
    <button key={id} type="button" className="vibe-pick" aria-pressed={shown === id} onClick={() => setShown(id)}>{title} <span className="subtle">{count}</span></button>
  )
  return (<>
    <WorldScope others={every.length - own.length} worldName={every.find((city) => city.id === home)?.world_name} everywhere={everywhere} onToggle={() => setEverywhere(!everywhere)} />
    {shown === 'all' && !searching && <FeaturedStrip featured={everywhere ? featured : undefined} />}
    <div className="city-filters">
      <div className="vibe-picks city-chips" role="group" aria-label="Show cities">
        {chip('all', 'All', cities.length)}
        {shelves.map((shelf) => chip(shelf.id, shelf.title, shelf.cities.length))}
      </div>
      <div className="search-field">
        <Search aria-hidden="true" />
        <label className="visually-hidden" htmlFor="city-search">Find a city</label>
        <input id="city-search" type="search" placeholder="Find a city" value={query} onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Escape') setQuery('') }} />
      </div>
    </div>
    <p className="visually-hidden" aria-live="polite">{searching ? `${total} ${total === 1 ? 'city' : 'cities'} found` : ''}</p>
    {searching && total === 0 && <p className="subtle">No cities match “{query.trim()}”.</p>}
    {found.filter((shelf) => shelf.cities.length > 0 || (shelf.id === 'custom' && !searching)).map((shelf) => (
      <div key={shelf.id} className="city-group">
        <h3>{shelf.title}</h3>
        {shelf.cities.length === 0 && <p className="subtle">None yet. New city or Copy makes one.</p>}
        <ul className="city-list">
          {shelf.cities.map((city) => (
            <li key={city.id} id={`city-${city.id}`} tabIndex={-1} className="city-card">
              <header>
                <h4>{city.name}{city.origin === 'pack' && <span className="badge">Pack</span>}{city.distribution === 'private' && <span className="badge">Private</span>}</h4>
                <p className="subtle">{[city.region, city.country].filter(Boolean).join(', ')} · {cityFacts(city)}</p>
              </header>
              <p>{city.summary}</p>
              <div className="person-actions">{actions(city)}</div>
            </li>
          ))}
        </ul>
      </div>
    ))}
  </>)
}

/** Whose cities the list shows, with a switch to every world's; nothing when no other world has any. */
function WorldScope({ others, worldName, everywhere, onToggle }: { others: number; worldName?: string | null; everywhere: boolean; onToggle: () => void }) {
  if (others === 0) return null
  const shown = everywhere ? `Every world's cities, ${others} of them from other worlds.`
    : worldName ? `${worldName}'s cities and your own.` : 'Cities that stand outside the built-in worlds, and your own.'
  return (
    <p className="subtle">{shown}{' '}
      <button type="button" className="text-button" aria-pressed={everywhere} onClick={onToggle}>
        {everywhere ? 'Only this world' : `Show other worlds' cities (${others})`}</button>
    </p>
  )
}

/** The release's featured cities as a row of compact cards (shown with every world's cities); a card jumps to the city's full card below. */
function FeaturedStrip({ featured }: { featured?: FeaturedCities }) {
  if (!featured?.cities.length) return null
  const jump = (id: string) => {
    const card = document.getElementById(`city-${id}`)
    if (!card) return
    const instant = reducedMotion()
    card.scrollIntoView({ behavior: instant ? 'auto' : 'smooth', block: 'start' })
    card.focus({ preventScroll: true })
    card.classList.add('jumped')
    window.setTimeout(() => card.classList.remove('jumped'), 2000)
  }
  return (
    <div className="featured-cities" role="region" aria-labelledby="featured-cities-heading">
      <h3 id="featured-cities-heading">{featured.title}</h3>
      {featured.note && <p className="subtle">{featured.note}</p>}
      <ul className="featured-strip">
        {featured.cities.map((city) => { const where = [city.region, city.country].filter(Boolean).join(', '); return (
          <li key={city.id}>
            <button type="button" className="featured-card" onClick={() => jump(city.id)}>
              <span className="featured-name">{city.name}{city.new && <span className="badge">New</span>}</span>
              <span className="subtle featured-region" title={where}>{where}</span>
              <span className="featured-summary">{city.summary}</span>
            </button>
          </li>
        ) })}
      </ul>
    </div>
  )
}

function CityEditor({ editing, onClose, onSaved }: { editing: Editing; onClose: () => void; onSaved: (city: CityListing) => void }) {
  const [text, setText] = useState(editing.text)
  const [result, setResult] = useState<Feedback>(null)
  const [busy, setBusy] = useState(false)
  const run = async (save: boolean) => {
    const parsed = parseDefinition(text)
    if (!parsed.ok) { setResult({ tone: 'error', text: parsed.error }); return }
    setBusy(true)
    try {
      if (!save) {
        const checked = await api<{ summary: CityListing }>('/world/validate', parsed.value)
        setResult({ tone: 'info', text: `Looks good: ${checked.summary.name}, ${cityFacts(checked.summary)}.`, notes: checked.summary.import_notes })
      } else if (editing.mode === 'create') {
        onSaved(await api<CityListing>('/world/cities', parsed.value))
      } else {
        onSaved(await api<CityListing>(`/world/cities/${editing.id}`, { definition: parsed.value, expected_revision: editing.revision }, 'PUT'))
      }
    } catch (error) {
      setResult({ tone: 'error', text: error instanceof Error ? error.message : 'Not saved.' })
    } finally { setBusy(false) }
  }
  return (
    <div className="city-editor form-stack">
      <h3>{editing.mode === 'create' ? 'New city' : `Editing ${editing.id}`}</h3>
      <p className="subtle" id="city-json-hint">A city is a JSON file. Every place, college and employer names its neighborhood. New kinds of places, schools and jobs are welcome, and small slips are mended when you save. <a href="https://github.com/vantaloomin/prosperos-dungeon/blob/main/Program/docs/world-data.md#building-a-city" target="_blank" rel="noreferrer">The guide</a> lists every field.</p>
      <label htmlFor="city-json" className="visually-hidden">City definition</label>
      <textarea id="city-json" aria-describedby="city-json-hint" className="city-json" rows={18} spellCheck={false} value={text} onChange={(event) => { setText(event.target.value); setResult(null) }} />
      <div aria-live="polite">{result && <FeedbackNotice feedback={result} />}</div>
      <div className="form-actions">
        <button type="button" className="button primary" disabled={busy} onClick={() => void run(true)}>Save</button>
        <button type="button" className="button" disabled={busy} onClick={() => void run(false)}>Check</button>
        <button type="button" className="button quiet" onClick={onClose}>Cancel</button>
      </div>
    </div>
  )
}

function CopyDialog({ city, onClose, onCopied }: { city: CityListing; onClose: () => void; onCopied: (name: string) => void }) {
  const [name, setName] = useState(`My ${city.name}`)
  const [error, setError] = useState('')
  const copy = async () => {
    try {
      const created = await api<CityListing>(`/world/cities/${city.id}/copy`, { id: slugify(name), name: name.trim() })
      onCopied(created.name)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Not copied.') }
  }
  return (
    <ConfirmDialog title={`Copy ${city.name}`} onClose={onClose} actions={<>
      <button type="button" className="button" onClick={onClose}>Cancel</button>
      <button type="button" className="button primary" disabled={!slugify(name)} onClick={() => void copy()}>Copy</button>
    </>}>
      <TextInput label="Name of your copy" value={name} onChange={(value) => { setName(value); setError('') }} maxLength={120} hint={`Its id will be ${slugify(name) || '…'}.`} />
      {error && <Notice tone="error">{error}</Notice>}
    </ConfirmDialog>
  )
}

function Packs({ onReloaded }: { onReloaded: () => void }) {
  const client = useQueryClient()
  const packs = useQuery({ queryKey: ['city-packs'], queryFn: () => api<PackReport>('/world/packs') })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const reload = async () => {
    setBusy(true)
    setError('')
    try {
      client.setQueryData(['city-packs'], await api<PackReport>('/world/packs/reload', {}))
      onReloaded()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The packs were not reloaded.') } finally { setBusy(false) }
  }
  if (!packs.data) return null
  return (<>
    {packs.data.errors.map((item) => <Notice key={item.file} tone="error">{fileProblem(item.file)} {item.error} The other cities are unaffected. Fix or remove the file, then Reload packs under Pack folders.</Notice>)}
    <details className="city-packs">
      <summary>Pack folders</summary>
      <p className="subtle">City files dropped in these folders load as read-only packs. Packs marked private are for your own use and are never shared from here.</p>
      <ul>{packs.data.folders.map((folder) => <li key={folder}><code>{shownPath(folder)}</code></li>)}</ul>
      {packs.data.loaded.length > 0 && <p className="subtle">Loaded: {packs.data.loaded.map((item) => item.file.split(/[\\/]/).pop()).join(', ')}</p>}
      {packs.data.loaded.filter((item) => item.import_notes?.length).map((item) => (
        <FeedbackNotice key={item.file} feedback={{ tone: 'info', text: `${item.file.split(/[\\/]/).pop()} loaded.`, notes: item.import_notes }} />
      ))}
      {error && <Notice tone="error">{error}</Notice>}
      <div className="form-actions"><button type="button" className="button" disabled={busy} onClick={() => void reload()}><FolderSync aria-hidden="true" />Reload packs</button></div>
    </details>
  </>)
}

/** Names a city file that did not load, and which folder it is in, since a file can be dropped in the wrong one. */
function fileProblem(path: string): string {
  const parts = path.split(/[\\/]/)
  const name = parts.pop() ?? path
  const folder = path.slice(0, Math.max(0, path.length - name.length - 1))
  const builtIn = parts.slice(-3).join('/') === 'world/data/cities'
  return `The city file ${name} ${builtIn ? 'in the built-in cities folder' : `in ${shownPath(folder) || 'a pack folder'}`} could not be read.`
}
