// 3D dice for "Roll the dice on screen" (src/features/story/dice.ts). Loaded only when a roll asks for it, so the
// 3D engine never weighs on anyone who leaves the setting off. The dice land on faces the code already rolled
// (the library's predetermined "@" notation); they never decide anything.
import DiceBox from '@3d-dice/dice-box-threejs'
import { diceNotation, type DieFace } from './storyText'

const STAGE = 'dice-stage'
const LINGER_MS = 900

let box: Promise<DiceBox> | null = null
let queue: Promise<unknown> = Promise.resolve()

function token(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/** One stage for every roll, over the middle of the story: it lets clicks through and shows only while dice are
 *  out. The table is sized once, when the 3D dice first load. */
function stage(): HTMLElement {
  const found = document.getElementById(STAGE)
  if (found) return found
  const made = document.createElement('div')
  made.id = STAGE
  made.className = 'dice-stage'
  made.setAttribute('aria-hidden', 'true')
  const story = document.querySelector('.story-log')?.getBoundingClientRect()
  if (story && story.width > 0) {
    const height = Math.min(story.height, 460)
    Object.assign(made.style, { left: `${story.left}px`, width: `${story.width}px`, top: `${story.top + (story.height - height) / 2}px`, height: `${height}px` })
  }
  document.body.appendChild(made)
  return made
}

function ready(): Promise<DiceBox> {
  box ??= (async () => {
    stage()
    const made = new DiceBox(`#${STAGE}`, {
      sounds: false, shadows: true, theme_surface: 'green-felt', theme_material: 'plastic', strength: 1.2, baseScale: 80,
      theme_customColorset: {
        name: 'dungeon', foreground: token('--on-accent', '#211c14'), background: token('--accent', '#c5a46d'),
        outline: token('--on-accent', '#211c14'), texture: 'none', material: 'plastic',
      },
    })
    await made.initialize()
    return made
  })()
  return box
}

async function play(faces: DieFace[]): Promise<void> {
  const dice = await ready()
  const shown = stage()
  shown.classList.add('rolling')
  try {
    await dice.roll(diceNotation(faces))
    await new Promise((settle) => window.setTimeout(settle, LINGER_MS))
  }
  finally {
    shown.classList.remove('rolling')
    window.setTimeout(() => { if (!shown.classList.contains('rolling')) dice.clearDice() }, 400)
  }
}

/** Rolls one roll's dice, after any roll already on the table; resolves once they have landed. */
export function roll3d(faces: DieFace[]): Promise<void> {
  const turn = queue.then(() => play(faces))
  queue = turn.catch(() => undefined)
  return turn
}

/** Takes the dice off the table at once (the player clicked to land them). */
export function clear3d(): void {
  document.getElementById(STAGE)?.classList.remove('rolling')
}
