import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphSidebar } from './graph-sidebar'
import type { Artifact } from '@/lib/architecture-artifact'
import { fixtureDetails } from '@/lib/graph-details-test.helpers'
import { buildProjectGraph } from '@/lib/project-graph'
import { fixtureNodes } from '@/lib/project-graph-fixture'

test('project map keeps structural navigation and connections without report panels', () => {
  const artifact: Artifact = {
    schemaVersion: 2,
    repository: { name: 'Example' },
    nodes: fixtureNodes(),
    edges: [],
  }
  for (const selected of [null, 'run']) {
    const html = renderToStaticMarkup(
      <GraphSidebar
        structureOnly
        graph={buildProjectGraph(artifact, { kind: 'file', key: 'service' })}
        details={fixtureDetails(artifact)}
        selected={selected}
        cycles={[]}
        activeCycle={null}
        onCycle={() => {}}
        onCycleScope={() => {}}
        onSelect={() => {}}
        onOpen={() => {}}
      />,
    )
    expect(html).not.toContain('Size metrics')
    expect(html).not.toContain('Dependency metrics')
    expect(html).not.toContain('Circular dependencies')
    expect(html).not.toContain('Re-index')
    expect(html).toContain(selected ? 'Connections' : 'Find in this view')
  }
})
