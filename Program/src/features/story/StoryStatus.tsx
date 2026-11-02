import { useQuery } from '@tanstack/react-query'
import { Bandage, Brain, Clock, Coins, HeartPulse, Link } from 'lucide-react'
import { api } from '../../api'
import type { Gear, Story } from '../../types'
import { moneyText, statusItems } from './storyText'

const ICONS = { time: Clock, condition: HeartPulse, nerve: Brain, lasting: Bandage, held: Link, coin: Coins }

/** The status strip (requirements "Play screen and widgets"): time, condition, nerve, lasting injuries and coin at a
 *  glance, under the scene line. The purse is the pack's (dungeon/inventory.py), read with it. */
export function StatusStrip({ story }: { story: Story }) {
  const gear = useQuery({ queryKey: ['story-gear'], queryFn: () => api<Gear>('/story/gear'), enabled: !!story.messages.length })
  const coin = gear.data ? moneyText(gear.data.coins, gear.data.currency) : null
  return (
    <ul className="status-strip" aria-label="How things stand">
      {statusItems(story.scene, story.fight, coin).map((item) => {
        const Icon = ICONS[item.kind]
        return <li key={item.kind} className={item.tone === 'loss' ? 'status-item loss' : 'status-item'}><Icon aria-hidden="true" />{item.text}</li>
      })}
    </ul>
  )
}
