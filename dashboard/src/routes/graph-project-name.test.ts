import { expect, test } from 'bun:test'

// Isolate module mocks so route rendering cannot affect other Bun tests.
function renderRoute(repositoryName: string | null) {
  const script = `
    import { mock } from 'bun:test'
    import * as React from 'react'
    import { renderToStaticMarkup } from 'react-dom/server'
    const name = ${JSON.stringify(repositoryName)}
    mock.module('@tanstack/react-query', () => ({
      useQuery: (options) => options.queryKey[0] === 'graph'
        ? { data: null, refetch() {} }
        : { data: name === null ? undefined : [{ id: 'storage-id', name, location: '/source' }], refetch() {} },
    }))
    mock.module('@tanstack/react-router', () => ({
      Link: 'a',
      createFileRoute: () => (config) => ({ ...config, useParams: () => ({ repositoryId: 'storage-id' }) }),
    }))
    mock.module('@/components/graph/graph-explorer', () => ({ GraphExplorer: () => null }))
    const { Route } = await import('./src/routes/graph.$repositoryId.tsx')
    console.log(renderToStaticMarkup(React.createElement(Route.component)))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  expect(result.exitCode).toBe(0)
  if (result.exitCode !== 0) throw new Error(result.stderr.toString())
  return result.stdout.toString()
}

test('registered graph has an empty state without terminal instructions', () => {
  const markup = renderRoute('My repository')
  expect(markup).toContain('My repository')
  expect(markup).toContain('Your repository is registered.')
  expect(markup).toContain('No graph has been indexed yet.')
  expect(markup).toContain('Refresh graph')
  expect(markup).not.toContain('Index instructions')
  expect(markup).not.toContain('Copy index command')
  expect(markup).not.toContain('architecture:index')
  expect(markup).not.toContain('Python indexer')
})

test('graph empty state waits for registered metadata', () => {
  const markup = renderRoute(null)
  expect(markup).not.toContain('Your repository is registered.')
})
