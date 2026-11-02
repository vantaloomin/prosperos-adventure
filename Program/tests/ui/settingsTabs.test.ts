import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ELSEWHERE, SETTINGS_TABS, availableTabs, pickTab, searchSettings } from '../../src/features/settings/sections.ts'
import { groupPrompts, placeholderHint } from '../../src/features/settings/prompts.ts'

test('a deep link opens its tab, an old one opens where its sections went, and an unknown one the first', () => {
  assert.equal(pickTab('images'), 'images')
  assert.equal(pickTab(undefined), 'general')
  assert.equal(pickTab('nonsense'), 'general')
  assert.equal(pickTab('debug'), 'developer')
  assert.equal(pickTab('advanced'), 'developer')
  assert.equal(pickTab('world'), 'general')
  assert.deepEqual(availableTabs().map((tab) => tab.id), ['general', 'models', 'images', 'data', 'developer'])
})

test('search finds sections by title, tab name or keyword, needing every word', () => {
  const found = (query: string) => searchSettings(query).map((match) => match.section.heading)
  assert.deepEqual(found('timezone'), ['time-heading'])
  assert.deepEqual(found('TIMEZONE'), ['time-heading'])
  assert.deepEqual(found('restore'), ['backup-heading'])
  assert.deepEqual(found('logging'), ['model-calls-heading'])
  assert.deepEqual(found('anthropic key'), ['models-heading'])
  assert.deepEqual(found('weather'), [])
  assert.deepEqual(found('   '), [])
})

test('every section heading is listed once', () => {
  const headings = SETTINGS_TABS.flatMap((tab) => tab.sections.map((section) => section.heading))
  assert.equal(new Set(headings).size, headings.length)
})

test('search finds what left Settings and says where it went', () => {
  const dice = searchSettings('dice')
  assert.deepEqual(dice.map((match) => match.section.heading), ['hidden-values-heading'])
  assert.ok(dice[0].elsewhere)
  assert.equal(dice[0].section.view, 'story')
  assert.deepEqual(searchSettings('townsfolk').map((match) => match.section.heading), ['townsfolk-mix-heading'])
  assert.deepEqual(searchSettings('prompt').map((match) => match.section.heading), ['prompts-heading'])
  const headings = [...SETTINGS_TABS.flatMap((tab) => tab.sections), ...ELSEWHERE].map((section) => section.heading)
  assert.equal(new Set(headings).size, headings.length)
})

test('prompts are grouped in order and their placeholders explained', () => {
  const prompt = (name: string, group: string, placeholders: string[] = [], help: Record<string, string> = {}) =>
    ({ name, group, label: name, description: '', text: '', default: '', customized: false, outdated: false, placeholders, placeholder_help: help })
  const groups = groupPrompts([prompt('a', 'Chat and life'), prompt('b', 'Character drafting'), prompt('c', 'Chat and life')])
  assert.deepEqual(groups.map(([group, items]) => [group, items.map((item) => item.name)]), [['Chat and life', ['a', 'c']], ['Character drafting', ['b']]])
  assert.equal(placeholderHint(prompt('x', 'g', ['name', 'reason'], { name: "the companion's name" })), "Must keep: {{name}} (the companion's name), {{reason}}.")
  assert.equal(placeholderHint(prompt('x', 'g')), '')
})
