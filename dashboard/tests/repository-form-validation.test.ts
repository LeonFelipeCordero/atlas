import { expect, test } from 'bun:test'

function formStates() {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    let values = [], cursor = 0, pending = false, error = null
    mock.module('react', () => ({ ...React, useState: () => [values[cursor++], () => {}] }))
    mock.module('@tanstack/react-query', () => ({
      useQueryClient: () => ({}),
      useMutation: () => ({ isPending: pending, error, mutate: () => {} }),
    }))
    const { RepositoryForm } = await import('./src/components/repository-form')
    const { renderToStaticMarkup } = await import('react-dom/server')
    const output = []
    for (const [name, location, busy, failure] of [
      ['', '', false, null], ['name', '', false, null], ['', 'path', false, null],
      ['  ', 'path', false, null], ['name', '  ', false, null],
      ['name', 'path', false, null], ['name', 'path', true, null],
      ['name', 'path', false, {message:'Duplicate repository'}],
    ]) {
      values = [name,location]; cursor = 0; pending = busy; error = failure
      output.push(renderToStaticMarkup(RepositoryForm({onCreated: () => {}})))
    }
    console.log(JSON.stringify(output))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  expect(result.exitCode).toBe(0)
  return JSON.parse(result.stdout.toString()) as Array<string>
}

test('repository form requires both trimmed values and blocks repeated pending submits', () => {
  const states = formStates()
  for (const html of states.slice(0, 5)) expect(html).toContain('disabled=""')
  expect(states[5]).not.toContain('disabled=""')
  expect(states[5]).not.toContain('role="alert"')
  expect(states[6]).toContain('disabled=""')
  expect(states[6]).toContain('Registering…')
  expect(states[7]).toContain('role="alert">Duplicate repository</p>')
})
