/** Settings is split into tabs; this lists them, what each holds, and the words a search finds them by. */

export type SettingsTab = 'general' | 'models' | 'images' | 'data' | 'developer'

export interface SettingsSection {
  /** The id of the section's heading, used to land on it from a search result. */
  heading: string
  title: string
  keywords: string
}

export interface SettingsTabInfo {
  id: SettingsTab
  label: string
  sections: SettingsSection[]
}

// Settings holds what belongs to this computer and the user's accounts. A campaign's rules live on the Story screen
// ("Tone and rules") and what a world is made of on the Worlds page; search still finds them (ELSEWHERE).
export const SETTINGS_TABS: SettingsTabInfo[] = [
  {
    id: 'general', label: 'General', sections: [
      { heading: 'time-heading', title: 'Your time', keywords: 'timezone time zone clock date pc' },
      { heading: 'appearance-heading', title: 'Appearance', keywords: 'appearance look colors colours theme dark light paper ink palette text size font motion layout reader classic custom grid arrange visual novel vn portraits story panel world colors pictures' },
    ],
  },
  {
    id: 'models', label: 'Models', sections: [
      { heading: 'hardware-heading', title: 'This computer', keywords: 'hardware graphics card gpu vram memory ram nvidia fit warning slow local' },
      { heading: 'models-heading', title: 'Models', keywords: 'model connection provider api key openai anthropic openrouter google local kobold codex claude profile story narrator referee continuity director recall temperature' },
      { heading: 'recall-profiles-heading', title: 'Recall', keywords: 'recall embedding embeddings semantic memory search ollama lm studio openai nomic qwen gemma profile' },
      { heading: 'turn-speed-heading', title: 'Turn speed', keywords: 'turn speed fast slow time budget seconds tokens cost cap check record rewrite' },
      { heading: 'local-programs-heading', title: 'Local programs', keywords: 'launch start open run lm studio ollama kobold koboldcpp comfyui local program auto start boot' },
      { heading: 'recall-heading', title: 'Built-in recall', keywords: 'recall embedding embeddings semantic llama.cpp llama-server gguf gemma embeddinggemma qwen local memory search' },
    ],
  },
  {
    id: 'images', label: 'Images', sections: [
      { heading: 'images-heading', title: 'Images', keywords: 'image pictures photos comfyui krea codex nsfw backend passive art automatic illustrations' },
    ],
  },
  {
    id: 'data', label: 'Data', sections: [
      { heading: 'data-folder-heading', title: 'Data folder', keywords: 'data folder location disk drive move portable' },
      { heading: 'backup-heading', title: 'Backups', keywords: 'backup restore data export archive' },
    ],
  },
  {
    id: 'developer', label: 'Developer', sections: [
      { heading: 'model-calls-heading', title: 'Record model calls', keywords: 'log logs logging record recording requests responses raw sent strange reply support troubleshoot' },
      { heading: 'debug-heading', title: 'Debug time', keywords: 'debug test testing time travel jump skip ahead days fast forward speed accelerate spoof date clock' },
      { heading: 'prompts-heading', title: 'Prompts', keywords: 'prompt prompts system instructions wording narrator story craft writing rules authors note power user advanced' },
    ],
  },
]

/** Where a section outside Settings lives: the view, and the words a search result names it by. */
export interface ElsewhereSection extends SettingsSection { view: 'story' | 'worlds'; where: string }

export const ELSEWHERE: ElsewhereSection[] = [
  { heading: 'hidden-values-heading', title: 'Dice and hidden values', view: 'story', where: 'Story, More, Tone and rules', keywords: 'hidden values show reveal odds dice roll rolling 3d why it went adult side' },
  { heading: 'story-dials-heading', title: 'Tone and rules', view: 'story', where: 'Story, More (or its tile in a Custom layout)', keywords: 'intensity how far violence sex horror drama eventful cutaways meanwhile injuries lasting tone rule text rules passages' },
  { heading: 'cities-heading', title: 'Cities', view: 'worlds', where: 'Worlds', keywords: 'city cities places home world pack' },
  { heading: 'adult-side-heading', title: 'Adult side of life', view: 'worlds', where: 'Worlds', keywords: 'adult adults nsfw 18 sex sexual sexuality orientation gay straight bisexual kink adventurous drive intimacy' },
  { heading: 'townsfolk-mix-heading', title: 'Townsfolk mix', view: 'worlds', where: 'Worlds', keywords: 'townsfolk mix ratio ratios shares population generation generate new world reseed gender women men nonbinary height build weight beard facial hair orientation sexuality gay lesbian bisexual straight adult side adventurous drive sliders' },
]

export function availableTabs(): SettingsTabInfo[] {
  return SETTINGS_TABS
}

/** The tab to show for a deep link: the one asked for when there is one, else the first one. Links to tabs
 *  that moved (#settings/debug, #settings/advanced) open where their sections went. */
export function pickTab(requested: string | undefined): SettingsTab {
  const renamed: Record<string, SettingsTab> = { debug: 'developer', advanced: 'developer' }
  const id = requested && (renamed[requested] ?? requested)
  return (SETTINGS_TABS.find((tab) => tab.id === id) ?? SETTINGS_TABS[0]).id
}

export type SettingsMatch = { tab: SettingsTabInfo; section: SettingsSection; elsewhere?: undefined }
  | { tab?: undefined; section: ElsewhereSection; elsewhere: true }

const matches = (words: string[], text: string) => words.every((word) => text.toLowerCase().includes(word))

/** Sections whose title, tab or keywords contain every word of the query; those outside Settings come last. */
export function searchSettings(query: string): SettingsMatch[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return []
  const here: SettingsMatch[] = SETTINGS_TABS.flatMap((tab) => tab.sections
    .filter((section) => matches(words, `${section.title} ${tab.label} ${section.keywords}`))
    .map((section) => ({ tab, section })))
  const there: SettingsMatch[] = ELSEWHERE.filter((section) => matches(words, `${section.title} ${section.where} ${section.keywords}`))
    .map((section) => ({ section, elsewhere: true }))
  return [...here, ...there]
}
