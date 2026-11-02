import type { StoryPerson } from '../../types'
import { personLine } from './storyText'
import { EntityName } from './EntityCard'

/** `title` names the list (the people here, in the scene panel); `open` shows it unfolded. */
interface Props { people: StoryPerson[]; onFind: (key: string) => void; title?: string; open?: boolean }

/** The people the user has met in the story. */
export function StoryPeople({ people, onFind, title = "People you've met", open }: Props) {
  if (!people.length) return null
  return (
    <details className="story-people" open={open}>
      <summary>{title} ({people.length})</summary>
      <ul>
        {people.map((person) => (
          <li key={person.key}>
            <p><strong><EntityName entity={{ kind: 'person', key: person.key }}>{person.name}</EntityName></strong> <span className="subtle">{person.role}, {person.city}</span></p>
            <p className="subtle">{personLine(person)}</p>
            {person.bond && <p className="subtle">Bonded to you ({person.bond})</p>}
            {person.feelings && <p className="subtle">{person.feelings}</p>}
            {person.notes.length > 0 && <p className="story-note">{person.notes[person.notes.length - 1]}</p>}
            <div className="form-actions">
              {person.place && <button type="button" className="text-button" onClick={() => onFind(person.key)}>Go to {person.name.split(' ')[0]}</button>}
            </div>
          </li>))}
      </ul>
    </details>
  )
}
