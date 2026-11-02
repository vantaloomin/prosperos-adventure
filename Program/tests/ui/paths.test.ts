import assert from 'node:assert/strict'
import { test } from 'node:test'
import { shownPath } from '../../src/paths.ts'

test('the home folder is shown as ~ so screenshots do not carry the user name', () => {
  assert.equal(shownPath('C:\\Users\\Jim\\AppData\\Local\\ProsperoDungeon\\embeddings\\models'), '~\\AppData\\Local\\ProsperoDungeon\\embeddings\\models')
  assert.equal(shownPath('c:/users/Jim Smith/Data'), '~/Data')
  assert.equal(shownPath('/Users/jim/Library/Application Support/ProsperoDungeon'), '~/Library/Application Support/ProsperoDungeon')
  assert.equal(shownPath('/home/jim'), '~')
})

test('other paths are shown as they are', () => {
  assert.equal(shownPath('Z:\\Coding Projects\\prosperos-dungeon\\Data'), 'Z:\\Coding Projects\\prosperos-dungeon\\Data')
  assert.equal(shownPath('/Volumes/Drive/Users/jim'), '/Volumes/Drive/Users/jim')
  assert.equal(shownPath('C:\\Usersfolder\\x'), 'C:\\Usersfolder\\x')
  assert.equal(shownPath(''), '')
})
