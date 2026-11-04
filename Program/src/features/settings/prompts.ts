/** One editable prompt as GET /api/prompts lists it (adventure/prompt_library.py). */
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
  /** A layout's slots, slowest-changing first (adventure/prompt_layout.py); empty for wording. */
  slots?: PromptSlot[]
}

export interface PromptSlot {
  name: string
  tier: number
  tier_name: string
  help: string
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

/** "Slots, slowest-changing first. Rules: {{RULES}} (...). Character: {{SHEET}} (...), ..." */
export function slotHint(prompt: Pick<EditablePrompt, 'slots'>): string {
  const slots = prompt.slots ?? []
  if (!slots.length) return ''
  const tiers = new Map<string, PromptSlot[]>()
  for (const slot of slots) tiers.set(slot.tier_name, [...(tiers.get(slot.tier_name) ?? []), slot])
  return 'Slots, slowest-changing first. ' + [...tiers].map(([tier, items]) =>
    `${tier[0].toUpperCase()}${tier.slice(1)}: ` + items.map((slot) => `{{${slot.name}}} (${slot.help})`).join(', ') + '.').join(' ')
}

/** What an edit box says under it: what the prompt is for, then the placeholders it keeps or the slots it places. */
export function promptHint(prompt: Pick<EditablePrompt, 'description' | 'placeholders' | 'placeholder_help' | 'slots'>): string {
  return [prompt.description, placeholderHint(prompt), slotHint(prompt)].filter(Boolean).join(' ')
}
