// The parts of @3d-dice/dice-box-threejs the play screen uses (src/features/story/dice3d.ts); it ships no types.
declare module '@3d-dice/dice-box-threejs' {
  interface ColorSet { name: string; foreground: string; background: string; outline: string; texture: string; material: string }
  interface Options {
    sounds?: boolean; shadows?: boolean; theme_surface?: string; theme_material?: string; strength?: number; baseScale?: number
    theme_customColorset?: ColorSet
  }
  export default class DiceBox {
    constructor(selector: string, options?: Options)
    initialize(): Promise<void>
    roll(notation: string): Promise<unknown>
    clearDice(): void
  }
}
