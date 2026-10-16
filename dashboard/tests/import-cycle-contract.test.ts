import { expect, test } from 'bun:test'
import { importCycles } from '../src/lib/import-cycles.servers'
import type { ArtifactNode, DirectEdge } from '../src/lib/architecture-artifact'

function node(
  key: string,
  ancestors: Array<string> = [],
  { type = 'file', level = type }: { type?: string; level?: string } = {},
): ArtifactNode {
  return {
    stableKey: key,
    name: key,
    path: key,
    type,
    kind: type,
    level,
    parentStableKey: ancestors.at(-1) ?? null,
    ancestorStableKeys: ancestors,
    depth: ancestors.length,
    language: null,
  }
}
function edge(source: string, target: string, evidence = 'import'): DirectEdge {
  return {
    sourceStableKey: source,
    targetStableKey: target,
    type: 'IMPORTS',
    confidence: 'EXTRACTED',
    evidence,
  }
}

test('import ownership stops at external nodes rather than leaking to an ancestor file', () => {
  for (const [type, level] of [
    ['external', 'callable'],
    ['symbol', 'external'],
  ]) {
    const nodes = [
      node('a'),
      node('b'),
      node('external', ['a'], { type, level }),
      node('child', ['a', 'external'], { type: 'function', level: 'callable' }),
    ]
    expect(importCycles(nodes, [edge('child', 'b'), edge('b', 'a')])).toEqual(
      [],
    )
    expect(importCycles(nodes, [edge('b', 'child'), edge('a', 'b')])).toEqual(
      [],
    )
    expect(
      importCycles(nodes, [edge('child', 'b'), edge('b', 'child')]),
    ).toEqual([])
  }
})

test('example cycles retain breadth-first parent links and ignore the starting self edge', () => {
  const nodes = ['a', 'b', 'c', 'd'].map((key) => node(key))
  const edges = [
    edge('a', 'a'),
    edge('a', 'b'),
    edge('b', 'c'),
    edge('b', 'd'),
    edge('c', 'd'),
    edge('d', 'a'),
  ]
  expect(importCycles(nodes, edges)[0].exampleCycle).toEqual([
    'a',
    'b',
    'd',
    'a',
  ])
})

test('import cycles retain deterministic evidence order across source directions', () => {
  const nodes = [
    node('a'),
    node('b'),
    node('fn', ['a'], { type: 'function', level: 'callable' }),
  ]
  const edges = [edge('a', 'b', 'a'), edge('b', 'a', 'z'), edge('a', 'b', 'b')]
  const [cycle] = importCycles(nodes, edges)
  expect(cycle.nodeStableKeys).toEqual(['a', 'b'])
  expect(cycle.exampleCycle).toEqual(['a', 'b', 'a'])
  expect(cycle.edges.map((item) => item.evidence)).toEqual(['a', 'b', 'z'])
  expect(importCycles(nodes, [...edges].reverse())).toEqual([cycle])
  expect(
    importCycles([...nodes, node('outside')], [...edges, edge('b', 'outside')]),
  ).toEqual([cycle])
  expect(
    importCycles(nodes, [edge('fn', 'b'), edge('b', 'a')])[0].nodeStableKeys,
  ).toEqual(['a', 'b'])
  expect(importCycles(nodes, [edge('fn', 'a')])).toEqual([])
  expect(importCycles(nodes, [edge('a', 'fn')])).toEqual([])
  expect(importCycles(nodes, [{ ...edge('a', 'a'), typeOnly: true }])).toEqual(
    [],
  )
  expect(importCycles(nodes, [{ ...edge('a', 'a'), type: 'CALLS' }])).toEqual(
    [],
  )
  expect(importCycles(nodes, [edge('a', 'missing')])).toEqual([])
  expect(importCycles(nodes, [edge('missing', 'a')])).toEqual([])
  expect(importCycles(nodes, [edge('a', 'a')])[0].exampleCycle).toEqual([
    'a',
    'a',
  ])
})
