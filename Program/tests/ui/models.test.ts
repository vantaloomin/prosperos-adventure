import assert from 'node:assert/strict'
import { test } from 'node:test'
import { applyDiscovered, discoveredSettings, filterModels, profileReady, recallReady, savedKeyApplies, typedModelSettings, type DiscoveredModel } from '../../src/features/settings/models/discovery.ts'
import { jobChoice } from '../../src/features/settings/models/routing.ts'
import { configFor, recallConfigFor, type ModelsOverview } from '../../src/features/settings/models/types.ts'

const sonnet: DiscoveredModel = { id: 'anthropic/claude-sonnet-5.5', name: 'Claude Sonnet 5.5', context_tokens: 200000, max_output_tokens: 500, limit_source: 'provider', supported_efforts: ['low', 'high'] }
const mystery: DiscoveredModel = { id: 'mystery', name: 'mystery', context_tokens: null, max_output_tokens: null, limit_source: 'unreported' }

test('a chosen model fills reported limits and never raises the reply above them', () => {
  const settings = discoveredSettings(sonnet, configFor('openrouter'))
  assert.equal(settings.context_tokens, 200000)
  assert.equal(settings.max_output_tokens, 500)
  assert.deepEqual(settings.reported_capabilities?.supported_efforts, ['low', 'high'])
})

test('testing again keeps the effort levels the app learned from the model, unless the service lists its own', () => {
  const learned = { ...configFor('openai'), model: 'mystery', reported_capabilities: { model_id: 'mystery', context_tokens: null, max_output_tokens: null, supported_parameters: null, supported_efforts: ['none', 'low'] } }
  assert.deepEqual(discoveredSettings(mystery, learned).reported_capabilities?.supported_efforts, ['none', 'low'])
  assert.equal(discoveredSettings({ ...mystery, id: 'other' }, learned).reported_capabilities?.supported_efforts, null)
  assert.deepEqual(discoveredSettings({ ...mystery, supported_efforts: ['high'] }, learned).reported_capabilities?.supported_efforts, ['high'])
})

test('a typed ID forgets reported limits unless it matches a listed model', () => {
  const current = { ...configFor('openrouter'), ...discoveredSettings(sonnet, configFor('openrouter')) }
  assert.equal(typedModelSettings('other', current, [sonnet]).reported_capabilities, null)
  assert.equal(typedModelSettings(sonnet.id, current, [sonnet]).context_tokens, 200000)
})

test('a test picks the only returned model, and otherwise keeps the choice', () => {
  assert.equal(applyDiscovered({ available: true, models: [], model_details: [mystery], generated: false }, configFor('local')).model, 'mystery')
  assert.equal(applyDiscovered({ available: true, models: [], model_details: [mystery, sonnet], generated: false }, configFor('local')).model, '')
  const plan = (id: string): DiscoveredModel => ({ id, name: id, context_tokens: null, max_output_tokens: null, limit_source: 'unreported' })
  assert.equal(applyDiscovered({ available: true, models: [], model_details: [plan('opus'), plan('sonnet')], generated: false }, configFor('claude_code')).model, 'sonnet')
})

test('model search matches every word in the name or ID', () => {
  assert.deepEqual(filterModels([sonnet, mystery], 'claude 5.5').map(model => model.id), [sonnet.id])
})

test('readiness and saved keys follow provider and address', () => {
  assert.equal(profileReady(configFor('codex')), false)
  assert.equal(profileReady({ ...configFor('codex'), model: 'gpt-5' }), true)
  assert.equal(profileReady({ ...configFor('claude_code'), model: 'sonnet' }), true)
  const saved = { ...configFor('compatible'), base_url: 'https://one.example/v1' }
  assert.equal(savedKeyApplies(saved, true, { ...saved, model: 'x' }), true)
  assert.equal(savedKeyApplies(saved, true, { ...saved, base_url: 'https://two.example/v1' }), false)
  assert.equal(savedKeyApplies(saved, true, configFor('openai')), false)
})

test('a job without its own profile shows the conversation profile it uses', () => {
  const profile = (id: string, name: string) => ({ id, name, revision: 1, config: configFor('local'), provider_name: 'Local', has_saved_key: false, ready: true })
  const overview: ModelsOverview = { profiles: [profile('a', 'Local'), profile('b', 'Claude')], routes: { chat: 'a', drafting: 'b' }, jobs: [] }
  assert.deepEqual(jobChoice(overview, 'life'), { value: '', inherited: 'Local' })
  assert.deepEqual(jobChoice(overview, 'drafting'), { value: 'b', inherited: null })
  assert.deepEqual(jobChoice(overview, 'chat'), { value: 'a', inherited: null })
})

test('recall profiles are apart from text profiles', () => {
  const recall = { ...recallConfigFor('local'), embedding_model: 'qwen3-embedding' }
  assert.equal(recallReady(recall), true)
  assert.equal(profileReady({ ...recall, model: 'chat' }), false)
  assert.equal(recallReady({ ...configFor('local'), embedding_model: 'qwen3-embedding' }), false)
  assert.equal(recallReady({ ...recallConfigFor('anthropic'), embedding_model: 'x' }), false)
})
