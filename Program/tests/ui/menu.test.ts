import assert from 'node:assert/strict'
import { test } from 'node:test'
import { filterCommands, menuCommands } from '../../src/features/story/menuText.ts'
import type { Story } from '../../src/types.ts'

function story(started: boolean): Story {
  return {
    scene: { city: { id: 'kingswood', name: 'Kingswood' }, place: { id: 'felled-oak' } },
    messages: started ? [{ id: 'm1' }] : [], people: [], branches: [], fight: {}, campaign: undefined, dice_shown: false, map: null,
  } as unknown as Story
}

test('the menu offers the composer extras, the panel views the story has, and starting over', () => {
  const ids = menuCommands(story(true)).map((command) => command.id)
  assert.deepEqual(ids.slice(0, 4), ['ideas', 'note', 'step-out', 'scene'])
  assert.ok(ids.includes('sheet') && ids.includes('pack') && ids.includes('journal') && ids.includes('rules'))
  assert.ok(!ids.includes('people') && !ids.includes('chapters'))
  assert.equal(ids[ids.length - 1], 'new-story')
  const before = menuCommands(story(false)).map((command) => command.id)
  assert.ok(!before.includes('ideas') && !before.includes('new-story') && !before.includes('sheet'))
})

test('typing narrows the menu to labels with every word', () => {
  const commands = menuCommands(story(true))
  assert.deepEqual(filterCommands(commands, 'pack').map((command) => command.id), ['pack'])
  assert.deepEqual(filterCommands(commands, 'story new').map((command) => command.id), ['new-story'])
  assert.equal(filterCommands(commands, '').length, commands.length)
  assert.deepEqual(filterCommands(commands, 'zzz'), [])
})
