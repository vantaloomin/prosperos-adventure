/** One editable prompt as GET /api/prompts lists it (dungeon/prompt_library.py). */
export interface EditablePrompt {
  name: string
  group: string
  label: string
  description: string
  text: string
  default: string
  customized: boolean
  /** Saved against an older default: the user's wording stays, with a note that a newer default exists. */
  outdated: boolean
  placeholders: string[]
  placeholder_help: Record<string, string>
}

/** The prompts in their groups, in the order the server lists them. */
export function groupPrompts(prompts: EditablePrompt[]): [string, EditablePrompt[]][] {
  const groups = new Map<string, EditablePrompt[]>()
  for (const prompt of prompts) groups.set(prompt.group, [...(groups.get(prompt.group) ?? []), prompt])
  return [...groups]
}

/** "Must keep: {{name}} (a character's name), {{reason}}." */
export function placeholderHint(prompt: Pick<EditablePrompt, 'placeholders' | 'placeholder_help'>): string {
  if (!prompt.placeholders.length) return ''
  return 'Must keep: ' + prompt.placeholders.map((key) => {
    const help = prompt.placeholder_help[key]
    return `{{${key}}}` + (help ? ` (${help})` : '')
  }).join(', ') + '.'
}
