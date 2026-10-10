import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphFileComplexity } from './graph-file-complexity'
import { GraphSidebar } from './graph-sidebar'
import type { Artifact, ArtifactNode } from '@/lib/architecture-artifact'
import type { GraphScope, ProjectGraph } from '@/lib/project-graph'
import { fixtureDetails } from '@/lib/graph-details-test.helpers'
import { sumFileComplexity } from '@/lib/file-complexity'
import { buildProjectGraph } from '@/lib/project-graph'

function fixture(): Artifact {
  const nodes: Array<ArtifactNode> = []
  function add(
    id: string,
    type: string,
    parent: string | null,
    value?: number,
  ) {
    const owner = nodes.find((node) => node.stableKey === parent)
    nodes.push({
      stableKey: id,
      name: id,
      type,
      kind: type,
      level: ['function', 'method', 'constructor'].includes(type)
        ? 'callable'
        : type,
      path: 'shared.ts',
      language: 'typescript',
      parentStableKey: parent,
      ancestorStableKeys: owner
        ? [...owner.ancestorStableKeys, owner.stableKey]
        : [],
      depth: owner ? owner.depth + 1 : 0,
      properties:
        value === undefined ? undefined : { cyclomaticComplexity: value },
    })
  }
  add('repo', 'repository', null)
  add('file', 'file', 'repo')
  add('class', 'class', 'file', 900)
  add('method', 'method', 'class', 8)
  add('nested', 'function', 'method', 2)
  add('function', 'function', 'file', 3)
  add('constructor', 'constructor', 'class', 100)
  add('other-file', 'file', 'repo')
  add('outside', 'function', 'other-file', 50)
  add('empty', 'file', 'repo')
  return {
    schemaVersion: 2,
    repository: { name: 'Example' },
    nodes,
    edges: [
      {
        sourceStableKey: 'method',
        targetStableKey: 'outside',
        type: 'CALLS',
        confidence: 'EXTRACTED',
      },
    ],
  }
}

function summary(artifact: Artifact, fileKey = 'file', compact = false) {
  return renderToStaticMarkup(
    <GraphFileComplexity
      sum={sumFileComplexity(artifact, fileKey)}
      compact={compact}
    />,
  )
}

function selectedFile(
  artifact: Artifact,
  selected: string | null,
  scope: GraphScope = { kind: 'repository' },
  graph: ProjectGraph = buildProjectGraph(artifact, scope),
) {
  return renderToStaticMarkup(
    <GraphSidebar
      details={fixtureDetails(artifact)}
      graph={graph}
      selected={selected}
      scope={scope}
      onSelect={() => {}}
      onOpen={() => {}}
      cycles={undefined}
      activeCycle={null}
      onCycle={() => {}}
      onCycleScope={() => {}}
    />,
  )
}

test('sums owned functions and methods once, not classes, constructors, or dependencies', () => {
  const artifact = fixture()
  const snapshot = structuredClone(artifact)
  expect(sumFileComplexity(artifact, 'file')).toEqual({
    total: 13,
    measured: 3,
    functions: 3,
  })
  expect(sumFileComplexity(artifact, 'other-file')).toEqual({
    total: 50,
    measured: 1,
    functions: 1,
  })
  expect(artifact).toEqual(snapshot)
  expect(
    artifact.nodes.find((node) => node.stableKey === 'file')!.properties,
  ).toBeUndefined()
})

test('selected file and inside-file summary show the same sum', () => {
  const artifact = fixture()
  for (const html of [
    selectedFile(artifact, 'file'),
    summary(artifact, 'file', true),
  ]) {
    expect(html).toContain('Function complexity sum')
    expect(html).toContain('<strong>13</strong>')
    expect(html).toContain('3 functions/methods in this file')
  }
  expect(summary(artifact, 'file', true)).toContain('file-complexity-bar')
  expect(selectedFile(artifact, 'empty')).toContain('<strong>0</strong>')
  expect(selectedFile(artifact, 'empty')).toContain('0 functions/methods')
})

test('unselected inside-file sidebar shows the current file sum', () => {
  const html = selectedFile(fixture(), null, { kind: 'file', key: 'file' })
  expect(html).toContain('Function complexity sum')
  expect(html).toContain('<strong>13</strong>')
  expect(html).toContain('In this view')
})

test('single local file preview ignores boundary nodes, multiple files have no implicit sum', () => {
  const artifact = fixture()
  const graph = buildProjectGraph(artifact, { kind: 'repository' })
  expect(selectedFile(artifact, null)).not.toContain('Function complexity sum')
  graph.nodes = graph.nodes.filter((node) => node.id !== 'empty')
  graph.nodes.find((node) => node.id === 'other-file')!.role = 'boundary'
  const html = selectedFile(artifact, null, { kind: 'repository' }, graph)
  expect(html).toContain('Function complexity sum')
  expect(html).toContain('<strong>13</strong>')
  expect(html).not.toContain('<strong>50</strong>')
})

test('outside-scope file inspector uses the target file sum', () => {
  const artifact = fixture()
  const graph = buildProjectGraph(artifact, { kind: 'file', key: 'file' })
  expect(graph.nodes.find((node) => node.id === 'outside')?.role).toBe(
    'boundary',
  )
  // In a folder view the same target is represented by its owning file.
  expect(selectedFile(artifact, 'other-file')).toContain('<strong>50</strong>')
})

test('partial and legacy data are not presented as a complete sum or zero', () => {
  const artifact = fixture()
  artifact.nodes.find((node) => node.stableKey === 'nested')!.properties =
    undefined
  expect(sumFileComplexity(artifact, 'file')).toEqual({
    total: 11,
    measured: 2,
    functions: 3,
  })
  const partial = summary(artifact)
  expect(partial).toContain('<strong>11</strong>')
  expect(partial).toContain('Partial sum')
  expect(partial).toContain('2 of 3 functions/methods measured')
  for (const node of artifact.nodes) node.properties = undefined
  const legacy = summary(artifact)
  expect(legacy).toContain('Not available')
  expect(legacy).not.toContain('<strong>0</strong>')
  expect(legacy).toContain('Re-index and import')
})
