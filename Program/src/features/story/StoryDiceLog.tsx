import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { DiceLog } from '../../types'
import { paceText, rollText, tallyText } from './storyText'

/** The dice log (dungeon/dice_log.py): every roll of this branch, turn by turn, and how long each turn took. Only
 *  while the dice are shown; the story refetches it after each turn. */
export function StoryDiceLog({ open }: { open?: boolean }) {
  const log = useQuery({ queryKey: ['story-dice-log'], queryFn: () => api<DiceLog>('/story/dice-log') })
  if (!log.data?.shown || !log.data.tally) return null
  const { turns, tally } = log.data
  return (
    <details className="story-people" open={open}>
      <summary>Dice log · {tallyText(tally)}</summary>
      <ol className="dice-log" aria-label="Rolls, newest first">
        {turns.map((item) => <li key={item.id}>
          <p className="story-note">“{item.line}”</p>
          {item.rolls.length > 0 && <ul>
            {item.rolls.map((roll, index) => <li key={index}><strong>{roll.action}</strong> <span className="subtle">{rollText(roll)}</span></li>)}
          </ul>}
          {item.pace && <p className="subtle">{paceText(item.pace)}</p>}
        </li>)}
      </ol>
    </details>
  )
}
