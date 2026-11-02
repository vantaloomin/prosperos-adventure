import type { StoryBranch } from '../../types'
import { branchLine } from './storyText'

interface Props { branches: StoryBranch[]; onSwitch: (id: string) => void; open?: boolean }

/** The other ways this story went (dungeon/timeline.py): each one is kept where it was left, to play on. */
export function StoryBranches({ branches, onSwitch, open }: Props) {
  const others = branches.filter((branch) => !branch.playing)
  if (!others.length) return null
  return (
    <details className="story-people" open={open}>
      <summary>Other branches ({others.length})</summary>
      <ul>
        {others.map((branch) => (
          <li key={branch.id}>
            <p className="subtle">{branchLine(branch)}</p>
            {branch.last_line && <p className="story-note">{branch.last_line}</p>}
            <div className="form-actions">
              <button type="button" className="text-button" onClick={() => onSwitch(branch.id)}>Play this branch</button>
            </div>
          </li>))}
      </ul>
    </details>
  )
}
