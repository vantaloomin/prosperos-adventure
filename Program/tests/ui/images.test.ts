import assert from 'node:assert/strict'
import { test } from 'node:test'
import { disclosureFor, imageAlt, imageLine, OUTDATED, isActive, isLoopback, provenance } from '../../src/features/images/imageState.ts'
import type { ImageJob, PostImage } from '../../src/types.ts'

const image = (values: Partial<PostImage>): PostImage => ({ status: 'none', job_id: null, ref: null, error: null, updated_at: null, ...values })

test('the image line says what is happening without hiding the text', () => {
  assert.equal(imageLine(image({})), null)
  assert.equal(imageLine(image({ status: 'running' })), 'Making an image…')
  assert.equal(imageLine(image({ status: 'running', ref: 'old' })), 'Making a new version…')
  assert.equal(imageLine(image({ status: 'queued' }), 'Run codex login.'), 'Waiting: Run codex login.')
  assert.equal(imageLine(image({ status: 'failed', error: 'No local backend.' })), 'No local backend.')
  assert.ok(isActive('queued') && isActive('running') && !isActive('failed'))
})

test('a picture of a corrected event says so instead of passing as the new account', () => {
  const old = image({ status: 'completed', ref: 'job', outdated: true })
  assert.equal(imageLine(old), OUTDATED)
  assert.ok(!imageAlt(old, 'Mira sat at Artifact Coffee.').includes('Artifact'))
  assert.equal(imageAlt(image({ status: 'completed', ref: 'job' }), 'Mira sat at Artifact Coffee.'), 'Illustration: Mira sat at Artifact Coffee.')
  assert.equal(imageLine(image({ status: 'running', ref: 'job', outdated: true })), 'Making a new version…')
})

test('loopback addresses are local and others need a disclosure', () => {
  assert.ok(isLoopback('http://127.0.0.1:8188') && isLoopback('http://localhost:8188') && isLoopback('http://[::1]:8188'))
  assert.ok(!isLoopback('https://gpu.example.com') && !isLoopback('not a url'))
  assert.equal(disclosureFor('comfyui', 'other', 'http://127.0.0.1:8188', false), null)
  assert.equal(disclosureFor('comfyui', 'other', 'https://gpu.example.com', true), null)
  assert.match(disclosureFor('comfyui', 'other', 'https://gpu.example.com', false) ?? '', /not on this computer/)
  assert.match(disclosureFor('codex', 'other', '', false) ?? '', /Codex CLI under your own codex login/)
  assert.match(disclosureFor('hosted', 'openrouter', '', false) ?? '', /OpenRouter/)
  assert.doesNotMatch(disclosureFor('hosted', 'openrouter', '', false) ?? '', /NSFW/)
  assert.match(disclosureFor('hosted', 'other', '', false, true) ?? '', /NSFW requests go there too/)
  assert.doesNotMatch(disclosureFor('hosted', 'google', '', false, true) ?? '', /NSFW/)
})

test('provenance names the backend, likeness method, content check and routing', () => {
  const job = {
    backend_label: 'OpenRouter', backend_kind: 'hosted', provider: 'openrouter', model: 'gemini-image', workflow: 'openrouter chat',
    identity_method: 'text description only', classification: 'nsfw', classification_reasons: ['refused by the provider'],
    routing_reason: 'nsfw: local backends only', seed: null, width: 1024, height: 1024, usage: { cost: 0.04 },
  } as unknown as ImageJob
  const rows = Object.fromEntries(provenance(job))
  assert.equal(rows.Backend, 'OpenRouter · openrouter')
  assert.equal(rows['Character likeness'], 'text description only')
  assert.equal(rows['Content check'], 'NSFW (local only): refused by the provider')
  assert.equal(rows.Seed, 'Not used by this backend')
  assert.equal(rows.Usage, 'cost 0.04')
})
