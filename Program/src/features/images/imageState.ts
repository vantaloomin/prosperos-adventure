import type { BackendKind, HostedProvider, ImageJob, ImageStatus, PostImage } from '../../types'

export const isActive = (status: ImageStatus) => status === 'queued' || status === 'running'

type Line = (image: PostImage, waitingFor?: string | null) => string

const LINES: Partial<Record<ImageStatus, Line>> = {
  queued: (image, waitingFor) => waitingFor ? `Waiting: ${waitingFor}` : image.ref ? 'A new version is waiting to start.' : 'An image is waiting to start.',
  running: (image) => image.ref ? 'Making a new version…' : 'Making an image…',
  failed: (image) => image.error ?? 'The image could not be made.',
  cancelled: () => 'The image was cancelled.',
  interrupted: (image) => image.error ?? 'The app closed before the image was made.',
}

export const OUTDATED = 'This picture shows the moment before it was corrected. Make a new version to match.'

/** One plain line about the post's current image job, or null when there is nothing to say. */
export function imageLine(image: PostImage, waitingFor?: string | null): string | null {
  return LINES[image.status]?.(image, waitingFor) ?? (image.outdated ? OUTDATED : null)
}

/** Alt text that never presents a picture of an earlier version as the corrected moment. */
export const imageAlt = (image: PostImage, summary: string) =>
  image.outdated ? `Illustration of an earlier version of this moment, before it was corrected` : `Illustration: ${summary}`

const TIERS: Record<ImageJob['classification'], string> = { safe: 'Safe', nsfw: 'NSFW (local only)', prohibited: 'Not allowed' }

const backendName = (job: ImageJob) => [job.backend_label ?? job.backend_kind ?? 'None', job.provider !== job.backend_kind ? job.provider : null].filter(Boolean).join(' · ')
const modelName = (job: ImageJob) => [job.model, job.workflow].filter(Boolean).join(' · ') || 'Not reported'
const contentCheck = (job: ImageJob) => [TIERS[job.classification], job.classification_reasons.join(', ')].filter(Boolean).join(': ')
const usageText = (usage: Record<string, unknown>) => Object.entries(usage).map(([key, value]) => `${key} ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`).join(', ')

/** Provenance rows for a job's details (F3, F5): what made it and why it went there. */
export function provenance(job: ImageJob): [string, string][] {
  const rows: [string, string][] = [
    ['Backend', backendName(job)],
    ['Model', modelName(job)],
    ['Character likeness', job.identity_method ?? 'Not started'],
    ['Content check', contentCheck(job)],
    ['Routing', job.routing_reason],
    ['Seed', job.seed === null ? 'Not used by this backend' : String(job.seed)],
  ]
  if (job.width && job.height) rows.push(['Size', `${job.width}×${job.height}`])
  if (job.usage) rows.push(['Usage', usageText(job.usage)])
  return rows
}

export const BACKEND_KINDS: { id: BackendKind; label: string; hint: string }[] = [
  { id: 'comfyui', label: 'ComfyUI', hint: 'A ComfyUI server you run. On this computer it can also make NSFW images.' },
  { id: 'codex', label: 'Codex (ChatGPT subscription)', hint: "Experimental. Uses the Codex CLI's built-in image generation under your own codex login. Safe images only." },
  { id: 'hosted', label: 'Image API', hint: 'OpenRouter, Google, NovelAI or another provider, with your own API key. Safe images only, unless you switch on NSFW for a provider that allows it.' },
]

export const PROVIDERS: { id: HostedProvider; label: string }[] = [
  { id: 'openrouter', label: 'OpenRouter' },
  { id: 'google', label: 'Google' },
  { id: 'openai', label: 'OpenAI API' },
  { id: 'nanogpt', label: 'NanoGPT' },
  { id: 'novelai', label: 'NovelAI' },
  { id: 'other', label: 'Other OpenAI-compatible API' },
]

/** Hosted providers the NSFW switch is offered for, matching the server's NSFW_PROVIDERS. */
export const NSFW_PROVIDERS: HostedProvider[] = ['openrouter', 'nanogpt', 'novelai', 'other']

export function isLoopback(url: string): boolean {
  try {
    const host = new URL(url).hostname.replace(/^\[|\]$/g, '')
    return host === 'localhost' || host === '::1' || /^127\./.test(host)
  } catch { return false }
}

function destinationFor(kind: BackendKind, provider: HostedProvider): string {
  if (kind === 'codex') return 'OpenAI, through the Codex CLI under your own codex login (your ChatGPT plan, or the API key Codex is signed in with)'
  if (kind === 'comfyui') return 'the ComfyUI server at this address, which is not on this computer'
  return provider === 'other' ? 'this image service' : PROVIDERS.find((item) => item.id === provider)?.label ?? 'this provider'
}

/** What a new backend will receive, matching the server's disclosure; null when nothing leaves this computer. */
export function disclosureFor(kind: BackendKind, provider: HostedProvider, baseUrl: string, controlled: boolean, nsfw = false): string | null {
  if (kind === 'comfyui' && (isLoopback(baseUrl) || controlled)) return null
  const novelai = kind === 'hosted' && provider === 'novelai' ? ' NovelAI does not take reference pictures, so only the prompt is sent.' : ''
  const text = `Each image request sends its prompt to ${destinationFor(kind, provider)}. Their retention rules apply. The story itself is not sent.${novelai}`
  return kind === 'hosted' && nsfw && NSFW_PROVIDERS.includes(provider)
    ? `${text} NSFW requests go there too, so their terms decide what they will make and keep. Prohibited requests are still never sent.`
    : text
}
