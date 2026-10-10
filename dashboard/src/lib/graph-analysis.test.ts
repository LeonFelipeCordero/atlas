import { expect, test } from 'bun:test'
import { components, dependencyMetrics } from './graph-analysis'
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
    transitiveChangeImpact: 4,
  })
  expect(metrics.get('e')).toEqual({
    fanIn: 1,
    fanOut: 1,
    transitiveChangeImpact: 4,
  })
  expect(metrics.get('a')).toEqual({
    fanIn: 0,
    fanOut: 2,
    transitiveChangeImpact: 0,
  })
  expect(metrics.get('isolated')).toEqual({
    fanIn: 0,
    fanOut: 0,
    transitiveChangeImpact: 0,
  })
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
