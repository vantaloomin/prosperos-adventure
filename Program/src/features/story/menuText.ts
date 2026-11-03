import type { Story } from '../../types'
import { hasWidget, WIDGET_NAMES, type Widget } from './scene.ts'

/** What the story's command menu (./StoryMenu.tsx, ⌘K) can do: the composer's extras, every panel view the story has
 *  something for, and starting over. Ids are what the menu runs; labels are what it shows and filters on. */
export type MenuCommand = { id: 'ideas' | 'note' | 'step-out' | 'scene' | 'assistant' | 'new-story'; label: string } | { id: Widget; label: string }

/** The panel views, in the order the old drawer had them (its tabs, then More). */
const VIEWS: Widget[] = ['sheet', 'pack', 'journal', 'inside', 'map', 'town', 'talk', 'people', 'party', 'art', 'powers', 'chapters', 'branches', 'notebook', 'dice', 'export', 'rules']

export function menuCommands(story: Story): MenuCommand[] {
  const started = story.messages.length > 0
  return [
    ...(started ? [{ id: 'ideas', label: 'Ideas' } as const] : []),
    { id: 'note', label: "Author's note" },
    { id: 'step-out', label: 'Step out of the story' },
    { id: 'scene', label: "Who's here" },
    { id: 'assistant', label: 'Sidebar Assistant' },
    ...VIEWS.filter((widget) => hasWidget(story, widget)).map((widget) => ({ id: widget, label: WIDGET_NAMES[widget] })),
    ...(started ? [{ id: 'new-story', label: 'Start a new story…' } as const] : []),
  ]
}

/** The commands whose label has every word typed, in order of where the first word starts. */
export function filterCommands(commands: MenuCommand[], typed: string): MenuCommand[] {
  const words = typed.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return commands
  const found = commands.filter((command) => words.every((word) => command.label.toLowerCase().includes(word)))
  return found.sort((a, b) => a.label.toLowerCase().indexOf(words[0]) - b.label.toLowerCase().indexOf(words[0]))
}

/** The line the composer gets for "Step out of the story": an out-of-character message (adventure/story.py OOC). */
export const OUT_OF_STORY = 'OOC: '
