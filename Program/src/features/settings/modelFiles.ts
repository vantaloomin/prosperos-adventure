import type { BackendFiles, FileListKey, ImageFamily, ModelFileKey, ModelFiles, ModelLink, SamplerSettings, StyleLora } from '../../types'

export interface FileSlot {
  key: ModelFileKey; label: string; role: ModelLink['role'] | null; hint: string; tip?: string
  // The first choice, for a slot whose default is another slot's file (saved empty).
  same?: string
}

/** A model family a ComfyUI server can run a built-in workflow for (dungeon/images/adapters/comfyui.py FAMILIES). */
export interface Family {
  label: string
  // Its name in running text and toggle labels; `looks` is what matching files look like.
  short: string; looks: string
  sampling: string; steps: string; slots: FileSlot[]
  // A line added to the dropdown's hint, when the family needs one.
  note?: string
  // What pictures made from a reference need, on its own muted line under the hint (Iris).
  reference?: string
  // The custom node pack its reference workflow needs; only Krea 2's installs with one press (Vanta, 2026-10-13).
  pack?: { label: string; url: string; install: boolean }
}

/** Files a reference workflow node loads without naming them (IPAdapter Plus picks its models by preset), for
 * "It needs" (dungeon/images/adapters/comfyui.py PRESET_FILES). */
export const PRESET_FILES: Record<string, string[]> = {
  IPAdapterUnifiedLoader: ['ip-adapter-plus_sdxl_vit-h.safetensors', 'CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors'],
}

const TURBO_STEPS = 'Turbo models need few.'

const separate = (model: string, encoder: string, type: string, vae: string): FileSlot[] => [
  { key: 'unet_name', label: 'Model', role: 'model', hint: 'From ComfyUI\'s models/diffusion_models folder.', tip: model },
  { key: 'clip_name', label: 'Text encoder', role: 'clip', hint: 'From models/text_encoders.', tip: encoder },
  { key: 'clip_type', label: 'Text encoder type', role: null, hint: type },
  { key: 'vae_name', label: 'VAE', role: 'vae', hint: 'From models/vae.', tip: vae },
]

/** In the order the dropdown lists them; Krea 2 first and the default. */
export const FAMILIES: Record<ImageFamily, Family> = {
  krea2: {
    label: 'Krea 2', short: 'Krea 2', looks: 'Krea 2', sampling: 'Krea 2 Turbo', steps: TURBO_STEPS,
    reference: 'Pictures from a reference need the Krea 2 Identity Edit nodes.',
    pack: { label: 'Krea 2 Identity Edit', url: 'https://github.com/lbouaraba/comfyui-krea2edit', install: true },
    slots: [...separate('The image model the UNETLoader node loads. A Krea 2 Turbo file or a fine-tune of it; the workflow runs 8 steps at CFG 1, which suits Turbo.',
      'Turns the prompt into what the model reads. Krea 2 uses the Qwen3-VL 4B encoder.', 'krea2 for Krea 2 models.',
      'Turns the finished picture from the model\'s internal form into pixels. Krea 2 uses the Qwen Image VAE.'),
    { key: 'ref_unet_name', label: 'Model for pictures from a reference', role: null, same: 'Same as the Model',
      hint: 'From models/diffusion_models. Pick a Krea 2 Edit model here if you have one.',
      tip: 'Profile pictures 2 and 3 are made from picture 1. With the same model, the Krea 2 Identity Edit LoRA reads that picture. A Krea 2 Edit model (with "Edit" in its name) has the LoRA built in, so it is left out.' }],
  },
  qwen21: {
    label: 'Qwen Image 2.1', short: 'Qwen Image 2.1', looks: 'Qwen Image 2.1', sampling: 'Qwen Image 2.1', steps: 'The full model uses about 25; its Turbo file needs 8.',
    slots: separate('A Qwen Image 2.1 file. The workflow runs the full model at 25 steps and CFG 1; for the Turbo file set 8 steps under Sampling.',
      'Qwen Image 2.1 uses the Qwen3-VL 8B encoder.', 'qwen_image for Qwen Image models.', 'Qwen Image 2.1 has a VAE of its own.'),
  },
  zimage: {
    // A non-breaking hyphen, so the name never breaks after "Z" on a phone (Iris).
    label: 'Z\u2011Image Turbo', short: 'Z\u2011Image Turbo', looks: 'Z\u2011Image', sampling: 'Z\u2011Image Turbo', steps: TURBO_STEPS,
    reference: 'Pictures from a reference rework that picture, so they keep its pose and colors.',
    slots: separate('A Z-Image Turbo file or a fine-tune of it; the workflow runs 9 steps at CFG 1.',
      'Z-Image uses the Qwen3 4B encoder.', 'lumina2 for Z-Image.', 'Z-Image uses the Flux VAE (ae.safetensors).'),
  },
  anima: {
    label: 'Anima', short: 'Anima', looks: 'Anima', sampling: 'Anima', steps: 'Anima Base uses about 30; its Turbo file needs about 10 at CFG 1.',
    reference: 'Pictures from a reference need the Cosmos Reference nodes and the Anima Edit LoRA (AnimeEditV2).',
    pack: { label: 'Cosmos Reference', url: 'https://github.com/Mirumo0u0/ComfyUI-Cosmos-Reference', install: false },
    slots: separate('An Anima file. The workflow runs Base at 30 steps and CFG 4; for Anima Turbo set about 10 steps at CFG 1 under Sampling.',
      'Anima uses the small Qwen3 0.6B encoder.', 'stable_diffusion for Anima.', 'Anima uses the Qwen Image VAE, the same file as Krea 2.'),
  },
  booru: {
    label: 'Booru (SDXL, Pony, Illustrious)', short: 'Booru', looks: 'SDXL, Pony or Illustrious', sampling: 'Illustrious XL', steps: 'Most SDXL models use 20 to 30.',
    note: 'Prompts go out as booru tags (solo, 1boy and so on), after the quality tags under Prompt style.',
    reference: 'Pictures from a reference need the IPAdapter Plus nodes and its two models.',
    pack: { label: 'IPAdapter Plus', url: 'https://github.com/cubiq/ComfyUI_IPAdapter_plus', install: false },
    slots: [{ key: 'ckpt_name', label: 'Model', role: 'model', hint: 'From ComfyUI\'s models/checkpoints folder.', tip: 'One file holds the model, its text encoders and VAE. Any SDXL, Pony or Illustrious checkpoint works.' }],
  },
}
export const FAMILY_KEYS = Object.keys(FAMILIES) as ImageFamily[]
export const familyOf = (family: ImageFamily | null | undefined): Family => FAMILIES[family ?? 'krea2'] ?? FAMILIES.krea2

export const MISSING = 'Not on this server yet.'
/** Every list empty, for the loaders a family does not have and a server that did not answer. */
const NO_FILES: Record<FileListKey, string[]> = { unet_name: [], clip_name: [], clip_type: [], vae_name: [], ckpt_name: [], ref_unet_name: [], lora: [], sampler_name: [], scheduler: [] }
export const MAX_STYLE_LORAS = 3
export const NEW_STYLE_LORA: StyleLora = { name: '', strength: 0.7, trigger: '' }

/** What the server said, ready to show: its lists only when it answered, and the reason when it could not
 * be asked (`failed`, a request error). Until the app answers, the saved choice stands in for the defaults. */
export function serverFiles(data: BackendFiles | undefined, failed: string | null, saved: ModelFiles) {
  return {
    answered: Boolean(data) || failed !== null,
    defaults: data?.defaults ?? saved,
    options: { ...NO_FILES, ...(data?.ok ? data.options : {}) } as Record<FileListKey, string[]>,
    matching: { ...NO_FILES, ...(data?.ok ? data.matching : {}) } as Record<FileListKey, string[]>,
    error: data && !data.ok ? data.error : failed,
  }
}

/** The choices for one slot: the server's files (only the family's when `familyOnly` and it has any), with the
 * current value first when the list leaves it out. */
export function fileChoices(options: string[], current: string, matching: string[] = [], familyOnly = false, same?: string): { value: string; label: string }[] {
  const shown = familyOnly && matching.length > 0 ? matching : options
  const listed = [...(same ? [{ value: '', label: same }] : []), ...shown.map(value => ({ value, label: value }))]
  if (!current || shown.includes(current)) return listed
  return [{ value: current, label: current }, ...listed]
}

/** Whether a server that listed files lacks this one, said on its own line under the dropdown (Iris). */
export const missingFrom = (options: string[], current: string) => options.length > 0 && Boolean(current) && !options.includes(current)

/** Whether the server listed any of the family's files, so "Only … files" has something to narrow to. */
export const hasMatching = (matching: Partial<Record<FileListKey, string[]>>) => Object.values(matching).some(list => (list ?? []).length > 0)

/** The request body for the style LoRAs: rows without a file are dropped, trigger words trimmed. */
export const stylesBody = (rows: StyleLora[]): { style_loras: StyleLora[] } =>
  ({ style_loras: rows.filter(row => row.name.trim()).slice(0, MAX_STYLE_LORAS).map(row => ({ name: row.name.trim(), strength: row.strength, trigger: row.trigger.trim() })) })

/** What each slot shows: the draft, else the saved choice, else the workflow's default file. */
export const shownFiles = (slots: FileSlot[], draft: ModelFiles, saved: ModelFiles, defaults: ModelFiles): ModelFiles =>
  Object.fromEntries(slots.map(({ key }) => [key, draft[key] ?? (saved[key] || defaults[key] || '')]))

/** The request body for saving: a slot set to its default is saved empty, so it follows the default. */
export const filesBody = (slots: FileSlot[], shown: ModelFiles, defaults: ModelFiles): ModelFiles =>
  Object.fromEntries(slots.map(({ key }) => [key, (shown[key] ?? '').trim() === defaults[key] ? '' : (shown[key] ?? '').trim()]))

/** Every slot back to its default. */
export const noChoice = (slots: FileSlot[]): ModelFiles => Object.fromEntries(slots.map(({ key }) => [key, '']))

export const isChosen = (saved: ModelFiles) => Object.values(saved).some(Boolean)

/** How the file list's heading describes it: the user's files, the smaller model the app picked for this computer's
 * graphics card (dungeon/hardware.py fit_images), or the family's own. */
export const filesLabel = (saved: ModelFiles, fit: string | null | undefined) =>
  isChosen(saved) ? '(your choice)' : fit ? '(picked for this graphics card)' : '(defaults)'

/** A model file's name without its folder or extension: krea2_turbo_nvfp4. */
export const shortName = (file: string) => (file.split(/[\\/]/).pop() ?? file).replace(/\.(safetensors|gguf)$/i, '')

/** The family hint's line when the model running is the one the app picked for the card, because the user hasn't
 * chosen one (Iris): "On this 12 GB card it uses krea2_turbo_nvfp4, a smaller file that fits." */
export function fitLine(fit: string | null | undefined, saved: ModelFiles | null, cardGb: number | null): string | null {
  if (!fit || saved?.unet_name) return null
  const card = cardGb === null ? 'this graphics card' : `this ${cardGb >= 10 ? Math.round(cardGb) : cardGb.toFixed(1)} GB card`
  return `On ${card} it uses ${shortName(fit)}, a smaller file that fits.`
}

/** Download pages for the family's slots that have them, in slot order. */
export const linksByRole = (links: ModelLink[], family: ImageFamily = 'krea2') => {
  const own = links.filter(link => (link.family ?? 'krea2') === family)
  return [...familyOf(family).slots.filter(slot => slot.role), REFERENCE_SLOT].map(slot => ({ slot, links: own.filter(link => link.role === slot.role) })).filter(group => group.links.length > 0)
}

/** Files only the built-in reference workflow (profile pictures) uses; not a pickable slot. */
const REFERENCE_SLOT = { label: 'Pictures made from a reference', role: 'reference' }

/** Krea 2 Turbo's settings, the default family's own, shown until the server says otherwise. */
export const TURBO: SamplerSettings = { steps: 8, cfg: 1, sampler_name: 'euler_ancestral', scheduler: 'simple' }
type Sampler = { steps: number; cfg: number; sampler_name: string; scheduler: string }

/** What each sampler field shows: the draft, else the saved value, else the workflow's own. */
export const shownSampler = (draft: Partial<SamplerSettings>, saved: SamplerSettings, defaults: SamplerSettings): Sampler =>
  Object.fromEntries((Object.keys(TURBO) as (keyof SamplerSettings)[]).map(key =>
    [key, draft[key] ?? saved[key] ?? defaults[key] ?? TURBO[key]])) as Sampler

export const isTuned = (saved: SamplerSettings) => Object.values(saved).some(value => value !== null)
