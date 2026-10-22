import { expect, test } from 'bun:test'
import { layoutGraph } from './graph-layout'
import type { ProjectGraph } from '@/lib/project-graph'

const graph: ProjectGraph = {
  nodes: ['a', 'b', 'c', 'isolated'].map((id) => ({
    id,
    label: id,
    kind: 'file',
    path: id,
    detail: '',
    scope: null,
  })),
  edges: [
    ['a', 'b'],
    ['b', 'c'],
    ['c', 'a'],
  ].map(([source, target]) => ({
    id: `${source}-${target}`,
    source,
    target,
    count: 1,
    relationships: { CALLS: 1 },
  })),
}

function expectSeparated(
  id: string,
  position: { x: number; y: number },
  entries: Array<[string, { x: number; y: number }]>,
) {
  for (const [otherId, other] of entries) {
    if (id === otherId) continue
    expect(
      Math.abs(position.x - other.x) >= 220 ||
        Math.abs(position.y - other.y) >= 110,
    ).toBe(true)
  }
}

test('layout retains cyclic and disconnected nodes with finite non-overlapping positions', () => {
  const positions = layoutGraph(graph)
  expect(positions.size).toBe(graph.nodes.length)
  const entries = Array.from(positions.entries())
  for (const [id, position] of entries) {
    expect(Number.isFinite(position.x) && Number.isFinite(position.y)).toBe(
      true,
    )
    expectSeparated(id, position, entries)
  }
})

test('lays out sorted rows and top-to-bottom dependency ranks', () => {
  const positions = layoutGraph({ ...graph, edges: graph.edges.slice(0, 2) })
  expect(Object.fromEntries(positions)).toEqual({
    a: { x: 32, y: 32 },
    b: { x: 32, y: 150 },
    c: { x: 32, y: 268 },
    isolated: { x: 304, y: 32 },
  })
})

test('cycles use a sorted root and do not move when input order changes', () => {
  const expected = {
    a: { x: 32, y: 32 },
    b: { x: 32, y: 150 },
    c: { x: 32, y: 268 },
    isolated: { x: 304, y: 32 },
  }
  expect(Object.fromEntries(layoutGraph(graph))).toEqual(expected)
  expect(
    Object.fromEntries(
      layoutGraph({
        nodes: [...graph.nodes].reverse(),
        edges: [...graph.edges].reverse(),
      }),
    ),
  ).toEqual(expected)
})

test('shared dependencies keep the first breadth-first rank', () => {
  const edges = [
    ['a', 'b'],
    ['a', 'c'],
    ['b', 'c'],
  ].map(([source, target]) => ({
    ...graph.edges[0],
    id: `${source}-${target}`,
    source,
    target,
  }))
  const positions = layoutGraph({ ...graph, edges })
  expect(positions.get('b')).toEqual({ x: 32, y: 150 })
  expect(positions.get('c')).toEqual({ x: 304, y: 150 })
})

test('rows sort equal labels by id without changing the graph', () => {
  const nodes = graph.nodes
    .map((node) => ({ ...node, label: 'same' }))
    .reverse()
  const input = structuredClone(nodes)
  const positions = layoutGraph({ nodes, edges: [] })
  expect(positions.get('a')).toEqual({ x: 32, y: 32 })
  expect(positions.get('isolated')).toEqual({ x: 848, y: 32 })
  expect(nodes).toEqual(input)
})

test('ignores edges whose endpoints are not visible', () => {
  const edges = [
    { ...graph.edges[0], source: 'missing' },
    { ...graph.edges[0], target: 'missing' },
  ]
  expect(layoutGraph({ ...graph, edges })).toEqual(
    layoutGraph({ ...graph, edges: [] }),
  )
})

test('empty and wholly disconnected graphs need no edges to render', () => {
  expect(layoutGraph({ nodes: [], edges: [] }).size).toBe(0)
  expect(layoutGraph({ ...graph, edges: [] }).size).toBe(graph.nodes.length)
})
