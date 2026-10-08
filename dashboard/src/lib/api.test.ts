import { expect, test } from 'bun:test'
import { indexCommand } from './api'

test('index command selects the registered folder without a project name', () => {
  expect(indexCommand('/work/My Project')).toBe(
    "bun run architecture:index -f '/work/My Project'",
  )
})

test('index command quotes folders as one literal shell argument', () => {
  for (const location of [
    'My Project',
    "Engineer's École",
    '$(exit 12) `exit 13` "$HOME"; exit 14',
    "'; exit 15; echo '",
    'line one\nline two',
    '--project',
  ]) {
    const command = indexCommand(location).replace(
      'bun run architecture:index',
      "printf '%s\\n'",
    )
    const result = Bun.spawnSync(['sh', '-c', command])
    expect(result.exitCode).toBe(0)
    expect(result.stdout.toString()).toBe(`-f\n${location}\n`)
  }
})
