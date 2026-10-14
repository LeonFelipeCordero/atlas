import { expect, test } from 'bun:test'
import { components, dependencyMetrics, internalNodes } from './graph-analysis'
import { importCycles } from './import-cycles.servers'
import type { ArtifactNode, DirectEdge } from './architecture-artifact'

const node = (key: string): ArtifactNode => ({
  stableKey: key,
  name: key,
  type: 'file',
  kind: 'file',
  level: 'file',
  path: key,
  language: null,
  parentStableKey: null,
  ancestorStableKeys: [],
  depth: 0,
})
const edge = (source: string, target: string): DirectEdge => ({
  sourceStableKey: source,
  targetStableKey: target,
  type: 'IMPORTS',
  confidence: 'EXTRACTED',
  path: null,
  line: null,
  evidence: null,
})

test('dependency counts deduplicate peers and diamond reachability while counting cyclic dependents', () => {
  const nodes = ['a', 'b', 'c', 'd', 'e', 'isolated'].map(node)
  const edges = [
    edge('a', 'b'),
    edge('a', 'b'),
    edge('a', 'c'),
    edge('b', 'd'),
    edge('c', 'd'),
    edge('d', 'e'),
    edge('e', 'd'),
    edge('d', 'd'),
  ]
  const metrics = dependencyMetrics(nodes, edges)
  expect(metrics.get('d')).toEqual({
    fanIn: 3,
    fanOut: 1,
    instability: 0.25,
    transitiveChangeImpact: 4,
  })
  expect(metrics.get('e')).toEqual({
    fanIn: 1,
    fanOut: 1,
    instability: 0.5,
    transitiveChangeImpact: 4,
  })
  expect(metrics.get('a')).toEqual({
    fanIn: 0,
    fanOut: 2,
    instability: 1,
    transitiveChangeImpact: 0,
  })
  expect(metrics.get('isolated')).toEqual({
    fanIn: 0,
    fanOut: 0,
    instability: null,
    transitiveChangeImpact: 0,
  })
})

function hierarchyFixture(): Array<ArtifactNode> {
  const nodes: Array<ArtifactNode> = []
  const add = (key: string, level: string, parent: string | null) => {
    const owner = nodes.find((entry) => entry.stableKey === parent)
    nodes.push({
      ...node(key),
      type: level,
      kind: level,
      level,
      parentStableKey: parent,
      ancestorStableKeys: owner
        ? [...owner.ancestorStableKeys, owner.stableKey]
        : [],
      depth: owner ? owner.depth + 1 : 0,
    })
  }
  add('repo', 'repository', null)
  for (const [module, file, type, callable] of [
    ['app', 'a.ts', 'A', 'run'],
    ['lib', 'b.ts', 'B', 'work'],
    ['tests', 'tests/test.ts', 'Test', 'check'],
  ]) {
    add(module, 'module', 'repo')
    add(file, 'file', module)
    add(type, 'type', file)
    add(callable, 'callable', type)
  }
  add('helper', 'callable', 'A')
  add('isolated.ts', 'file', 'app')
  add('Quiet', 'type', 'isolated.ts')
  add('quiet', 'callable', 'Quiet')
  add('external', 'external', 'repo')
  add('external-module', 'module', 'external')
  add('external-file', 'file', 'external-module')
  add('External', 'type', 'external-file')
  add('external-run', 'callable', 'External')
  return nodes
}

test('instability uses distinct internal peers at each level, including hidden tests and type-only relations', () => {
  const nodes = hierarchyFixture()
  const snapshot = structuredClone(nodes)
  const edges: Array<DirectEdge> = [
    edge('run', 'work'),
    edge('run', 'work'),
    { ...edge('run', 'work'), confidence: 'INFERRED' },
    edge('helper', 'work'),
    { ...edge('check', 'run'), typeOnly: true },
    edge('helper', 'run'),
    edge('run', 'run'),
    edge('quiet', 'quiet'),
    edge('run', 'external'),
    edge('run', 'external-run'),
    edge('external-run', 'run'),
    edge('run', 'missing'),
  ]
  const metrics = dependencyMetrics(nodes, edges)
  for (const key of ['app', 'a.ts', 'A'])
    expect(metrics.get(key)).toEqual({
      fanIn: 1,
      fanOut: 1,
      instability: 0.5,
      transitiveChangeImpact: 1,
    })
  for (const key of ['lib', 'b.ts', 'B'])
    expect(metrics.get(key)).toEqual({
      fanIn: 1,
      fanOut: 0,
      instability: 0,
      transitiveChangeImpact: 2,
    })
  expect(metrics.get('run')).toEqual({
    fanIn: 2,
    fanOut: 1,
    instability: 1 / 3,
    transitiveChangeImpact: 2,
  })
  expect(metrics.get('work')).toEqual({
    fanIn: 2,
    fanOut: 0,
    instability: 0,
    transitiveChangeImpact: 3,
  })
  for (const key of ['tests', 'tests/test.ts', 'Test', 'check', 'helper'])
    expect(metrics.get(key)?.instability).toBe(1)
  for (const key of ['isolated.ts', 'Quiet', 'quiet'])
    expect(metrics.get(key)?.instability).toBeNull()
  for (const key of [
    'repo',
    'external',
    'external-module',
    'external-file',
    'External',
    'external-run',
  ])
    expect(metrics.has(key)).toBe(false)
  expect(nodes).toEqual(snapshot)
})

test('internal nodes exclude subtrees marked external by either type or level without hiding tests', () => {
  const nodes = hierarchyFixture()
  const typeExternal = { ...node('type-external'), type: 'external' }
  const descendant = {
    ...node('type-external-child'),
    parentStableKey: typeExternal.stableKey,
    ancestorStableKeys: [typeExternal.stableKey],
    depth: 1,
  }
  const levelExternal = {
    ...node('level-external'),
    level: 'external',
  }
  nodes.push(descendant, typeExternal, levelExternal)
  const snapshot = structuredClone(nodes)
  const internal = internalNodes(nodes)
  expect(internal).toEqual(
    nodes.slice(
      0,
      nodes.findIndex((entry) => entry.stableKey === 'external'),
    ),
  )
  expect(internal.find((entry) => entry.stableKey === 'tests/test.ts')).toBe(
    nodes.find((entry) => entry.stableKey === 'tests/test.ts'),
  )
  expect(nodes).toEqual(snapshot)
})

test('SCC traversal is iterative for deep graphs', () => {
  const adjacency = new Map(
    Array.from({ length: 12000 }, (_, index) => [
      String(index),
      index === 11999 ? [] : [String(index + 1)],
    ]),
  )
  expect(components(adjacency)).toHaveLength(12000)
})

test('file self-imports are cycles but intra-file symbol imports and type-only imports are not', () => {
  const file = node('file')
  const callable: ArtifactNode = {
    ...node('symbol'),
    type: 'function',
    kind: 'function',
    level: 'callable',
    parentStableKey: 'file',
    ancestorStableKeys: ['file'],
    depth: 1,
  }
  expect(
    importCycles(
      [file, callable],
      [edge('symbol', 'file'), { ...edge('file', 'file'), typeOnly: true }],
    ),
  ).toEqual([])
  const groups = importCycles(
    [file],
    [edge('file', 'file'), edge('file', 'file')],
  )
  expect(groups[0].nodeStableKeys).toEqual(['file'])
  expect(groups[0].exampleCycle).toEqual(['file', 'file'])
  expect(groups[0].edges).toHaveLength(2)
})
