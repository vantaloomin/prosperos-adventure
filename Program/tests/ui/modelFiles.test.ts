import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { FAMILIES, FAMILY_KEYS, familyOf, missingFrom, fileChoices, filesBody, filesLabel, TURBO, hasMatching, isChosen, isTuned, linksByRole, noChoice, serverFiles, shownFiles, shownSampler, stylesBody, fitLine, shortName } from '../../src/features/settings/modelFiles.ts'
import type { ModelFiles, ModelLink } from '../../src/types.ts'

const DEFAULTS: ModelFiles = { unet_name: 'krea2_turbo_fp8_scaled.safetensors', clip_name: 'qwen3vl_4b_fp8_scaled.safetensors', clip_type: 'krea2', vae_name: 'qwen_image_vae.safetensors', ref_unet_name: '' }
const NONE: ModelFiles = { unet_name: '', clip_name: '', clip_type: '', vae_name: '', ref_unet_name: '' }
const SLOTS = FAMILIES.krea2.slots
// As a Windows ComfyUI lists them: subfolder, backslash and spaces kept.
const MUSE = 'Krea 2\\Muse by Stable Yogi Krea2 V3.5 Civ NVFP4 C84.safetensors'

test('each dropdown preselects the saved choice, else the default, and keeps a value the server lacks', () => {
  assert.deepEqual(shownFiles(SLOTS, {}, NONE, DEFAULTS), DEFAULTS)
  assert.equal(shownFiles(SLOTS, {}, { ...NONE, unet_name: MUSE }, DEFAULTS).unet_name, MUSE)
  assert.equal(shownFiles(SLOTS, { vae_name: 'Qwen\\sharp.safetensors' }, NONE, DEFAULTS).vae_name, 'Qwen\\sharp.safetensors')
  assert.deepEqual(fileChoices([MUSE], MUSE), [{ value: MUSE, label: MUSE }])
  const krea = DEFAULTS.unet_name ?? ''
  assert.deepEqual(fileChoices([MUSE], krea), [{ value: krea, label: krea }, { value: MUSE, label: MUSE }])
  assert.ok(missingFrom([MUSE], krea) && !missingFrom([MUSE], MUSE) && !missingFrom([], krea))
})

test('saving stores only what differs from the default, exactly as named', () => {
  assert.deepEqual(filesBody(SLOTS, { ...DEFAULTS, unet_name: MUSE }, DEFAULTS), { ...NONE, unet_name: MUSE })
  assert.deepEqual(filesBody(SLOTS, DEFAULTS, DEFAULTS), NONE)
  assert.deepEqual(noChoice(SLOTS), NONE)
  assert.ok(isChosen({ ...NONE, clip_type: 'qwen_image' }) && !isChosen(NONE))
})

test('download pages are grouped under the dropdown they fill', () => {
  const link = (role: ModelLink['role'], name: string, family: ModelLink['family'] = 'krea2'): ModelLink => ({ role, name, url: `https://huggingface.co/${name}`, file: null, licence: 'Apache 2.0', family })
  const groups = linksByRole([link('vae', 'v'), link('model', 'm1'), link('model', 'm2'), link('model', 'a', 'anima')])
  assert.deepEqual(groups.map(group => [group.slot.label, group.links.map(item => item.name)]), [['Model', ['m1', 'm2']], ['VAE', ['v']]])
  assert.deepEqual(linksByRole([link('model', 'm1'), link('model', 'a', 'anima')], 'anima').map(group => group.links.map(item => item.name)), [['a']])
  assert.deepEqual(SLOTS.map(slot => slot.label), ['Model', 'Text encoder', 'Text encoder type', 'VAE', 'Model for pictures from a reference'])
})

test('the shipped download list links to pages, never to a file download', () => {
  const links = JSON.parse(readFileSync('dungeon/images/model_links.json', 'utf8')) as ModelLink[]
  assert.ok(links.length > 0)
  for (const item of links) {
    assert.match(item.url, /^https:\/\/huggingface\.co\/[\w.-]+\/[\w.-]+(\/tree\/main(\/[\w./-]+)?)?$/)
    assert.ok(['model', 'clip', 'vae', 'reference'].includes(item.role) && item.name && item.licence && FAMILY_KEYS.includes(item.family))
  }
})

test('a server that cannot be asked leaves typed names, and one that answers fills the lists', () => {
  const options = { unet_name: [MUSE], clip_name: [], clip_type: ['krea2'], vae_name: [], ref_unet_name: [], lora: [], sampler_name: [], scheduler: [] }
  const matching = { unet_name: [MUSE], clip_name: [], clip_type: [], vae_name: [], ref_unet_name: [], lora: [], sampler_name: [], scheduler: [] }
  const empty = { ...options, unet_name: [], clip_type: [], ckpt_name: [] }
  assert.deepEqual(serverFiles(undefined, null, NONE), { answered: false, defaults: NONE, options: empty, matching: empty, error: null })
  const down = serverFiles({ ok: false, error: 'Cannot reach the ComfyUI server.', family: 'krea2', defaults: DEFAULTS, sampler_defaults: TURBO, options, matching, character_lora: null }, null, NONE)
  assert.ok(down.answered && down.options.unet_name.length === 0 && down.defaults === DEFAULTS && down.error?.startsWith('Cannot reach'))
  assert.deepEqual(serverFiles({ ok: true, error: null, family: 'krea2', defaults: DEFAULTS, sampler_defaults: TURBO, options, matching, character_lora: null }, null, NONE).options, { ...options, ckpt_name: [] })
  assert.equal(serverFiles(undefined, 'Not found.', NONE).error, 'Not found.')
})

test('the settings page opens download pages in a new tab', () => {
  const source = readFileSync('src/features/settings/ImageSettings.tsx', 'utf8')
  assert.match(source, /href=\{link\.url\} target="_blank" rel="noreferrer"/)
})

test('"Only Krea 2 files" narrows a list to the family\'s files but never drops the current choice', () => {
  const other = 'sdxl\\juggernaut.safetensors'
  assert.deepEqual(fileChoices([MUSE, other], '', [MUSE], true).map(choice => choice.value), [MUSE])
  assert.deepEqual(fileChoices([MUSE, other], other, [MUSE], true), [{ value: other, label: other }, { value: MUSE, label: MUSE }])
  assert.deepEqual(fileChoices([MUSE, other], '', [], true).map(choice => choice.value), [MUSE, other])
  assert.ok(hasMatching({ unet_name: [], lora: ['a'] }) && !hasMatching({ unet_name: [] }))
})

test('style LoRAs are saved without empty rows, trimmed, at most three', () => {
  const row = { name: ' Krea 2\\phone_photography_2025_krea2.safetensors ', strength: 0.7, trigger: ' phone photo ' }
  assert.deepEqual(stylesBody([row, { name: '', strength: 1, trigger: '' }, row, row, row]).style_loras,
    Array(3).fill({ name: 'Krea 2\\phone_photography_2025_krea2.safetensors', strength: 0.7, trigger: 'phone photo' }))
})

test('sampling starts on Krea 2 Turbo settings and shows a draft over a saved value', () => {
  const none = { steps: null, cfg: null, sampler_name: null, scheduler: null }
  assert.deepEqual(shownSampler({}, none, TURBO), { steps: 8, cfg: 1, sampler_name: 'euler_ancestral', scheduler: 'simple' })
  assert.deepEqual(shownSampler({ steps: 12 }, { ...none, scheduler: 'beta' }, TURBO), { steps: 12, cfg: 1, sampler_name: 'euler_ancestral', scheduler: 'beta' })
  assert.ok(isTuned({ ...none, cfg: 2 }) && !isTuned(none))
})

test('each model family lists only its own loaders, and an unknown family is Krea 2', () => {
  assert.deepEqual(FAMILY_KEYS, ['krea2', 'qwen21', 'zimage', 'anima', 'booru'])
  assert.deepEqual(FAMILIES.booru.slots.map(slot => slot.key), ['ckpt_name'])
  assert.deepEqual(FAMILIES.anima.slots.map(slot => slot.key), ['unet_name', 'clip_name', 'clip_type', 'vae_name'])
  assert.equal(familyOf(null), FAMILIES.krea2)
  // Only Krea 2 has a model of its own for pictures from a reference, which starts as the same one.
  assert.deepEqual(FAMILIES.krea2.slots.filter(slot => slot.same).map(slot => slot.key), ['ref_unet_name'])
  assert.deepEqual(fileChoices(['a_edit.safetensors'], '', [], false, 'Same as the Model'), [{ value: '', label: 'Same as the Model' }, { value: 'a_edit.safetensors', label: 'a_edit.safetensors' }])
})

test('the settings page and the server agree on the families', () => {
  const server = readFileSync('dungeon/images/models.py', 'utf8')
  assert.match(server, new RegExp(`Family = Literal\\[${FAMILY_KEYS.map(key => `'${key}'`).join(', ')}\\]`))
})

test('the file list says when its model was picked for the graphics card', () => {
  const fit = 'krea2_turbo_nvfp4.safetensors'
  assert.equal(filesLabel(NONE, fit), '(picked for this graphics card)')
  assert.equal(filesLabel(NONE, null), '(defaults)')
  assert.equal(filesLabel({ ...NONE, vae_name: 'mine.safetensors' }, fit), '(your choice)')
  assert.equal(fitLine(fit, NONE, 11.9), 'On this 12 GB card it uses krea2_turbo_nvfp4, a smaller file that fits.')
  assert.equal(fitLine('Krea 2\\krea2_turbo-Q3_K_M.gguf', NONE, 8), 'On this 8.0 GB card it uses krea2_turbo-Q3_K_M, a smaller file that fits.')
  assert.equal(fitLine(fit, NONE, null), 'On this graphics card it uses krea2_turbo_nvfp4, a smaller file that fits.')
  assert.equal(fitLine(fit, { ...NONE, unet_name: 'mine.safetensors' }, 12), null)
  assert.equal(fitLine(null, NONE, 12), null)
  assert.equal(shortName('Krea 2/krea2_turbo-Q4_K_M.gguf'), 'krea2_turbo-Q4_K_M')
})
