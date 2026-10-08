import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { indexCommand } from '@/lib/api'

// Isolate module mocks so route rendering cannot affect other Bun tests.
function renderRoute(repositoryName: string | null, showImport: boolean) {
  const script = `
    import { mock } from 'bun:test'
    import * as React from 'react'
    import { renderToStaticMarkup } from 'react-dom/server'
    const name = ${JSON.stringify(repositoryName)}
    mock.module('react', () => ({ ...React, useState: () => [${showImport}, () => {}] }))
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

for (const showImport of [false, true]) {
  test(`graph instructions use the registered name (expanded=${showImport})`, () => {
    const name = "Engineer's École $app"
    const markup = renderRoute(name, showImport)
    const command = renderToStaticMarkup(
      createElement('code', null, indexCommand(name)),
    )
    expect(markup).toContain(command)
    expect(markup).not.toContain(
      renderToStaticMarkup(
        createElement('code', null, indexCommand('storage-id')),
      ),
    )
    expect(markup.split(command)).toHaveLength(2)
  })

  test(`graph instructions wait for registered metadata (expanded=${showImport})`, () => {
    const markup = renderRoute(null, showImport)
    expect(markup).not.toContain('architecture:index')
    expect(markup).not.toContain('Your repository is registered.')
  })
}
