import { useEffect, useState } from 'react'
import type { StoryRoll } from '../../types'
import { diceFaces, tumbleFace, type DieFace } from './storyText'

// The dice only act out a roll the code already made (dungeon/rules/marvel.py): each one tumbles, then lands on its
// real face, one after another; the strip and the band show once the last has landed.
const TICK_MS = 70
const landsAt = (index: number) => 650 + index * 280

/** The user's reduced-motion choice in Settings, else the computer's. */
function calm(): boolean {
  const motion = document.documentElement.dataset.motion
  return motion === 'reduce' || (motion !== 'full' && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
}

export interface Tumble { faces: DieFace[]; shown: string[]; landed: boolean[]; done: boolean; skip: () => void }

/** The dice of one roll as they tumble: `rolling` false (a saved roll, or reduced motion) shows them landed. */
/** Whether this PC can draw the 3D dice; without WebGL the flat dice tumble instead. */
function webgl(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  }
  catch { return false }
}

/** The 3D dice, if this PC can draw them: `landed` once they have, `failed` to fall back to the flat ones. */
function use3d(faces: DieFace[], on: boolean, landed: () => void, failed: () => void) {
  useEffect(() => {
    if (!on) return
    let gone = false
    import('./dice3d').then((dice) => dice.roll3d(faces))
      .then(() => { if (!gone) landed() }, () => { if (!gone) failed() })
    return () => { gone = true }
    // One throw per roll: the faces are fixed once the roll is made.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on])
}

/** The flat dice: random faces until each lands in turn. */
function useFlat(faces: DieFace[], on: boolean, elapsed: number, tick: (elapsed: number, picks: number[]) => void) {
  useEffect(() => {
    if (!on) return
    const started = Date.now() - elapsed
    const timer = window.setInterval(() => tick(Date.now() - started, faces.map(() => Math.random())), TICK_MS)
    return () => window.clearInterval(timer)
    // The timer runs once per roll; it reads elapsed only to resume where it stood.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on])
}

/** The dice of one roll as they roll: in 3D where the PC can, else flat. `rolling` false (a saved roll, or reduced
 *  motion) shows them landed. */
export function useTumble(roll: StoryRoll, rolling: boolean): Tumble {
  const faces = diceFaces(roll)
  const end = landsAt(faces.length - 1)
  const [elapsed, setElapsed] = useState(() => (rolling && !calm() ? 0 : end))
  // Fate dice have no 3D model: they always roll flat.
  const [flat, setFlat] = useState(() => !rolling || !webgl() || roll.ruleset === 'fate')
  const [picks, setPicks] = useState<number[]>(() => faces.map(() => 0))
  const done = elapsed >= end
  use3d(faces, !done && !flat, () => setElapsed(end), () => setFlat(true))
  useFlat(faces, !done && flat, elapsed, (next, faces) => { setElapsed(next); setPicks(faces) })
  const landed = faces.map((_, index) => elapsed >= landsAt(index))
  return {
    faces, landed, done,
    shown: faces.map((face, index) => (landed[index] ? face.value : flat ? tumbleFace(face, picks[index] ?? 0) : '')),
    skip: () => {
      setElapsed(end)
      if (!flat) void import('./dice3d').then((dice) => dice.clear3d())
    },
  }
}
