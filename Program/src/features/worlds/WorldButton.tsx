import { UserRound } from 'lucide-react'
import { useFollowWorld } from './useWorlds'
import { initial, whereLine } from './worldsText'

/** Who the user is and which world they are in, at the top of the nav; opens Worlds, where they switch persona or
 * world. It also follows a switch made in another tab. */
export function WorldButton({ current, onOpen }: { current: boolean; onOpen: () => void }) {
  const worlds = useFollowWorld().data
  return (
    <button type="button" className="nav-world" aria-current={current ? 'page' : undefined} onClick={onOpen}
      title={worlds ? `${whereLine(worlds.persona, worlds.world)}. Switch persona or world.` : 'Worlds'}>
      <span className="nav-persona" aria-hidden="true">{initial(worlds?.persona) || <UserRound size={14} />}</span><span>{worlds?.world.name ?? 'Worlds'}</span>
    </button>
  )
}
