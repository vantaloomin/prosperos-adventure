import { Pause, Play, SkipForward } from 'lucide-react'
import { AiFooter } from '../../components/Safety'
import type { WatchPause } from './round'
import { pauseLine, WATCH_NAMES } from './roundText'

interface Props {
  playing: boolean; busy: boolean; pause: WatchPause
  onPlay: () => void; onPause: () => void; onNext: () => void; onRaise: () => void; onStop: () => void
}

/** Watch's composer (PL-10): Play / Pause and Next, with one banner when play stops on its own, always saying why. */
export function WatchBar({ playing, busy, pause, onPlay, onPause, onNext, onRaise, onStop }: Props) {
  return (<>
    {pause && <div className="pause-banner" role="status">
      <p>{pauseLine(pause)}</p>
      <div className="pause-actions">
        {pause.reason === 'cap'
          ? <button type="button" className="button" onClick={onRaise}>{WATCH_NAMES.raise}</button>
          : <button type="button" className="button" onClick={onPlay}>{WATCH_NAMES.retry}</button>}
        <button type="button" className="button" onClick={onStop}>{WATCH_NAMES.stop}</button>
      </div>
    </div>}
    <div className="composer watch-bar" role="group" aria-label={WATCH_NAMES.label}>
      {playing
        ? <button type="button" className="button" onClick={onPause}><Pause aria-hidden="true" />{WATCH_NAMES.pause}</button>
        : <button type="button" className="button" onClick={onPlay}><Play aria-hidden="true" />{WATCH_NAMES.play}</button>}
      <button type="button" className="button primary" disabled={busy || playing} onClick={onNext}><SkipForward aria-hidden="true" />{WATCH_NAMES.next}</button>
    </div>
    <AiFooter />
  </>)
}
