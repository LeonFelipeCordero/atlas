import { expect, test } from 'bun:test'

function workspace(area: 'map' | 'report') {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    mock.module('react', () => ({ ...React, useState: (value) => [value === 'map' ? '${area}' : value, () => {}] }))
    const { renderToStaticMarkup } = await import('react-dom/server')
    const { QueryClient, QueryClientProvider } = await import('@tanstack/react-query')
    const { GraphWorkspace } = await import('./src/components/graph/graph-workspace')
    const view = {
      state: 'ready', repositoryId: 'repo', graphRevision: 'revision', rootName: 'Same project',
      scope: { kind: 'repository' }, graph: { nodes: [], edges: [] },
      trail: [{ label: 'Same project', scope: { kind: 'repository' } }],
      details: { nodes: [], fileComplexities: {} }, cycles: [], diagnostics: [],
    }
    const noop = () => {}
    const props = { initial: view, view, selected: null, focusId: null, activeCycle: null, navigate: noop, onScope: noop, onSelect: noop, onOpen: noop, onCycle: noop, onCycleScope: noop }
    console.log(renderToStaticMarkup(React.createElement(QueryClientProvider, {client: new QueryClient()}, React.createElement(GraphWorkspace, props))))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  if (result.exitCode !== 0) throw new Error(result.stderr.toString())
  return result.stdout.toString()
}

test('project navigator and breadcrumbs persist in both work areas', () => {
  for (const area of ['map', 'report'] as const) {
    const html = workspace(area)
    expect(html).toContain('aria-label="Project navigator"')
    expect(html).toContain('Same project')
    expect(html).toContain('aria-label="Work area"')
    expect(html).toContain('Filter project roots')
    expect(html.indexOf('Project navigator')).toBeLessThan(
      html.indexOf('Work area'),
    )
    if (area === 'map') {
      expect(html).toContain('dependency graph')
      expect(html).not.toContain('Scope report')
    } else {
      expect(html).toContain('Scope report')
      expect(html).toContain('View scope on map')
      expect(html).not.toContain('dependency graph')
    }
  }
})
