import { expect, test } from 'bun:test'
import {
  getGraphEdgeChannels,
  getGraphEdgeHandles,
  getGraphEdgePath,
} from './graph-edge-routing'

test.each([
  [
    'forward left',
    { x: 100, y: 0 },
    { x: 0, y: 200 },
    'source-bottom',
    'target-top',
  ],
  [
    'forward aligned',
    { x: 0, y: 0 },
    { x: 0, y: 200 },
    'source-bottom',
    'target-top',
  ],
  [
    'forward right',
    { x: 0, y: 0 },
    { x: 100, y: 200 },
    'source-bottom',
    'target-top',
  ],
  [
    'back left',
    { x: 100, y: 200 },
    { x: 0, y: 0 },
    'source-bottom',
    'target-left',
  ],
  [
    'back aligned',
    { x: 0, y: 200 },
    { x: 0, y: 0 },
    'source-bottom',
    'target-left',
  ],
  [
    'back right',
    { x: 0, y: 200 },
    { x: 100, y: 0 },
    'source-bottom',
    'target-left',
  ],
  [
    'same row left',
    { x: 100, y: 0 },
    { x: 0, y: 0 },
    'source-bottom',
    'target-left',
  ],
  [
    'same row right',
    { x: 0, y: 0 },
    { x: 100, y: 0 },
    'source-right',
    'target-left',
  ],
  ['self loop', { x: 0, y: 0 }, { x: 0, y: 0 }, 'source-bottom', 'target-left'],
  ['missing source', undefined, { x: 0, y: 0 }, 'source-bottom', 'target-top'],
  ['missing target', { x: 0, y: 0 }, undefined, 'source-bottom', 'target-top'],
] as const)(
  'routes top-to-bottom dependencies: %s',
  (_, source, target, sourceHandle, targetHandle) => {
    expect(getGraphEdgeHandles(source, target)).toEqual({
      sourceHandle,
      targetHandle,
    })
  },
)

const positions = new Map([
  ['a', { x: 32, y: 32 }],
  ['b', { x: 304, y: 150 }],
  ['c', { x: 32, y: 268 }],
])

function route(sourceId: string, targetId: string) {
  const source = positions.get(sourceId)!
  const target = positions.get(targetId)!
  const { sourceHandle, targetHandle } = getGraphEdgeHandles(source, target)
  const sourceSide = sourceHandle.replace('source-', '')
  const targetSide = targetHandle.replace('target-', '')
  return getGraphEdgePath(
    {
      x: source.x + (sourceSide === 'bottom' ? 110 : 220),
      y: source.y + (sourceSide === 'bottom' ? 78 : 39),
    },
    {
      x: target.x + (targetSide === 'top' ? 110 : 0),
      y: target.y + (targetSide === 'top' ? 0 : 39),
    },
    sourceSide,
    targetSide,
    getGraphEdgeChannels(source, target, positions),
  )
}

test('adjacent rows use the exact gap midpoint, even for a short gap', () => {
  expect(route('a', 'b')).toBe('M142 110L142 130L414 130L414 150')
})

test('outgoing edges share the same segment and skip ranks through a column gap', () => {
  expect(route('a', 'c')).toBe('M142 110L142 130L-8 130L-8 248L142 248L142 268')
  expect(route('a', 'b')).toStartWith('M142 110L142 130')
  expect(route('b', 'c')).toEndWith('L142 248L142 268')
})

test('back edges and self loops leave 40 px outside the graph for arrowheads', () => {
  expect(route('c', 'a')).toBe('M142 346L142 386L-8 386L-8 71L32 71')
  expect(route('a', 'a')).toBe('M142 110L142 130L-8 130L-8 71L32 71')
  expect(route('b', 'a')).toBe('M414 228L414 248L-8 248L-8 71L32 71')
})

test('back edges to the right leave below and enter left through a shared column', () => {
  expect(route('c', 'b')).toBe('M142 346L142 386L278 386L278 189L304 189')
})

test('same-row edges share a lower corridor when an intermediate node blocks the way', () => {
  const nodes = new Map([
    ['a', { x: 32, y: 32 }],
    ['b', { x: 304, y: 32 }],
    ['c', { x: 576, y: 32 }],
  ])
  const channels = getGraphEdgeChannels(nodes.get('a')!, nodes.get('c')!, nodes)
  expect(
    getGraphEdgePath(
      { x: 252, y: 71 },
      { x: 576, y: 71 },
      'right',
      'left',
      channels,
    ),
  ).toBe('M252 71L278 71L278 150L550 150L550 71L576 71')
  expect(
    getGraphEdgePath(
      { x: 252, y: 71 },
      { x: 304, y: 71 },
      'right',
      'left',
      getGraphEdgeChannels(nodes.get('a')!, nodes.get('b')!, nodes),
    ),
  ).toBe('M252 71L304 71')
})
