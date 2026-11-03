import { ArrowDown, ArrowUp } from 'lucide-react'
import { AddLine } from './AddLine'
import { beatMoves, beatStanding, type BoardArc, type BoardBeat } from './round'
import { BEAT_MARKS } from './roundText'
import { useAuthor } from './useAuthor'

type Author = ReturnType<typeof useAuthor>

/** In Author, under the nudge box: the director's plan, each arc's beats for its stage (the spine first), to add to,
 *  cut and reorder (PL-4). Shown only while the coming turn is the Author's (GET /api/rounds/author `editable`). */
export function BeatBoard({ onError }: { onError: (text: string) => void }) {
  const author = useAuthor(onError)
  const arcs = author.view?.board ?? []
  if (!author.view?.editable || !arcs.length) return null
  return <details className="beat-board">
    <summary>Beats</summary>
    {arcs.map((arc) => <ArcBeats key={arc.arc_id} arc={arc} author={author} />)}
  </details>
}

function ArcBeats({ arc, author }: { arc: BoardArc; author: Author }) {
  return <section aria-label={arc.name}>
    <h4>{arc.name}</h4>
    {arc.beats.length > 0 && <ol>{arc.beats.map((beat, index) =>
      <BeatRow key={beat.id} beat={beat} moves={beatMoves(index, arc.beats.length)} index={index} author={author} />)}</ol>}
    <AddLine label={`New beat for ${arc.name}`} placeholder="Add a beat" onAdd={(text) => author.addBeat(arc.arc_id, text)} />
  </section>
}

interface RowProps { beat: BoardBeat; index: number; moves: { up: boolean; down: boolean }; author: Author }

function BeatRow({ beat, index, moves, author }: RowProps) {
  const standing = beatStanding(beat)
  return <li className={beat.cut ? 'beat-cut' : undefined}>
    <span className="beat-text">{beat.cut ? <s>{beat.text}</s> : beat.text}</span>
    {standing && <span className="beat-mark">{BEAT_MARKS[standing]}</span>}
    <span className="beat-tools">
      <button type="button" className="text-button" onClick={() => void author.cut(beat.id, !beat.cut)}>{beat.cut ? 'Bring back' : 'Cut'}</button>
      <button type="button" className="icon-button" aria-label={`Move "${beat.text}" up`} disabled={!moves.up} onClick={() => void author.move(beat.id, index - 1)}><ArrowUp aria-hidden="true" /></button>
      <button type="button" className="icon-button" aria-label={`Move "${beat.text}" down`} disabled={!moves.down} onClick={() => void author.move(beat.id, index + 1)}><ArrowDown aria-hidden="true" /></button>
    </span>
  </li>
}
