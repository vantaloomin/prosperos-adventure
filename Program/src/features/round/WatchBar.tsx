import { useState } from 'react'
import { Pause, Play, SkipForward } from 'lucide-react'
import { AiFooter } from '../../components/Safety'
import { WATCH_SECONDS, type WatchPaused, type WatchPause } from './round'
import { pauseLine, secondsName, WATCH_NAMES } from './roundText'

interface Props {
  playing: boolean; busy: boolean; pause: WatchPause; seconds: number
  onPlay: () => void; onPause: () => void; onNext: () => void; onEvery: (seconds: number) => void
  onGoOn: () => void; onAuthor: () => void; onRaise: () => void; onStop: () => void
}

/** Watch's composer (PL-10): Play / Pause on the timer, how long it waits between turns, and Next by hand; with one
 *  banner when play stops on its own, always saying why. */
export function WatchBar({ playing, busy, pause, seconds, onPlay, onPause, onNext, onEvery, ...banner }: Props) {
  return (<>
    {pause && <PauseBanner key={`${pause.kind}:${pause.turn_id ?? ''}`} pause={pause} onPlay={onPlay} {...banner} />}
    <div className="composer watch-bar" role="group" aria-label={WATCH_NAMES.label}>
      <label className="watch-every">{WATCH_NAMES.every}
        <select value={seconds} onChange={(event) => onEvery(Number(event.target.value))}>
          {WATCH_SECONDS.map((value) => <option key={value} value={value}>{secondsName(value)}</option>)}
        </select>
      </label>
      {seconds > 0 && (playing
        ? <button type="button" className="button" onClick={onPause}><Pause aria-hidden="true" />{WATCH_NAMES.pause}</button>
        : <button type="button" className="button" disabled={!!pause} onClick={onPlay}><Play aria-hidden="true" />{WATCH_NAMES.play}</button>)}
      <button type="button" className="button primary" disabled={busy || playing} onClick={onNext}><SkipForward aria-hidden="true" />{WATCH_NAMES.next}</button>
    </div>
    <AiFooter />
  </>)
}

type BannerProps = Pick<Props, 'onGoOn' | 'onAuthor' | 'onRaise' | 'onStop' | 'onPlay'> & { pause: WatchPaused }

/** "Paused: Mara betrayed the party" with Continue and Switch to Author; the session cap with Raise cap and Stop
 *  here; a failed turn with Try again and Stop here. Stop here puts the banner away until the next pause. */
function PauseBanner({ pause, onGoOn, onAuthor, onRaise, onStop, onPlay }: BannerProps) {
  const [away, setAway] = useState(false)
  if (away) return null
  const stop = () => { setAway(true); onStop() }
  return (
    <div className="pause-banner" role="status">
      <p>{pauseLine(pause)}</p>
      <div className="pause-actions">
        {pause.kind === 'cap' && <><button type="button" className="button" onClick={onRaise}>{WATCH_NAMES.raise}</button>
          <button type="button" className="button" onClick={stop}>{WATCH_NAMES.stop}</button></>}
        {pause.kind === 'error' && <><button type="button" className="button" onClick={onPlay}>{WATCH_NAMES.retry}</button>
          <button type="button" className="button" onClick={stop}>{WATCH_NAMES.stop}</button></>}
        {pause.kind !== 'cap' && pause.kind !== 'error' && <><button type="button" className="button primary" onClick={onGoOn}>{WATCH_NAMES.go}</button>
          <button type="button" className="button" onClick={onAuthor}>{WATCH_NAMES.author}</button></>}
      </div>
    </div>
  )
}
