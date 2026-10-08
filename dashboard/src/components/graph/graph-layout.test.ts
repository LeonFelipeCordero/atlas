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

test('empty and wholly disconnected graphs need no edges to render', () => {
  expect(layoutGraph({ nodes: [], edges: [] }).size).toBe(0)
  expect(layoutGraph({ ...graph, edges: [] }).size).toBe(graph.nodes.length)
})
