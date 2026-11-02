import { Check, Dices, PenLine } from 'lucide-react'
import type { BandStep, HiddenRoll, StoryRoll, TurnSoFar } from '../../types'
import { DiceTray } from './StoryDice'
import { useTumble } from './dice'
import { useTable } from './table'
import { actionLine, bandSpans, isShown, markerAt, nearMiss, rollText, rollWhat, unrolled } from './storyText'

const SUCCESS = new Set(['success_cost', 'success', 'critical_success'])

/** One roll: with the dice shown, the action, stat and difficulty, where the total landed on the ruleset's band
 *  strip and the band in words; with them hidden, only that a stat was tested. `live` lets the marker land, and
 *  with rolling dice on (the Table) the roll's dice tumble first and land on the code's faces. */
export function RollCard({ roll, bands, live }: { roll: StoryRoll | HiddenRoll; bands?: BandStep[] | null; live?: boolean }) {
  const dice = useTable().rules?.roll_dice === true
  if (!isShown(roll)) return (
    <p className="roll-hidden" title={roll.action}><Dices aria-hidden="true" />Your {roll.stat} is tested</p>
  )
  if (unrolled(roll)) return <NoRoll roll={roll} />
  return <ShownRoll roll={roll} bands={bands} live={!!live} dice={!!dice} />
}

/** A check that failed with no dice to throw: what was tried and why it could not work. */
function NoRoll({ roll }: { roll: StoryRoll }) {
  return (
    <div className="roll-card" title={rollText(roll)} aria-label={`${roll.action}: ${rollWhat(roll)}. ${roll.label}.`}>
      <div className="roll-what">
        <span className="subtle">{roll.action}</span>
        <strong>{rollWhat(roll)}</strong>
      </div>
      <div className="roll-result"><span className="roll-band">{roll.label}</span></div>
    </div>
  )
}

function ShownRoll({ roll, bands, live, dice }: { roll: StoryRoll; bands?: BandStep[] | null; live: boolean; dice: boolean }) {
  const tumble = useTumble(roll, live && dice)
  const close = bands ? nearMiss(roll, bands) : ''
  return (
    <div className={dice ? 'roll-card with-dice' : 'roll-card'} title={rollText(roll)} aria-label={`${roll.action}: ${rollWhat(roll)}. ${roll.label}, ${roll.total}.`}>
      {dice && <DiceTray tumble={tumble} />}
      <div className="roll-what">
        <span className="subtle">{roll.action}</span>
        <strong>{rollWhat(roll)}</strong>
      </div>
      {!!bands?.length && <RollStrip bands={bands} total={roll.total} marker={tumble.done} live={live} />}
      <div className="roll-result">
        {tumble.done ? <><span className={SUCCESS.has(roll.band) ? 'roll-band won' : 'roll-band'}>{roll.label}</span>
          <span className="subtle">{close || roll.total}</span></> : <span className="subtle">Rolling…</span>}
      </div>
    </div>
  )
}

/** The ruleset's bands from 1 to 100, and the marker where the total landed once the dice have. */
function RollStrip({ bands, total, marker, live }: { bands: BandStep[]; total: number; marker: boolean; live: boolean }) {
  return (
    <div className="roll-strip" aria-hidden="true">
      {bandSpans(bands).map((step) => <span key={step.band} className={`band-${step.band}`} style={{ flexGrow: step.to - step.from + 1 }}
        title={`${step.label}: ${step.from}${step.ceiling === null ? '+' : `–${step.to}`}`} />)}
      {marker && <i className={live ? 'roll-marker landing' : 'roll-marker'} style={{ left: `${markerAt(total)}%` }} />}
    </div>
  )
}

/** A turn under way before its narration: what the game is doing (reading the line, rolling, writing) and each roll
 *  as it lands, so the wait shows its work (dungeon/story.py answer). The rolls stay once the prose streams. */
export function TurnLive({ turn, writing }: { turn: TurnSoFar; writing: boolean }) {
  const rolled = turn.rolls.length >= turn.actions.length
  return (<>
    {turn.rolls.map((roll, index) => <RollCard key={index} roll={roll} bands={turn.bands} live />)}
    {!writing && <ol className="turn-steps" aria-label="What the game is doing">
      <li className={turn.actions.length || turn.stage === 'writing' ? 'done' : 'now'}>
        {turn.actions.length || turn.stage === 'writing' ? <Check aria-hidden="true" /> : <span className="turn-dot" />}
        {turn.actions.length ? `Read your move: ${turn.actions.map((action) => action.action).join(', then ')}` : 'Reading your move'}
      </li>
      {turn.actions.map((action, index) => <li key={index} className={index < turn.rolls.length ? 'done' : 'now'}>
        {index < turn.rolls.length ? <Check aria-hidden="true" /> : <Dices aria-hidden="true" />}{actionLine(action)}
      </li>)}
      <li className={turn.stage === 'writing' && rolled ? 'now' : 'later'}><PenLine aria-hidden="true" />The narrator writes what happens</li>
    </ol>}
  </>)
}
