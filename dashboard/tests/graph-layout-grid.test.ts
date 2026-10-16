import { expect, test } from 'bun:test'
import { layoutGraph } from '../src/components/graph/graph-layout'
import type { ProjectGraph } from '../src/lib/project-graph'

function nodes(count: number): ProjectGraph['nodes'] {
  return Array.from({ length: count }, (_, index) => ({
    id: String(index),
    label: String(index),
    kind: 'file',
    path: '',
    detail: '',
    scope: null,
  }))
}

test('isolated nodes occupy positive grid columns and rows without overlap', () => {
  const graph = { nodes: nodes(5), edges: [] }
  expect([...layoutGraph(graph).values()]).toEqual([
    { x: 30, y: 30 },
    { x: 290, y: 30 },
    { x: 550, y: 30 },
    { x: 30, y: 143 },
    { x: 290, y: 143 },
  ])
})

test('isolated grid starts below connected node rectangles', () => {
  const graph: ProjectGraph = {
    nodes: nodes(4),
    edges: [
      {
        id: '01',
        source: '0',
        target: '1',
        count: 1,
        relationships: { CALLS: 1 },
      },
    ],
  }
  const positions = layoutGraph(graph)
  const connected = [positions.get('0')!, positions.get('1')!]
  expect(
    connected.every((position) => position.x >= 0 && position.y >= 0),
  ).toBe(true)
  expect(positions.get('1')!.x).toBeGreaterThan(positions.get('0')!.x)
  expect(Math.min(...connected.map((position) => position.x))).toBe(30)
  expect(Math.min(...connected.map((position) => position.y))).toBe(30)
  expect(positions.get('2')).toEqual({
    x: 30,
    y: Math.max(...connected.map((position) => position.y + 128)) + 30,
  })
  expect(positions.get('3')).toEqual({ x: 290, y: positions.get('2')!.y })
})
