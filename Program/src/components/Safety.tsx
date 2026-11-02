import { LifeBuoy } from 'lucide-react'

/** Under every message box: the characters are AI. Always shown, in every chat and every style (docs/safety.md). */
const AI_FOOTER = 'Characters are AI and can make mistakes.'

export function AiFooter() {
  return <p className="ai-footer">{AI_FOOTER}</p>
}

/** The app's note under a message of yours that sounds like self-harm (dungeon/safety.py). It comes from the app,
 * never from the character, so it looks like nothing a character would send; the chat goes on as usual. */
export function CrisisNote() {
  return (
    <aside className="crisis-note" role="note" aria-label="A note from Prospero's Dungeon">
      <LifeBuoy aria-hidden="true" />
      <div>
        <p className="crisis-from">From Prospero&apos;s Dungeon, not the narrator</p>
        <p>If you&apos;re thinking about hurting yourself, you don&apos;t have to go through it alone. In the US, call or text <strong>988</strong> (Suicide &amp; Crisis Lifeline), or text <strong>HOME</strong> to <strong>741741</strong> (Crisis Text Line), any time, for free. Elsewhere, <a href="https://findahelpline.com" target="_blank" rel="noreferrer">findahelpline.com</a> lists free lines near you. If you&apos;re in danger right now, call your local emergency number.</p>
      </div>
    </aside>
  )
}
