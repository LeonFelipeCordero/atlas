import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphSidebar } from './graph-sidebar'
import { GraphSizeMetrics } from './graph-size-metrics'
import type { Artifact, NodeSizeMetrics } from '@/lib/architecture-artifact'
import { fixtureDetails } from '@/lib/graph-details-test.helpers'
import { buildProjectGraph } from '@/lib/project-graph'
import { fixtureNodes } from '@/lib/project-graph-fixture'

function fixture(key: string, properties?: NodeSizeMetrics): Artifact {
  const nodes = fixtureNodes()
  nodes.find((node) => node.stableKey === key)!.properties = properties
  return { schemaVersion: 2, repository: { name: 'Example' }, nodes, edges: [] }
}

function sidebar(key: string, properties?: NodeSizeMetrics, selected = true) {
  const artifact = fixture(key, properties)
  const scope =
    key === 'run'
      ? { kind: 'file' as const, key: 'service' }
      : { kind: 'folder' as const, key: 'acme' }
  return renderToStaticMarkup(
    <GraphSidebar
      details={fixtureDetails(artifact)}
      graph={buildProjectGraph(artifact, scope)}
      scope={scope}
      selected={selected ? key : null}
      onSelect={() => {}}
      onOpen={() => {}}
      cycles={undefined}
      activeCycle={null}
      onCycle={() => {}}
      onCycleScope={() => {}}
    />,
  )
}

test('selected callables display line and parameter counts, including zero parameters', () => {
  const html = sidebar('run', { lineCount: 12, parameterCount: 0 })
  expect(html).toContain('aria-label="Size metrics"')
  expect(html).toContain('<dt>Lines</dt><dd>12</dd>')
  expect(html).toContain('<dt>Parameters</dt><dd>0</dd>')
  expect(html).toContain('including comments and blanks')
})

test('selected files and single-file summaries display lines only', () => {
  for (const selected of [true, false]) {
    const html = sidebar('service', { lineCount: 42 }, selected)
    expect(html).toContain('<dt>Lines</dt><dd>42</dd>')
    expect(html).not.toContain('<dt>Parameters</dt>')
  }
})

test('missing and partial metrics are not presented as zero', () => {
  expect(sidebar('run')).toContain(
    'Re-index this repository to include size metrics',
  )
  expect(sidebar('run', { lineCount: 1 })).toContain(
    '<dt>Parameters</dt><dd>Not available</dd>',
  )
})

test('folders do not display size metrics', () => {
  const artifact = fixture('app', { lineCount: 42 })
  const node = artifact.nodes.find((item) => item.stableKey === 'app')!
  expect(renderToStaticMarkup(<GraphSizeMetrics node={node} />)).toBe('')
})
