import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphSidebar } from './graph-sidebar'
import type {
  Artifact,
  NodeDependencyMetrics,
} from '@/lib/architecture-artifact'
import { parseArtifact } from '@/lib/architecture-artifact'
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
      artifact={parseArtifact(artifact)}
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

const metrics = { fanIn: 2, fanOut: 3, transitiveChangeImpact: 5 }

test('sidebar shows indexed dependency metrics for folders, files, and callables', () => {
  for (const key of ['app', 'service', 'run']) {
    const html = sidebar(key, metrics)
    expect(html).toContain('aria-label="Dependency metrics"')
    expect(html).toContain('>Fan-in</dt><dd>2</dd>')
    expect(html).toContain('>Fan-out</dt><dd>3</dd>')
    expect(html).toContain('>Transitive change impact</dt><dd>5</dd>')
    expect(html).toContain('full index, including tests')
  }
})

test('missing metrics require reindexing; indexed zeros and partial values remain distinct', () => {
  const legacy = sidebar('run')
  expect(legacy).toContain(
    'Re-index this repository to include dependency metrics',
  )
  expect(legacy).not.toContain('>Fan-in</dt>')
  const partial = sidebar('run', { fanIn: 0 })
  expect(partial).toContain('>Fan-in</dt><dd>0</dd>')
  expect(partial).toContain('>Fan-out</dt><dd>Not indexed</dd>')
  expect(partial).toContain(
    '>Transitive change impact</dt><dd>Not indexed</dd>',
  )
})

test('single-file contents summary includes dependency metrics without selecting it', () => {
  expect(sidebar('service', metrics, false)).toContain('>Fan-in</dt><dd>2</dd>')
})

test('artifact validation preserves metrics and rejects invalid counts', () => {
  const artifact = fixture()
  artifact.nodes[0].properties = { ...metrics, custom: 'preserved' }
  expect(parseArtifact(artifact).nodes[0].properties).toEqual({
    ...metrics,
    custom: 'preserved',
  })
  for (const key of Object.keys(metrics)) expectInvalidCounts(artifact, key)
})

function expectInvalidCounts(artifact: Artifact, key: string) {
  for (const value of [
    -1,
    1.5,
    '2',
    null,
    NaN,
    Infinity,
    Number.MAX_SAFE_INTEGER + 1,
  ]) {
    artifact.nodes[0].properties = { [key]: value }
    expect(() => parseArtifact(artifact)).toThrow(`properties.${key}`)
  }
}
