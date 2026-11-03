import { useState } from 'react'
import { api } from '../../api'
import type { Story as StoryData, StoryBranch } from '../../types'
import { Notice } from '../../components/Feedback'
import { branchLine, branchName } from './storyText'
import { whatIf } from '../round/roundText'

interface Props { branches: StoryBranch[]; change: (request: () => Promise<StoryData>) => Promise<void>; open?: boolean }

const path = (id: string) => `/story/branches/${encodeURIComponent(id)}`

/** The other ways this story went (adventure/timeline.py): each one is kept where it was left, to play on, rename or
 * take out of the list. Deleting erases nothing, so Undo brings it back (from Prospero's Companion #496). */
export function StoryBranches({ branches, change, open }: Props) {
  const others = branches.filter((branch) => !branch.playing)
  const [removed, setRemoved] = useState<{ id: string; name: string } | null>(null)
  if (!others.length && !removed) return null
  // `change` shows its own error, so each step's follow-up runs only once the request has worked.
  const remove = (branch: StoryBranch) => void change(() => api<StoryData>(path(branch.id), undefined, 'DELETE')
    .then((data) => { setRemoved({ id: branch.id, name: branchName(branch) || 'The branch' }); return data }))
  const undo = (id: string) => void change(() => api<StoryData>(`${path(id)}/restore`, {}).then((data) => { setRemoved(null); return data }))
  return (
    <details className="story-people" open={open}>
      <summary>Other branches ({others.length})</summary>
      {removed && <Notice action={<button type="button" className="text-button" onClick={() => undo(removed.id)}>Undo</button>}>{removed.name} is out of the list.</Notice>}
      <ul>
        {others.map((branch) => <BranchRow key={branch.id} branch={branch} change={change} onDelete={() => remove(branch)} />)}
      </ul>
    </details>
  )
}

function BranchRow({ branch, change, onDelete }: { branch: StoryBranch; change: Props['change']; onDelete: () => void }) {
  const [name, setName] = useState<string | null>(null)
  const save = () => {
    if (!name?.trim()) return
    void change(() => api<StoryData>(path(branch.id), { label: name.trim() }, 'PATCH').then((data) => { setName(null); return data }))
  }
  return (
    <li>
      {branch.reask && !branch.label && <p className="branch-question"><span className="portrait" aria-hidden="true">{branch.reask.name.charAt(0)}</span>{whatIf(branch.reask.name)}</p>}
      {branch.label && name === null && <p className="branch-name">{branch.label}</p>}
      {name !== null && <form className="branch-rename" onSubmit={(event) => { event.preventDefault(); save() }}>
        <input autoComplete="off" aria-label="Name this branch" maxLength={80} value={name} autoFocus onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Escape') { event.stopPropagation(); setName(null) } }} />
        <button type="submit" className="button primary" aria-disabled={!name.trim()}>Save</button>
        <button type="button" className="text-button" onClick={() => setName(null)}>Cancel</button>
      </form>}
      <p className="subtle">{branchLine(branch)}</p>
      {branch.last_line && <p className="story-note">{branch.last_line}</p>}
      <div className="form-actions">
        <button type="button" className="text-button" onClick={() => void change(() => api<StoryData>(`${path(branch.id)}/switch`, {}))}>Play this branch</button>
        {name === null && <button type="button" className="text-button" onClick={() => setName(branch.label || (branch.reask ? whatIf(branch.reask.name) : ''))}>Rename</button>}
        <button type="button" className="text-button" onClick={onDelete}>Delete</button>
      </div>
    </li>
  )
}
