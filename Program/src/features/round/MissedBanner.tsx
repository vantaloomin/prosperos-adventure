import { MISSED } from './roundText'

/** On leaving Play, once: whether the turns played in Play now show the motives they kept hidden (PL-11). */
export function MissedBanner({ asking, onAnswer }: { asking: boolean; onAnswer: (reveal: boolean) => void }) {
  if (!asking) return null
  return (
    <div className="pause-banner" role="status">
      <p>{MISSED.question}</p>
      <div className="pause-actions">
        <button type="button" className="button primary" onClick={() => onAnswer(false)}>{MISSED.hide}</button>
        <button type="button" className="button" onClick={() => onAnswer(true)}>{MISSED.show}</button>
      </div>
    </div>
  )
}
