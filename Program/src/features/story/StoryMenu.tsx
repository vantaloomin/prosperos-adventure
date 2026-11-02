import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Command } from 'lucide-react'
import { filterCommands, type MenuCommand } from './menuText'

/** The story's command menu: the button left of the message box, or ⌘K (Ctrl+K) anywhere on the story screen. A
 *  filter box over the commands; the arrow keys move through them, Enter runs one, Escape closes it. */
export function StoryMenu({ commands, onRun }: { commands: MenuCommand[]; onRun: (command: MenuCommand) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [open, setOpen] = useState(false)
  const show = () => { dialog.current?.showModal(); setOpen(true) }
  useEffect(() => {
    const key = (event: globalThis.KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'k' || !(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return
      event.preventDefault()
      if (dialog.current?.open) dialog.current.close(); else show()
    }
    document.addEventListener('keydown', key)
    return () => document.removeEventListener('keydown', key)
  }, [])
  const run = (command: MenuCommand) => { dialog.current?.close(); onRun(command) }
  return <>
    <button type="button" className="button composer-menu" aria-label="Menu" aria-haspopup="dialog" aria-expanded={open} title="Menu (⌘K)" onClick={show}>
      <Command aria-hidden="true" />
    </button>
    <dialog ref={dialog} className="dialog story-menu" aria-label="Menu" onClose={() => setOpen(false)}
      onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close() }}>
      {open && <MenuList commands={commands} onRun={run} />}
    </dialog>
  </>
}

function MenuList({ commands, onRun }: { commands: MenuCommand[]; onRun: (command: MenuCommand) => void }) {
  const [typed, setTyped] = useState('')
  const [active, setActive] = useState(0)
  const shown = filterCommands(commands, typed)
  const at = Math.min(active, Math.max(shown.length - 1, 0))
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const step = { ArrowDown: 1, ArrowUp: -1 }[event.key]
    if (step) { event.preventDefault(); setActive((at + step + shown.length) % Math.max(shown.length, 1)) }
    if (event.key === 'Enter' && shown[at]) { event.preventDefault(); onRun(shown[at]) }
  }
  return <>
    <input className="story-menu-filter" aria-label="Find a command" placeholder="Search" aria-controls="story-menu-list" aria-activedescendant={shown[at] ? `story-menu-${shown[at].id}` : undefined}
      role="combobox" aria-expanded="true" autoFocus value={typed} onChange={(event) => { setTyped(event.target.value); setActive(0) }} onKeyDown={onKeyDown} />
    <ul id="story-menu-list" role="listbox" aria-label="Commands" className="story-menu-list">
      {shown.map((command, index) => (
        <li key={command.id} id={`story-menu-${command.id}`} role="option" aria-selected={index === at}
          onPointerMove={() => setActive(index)} onClick={() => onRun(command)}>{command.label}</li>
      ))}
    </ul>
  </>
}
