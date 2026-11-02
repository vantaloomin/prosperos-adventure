// Applying a connection test's model list, adapted from prosperos-study src/features/models/discovery.ts at bbcbde4.
import { cliProviders, decisionProviders, embeddingProviders, initialConfig, providers, type ModelProfile, type ProfileConfig, type Provider } from './types.ts'

export interface DiscoveredModel { id: string; name: string; context_tokens: number | null; max_output_tokens: number | null; limit_source: 'provider' | 'unreported'; supported_parameters?: string[]; supported_efforts?: string[] }
export interface Discovery { available: boolean; models: string[]; model_details?: DiscoveredModel[]; generated: false; note?: string; location?: string }

/** Reported limits fill the profile; the longest reply never rises above what the model reports. Effort levels the
 * service does not list stay as the app learned them from the model (companion/providers/efforts.py). */
export function discoveredSettings(model: DiscoveredModel, current: ProfileConfig): Partial<ProfileConfig> {
  return {
    model: model.id,
    reported_capabilities: { model_id: model.id, context_tokens: model.context_tokens, max_output_tokens: model.max_output_tokens, supported_parameters: model.supported_parameters ?? null, supported_efforts: model.supported_efforts ?? learnedEfforts(model.id, current) },
    context_tokens: model.context_tokens ? Math.max(1024, Math.min(model.context_tokens, 2000000)) : (model.id === current.model ? current.context_tokens : initialConfig.context_tokens),
    max_output_tokens: model.max_output_tokens ? Math.max(64, Math.min(current.max_output_tokens, model.max_output_tokens)) : current.max_output_tokens,
  }
}

function learnedEfforts(id: string, current: ProfileConfig): string[] | null {
  const reported = current.reported_capabilities
  return reported?.model_id === id ? reported.supported_efforts ?? null : null
}

/** A typed ID uses a listed model's limits when it matches one, and otherwise forgets reported limits. */
export function typedModelSettings(id: string, current: ProfileConfig, models: DiscoveredModel[] = []): Partial<ProfileConfig> {
  const known = models.find(model => model.id === id)
  return known ? discoveredSettings(known, current) : {
    model: id, context_tokens: id === current.model ? current.context_tokens : initialConfig.context_tokens,
    ...(id === current.model ? {} : { reported_capabilities: null }),
  }
}

/** After a test, keep the chosen model, or choose the only one returned. */
export function applyDiscovered(result: Discovery, config: ProfileConfig): ProfileConfig {
  const models = result.model_details ?? []
  const selected = models.find(model => model.id === config.model) ?? (!config.model && models.length === 1 ? models[0] : undefined)
    // The app decides: a Claude plan profile starts on Sonnet, which every plan includes.
    ?? (!config.model && config.provider === 'claude_code' ? models.find(model => model.id === 'sonnet') : undefined)
  return selected ? { ...config, ...discoveredSettings(selected, config) } : config
}

export function filterModels(models: DiscoveredModel[], query: string) {
  const words = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean)
  return models.filter(model => words.every(word => `${model.name} ${model.id}`.toLocaleLowerCase().includes(word)))
}

export const profileReady = (config: ProfileConfig) => (config.purpose ?? 'text') === 'text' && !!config.model.trim() && (cliProviders.includes(config.provider) || !!config.base_url.trim())
/** A recall profile with an embedding model can do recall, and only recall. */
export const recallReady = (config: ProfileConfig) => config.purpose === 'recall' && !!config.embedding_model?.trim() && embeddingProviders.includes(config.provider) && !!config.base_url.trim()

/** A decisions profile with a model can answer the Referee's questions, and nothing else. */
export const decisionsReady = (config: ProfileConfig) => config.purpose === 'decisions' && !!config.model.trim() && decisionProviders.includes(config.provider) && !!config.base_url.trim()

/** A key typed for one provider and address is never kept for another. */
export function savedKeyApplies(initial: ProfileConfig | undefined, hasSavedKey: boolean, config: ProfileConfig) {
  return !!initial && hasSavedKey && initial.provider === config.provider && (!initial.base_url || initial.base_url === config.base_url)
}

const address = (config: ProfileConfig) => (config.base_url || '').replace(/\/+$/, '')

/** The profile whose saved key a new or keyless profile on the same provider and address uses (the server reuses it on
 * save, most recently changed first), so one key does every job. */
export function reusableKey(profiles: ModelProfile[], config: ProfileConfig, excluding?: string) {
  if (cliProviders.includes(config.provider)) return undefined
  return profiles.filter(other => other.id !== excluding && other.has_saved_key && other.config.provider === config.provider && address(other.config) === address(config))
    .sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))[0]
}

/** The text profile whose saved key an image API on `provider` borrows when it has none of its own
 * (dungeon/images/backends.py text_profile_key): the same provider at its usual address. */
export function imageKeyFrom(profiles: ModelProfile[], provider: string, baseUrl: string) {
  const text = (provider === 'other' ? 'compatible' : provider) as Provider
  const wanted = (provider === 'other' ? baseUrl : providers[text]?.url ?? '').replace(/\/+$/, '')
  if (!wanted) return undefined
  return profiles.filter(profile => profile.has_saved_key && profile.config.provider === text && address(profile.config) === wanted)
    .sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))[0]
}
