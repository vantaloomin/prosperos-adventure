import { useState } from 'react'
import { useRoundTable } from '../round/useRound'
import { knowerChoices, knowersAfter, visibilityChoices, type LoreEntry, type Visibility } from './loreText'

/** Who may read an entry (PUT /api/lore/entries/{id}/visibility): everyone, some characters, or only the GM view. The
 *  characters are those at the table (GET /api/rounds); Some characters is saved once one of them is ticked, and the
 *  last one ticked stays so. */
export function LoreVisibility({ entry, onSave }: { entry: LoreEntry; onSave: (visibility: Visibility, knownTo: string[]) => Promise<void> }) {
  const seats = useRoundTable().data?.seats ?? []
  const [chosen, setChosen] = useState<Visibility>(entry.visibility)
  const people = knowerChoices(seats, entry.known_to)
  const pick = (visibility: Visibility) => {
    setChosen(visibility)
    if (visibility !== 'known') void onSave(visibility, [])
    else if (entry.known_to.length) void onSave('known', entry.known_to)
  }
  // The last one named stays ticked: an entry known to nobody is GM only, which is the choice above.
  const last = (key: string) => entry.visibility === 'known' && entry.known_to.length === 1 && entry.known_to[0] === key
  return (
    <div className="lore-who">
      <select aria-label="Who knows this" value={chosen} onChange={(event) => pick(event.target.value as Visibility)}>
        {visibilityChoices(people.length > 0).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
      {chosen === 'known' && <ul className="lore-knowers" aria-label="Characters who know this">
        {people.map((person) => <li key={person.key}><label>
          <input type="checkbox" checked={entry.known_to.includes(person.key)} disabled={last(person.key)}
            onChange={(event) => void onSave('known', knowersAfter(entry.known_to, person.key, event.target.checked))} />{person.name}
        </label></li>)}
      </ul>}
    </div>
  )
}
