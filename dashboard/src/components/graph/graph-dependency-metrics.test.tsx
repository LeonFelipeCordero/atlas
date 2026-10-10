import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphSidebar } from './graph-sidebar'
import type {
  Artifact,
  NodeDependencyMetrics,
} from '@/lib/architecture-artifact'
import { fixtureDetails } from '@/lib/graph-details-test.helpers'
import { buildProjectGraph } from '@/lib/project-graph'
import { fixtureNodes } from '@/lib/project-graph-fixture'

function fixture(): Artifact {
  return {
    schemaVersion: 2,
    repository: { name: 'Example' },
    nodes: fixtureNodes(),
    edges: [],
  }
}

function sidebar(
  key: string,
  properties?: NodeDependencyMetrics,
  selected = true,
) {
  const artifact = fixture()
  const node = artifact.nodes.find((entry) => entry.stableKey === key)!
  node.properties = properties
  const scope =
    key === 'run'
      ? { kind: 'file' as const, key: 'service' }
      : key === 'service'
        ? { kind: 'folder' as const, key: 'acme' }
        : { kind: 'repository' as const }
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

const metrics = {
  fanIn: 2,
  fanOut: 3,
  instability: 0.6,
  transitiveChangeImpact: 5,
}

test('sidebar shows indexed dependency metrics for folders, files, and callables', () => {
  for (const key of ['app', 'service', 'run']) {
    const html = sidebar(key, metrics)
    expect(html).toContain('aria-label="Dependency metrics"')
    expect(html).toContain('>Fan-in</dt><dd>2</dd>')
    expect(html).toContain('>Fan-out</dt><dd>3</dd>')
    expect(html).toContain('>Internal instability</dt><dd>0.60</dd>')
    expect(html).toContain('>Transitive change impact</dt><dd>5</dd>')
    expect(html).toContain('distinct internal')
    expect(html).toContain('full index, including tests and type-only')
    expect(html).toContain('Self and external dependencies are excluded')
    expect(html).toContain('fan-out / (fan-in + fan-out); N/A means isolated')
  }
})

test('missing metrics require reindexing; indexed zeros and partial values remain distinct', () => {
  const legacy = sidebar('run')
  expect(legacy).toContain(
    'Re-index this repository to include dependency metrics',
  )
  expect(legacy).not.toContain('>Fan-in</dt>')
  expect(legacy).not.toContain('>Internal instability</dt>')
  const partial = sidebar('run', { fanIn: 0 })
  expect(partial).toContain('>Fan-in</dt><dd>0</dd>')
  expect(partial).toContain('>Fan-out</dt><dd>Not indexed</dd>')
  expect(partial).toContain('>Internal instability</dt><dd>Not indexed</dd>')
  expect(partial).toContain(
    '>Transitive change impact</dt><dd>Not indexed</dd>',
  )
})

test('internal instability formats ratios, including zero, separately from isolated and missing values', () => {
  for (const [instability, display] of [
    [0, '0.00'],
    [1, '1.00'],
    [1 / 3, '0.33'],
    [null, 'N/A'],
    [undefined, 'Not indexed'],
  ] as const) {
    const html = sidebar('run', { ...metrics, instability })
    expect(html).toContain(`>Internal instability</dt><dd>${display}</dd>`)
  }
  expect(sidebar('run', { instability: null })).toContain(
    '>Internal instability</dt><dd>N/A</dd>',
  )
})

test('single-file contents summary includes dependency metrics without selecting it', () => {
  const html = sidebar('service', metrics, false)
  expect(html).toContain('>Fan-in</dt><dd>2</dd>')
  expect(html).toContain('>Internal instability</dt><dd>0.60</dd>')
})
