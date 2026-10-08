import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphSidebar } from './graph-sidebar'
import type { Artifact, NodeComplexity } from '@/lib/architecture-artifact'
import { parseArtifact } from '@/lib/architecture-artifact'
import { buildProjectGraph } from '@/lib/project-graph'

const metrics = {
  baseCyclomaticComplexity: 5,
  nestedCyclomaticComplexity: 2,
  loopNestedComplexity: 1,
  cyclomaticComplexity: 8,
  maxDecisionDepth: 4,
}

function fixture(properties?: NodeComplexity): Artifact {
  const root = {
    stableKey: 'repo',
    type: 'repository',
    kind: 'repository',
    level: 'repository',
    name: 'Example',
    path: '.',
    language: null,
    parentStableKey: null,
    ancestorStableKeys: [],
    depth: 0,
  }
  const file = {
    ...root,
    stableKey: 'file',
    type: 'file',
    kind: 'file',
    level: 'file',
    name: 'main.ts',
    path: 'main.ts',
    parentStableKey: 'repo',
    ancestorStableKeys: ['repo'],
    depth: 1,
  }
  return parseArtifact({
    schemaVersion: 2,
    repository: { name: 'Example' },
    edges: [],
    nodes: [
      root,
      file,
      {
        ...file,
        stableKey: 'run',
        type: 'method',
        kind: 'method',
        level: 'callable',
        name: 'run',
        parentStableKey: 'file',
        ancestorStableKeys: ['repo', 'file'],
        depth: 2,
        properties: properties ? { ...properties } : undefined,
      },
    ],
  })
}

function sidebar(artifact: Artifact, selected = 'run', file = true) {
  const graph = buildProjectGraph(
    artifact,
    file ? { kind: 'file', key: 'file' } : { kind: 'repository' },
  )
  return renderToStaticMarkup(
    <GraphSidebar
      artifact={artifact}
      graph={graph}
      selected={selected}
      onSelect={() => {}}
      onOpen={() => {}}
      cycles={undefined}
      activeCycle={null}
      onCycle={() => {}}
      onCycleScope={() => {}}
    />,
  )
}

test('imported complexity survives graph projection and displays its breakdown', () => {
  const artifact = fixture(metrics)
  const graph = buildProjectGraph(artifact, { kind: 'file', key: 'file' })
  expect(graph.nodes[0].properties).toEqual(metrics)
  const html = sidebar(artifact)
  expect(html).toContain('Cyclomatic complexity')
  for (const [label, value] of [
    ['Total', 8],
    ['Base complexity', 5],
    ['Nested decisions extra', 2],
    ['Nested loops extra', 1],
    ['Maximum decision depth', 4],
  ])
    expect(html).toContain(`<dt>${label}</dt><dd>${value}</dd>`)
})

test('zero penalties display, missing metrics never become zero', () => {
  expect(
    sidebar(
      fixture({
        ...metrics,
        nestedCyclomaticComplexity: 0,
        loopNestedComplexity: 0,
      }),
    ),
  ).toContain('<dt>Nested loops extra</dt><dd>0</dd>')
  const legacy = sidebar(fixture())
  expect(legacy).toContain('Not available. Re-index this repository')
  expect(legacy).not.toContain('<dt>Total</dt>')
  const partial = sidebar(fixture({ cyclomaticComplexity: 1 }))
  expect(partial).toContain('<dt>Total</dt><dd>1</dd>')
  expect(partial).not.toContain('Nested loops extra')
})

test('containers and constructors do not show complexity', () => {
  const artifact = fixture(metrics)
  expect(sidebar(artifact, 'file', false)).not.toContain(
    'Cyclomatic complexity',
  )
  artifact.nodes[2].type = artifact.nodes[2].kind = 'constructor'
  expect(sidebar(artifact)).not.toContain('Cyclomatic complexity')
})

function expectInvalidMetricValues(artifact: Artifact, key: string) {
  for (const value of [
    -1,
    1.5,
    '8',
    null,
    Number.NaN,
    Number.POSITIVE_INFINITY,
  ]) {
    const invalid = structuredClone(artifact)
    invalid.nodes[2].properties = { [key]: value }
    expect(() => parseArtifact(invalid)).toThrow(`properties.${key}`)
  }
}

test('import validates complexity numbers without dropping other properties', () => {
  const artifact = fixture(metrics)
  artifact.nodes[2].properties!.custom = 'kept'
  expect(parseArtifact(artifact).nodes[2].properties!.custom).toBe('kept')
  for (const key of Object.keys(metrics))
    expectInvalidMetricValues(artifact, key)
  for (const key of ['cyclomaticComplexity', 'baseCyclomaticComplexity']) {
    const invalid = structuredClone(artifact)
    invalid.nodes[2].properties = { [key]: 0 }
    expect(() => parseArtifact(invalid)).toThrow(`properties.${key}`)
  }
})
