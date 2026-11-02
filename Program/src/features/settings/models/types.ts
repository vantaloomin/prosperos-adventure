// Provider presets and profile shapes adapted from prosperos-study src/features/models/types.ts at bbcbde4.
export type Provider = 'openai' | 'anthropic' | 'openrouter' | 'google' | 'nanogpt' | 'compatible' | 'local' | 'kobold' | 'codex' | 'claude_code'
export interface ReportedCapabilities { model_id: string; context_tokens?: number | null; max_output_tokens?: number | null; supported_parameters?: string[] | null; supported_efforts?: string[] | null }
export interface ProfileConfig {
  provider: Provider
  model: string
  base_url: string
  max_output_tokens: number
  context_tokens: number
  timeout_seconds: number
  temperature?: number | null
  reasoning_effort?: string | null
  top_p?: number | null
  top_k?: number | null
  min_p?: number | null
  frequency_penalty?: number | null
  presence_penalty?: number | null
  repetition_penalty?: number | null
  seed?: number | null
  thinking_mode?: 'off' | 'budget' | 'adaptive' | null
  thinking_budget_tokens?: number | null
  response_reserve_tokens?: number
  response_verbosity?: 'low' | 'medium' | 'high' | null
  compatible_thinking?: boolean | null
  output_token_parameter?: 'max_tokens' | 'max_completion_tokens'
  reported_capabilities?: ReportedCapabilities | null
  resource_group?: string
  /** Text profiles write; recall profiles only make embeddings for semantic recall; decisions profiles only answer the Referee's questions with probabilities. */
  purpose?: 'text' | 'recall' | 'decisions'
  embedding_model?: string
  /** Where the Claude Code CLI is installed, when it is not on PATH. */
  cli_path?: string
  /** The folder that keeps this profile's own Claude account (CLAUDE_CONFIG_DIR); empty uses the usual one. */
  cli_account_dir?: string
}
export interface ModelProfile { id: string; name: string; revision: number; config: ProfileConfig; provider_name: string; has_saved_key: boolean; key_shared_with?: string[]; ready: boolean; recall_ready?: boolean; decisions_ready?: boolean; updated_at?: string }
export interface ModelJob { key: string; name: string; detail: string }
export interface ModelMix { enabled: boolean; mode: 'random' | 'in_turn'; profile_ids: string[] }
export interface ModelsOverview { profiles: ModelProfile[]; routes: Record<string, string>; jobs: ModelJob[]; mix?: Record<string, ModelMix> }

export const providers: Record<Provider, { name: string; url: string; description: string }> = {
  openai: { name: 'OpenAI', url: 'https://api.openai.com/v1', description: 'Connect with an OpenAI API key.' },
  anthropic: { name: 'Anthropic', url: 'https://api.anthropic.com/v1', description: 'Connect with an Anthropic API key.' },
  openrouter: { name: 'OpenRouter', url: 'https://openrouter.ai/api/v1', description: 'Choose a model through your OpenRouter account.' },
  google: { name: 'Google / Gemini', url: 'https://generativelanguage.googleapis.com/v1beta', description: 'Connect directly with a Google AI Studio / Gemini API key.' },
  nanogpt: { name: 'NanoGPT', url: 'https://nano-gpt.com/api/v1', description: 'Choose a model through your NanoGPT account.' },
  compatible: { name: 'OpenAI-compatible API', url: '', description: 'Any OpenAI-compatible Chat Completions API, such as DeepSeek or NVIDIA NIM. Enter its API base URL.' },
  local: { name: 'Local / LM Studio', url: 'http://127.0.0.1:1234/v1', description: 'LM Studio, Ollama or another server on this computer.' },
  kobold: { name: 'Kobold', url: 'http://127.0.0.1:5001/api/v1', description: 'The native KoboldCpp generation API on this computer.' },
  codex: { name: 'Codex / ChatGPT', url: '', description: 'Your installed Codex CLI and its existing login. Sign in with codex login in a terminal.' },
  claude_code: { name: 'Claude Code / Claude plan', url: '', description: 'Your installed Claude Code and the Claude plan it is signed in to. Sign in by running claude once in a terminal.' },
}
export const providerOrder = Object.keys(providers) as Provider[]
export const initialConfig: ProfileConfig = { provider: 'local', model: '', base_url: providers.local.url, max_output_tokens: 800, context_tokens: 16000, timeout_seconds: 180 }
export const configFor = (provider: Provider): ProfileConfig => ({ ...initialConfig, provider, base_url: providers[provider].url })
export const recallConfigFor = (provider: Provider): ProfileConfig => ({ ...configFor(provider), purpose: 'recall', embedding_model: '' })
export const isRecall = (config: ProfileConfig) => config.purpose === 'recall'
export const isDecisions = (config: ProfileConfig) => config.purpose === 'decisions'
export const isText = (config: ProfileConfig) => !isRecall(config) && !isDecisions(config)
/** Jev through OpenRouter, OpenAI Decisions, or a model on a local or compatible server scored by its answer odds. */
export const decisionProviders: Provider[] = ['openrouter', 'openai', 'local', 'compatible']
/** The decision model each hosted service offers, filled in when it is chosen. */
export const decisionModels: Partial<Record<Provider, string>> = { openrouter: 'typesafe/jev-1.14', openai: 'gpt-6-luna' }
export const decisionsConfigFor = (provider: Provider): ProfileConfig => ({ ...configFor(provider), purpose: 'decisions', model: decisionModels[provider] ?? '' })
/** Providers that run a program on this computer under its own login: no address and no key. */
export const cliProviders: Provider[] = ['codex', 'claude_code']
export const embeddingProviders: Provider[] = ['openai', 'nanogpt', 'compatible', 'local']
