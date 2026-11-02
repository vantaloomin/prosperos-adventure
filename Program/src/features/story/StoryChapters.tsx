import { type ReactElement, useState } from 'react'
import { api } from '../../api'
import type { Story as StoryData, StoryBack, StoryCampaign, StoryChapter, StoryTreeBranch } from '../../types'
import { Notice } from '../../components/Feedback'
import { chapterLine, endingText } from './storyText'

interface Props {
  campaign: StoryCampaign
  change: (request: () => Promise<StoryData>) => Promise<void>
  onBack: (data: StoryBack) => void
  open?: boolean
}

/** The story's chapters and branches (dungeon/chapters.py): the current branch like a table of contents, the tree of
 * every branch, and the bookmarks. In Ironman there is no going back, so the tree only reads. */
export function StoryChapters({ campaign, change, onBack, open }: Props) {
  const [title, setTitle] = useState('')
  const { chapters, tree, bookmarks, ironman, pending } = campaign
  if (!chapters.length) return null
  const close = () => change(() => api<StoryData>('/story/chapters/close', { title: title.trim() })).then(() => setTitle(''))
  const playFrom = (chapter: StoryChapter) => change(() => api<StoryBack>(`/story/chapters/${chapter.id}/back`, {}).then((data) => { onBack(data); return data }))
  const goTo = (id: string) => change(() => api<StoryData>(`/story/bookmarks/${id}/go`, {}).then((data) => {
    requestAnimationFrame(() => document.getElementById(`line-${data.message_id}`)?.scrollIntoView({ block: 'center' }))
    return data
  }))
  return (
    <details className="story-people" open={open}>
      <summary>Chapters ({chapters.length}){ironman && ' · Ironman'}</summary>
      <ol aria-label="Chapters of this branch">
        {chapters.map((chapter) => <ChapterLine key={chapter.id} chapter={chapter} />)}
      </ol>
      {pending ? <p className="subtle">This chapter ends here; your next line starts the next one.</p>
        : <form className="story-add-form" onSubmit={(event) => { event.preventDefault(); void close() }}>
          <input aria-label="Name the chapter that ends here" placeholder="Name it (or leave it to the story)" maxLength={80} value={title} onChange={(event) => setTitle(event.target.value)} />
          <button type="submit" className="button">End the chapter</button>
        </form>}
      {tree.length > 1 && <BranchTree tree={tree} onPlay={ironman ? undefined : (chapter) => void playFrom(chapter)} />}
      {!!bookmarks.length && <ul aria-label="Bookmarks">
        {bookmarks.map((mark) => <li key={mark.id}>
          <p><strong>{mark.name}</strong></p>
          <p className="story-note">{mark.text}</p>
          <div className="form-actions">
            <button type="button" className="text-button" onClick={() => void goTo(mark.id)}>Go there</button>
            <button type="button" className="text-button" onClick={() => void change(() => api<StoryData>(`/story/bookmarks/${mark.id}`, undefined, 'DELETE'))}>Remove</button>
          </div>
        </li>)}
      </ul>}
    </details>
  )
}

function ChapterLine({ chapter, branchId }: { chapter: StoryChapter; branchId?: string }) {
  const [lines, setLines] = useState<{ id: string; role: string; text: string }[] | null>(null)
  const [error, setError] = useState('')
  const read = async () => {
    setError('')
    try {
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : ''
      setLines((await api<{ lines: { id: string; role: string; text: string }[] }>(`/story/chapters/${chapter.id}${query}`)).lines)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'That chapter could not be read.') }
  }
  return (
    <li>
      <p className="subtle">{chapterLine(chapter)}</p>
      <p><strong>{chapter.title}</strong></p>
      {chapter.summary && <p>{chapter.summary}</p>}
      {chapter.hook && <p className="story-note">Still open: {chapter.hook}</p>}
      {lines === null ? <button type="button" className="text-button" onClick={() => void read()}>Read it</button>
        : <div className="story-chapter-text">
          {lines.map((line) => <p key={line.id} className={line.role === 'user' ? 'story-user' : undefined}>{line.text}</p>)}
          <button type="button" className="text-button" onClick={() => setLines(null)}>Close</button>
        </div>}
      {error && <Notice tone="error">{error}</Notice>}
    </li>
  )
}

/** Every branch as a tree: each branch under the one it forked from, with the chapters it began itself. */
function BranchTree({ tree, onPlay }: { tree: StoryTreeBranch[]; onPlay?: (chapter: StoryChapter) => void }) {
  const children = (parent: string | null) => tree.filter((branch) => branch.parent_id === parent)
  const roots = tree.filter((branch) => !branch.parent_id || !tree.some((other) => other.id === branch.parent_id))
  const node = (branch: StoryTreeBranch): ReactElement => (
    <li key={branch.id}>
      <p className="subtle">{branch.playing ? 'The branch you are playing' : 'Another branch'}{endingText(branch.ending)}</p>
      <ul>
        {branch.chapters.map((chapter) => <li key={chapter.id}>
          <p><strong>{chapter.title}</strong> <span className="subtle">{chapterLine(chapter)}</span></p>
          {onPlay && <button type="button" className="text-button" onClick={() => onPlay(chapter)}
            title="Go back to this chapter's first line and play on from there, with new dice. Nothing is lost.">Play from here</button>}
        </li>)}
      </ul>
      {!!children(branch.id).length && <ul>{children(branch.id).map(node)}</ul>}
    </li>
  )
  return <details><summary>Every branch</summary><ul aria-label="Every branch" className="story-tree">{roots.map(node)}</ul></details>
}
