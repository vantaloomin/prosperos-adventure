import type { UpdateCheck as Found } from '../../types'

const SCRIPT: Record<Found['system'], string> = {
  windows: 'update.bat in the Windows folder',
  mac: 'update.command in the Mac folder',
  other: 'update.bat (Windows) or update.command (Mac)',
}

/** How to get a newer version onto this copy: the installer from the release page, or the folder's update script. */
export function howToUpdate(found: Found): string {
  return found.install === 'installer'
    ? 'Download the new installer from the release page and run it. Your worlds and stories stay as they are.'
    : `Close Adventure, then run ${SCRIPT[found.system]} next to the Program folder. Your worlds and stories stay as they are.`
}

/** ", released 3 November 2026", or nothing when GitHub gave no date. */
export function releasedOn(iso: string | null): string {
  return iso ? `, released ${new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}` : ''
}

/** "Download" only where the release page is the next step (the installer); a folder copy is shown what changed. */
export function linkLabel(found: Found): string {
  if (found.status === 'unavailable') return 'Releases page'
  if (found.status === 'current') return `What’s new in ${found.current}`
  return found.install === 'installer' ? 'Download' : 'What’s new'
}
