import { expect, test } from 'bun:test'

function pageStates() {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    let response, showForm = false
    mock.module('react', () => ({ ...React, useState: () => [showForm, () => {}] }))
    mock.module('@tanstack/react-query', () => ({ useQuery: () => response }))
    mock.module('@tanstack/react-router', () => ({ createFileRoute: () => value => value }))
    mock.module('./src/components/repository-form', () => ({ RepositoryForm: () => React.createElement('form', {'aria-label':'Register'}) }))
    mock.module('./src/components/repository-row', () => ({ RepositoryRow: ({repository}) => React.createElement('p', null, repository.name) }))
    const { Route } = await import('./src/routes/index')
    const { renderToStaticMarkup } = await import('react-dom/server')
    const states = [
      {isPending:true}, {error:new Error('Storage unavailable')}, {data:[]},
      {data:[{id:'one',name:'Example'}]}, {data:[{id:'one',name:'Example'}]},
    ].map((value,index) => {
      response = value; showForm = index === 4
      return renderToStaticMarkup(React.createElement(Route.component))
    })
    console.log(JSON.stringify(states))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  expect(result.exitCode).toBe(0)
  return JSON.parse(result.stdout.toString()) as Array<string>
}

test('repository page distinguishes loading, error, empty and registration states', () => {
  const states = pageStates()
  expect(states[0]).toContain('Loading repositories…')
  expect(states[0]).not.toContain('role="alert"')
  expect(states[0]).not.toContain('A clearer view starts here')
  expect(states[1]).toContain('role="alert"')
  expect(states[1]).toContain('Storage unavailable')
  expect(states[1]).not.toContain('Loading repositories…')
  expect(states[2]).toContain('A clearer view starts here')
  expect(states[2]).toContain('aria-label="Register"')
  expect(states[2]).not.toContain('Add repository')
  expect(states[3]).toContain('Add repository')
  expect(states[3]).toContain('Example')
  expect(states[3]).not.toContain('aria-label="Register"')
  expect(states[3]).not.toContain('A clearer view starts here')
  expect(states[4]).toContain('aria-label="Register"')
  expect(states[4]).toContain('Cancel')
})
