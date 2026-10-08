import { expect, test } from 'bun:test'
import { indexCommand } from './api'

test('index command uses the registered project name', () => {
  expect(indexCommand('My Project')).toBe(
    "bun run architecture:index <repository-path> --project 'My Project'",
  )
})

test('index command quotes names as one literal shell argument', () => {
  for (const name of [
    'My Project',
    "Engineer's École",
    '$(exit 12) `exit 13` "$HOME"; exit 14',
    "'; exit 15; echo '",
    'line one\nline two',
    '--project',
  ]) {
    const command = indexCommand(name).replace(
      'bun run architecture:index <repository-path>',
      "printf '%s\\n'",
    )
    const result = Bun.spawnSync(['sh', '-c', command])
    expect(result.exitCode).toBe(0)
    expect(result.stdout.toString()).toBe(`--project\n${name}\n`)
  }
})
